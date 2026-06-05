import sys
import json
import jsonschema

with open("config/json_output_schema.json", "r") as f:
    schema = json.load(f)

# Create a mock facade with "vi_class": "I"
facade_obj = {
    "id": "FACADE-MAIN",
    "orientation": "N",
    "area_m2": 15.0,
    "vi_score": 10.0,
    "vi_class": "minor", # Aligned with schema enum
    "mosaic_path": "mosaic.png",
    "enhancement_params": {"clahe_clip_limit": 2.0},
    "zones": []
}

data = {
    "schema_version": "1.0.0",
    "generated_at": "2026-06-02T15:00:00Z",
    "pipeline_config_hash": "0123456789abcdef",
    "buildings": [
        {
            "id": "BLDG-01",
            "name": "IIT",
            "address": "Kharagpur",
            "gps_centroid": {"lat": 22.31, "lon": 87.31},
            "inspection_date": "2026-06-02",
            "inspector_module_version": "1.0.0",
            "cycle_number": 1,
            "facades": [facade_obj]
        }
    ]
}

print("Running validation using standard jsonschema.validate...")
try:
    jsonschema.validate(instance=data, schema=schema)
    print("Success!")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
