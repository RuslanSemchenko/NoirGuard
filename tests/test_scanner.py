"""Tests for the AST-based static security scanner."""

from app.scanner import SecurityScanner


def test_clean_code_passes():
    """Safe code produces no findings."""
    report = SecurityScanner().scan("def add(a, b):\n    return a + b\n")
    assert report.passed
    assert report.summary() == "No security issues detected."


def test_detects_eval():
    """eval() is flagged as code injection."""
    report = SecurityScanner().scan("eval(user_input)")
    assert not report.passed
    assert report.findings[0].rule == "CODE_INJECTION"
    assert report.findings[0].severity == "critical"


def test_detects_exec():
    """exec() is flagged as code injection."""
    report = SecurityScanner().scan("exec(payload)")
    rules = [f.rule for f in report.findings]
    assert "CODE_INJECTION" in rules


def test_detects_os_system():
    """os.system() is flagged as command injection."""
    source = "import os\nos.system(cmd)\n"
    report = SecurityScanner().scan(source)
    rules = [f.rule for f in report.findings]
    assert "COMMAND_INJECTION" in rules


def test_detects_pickle_loads():
    """pickle.loads() is flagged as unsafe deserialization."""
    source = "import pickle\npickle.loads(data)\n"
    report = SecurityScanner().scan(source)
    rules = [f.rule for f in report.findings]
    assert "DESERIALIZATION" in rules


def test_detects_subprocess_shell_true():
    """subprocess with shell=True is flagged."""
    source = "import subprocess\nsubprocess.run(cmd, shell=True)\n"
    report = SecurityScanner().scan(source)
    rules = [f.rule for f in report.findings]
    assert "SHELL_TRUE" in rules


def test_subprocess_shell_false_ok():
    """subprocess with shell=False is not flagged."""
    source = "import subprocess\nsubprocess.run(cmd, shell=False, check=True)\n"
    report = SecurityScanner().scan(source)
    assert report.passed


def test_detects_hardcoded_secret():
    """String assignment to a secret-like name is flagged."""
    report = SecurityScanner().scan('api_key = "sk-123456"\n')
    rules = [f.rule for f in report.findings]
    assert "HARDCODED_SECRET" in rules


def test_empty_secret_not_flagged():
    """Empty strings assigned to secret names are ignored."""
    report = SecurityScanner().scan('password = ""\n')
    assert report.passed


def test_syntax_error_reported():
    """Unparseable source yields a SYNTAX_ERROR finding."""
    report = SecurityScanner().scan("def broken(:\n")
    assert not report.passed
    assert report.findings[0].rule == "SYNTAX_ERROR"


def test_report_to_dict():
    """Report serialization contains counts and findings."""
    report = SecurityScanner().scan("eval(x)")
    data = report.to_dict()
    assert data["passed"] is False
    assert data["finding_count"] == 1
    assert data["findings"][0]["rule"] == "CODE_INJECTION"


def test_finding_line_numbers():
    """Findings carry the correct source line number."""
    source = "x = 1\ny = 2\neval(z)\n"
    report = SecurityScanner().scan(source)
    assert report.findings[0].line == 3
