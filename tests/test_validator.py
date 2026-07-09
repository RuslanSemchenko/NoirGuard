"""Tests for the pylint/snyk validator."""

from unittest.mock import patch

from app.validator import Validator


def _make_validator() -> Validator:
    return Validator(work_dir="/tmp")


def test_validation_passes_when_logs_clean():
    """Empty tool logs mean the validation passed."""
    validator = _make_validator()
    with patch.object(validator, "run_pylint", return_value=""), patch.object(
        validator, "run_snyk", return_value=""
    ):
        result = validator.run_validation("dummy.py")
    assert result["passed"] is True
    assert result["status"] == 0


def test_validation_fails_on_pylint_error():
    """A pylint error log marks the validation as failed."""
    validator = _make_validator()
    with patch.object(
        validator, "run_pylint", return_value="E0001: syntax-error"
    ), patch.object(validator, "run_snyk", return_value=""):
        result = validator.run_validation("dummy.py")
    assert result["passed"] is False
    assert result["status"] == 1


def test_validation_fails_on_snyk_issue():
    """A snyk issue log marks the validation as failed."""
    validator = _make_validator()
    with patch.object(validator, "run_pylint", return_value=""), patch.object(
        validator, "run_snyk", return_value='{"issues": [{"id": 1}]}'
    ):
        result = validator.run_validation("dummy.py")
    assert result["passed"] is False


def test_missing_tools_do_not_crash():
    """'not installed' logs do not raise and do not fail validation."""
    validator = _make_validator()
    with patch.object(
        validator, "run_pylint", return_value="pylint not installed"
    ), patch.object(validator, "run_snyk", return_value="snyk not installed"):
        result = validator.run_validation("dummy.py")
    assert result["passed"] is True


def test_run_pylint_on_real_file(tmp_path):
    """pylint runs end-to-end against a real temp file with clean code."""
    code_file = tmp_path / "clean.py"
    code_file.write_text('"""Docstring."""\nVALUE = 1\n')
    validator = _make_validator()
    log = validator.run_pylint(str(code_file))
    assert "error" not in log.lower()
