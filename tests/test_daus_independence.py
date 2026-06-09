from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_core_import_does_not_import_host_project_modules() -> None:
    code = """
import sys
import daus
for module_name in ["allocation", "shuyuan_metering", "reporting", "demo_ui"]:
    if module_name in sys.modules:
        raise SystemExit(f"unexpected host module import: {module_name}")
print("DAUS import boundary OK")
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "DAUS import boundary OK" in completed.stdout


def test_no_host_allocation_adapter_is_exported_from_core() -> None:
    import daus

    assert not hasattr(daus, "daus_result_to_contribution_input_batch")
