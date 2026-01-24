from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple, Union

from sfproto.sf.v6 import geometry_pb2

GeoJSON = Dict[str, Any]
GeoJSONInput = Union[GeoJSON, str]


# ------------------- quantization -------------------

def _q(v: float, scale: int) -> int:
    return int(round(float(v) * scale))


def _uq(v: int, scale: int) -> float:
    return float(v) / float(scale)


# ------------------- geometry helpers -------------------

def _ring_drop_closure(ring: List[List[float]]) -> List[List[float]]:
    if len(ring) >= 2 and ring[0][0] == ring[-1][0] and ring[0][1] == ring[-1][1]:
        return ring[:-1]
    return ring


def _first_coord_of_geometry(geom: GeoJSON) -> Tuple[float, float]:
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point":
        return float(c[0]), float(c[1])
    if t == "MultiPoint":
        return float(c[0][0]), float(c[0][1])
    if t == "LineString":
        return float(c[0][0]), float(c[0][1])
    if t == "MultiLineString":
        return float(c[0][0][0]), float(c[0][0][1])
    if t == "Polygon":
        return float(c[0][0][0]), float(c[0][0][1])
    if t == "MultiPolygon":
        return float(c[0][0][0][0]), float(c[0][0][0][1])
    raise ValueError(f"Unsupported geometry type: {t!r}")


def _flatten_geometry(geom: GeoJSON) -> Tuple[int, List[Tuple[float, float]], List[int], List[int]]:
    """
    Returns (GeomType enum int, flat_points, part_sizes, poly_ring_counts)
    """
    t = geom.get("type")
    coords = geom.get("coordinates")

    part_sizes: List[int] = []
    poly_ring_counts: List[int] = []
    flat: List[Tuple[float, float]] = []

    if t == "Point":
        flat = [(coords[0], coords[1])]
        return geometry_pb2.POINT, flat, part_sizes, poly_ring_counts

    if t == "MultiPoint":
        pts = [(p[0], p[1]) for p in coords]
        flat = pts
        part_sizes = [len(pts)]
        return geometry_pb2.MULTIPOINT, flat, part_sizes, poly_ring_counts

    if t == "LineString":
        pts = [(p[0], p[1]) for p in coords]
        flat = pts
        part_sizes = [len(pts)]
        return geometry_pb2.LINESTRING, flat, part_sizes, poly_ring_counts

    if t == "MultiLineString":
        for ls in coords:
            pts = [(p[0], p[1]) for p in ls]
            part_sizes.append(len(pts))
            flat.extend(pts)
        return geometry_pb2.MULTILINESTRING, flat, part_sizes, poly_ring_counts

    if t == "Polygon":
        for ring in coords:
            ring2 = _ring_drop_closure(ring)
            pts = [(p[0], p[1]) for p in ring2]
            part_sizes.append(len(pts))
            flat.extend(pts)
        return geometry_pb2.POLYGON, flat, part_sizes, poly_ring_counts

    if t == "MultiPolygon":
        for poly in coords:
            poly_ring_counts.append(len(poly))
            for ring in poly:
                ring2 = _ring_drop_closure(ring)
                pts = [(p[0], p[1]) for p in ring2]
                part_sizes.append(len(pts))
                flat.extend(pts)
        return geometry_pb2.MULTIPOLYGON, flat, part_sizes, poly_ring_counts

    raise ValueError(f"Unsupported geometry type: {t!r}")


def _encode_stream_geometry(geom: GeoJSON, cursor_xy: Tuple[int, int], scale: int) -> Tuple[geometry_pb2.StreamGeometry, Tuple[int, int]]:
    gtype, flat_pts, part_sizes, poly_ring_counts = _flatten_geometry(geom)

    cursor_x, cursor_y = cursor_xy
    pb = geometry_pb2.StreamGeometry()
    pb.type = int(gtype)
    pb.n_points = len(flat_pts)

    if part_sizes:
        pb.part_sizes.extend([int(x) for x in part_sizes])
    if poly_ring_counts:
        pb.poly_ring_counts.extend([int(x) for x in poly_ring_counts])

    # stream deltas across ALL points
    for (x, y) in flat_pts:
        qx, qy = _q(x, scale), _q(y, scale)
        d = pb.d.add()
        d.dx = int(qx - cursor_x)
        d.dy = int(qy - cursor_y)
        cursor_x, cursor_y = qx, qy

    return pb, (cursor_x, cursor_y)


def _decode_stream_geometry(pb: geometry_pb2.StreamGeometry, cursor_xy: Tuple[int, int], scale: int) -> Tuple[GeoJSON, Tuple[int, int]]:
    cursor_x, cursor_y = cursor_xy
    qpts: List[Tuple[int, int]] = []

    if pb.n_points != len(pb.d):
        raise ValueError("Invalid StreamGeometry: n_points != len(d)")

    for d in pb.d:
        cursor_x += int(d.dx)
        cursor_y += int(d.dy)
        qpts.append((cursor_x, cursor_y))

    pts = [(_uq(x, scale), _uq(y, scale)) for (x, y) in qpts]

    t = int(pb.type)
    part_sizes = list(pb.part_sizes)
    poly_ring_counts = list(pb.poly_ring_counts)

    # rebuild nesting
    if t == geometry_pb2.POINT:
        x, y = pts[0]
        return {"type": "Point", "coordinates": [x, y]}, (cursor_x, cursor_y)

    if t == geometry_pb2.MULTIPOINT:
        return {"type": "MultiPoint", "coordinates": [[x, y] for (x, y) in pts]}, (cursor_x, cursor_y)

    if t == geometry_pb2.LINESTRING:
        return {"type": "LineString", "coordinates": [[x, y] for (x, y) in pts]}, (cursor_x, cursor_y)

    if t == geometry_pb2.MULTILINESTRING:
        out_lines = []
        idx = 0
        for n in part_sizes:
            seg = pts[idx: idx + n]
            out_lines.append([[x, y] for (x, y) in seg])
            idx += n
        return {"type": "MultiLineString", "coordinates": out_lines}, (cursor_x, cursor_y)

    if t == geometry_pb2.POLYGON:
        out_rings = []
        idx = 0
        for n in part_sizes:
            ring = pts[idx: idx + n]
            idx += n
            ring_coords = [[x, y] for (x, y) in ring]
            # close ring for GeoJSON
            if ring_coords:
                ring_coords.append(ring_coords[0])
            out_rings.append(ring_coords)
        return {"type": "Polygon", "coordinates": out_rings}, (cursor_x, cursor_y)

    if t == geometry_pb2.MULTIPOLYGON:
        out_polys = []
        idx = 0
        ring_size_idx = 0
        for ring_count in poly_ring_counts:
            poly = []
            for _ in range(ring_count):
                n = part_sizes[ring_size_idx]
                ring_size_idx += 1
                ring = pts[idx: idx + n]
                idx += n
                ring_coords = [[x, y] for (x, y) in ring]
                if ring_coords:
                    ring_coords.append(ring_coords[0])
                poly.append(ring_coords)
            out_polys.append(poly)
        return {"type": "MultiPolygon", "coordinates": out_polys}, (cursor_x, cursor_y)

    raise ValueError(f"Unsupported StreamGeometry type enum: {t}")


# ------------------- public API -------------------

def geojson_featurecollection_to_bytes_v6(obj_or_json: GeoJSONInput, srid: int, scale: int) -> bytes:
    obj = json.loads(obj_or_json) if isinstance(obj_or_json, str) else obj_or_json

    if obj.get("type") != "FeatureCollection":
        raise ValueError(f"Expected FeatureCollection, got {obj.get('type')!r}")

    feats = obj.get("features")
    if not isinstance(feats, list) or not feats:
        raise ValueError("FeatureCollection.features must be a non-empty list")

    fc = geometry_pb2.FeatureCollectionStream()
    fc.crs.srid = int(srid)
    fc.crs.scale = int(scale)

    first_geom = feats[0].get("geometry")
    if not isinstance(first_geom, dict):
        raise ValueError("First feature has no geometry object")

    x0, y0 = _first_coord_of_geometry(first_geom)
    fc.global_start.x = _q(x0, scale)
    fc.global_start.y = _q(y0, scale)

    cursor = (fc.global_start.x, fc.global_start.y)

    for feat in feats:
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            raise ValueError("Feature.geometry must be an object")
        pb_geom, cursor = _encode_stream_geometry(geom, cursor, scale)
        fc.geometries.append(pb_geom)

    return fc.SerializeToString()


def bytes_to_geojson_featurecollection_v6(data: bytes) -> GeoJSON:
    fc = geometry_pb2.FeatureCollectionStream.FromString(data)
    srid = int(fc.crs.srid)
    scale = int(fc.crs.scale)

    cursor = (int(fc.global_start.x), int(fc.global_start.y))

    features: List[GeoJSON] = []
    for pb_geom in fc.geometries:
        geom, cursor = _decode_stream_geometry(pb_geom, cursor, scale)
        features.append({"type": "Feature", "geometry": geom, "properties": None})

    out: GeoJSON = {"type": "FeatureCollection", "features": features}
    # (optional) restore CRS object if you want:
    # out["crs"] = {"type": "name", "properties": {"name": f"urn:ogc:def:crs:EPSG::{srid}"}}
    return out
