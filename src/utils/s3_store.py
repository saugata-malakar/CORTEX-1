"""
s3_store.py — Production S3/Cloudflare R2 Object Storage Adapter
================================================================
Stores raw output JSON and GeoJSON artifacts in object storage, keeping
the primary database lean by storing only the reference key URI.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

class S3Store:
    """Manages raw JSON and GeoJSON artifact uploads to S3/R2 storage."""

    def __init__(self) -> None:
        self.bucket_name = os.getenv("CORTEX_S3_BUCKET", "cortex-inspection-artifacts")
        self.endpoint_url = os.getenv("CORTEX_S3_ENDPOINT", None) # For R2/MinIO
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", None)
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", None)

        self.s3_client = None
        if self.aws_access_key and self.aws_secret_key:
            try:
                import boto3
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key
                )
                logger.info("Initialized boto3 client for object storage bucket: %s", self.bucket_name)
            except Exception as e:
                logger.warning("Failed to initialize boto3 S3 client: %s. Using local fallback.", e)
        else:
            logger.info("No object storage credentials found. Initializing local S3 mock repository.")

    def upload_artifact(
        self,
        building_id: str,
        run_timestamp: str,
        artifact_type: str,
        payload: Dict[str, Any]
    ) -> str:
        """Upload an inspection artifact to object storage and return its URI key.

        Parameters
        ----------
        building_id : str
            Unique building key.
        run_timestamp : str
            Timestamp of the run.
        artifact_type : str
            The type of artifact (e.g. 'inspection_results' or 'defects_geojson').
        payload : dict
            The serializable data dictionary to upload.

        Returns
        -------
        str
            The S3 storage key or local file URI.
        """
        # Sanitize timestamp for paths
        safe_ts = run_timestamp.replace(":", "-").replace(" ", "_")
        s3_key = f"{building_id}/{safe_ts}/{artifact_type}.json"

        # 1. If S3 client is configured, upload to bucket
        if self.s3_client:
            try:
                json_str = json.dumps(payload, indent=2, default=str)
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=json_str.encode("utf-8"),
                    ContentType="application/json"
                )
                logger.info("Uploaded artifact to S3: s3://%s/%s", self.bucket_name, s3_key)
                return f"s3://{self.bucket_name}/{s3_key}"
            except Exception as e:
                logger.error("Failed to upload artifact to S3 bucket %s: %s. Falling back to local.", self.bucket_name, e)

        # 2. Local fallback mock directory
        data_root = Path(os.getenv("CORTEX_DATA_DIR", str(Path(__file__).parents[2] / "data")))
        mock_dir = data_root / "reports" / "s3_mock" / building_id / safe_ts
        mock_dir.mkdir(parents=True, exist_ok=True)
        local_path = mock_dir / f"{artifact_type}.json"

        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

        logger.info("Saved local mock artifact to: %s", local_path)
        # Returns path relative to workspace root
        return f"local://data/reports/s3_mock/{building_id}/{safe_ts}/{artifact_type}.json"

    def convert_to_geojson(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a standard pipeline results payload into a GeoJSON FeatureCollection.

        Parameters
        ----------
        payload : dict
            Master root-level JSON results structure.

        Returns
        -------
        dict
            GeoJSON FeatureCollection structure.
        """
        features = []
        try:
            building = payload["buildings"][0]
            facade = building["facades"][0]
            for zone in facade["zones"]:
                for d in zone["defects"]:
                    coords = d.get("centroid_gps", {"lat": 0.0, "lon": 0.0})
                    feat = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [coords["lon"], coords["lat"]]
                        },
                        "properties": {
                            "defect_id": d["defect_id"],
                            "type": d["type"],
                            "length_cm": d.get("length_cm"),
                            "width_mm": d.get("width_mm"),
                            "area_cm2": d["area_cm2"],
                            "severity_class": d["severity_class"],
                            "vi_contribution": d["vi_contribution"],
                            "confidence_score": d["confidence_score"],
                            "is_false_positive": d["is_false_positive"],
                            "temporal_status": d.get("temporal_status", "new")
                        }
                    }
                    features.append(feat)
        except Exception as e:
            logger.warning("Error converting payload to GeoJSON format: %s", e)

        return {
            "type": "FeatureCollection",
            "features": features
        }
