from __future__ import annotations

import json
import struct
from typing import Any, Dict, List, Union

from sfproto.geojson.v4.geojson_feature import (
    geojson_feature_to_bytes_v4,
    bytes_to_geojson_feature_v4,
)

GeoJSON = Dict[str, Any]


def _pack_chunks(chunks: List[bytes]) -> bytes:
    # u32 count, then repeated (u32 len, bytes)
    out = bytearray()
    out += struct.pack(">I", len(chunks))
    for c in chunks:
        out += struct.pack(">I", len(c))
        out += c
    return bytes(out)


def _unpack_chunks(payload: bytes) -> List[bytes]:
    mv = memoryview(payload)
    if len(mv) < 4:
        raise ValueError("Invalid FeatureCollection bytes: too short")

    (n,) = struct.unpack(">I", mv[:4])
    offset = 4
    chunks: List[bytes] = []

    for _ in range(n):
        if offset + 4 > len(mv):
            raise ValueError("Invalid FeatureCollection bytes: truncated length")
        (ln,) = struct.unpack(">I", mv[offset : offset + 4])
        offset += 4

        if offset + ln > len(mv):
            raise ValueError("Invalid FeatureCollection bytes: truncated feature payload")
        chunks.append(bytes(mv[offset : offset + ln]))
        offset += ln

    if offset != len(mv):
        raise ValueError("Invalid FeatureCollection bytes: trailing bytes")

    return chunks


def geojson_featurecollection_to_bytes_v4(
    obj_or_json: Union[GeoJSON, str], srid: int = 0
) -> bytes:
    """
    Convert GeoJSON FeatureCollection -> bytes.
    Each Feature is encoded as sf.v4.Feature bytes (with properties).
    The collection is stored as a length-prefixed list of features.
    """
    obj = json.loads(obj_or_json) if isinstance(obj_or_json, str) else obj_or_json

    if obj.get("type") != "FeatureCollection":
        raise ValueError(
            f"Expected GeoJSON type=FeatureCollection, got: {obj.get('type')!r}"
        )

    feats = obj.get("features")
    if not isinstance(feats, list):
        raise ValueError("FeatureCollection.features must be a list")

    feature_chunks = [geojson_feature_to_bytes_v4(f, srid=srid) for f in feats]
    return _pack_chunks(feature_chunks)


def bytes_to_geojson_featurecollection_v4(data: bytes) -> GeoJSON:
    """
    Convert bytes -> GeoJSON FeatureCollection.
    Expects the length-prefixed list written by geojson_featurecollection_to_bytes_v4().
    """
    chunks = _unpack_chunks(data)
    features = [bytes_to_geojson_feature_v4(c) for c in chunks]

    return {
        "type": "FeatureCollection",
        "features": features,
    }
