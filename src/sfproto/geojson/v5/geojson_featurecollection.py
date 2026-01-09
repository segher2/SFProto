from __future__ import annotations

import json
from typing import Any, Dict, List, Union

from sfproto.geojson.v5.geojson_feature import (
    geojson_feature_to_bytes_v5,
    bytes_to_geojson_feature_v5,
)

GeoJSON = Dict[str, Any]

DEFAULT_SCALE = 10000000  # 1e7 -> ~cm accuracy for EPSG:4326


def geojson_featurecollection_to_bytes_v5(
    obj_or_json: Union[GeoJSON, str],
    srid: int = 0,
    scale: int = DEFAULT_SCALE,
) -> List[bytes]:
    """
    Convert GeoJSON FeatureCollection -> list of sf.v5.Feature bytes.
    Properties ARE encoded (unlike v2).
    """
    obj = json.loads(obj_or_json) if isinstance(obj_or_json, str) else obj_or_json

    if obj.get("type") != "FeatureCollection":
        raise ValueError(
            f"Expected GeoJSON type=FeatureCollection, got: {obj.get('type')!r}"
        )

    features = obj.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection.features must be a list")

    return [geojson_feature_to_bytes_v5(f, srid=srid, scale=scale) for f in features]


def bytes_to_geojson_featurecollection_v5(data: List[bytes]) -> GeoJSON:
    """
    Convert list of sf.v5.Feature bytes -> GeoJSON FeatureCollection.
    Properties ARE decoded (unlike v2).
    """
    features = [bytes_to_geojson_feature_v5(b) for b in data]

    return {
        "type": "FeatureCollection",
        "features": features,
    }
