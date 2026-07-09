"""AST-based static security scanner for Python source code.

Detects common high-impact vulnerability patterns locally, without any
external tools or network calls. Complements the pylint/snyk validation.
"""

import ast
from dataclasses import dataclass, field

DANGEROUS_CALLS: dict[str, tuple[str, str]] = {
    "eval": ("CODE_INJECTION", "Use of eval() allows arbitrary code execution"),
    "exec": ("CODE_INJECTION", "Use of exec() allows arbitrary code execution"),
    "compile": ("CODE_INJECTION", "Dynamic compile() can enable code injection"),
    "os.system": ("COMMAND_INJECTION", "os.system() is vulnerable to shell injection"),
    "os.popen": ("COMMAND_INJECTION", "os.popen() is vulnerable to shell injection"),
    "pickle.load": ("DESERIALIZATION", "pickle.load() can execute arbitrary code"),
    "pickle.loads": ("DESERIALIZATION", "pickle.loads() can execute arbitrary code"),
    "yaml.load": ("DESERIALIZATION", "yaml.load() without SafeLoader is unsafe"),
    "marshal.load": ("DESERIALIZATION", "marshal.load() is unsafe on untrusted data"),
    "marshal.loads": ("DESERIALIZATION", "marshal.loads() is unsafe on untrusted data"),
}

SECRET_KEYWORDS = ("password", "secret", "api_key", "apikey", "token", "passwd")

SEVERITY: dict[str, str] = {
    "CODE_INJECTION": "critical",
    "COMMAND_INJECTION": "critical",
    "DESERIALIZATION": "high",
    "SHELL_TRUE": "high",
    "HARDCODED_SECRET": "medium",
    "SYNTAX_ERROR": "low",
}


@dataclass
class Finding:
    """A single security finding located in the scanned source."""

    rule: str
    message: str
    line: int
    severity: str = "high"

    def to_dict(self) -> dict[str, str | int]:
        """Serialize the finding to a plain dict."""
        return {
            "rule": self.rule,
            "message": self.message,
            "line": self.line,
            "severity": self.severity,
        }


@dataclass
class ScanReport:
    """Aggregated result of scanning one piece of source code."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when no findings were detected."""
        return not self.findings

    def to_dict(self) -> dict[str, object]:
        """Serialize the report to a plain dict."""
        return {
            "passed": self.passed,
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }

    def summary(self) -> str:
        """Human-readable summary of all findings."""
        if self.passed:
            return "No security issues detected."
        lines = [f"{len(self.findings)} security issue(s) detected:"]
        for finding in self.findings:
            lines.append(
                f"- [{finding.severity.upper()}] line {finding.line}: "
                f"{finding.rule} - {finding.message}"
            )
        return "\n".join(lines)


def _call_name(node: ast.Call) -> str:
    """Resolve a dotted call name such as ``os.system`` from a Call node."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts: list[str] = [func.attr]
        value = func.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def _has_shell_true(node: ast.Call) -> bool:
    """Check whether a call passes ``shell=True``."""
    for keyword in node.keywords:
        if keyword.arg == "shell":
            value = keyword.value
            if isinstance(value, ast.Constant) and value.value is True:
                return True
    return False


class _SecurityVisitor(ast.NodeVisitor):
    """Walks the AST collecting security findings."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def _add(self, rule: str, message: str, line: int) -> None:
        severity = SEVERITY.get(rule, "high")
        self.findings.append(Finding(rule, message, line, severity))

    def visit_Call(self, node: ast.Call) -> None:  # pylint: disable=invalid-name
        """Inspect function calls for dangerous patterns."""
        name = _call_name(node)
        if name in DANGEROUS_CALLS:
            rule, message = DANGEROUS_CALLS[name]
            self._add(rule, message, node.lineno)
        if name.startswith("subprocess.") and _has_shell_true(node):
            self._add(
                "SHELL_TRUE",
                "subprocess call with shell=True enables shell injection",
                node.lineno,
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # pylint: disable=invalid-name
        """Inspect assignments for hardcoded secrets."""
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            if node.value.value:
                for target in node.targets:
                    if isinstance(target, ast.Name) and any(
                        key in target.id.lower() for key in SECRET_KEYWORDS
                    ):
                        self._add(
                            "HARDCODED_SECRET",
                            f"Possible hardcoded secret in variable '{target.id}'",
                            node.lineno,
                        )
        self.generic_visit(node)


class SecurityScanner:
    """Static analyzer producing a :class:`ScanReport` for Python source."""

    def scan(self, source: str) -> ScanReport:
        """Scan source code and return a report of findings."""
        report = ScanReport()
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            report.findings.append(
                Finding(
                    "SYNTAX_ERROR",
                    f"Could not parse source: {exc.msg}",
                    exc.lineno or 0,
                    SEVERITY["SYNTAX_ERROR"],
                )
            )
            return report

        visitor = _SecurityVisitor()
        visitor.visit(tree)
        report.findings = visitor.findings
        return report
