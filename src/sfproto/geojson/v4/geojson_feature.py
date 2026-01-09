from __future__ import annotations

import json
from typing import Any, Dict, Union, Optional

from google.protobuf.struct_pb2 import Struct

from sfproto.sf.v4 import geometry_pb2  # your generated v4 module

# reuse same style of v1 geometry encoders, but in v4 package
from sfproto.geojson.v1.geojson_point import geojson_point_to_bytes, bytes_to_geojson_point
from sfproto.geojson.v1.geojson_polygon import geojson_polygon_to_bytes, bytes_to_geojson_polygon
from sfproto.geojson.v1.geojson_multipolygon import geojson_multipolygon_to_bytes, bytes_to_geojson_multipolygon
from sfproto.geojson.v1.geojson_multipoint import geojson_multipoint_to_bytes, bytes_to_geojson_multipoint
from sfproto.geojson.v1.geojson_linestring import geojson_linestring_to_bytes, bytes_to_geojson_linestring
from sfproto.geojson.v1.geojson_multilinestring import geojson_multilinestring_to_bytes, bytes_to_geojson_multilinestring

GeoJSON = Dict[str, Any]


def _dict_to_struct(d: Optional[Dict[str, Any]]) -> Struct:
    s = Struct()
    if d is None:
        return s  # empty struct represents null/none in your design
    s.update(d)
    return s


def _struct_to_dict(s: Struct) -> Dict[str, Any]:
    # Struct behaves like a mapping; easiest conversion is via MessageToDict
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(s)


def geojson_feature_to_bytes_v4(obj_or_json: Union[GeoJSON, str], srid: int = 0) -> bytes:
    """
    Convert GeoJSON Feature -> Protobuf sf.v4.Feature bytes.
    Properties are encoded (unlike v1).
    """
    obj = json.loads(obj_or_json) if isinstance(obj_or_json, str) else obj_or_json

    if obj.get("type") != "Feature":
        raise ValueError(f"Expected GeoJSON type=Feature, got: {obj.get('type')!r}")

    geometry = obj.get("geometry")
    if geometry is None:
        raise ValueError("Feature.geometry cannot be null")

    props = obj.get("properties")  # can be None or dict

    gtype = geometry.get("type")

    # encode geometry to *Geometry bytes* (same as v1 approach)
    if gtype == "Point":
        geom_bytes = geojson_point_to_bytes(geometry, srid=srid)
    elif gtype == "MultiPoint":
        geom_bytes = geojson_multipoint_to_bytes(geometry, srid=srid)
    elif gtype == "LineString":
        geom_bytes = geojson_linestring_to_bytes(geometry, srid=srid)
    elif gtype == "MultiLineString":
        geom_bytes = geojson_multilinestring_to_bytes(geometry, srid=srid)
    elif gtype == "Polygon":
        geom_bytes = geojson_polygon_to_bytes(geometry, srid=srid)
    elif gtype == "MultiPolygon":
        geom_bytes = geojson_multipolygon_to_bytes(geometry, srid=srid)
    else:
        raise ValueError(f"Unsupported Feature geometry type: {gtype!r}")

    # parse geometry bytes into v4 Geometry message
    geom_msg = geometry_pb2.Geometry.FromString(geom_bytes)

    # build v4 Feature message
    feat = geometry_pb2.Feature()
    feat.geometry.CopyFrom(geom_msg)

    if props is None:
        # represent null as empty struct (or choose a separate bool flag if you want)
        feat.properties.CopyFrom(Struct())
    elif isinstance(props, dict):
        feat.properties.CopyFrom(_dict_to_struct(props))
    else:
        raise ValueError("Feature.properties must be an object or null")

    return feat.SerializeToString()


def bytes_to_geojson_feature_v4(data: bytes) -> GeoJSON:
    """
    Convert Protobuf sf.v4.Feature bytes -> GeoJSON Feature.
    """
    feat = geometry_pb2.Feature.FromString(data)

    # decode geometry by re-serializing the embedded Geometry message and using existing decoders
    geom_bytes = feat.geometry.SerializeToString()

    for decoder in (
        bytes_to_geojson_point,
        bytes_to_geojson_multipoint,
        bytes_to_geojson_polygon,
        bytes_to_geojson_multipolygon,
        bytes_to_geojson_linestring,
        bytes_to_geojson_multilinestring,
    ):
        try:
            geometry = decoder(geom_bytes)
            break
        except Exception:
            geometry = None
    if geometry is None:
        raise ValueError("Feature.geometry contains an unsupported Geometry")

    props_dict = _struct_to_dict(feat.properties)
    # If you want to preserve GeoJSON null semantics, treat empty struct as None:
    properties = None if props_dict == {} else props_dict

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }
