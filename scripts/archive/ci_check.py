#!/usr/bin/env python
"""
ci_check.py — Cross-Platform Local CI/CD Pipeline Automation Script
=====================================================================
Automates linting, phase-by-phase testing, coverage reporting, and
handover package validation. Prints color-coded, clean diagnostic reports.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Initialize ANSI colors (forces Windows cmd/powershell to process ANSI colors)
os.system("")

COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def print_header(title: str) -> None:
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== {title} ==={COLOR_RESET}")

def print_success(message: str) -> None:
    print(f"{COLOR_GREEN}[OK] {message}{COLOR_RESET}")

def print_failure(message: str) -> None:
    print(f"{COLOR_RED}[FAIL] {message}{COLOR_RESET}")

def print_warning(message: str) -> None:
    print(f"{COLOR_YELLOW}[WARN] {message}{COLOR_RESET}")

def run_step(name: str, command: list[str]) -> bool:
    print(f"Running: {' '.join(command)}...")
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print_success(f"{name} passed.")
            return True
        else:
            print_failure(f"{name} failed with exit code {result.returncode}.")
            print(f"{COLOR_BOLD}Output:{COLOR_RESET}\n{result.stdout}\n{result.stderr}")
            return False
    except Exception as exc:
        print_failure(f"Error executing {name}: {exc}")
        return False

def main() -> None:
    print_header("CORTEX PIPELINE LOCAL CI/CD RUNNER")
    
    workspace = Path(__file__).parent.resolve()
    os.chdir(workspace)
    
    overall_success = True
    
    # ----------------------------------------------------
    # STEP 1: Linting
    # ----------------------------------------------------
    print_header("Step 1: Code Linting & Style Compliance")
    lint_ok = run_step("Style Linter (flake8)", [sys.executable, "-m", "flake8", "src/", "tests/"])
    if not lint_ok:
        overall_success = False

    # ----------------------------------------------------
    # STEP 2: Phase-by-Phase Testing
    # ----------------------------------------------------
    print_header("Step 2: Functional Testing (Phase-by-Phase)")
    
    phases = {
        "Phase 1: Ingestion & Pre-processing": "tests/test_phase1/",
        "Phase 2: Quantification & Temporal": "tests/test_phase2/",
        "Phase 3: Features & FP Filtering": "tests/test_phase3/",
        "Phase 4: Output Sch & PDF Reporting": "tests/test_phase4/"
    }
    
    for phase_name, test_path in phases.items():
        if Path(test_path).exists():
            ok = run_step(phase_name, [sys.executable, "-m", "pytest", test_path, "-q", "--tb=short"])
            if not ok:
                overall_success = False
        else:
            print_warning(f"{phase_name} tests path not found: {test_path}")
            
    # ----------------------------------------------------
    # STEP 3: Test Coverage
    # ----------------------------------------------------
    print_header("Step 3: Test Coverage Validation")
    cov_ok = run_step(
        "Coverage Report",
        [sys.executable, "-m", "pytest", "tests/", "-q", "--cov=src", "--cov-report=term-missing"]
    )
    if not cov_ok:
        overall_success = False

    # ----------------------------------------------------
    # STEP 4: Handover Compilation & Schema Validation
    # ----------------------------------------------------
    print_header("Step 4: End-to-End Handover Package & Schema Check")
    handover_script = workspace / "scratch" / "compile_handover.py"
    if handover_script.exists():
        compile_ok = run_step(
            "Compile Handover",
            [sys.executable, "-m", "scratch.compile_handover"]
        )
        if compile_ok:
            zip_file = workspace / "handover_package.zip"
            if zip_file.exists():
                print_success(f"Handover ZIP compiled successfully: {zip_file}")
                # Print size of the ZIP file
                size_mb = zip_file.stat().st_size / (1024 * 1024)
                print(f"Archive Size: {size_mb:.2f} MB")
            else:
                print_failure("handover_package.zip was not created.")
                overall_success = False
        else:
            overall_success = False
    else:
        print_failure(f"Handover compile script not found at {handover_script}")
        overall_success = False

    # ----------------------------------------------------
    # STEP 5: Schema Validation Validation
    # ----------------------------------------------------
    print_header("Step 5: output_schema Validation Test")
    validate_script = workspace / "test_validate.py"
    if validate_script.exists():
        val_ok = run_step("JSON Schema Validator", [sys.executable, str(validate_script)])
        if not val_ok:
            overall_success = False
    else:
        print_warning("test_validate.py not found; skipping schema validation sanity check.")

    # ----------------------------------------------------
    # STEP 6: End-to-End Integration Testing
    # ----------------------------------------------------
    print_header("Step 6: End-to-End Integration Verification")
    e2e_test_path = workspace / "tests" / "test_e2e.py"
    if e2e_test_path.exists():
        e2e_ok = run_step("E2E Integration Verification", [sys.executable, "-m", "pytest", str(e2e_test_path), "-q"])
        if not e2e_ok:
            overall_success = False
    else:
        print_failure("test_e2e.py integration script not found.")
        overall_success = False

    # ----------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------
    print_header("Local CI/CD Pipeline Execution Summary")
    if overall_success:
        print(f"\n{COLOR_BOLD}{COLOR_GREEN}=============================================")
        print("SUCCESS: ALL CI/CD TESTS PASSED SUCCESSFULLY! Ready for Handover.")
        print(f"============================================={COLOR_RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{COLOR_BOLD}{COLOR_RED}=============================================")
        print("FAIL: CI/CD PIPELINE ENCOUNTERED FAILURES. Fix issues above.")
        print(f"============================================={COLOR_RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
