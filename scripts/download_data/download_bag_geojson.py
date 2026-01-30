import requests
import json
import os
from typing import List, Dict, Any, Tuple


BASE_URL = "https://service.pdok.nl/lv/bag/wfs/v2_0"
CRS = "EPSG:28992"


def generate_bbox_grid(
    xmin: int,
    ymin: int,
    xmax: int,
    ymax: int,
    tile_size: int,
) -> List[Tuple[int, int, int, int]]:
    """
    Generate a grid of bounding boxes.

    tile_size in meters (e.g. 5000 = 5 km)
    """
    bboxes = []

    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            bboxes.append((
                x,
                y,
                min(x + tile_size, xmax),
                min(y + tile_size, ymax),
            ))
            y += tile_size
        x += tile_size

    return bboxes


def download_bag_pand_by_bbox(
    output_path: str,
    tile_size: int = 5000,
    max_features_per_tile: int = 1000,
    max_total_features: int | None = None,
):
    """
    Download BAG panden by tiling the Netherlands into bbox chunks,
    with an optional global feature limit.
    """

    xmin, ymin, xmax, ymax = 0, 300000, 300000, 620000
    bboxes = generate_bbox_grid(xmin, ymin, xmax, ymax, tile_size)

    all_features: List[Dict[str, Any]] = []
    crs = None
    name = None
    global_bbox = None
    total_downloaded = 0

    for i, (bxmin, bymin, bxmax, bymax) in enumerate(bboxes, start=1):
        if max_total_features is not None and total_downloaded >= max_total_features:
            print("Reached global feature limit, stopping.")
            break

        bbox_param = f"{bxmin},{bymin},{bxmax},{bymax},EPSG:28992"
        print(f"[{i}/{len(bboxes)}] Downloading bbox {bbox_param}")

        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": "bag:pand",
            "outputFormat": "application/json",
            "bbox": bbox_param,
            "count": max_features_per_tile,
        }

        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        features = data.get("features", [])
        if not features:
            continue

        # Trim last tile if we exceed global limit
        if max_total_features is not None:
            remaining = max_total_features - total_downloaded
            if remaining <= 0:
                break
            features = features[:remaining]

        if len(features) == max_features_per_tile:
            print("⚠️  Tile hit max features — consider smaller tiles here.")

        if crs is None:
            crs = data.get("crs")
        if name is None:
            name = data.get("name")

        page_bbox = data.get("bbox")
        if page_bbox:
            if global_bbox is None:
                global_bbox = page_bbox
            else:
                global_bbox = [
                    min(global_bbox[0], page_bbox[0]),
                    min(global_bbox[1], page_bbox[1]),
                    max(global_bbox[2], page_bbox[2]),
                    max(global_bbox[3], page_bbox[3]),
                ]

        all_features.extend(features)
        total_downloaded += len(features)

        print(f"Total downloaded so far: {total_downloaded}")

    print(f"Final feature count: {len(all_features)}")

    feature_collection = {
        "type": "FeatureCollection",
        "name": name,
        "crs": crs,
        "features": all_features,
        "bbox": global_bbox,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(feature_collection, f)

    print(f"Saved GeoJSON to {output_path}")


download_bag_pand_by_bbox(
    output_path="data/bag_data/bag_pand_100000.geojson",
    tile_size=2000,
    max_total_features=100_000,
)
