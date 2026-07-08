import subprocess
import tempfile
import sys
from typing import Any


PYTHON = sys.executable


class Validator:
    def __init__(self, work_dir: str | None = None):
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="noirguard_")

    def run_validation(self, code_path: str) -> dict[str, Any]:
        pylint_log = ""
        snyk_log = ""

        try:
            result = subprocess.run(
                [PYTHON, "-m", "pylint", "--errors-only", code_path],
                capture_output=True, text=True, timeout=60
            )
            pylint_log = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            pylint_log = "pylint timed out"
        except FileNotFoundError:
            pylint_log = "pylint not installed"
        except Exception as e:
            pylint_log = f"pylint error: {e}"

        try:
            result = subprocess.run(
                ["snyk", "code", "test", code_path, "--json"],
                capture_output=True, text=True, timeout=120
            )
            snyk_log = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            snyk_log = "snyk timed out"
        except FileNotFoundError:
            snyk_log = "snyk not installed"
        except Exception as e:
            snyk_log = f"snyk error: {e}"

        status = 0
        if pylint_log and "error" in pylint_log.lower():
            status = 1
        if snyk_log and ("issue" in snyk_log.lower() or "error" in snyk_log.lower()):
            status = 1

        return {"pylint_log": pylint_log, "snyk_log": snyk_log, "status": status}
