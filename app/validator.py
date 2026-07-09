"""Host-based validation of Python code using pylint and snyk via subprocess."""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PYTHON = sys.executable

PYLINT_TIMEOUT = 60
SNYK_TIMEOUT = 120


def _run_tool(command: list[str], timeout: int) -> str:
    """Run an external tool and return its combined stdout/stderr output."""
    tool_name = command[0] if command[0] != PYTHON else command[2]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return f"{tool_name} timed out"
    except FileNotFoundError:
        return f"{tool_name} not installed"
    except OSError as exc:
        return f"{tool_name} error: {exc}"


class Validator:
    """Runs pylint and snyk checks against a Python file on the host."""

    def __init__(self, work_dir: str | None = None):
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="noirguard_")

    def run_pylint(self, code_path: str) -> str:
        """Run pylint in errors-only mode and return its log output."""
        return _run_tool(
            [PYTHON, "-m", "pylint", "--errors-only", code_path],
            PYLINT_TIMEOUT,
        )

    def run_snyk(self, code_path: str) -> str:
        """Run snyk code test and return its log output."""
        return _run_tool(
            ["snyk", "code", "test", code_path, "--json"],
            SNYK_TIMEOUT,
        )

    def run_validation(self, code_path: str) -> dict[str, Any]:
        """Validate a file with pylint and snyk.

        Returns a dict with ``pylint_log``, ``snyk_log``, per-tool
        ``pylint_passed``/``snyk_passed`` booleans, an overall ``passed``
        flag and the legacy ``status`` field (0 = passed, 1 = failed).
        """
        pylint_log = self.run_pylint(code_path)
        snyk_log = self.run_snyk(code_path)

        pylint_passed = not (bool(pylint_log) and "error" in pylint_log.lower())
        snyk_passed = not (
            bool(snyk_log)
            and ("issue" in snyk_log.lower() or "error" in snyk_log.lower())
        )
        passed = pylint_passed and snyk_passed

        return {
            "pylint_log": pylint_log,
            "snyk_log": snyk_log,
            "pylint_passed": pylint_passed,
            "snyk_passed": snyk_passed,
            "passed": passed,
            "status": 0 if passed else 1,
        }

    def validate_code(self, code: str) -> dict[str, Any]:
        """Write ``code`` to a temp file, validate it and clean up afterwards."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(code)
            tmp_path = tmp_file.name
        try:
            return self.run_validation(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
