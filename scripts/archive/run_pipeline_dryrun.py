"""
run_pipeline_dryrun.py — Validates pipeline module can be imported and initialized.
Does NOT run the full pipeline (which requires actual drone imagery).
"""
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

try:
    # Phase 1: Validate all imports resolve
    print("  Checking pipeline imports...")
    from src.pipeline import CortexPipeline, PIPELINE_VERSION, SIFTCache, MAX_WORKERS
    print(f"  ✅ Pipeline module loaded (v{PIPELINE_VERSION})")
    print(f"  ✅ MAX_WORKERS = {MAX_WORKERS}")

    # Phase 2: Validate SIFTCache instantiation
    print("  Checking SIFTCache...")
    cache = SIFTCache()
    print("  ✅ SIFTCache instance created")

    # Phase 3: Validate config loader
    print("  Checking config loader...")
    from src.utils.config_loader import PipelineConfig
    config_path = "config/pipeline_config.yaml"
    if os.path.exists(config_path):
        cfg = PipelineConfig(config_path)
        print(f"  ✅ Config loaded from {config_path}")
    else:
        print(f"  ⚠️  Config file not found at {config_path} (non-fatal)")

    # Phase 4: Validate SQLite store imports
    print("  Checking SQLite store...")
    from src.utils.sqlite_store import DefectStore, ORMInspection, ORMDefect
    print("  ✅ SQLite store ORM models imported")

    print("\n✅ Pipeline dry-run passed — all modules validated")
    sys.exit(0)

except Exception as exc:
    print(f"\n❌ Pipeline dry-run failed: {exc}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
