from pathlib import Path
import subprocess
import shutil

DATA_DIR = Path(__file__).resolve().parents[1] / "examples" / "data"

input_geojson = DATA_DIR / "bag_pand_50k.geojson"
output_fgb = DATA_DIR / "bag_pand_50k.fgb"

ogr2ogr = shutil.which("ogr2ogr")
if ogr2ogr is None:
    raise RuntimeError(
        "ogr2ogr not found. Run using your conda env (where GDAL is installed) "
        "or install GDAL: conda install -c conda-forge gdal"
    )

subprocess.run(
    [
        ogr2ogr,
        "-f", "FlatGeobuf",
        str(output_fgb),
        str(input_geojson),
    ],
    check=True,
)

print("Wrote:", output_fgb)

#command:
#where ogr2ogr
# C:\Users\Julia>C:\Users\Julia\miniconda3\python.exe "C:\Users\Julia\OneDrive - Delft University of Technology\MSc Geomatics\Geomatics 2025-2026\Q5\Protobuff\scripts\convert_geojson_to_fgb.py"