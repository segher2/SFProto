from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from google.protobuf.struct_pb2 import Struct
from google.protobuf.json_format import MessageToDict

from sfproto.sf.v5 import geometry_pb2  # generated from your sf.v5 geometry.proto

from sfproto.geojson.v2.geojson_point import geojson_point_to_bytes_v2, bytes_to_geojson_point_v2
from sfproto.geojson.v2.geojson_polygon import geojson_polygon_to_bytes_v2, bytes_to_geojson_polygon_v2
from sfproto.geojson.v2.geojson_multipolygon import geojson_multipolygon_to_bytes_v2, bytes_to_geojson_multipolygon_v2
from sfproto.geojson.v2.geojson_multipoint import geojson_multipoint_to_bytes_v2, bytes_to_geojson_multipoint_v2
from sfproto.geojson.v2.geojson_linestring import geojson_linestring_to_bytes_v2, bytes_to_geojson_linestring_v2
from sfproto.geojson.v2.geojson_multilinestring import geojson_multilinestring_to_bytes_v2, bytes_to_geojson_multilinestring_v2

GeoJSON = Dict[str, Any]

DEFAULT_SCALE = 10000000  # 1e7 -> ~cm in EPSG:4326


def _dict_to_struct(d: Optional[Dict[str, Any]]) -> Struct:
    s = Struct()
    if d is None:
        return s  # empty struct represents null (your v4 convention)
    s.update(d)
    return s


def _struct_to_dict(s: Struct) -> Dict[str, Any]:
    return MessageToDict(s)


def geojson_feature_to_bytes_v5(
    obj_or_json: Union[GeoJSON, str],
    srid: int = 0,
    scale: int = DEFAULT_SCALE,
) -> bytes:
    """
    Convert GeoJSON Feature -> Protobuf sf.v5.Feature bytes.
    Properties are encoded (unlike v2).
    """
    obj = json.loads(obj_or_json) if isinstance(obj_or_json, str) else obj_or_json

    if obj.get("type") != "Feature":
        raise ValueError(f"Expected GeoJSON type=Feature, got: {obj.get('type')!r}")

    geometry = obj.get("geometry")
    if geometry is None:
        raise ValueError("Feature.geometry cannot be null")

    props = obj.get("properties")  # may be dict or None
    if props is not None and not isinstance(props, dict):
        raise ValueError("Feature.properties must be an object or null")

    gtype = geometry.get("type")

    # Encode geometry using existing v2 encoders (returns sf.v2.Geometry bytes)
    if gtype == "Point":
        geom_bytes = geojson_point_to_bytes_v2(geometry, srid=srid, scale=scale)
    elif gtype == "MultiPoint":
        geom_bytes = geojson_multipoint_to_bytes_v2(geometry, srid=srid, scale=scale)
    elif gtype == "Polygon":
        geom_bytes = geojson_polygon_to_bytes_v2(geometry, srid=srid, scale=scale)
    elif gtype == "MultiPolygon":
        geom_bytes = geojson_multipolygon_to_bytes_v2(geometry, srid=srid, scale=scale)
    elif gtype == "LineString":
        geom_bytes = geojson_linestring_to_bytes_v2(geometry, srid=srid, scale=scale)
    elif gtype == "MultiLineString":
        geom_bytes = geojson_multilinestring_to_bytes_v2(geometry, srid=srid, scale=scale)
    else:
        raise ValueError(f"Unsupported Feature geometry type: {gtype!r}")

    # IMPORTANT:
    # sf.v5.Geometry has the same *field layout* as sf.v2.Geometry (plus different package),
    # so parsing bytes directly into sf.v5.Geometry works as long as message names/fields match.
    geom_msg_v5 = geometry_pb2.Geometry.FromString(geom_bytes)

    feat = geometry_pb2.Feature()
    feat.geometry.CopyFrom(geom_msg_v5)
    feat.properties.CopyFrom(_dict_to_struct(props))

    return feat.SerializeToString()


def bytes_to_geojson_feature_v5(data: bytes) -> GeoJSON:
    """
    Convert Protobuf sf.v5.Feature bytes -> GeoJSON Feature.
    """
    feat = geometry_pb2.Feature.FromString(data)

    # Decode geometry by re-serializing embedded v5 Geometry message to bytes.
    # v2 decoders can parse it because fields are identical.
    geom_bytes = feat.geometry.SerializeToString()

    geometry: Optional[GeoJSON] = None
    for decoder in (
        bytes_to_geojson_point_v2,
        bytes_to_geojson_multipoint_v2,
        bytes_to_geojson_polygon_v2,
        bytes_to_geojson_multipolygon_v2,
        bytes_to_geojson_linestring_v2,
        bytes_to_geojson_multilinestring_v2,
    ):
        try:
            geometry = decoder(geom_bytes)
            break
        except Exception:
            pass

    if geometry is None:
        raise ValueError("Feature.geometry contains an unsupported Geometry")

    props_dict = _struct_to_dict(feat.properties)
    properties = None if props_dict == {} else props_dict  # v4-style null convention

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }
