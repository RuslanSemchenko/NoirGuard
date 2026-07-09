"""Remediation orchestrator: iterative LLM patch generation with validation."""

import re
import tempfile
import time
from pathlib import Path

from app.agent import QwenClient
from app.scanner import SecurityScanner
from app.validator import Validator

APPSEC_SYSTEM_PROMPT = """
You are a hardened, adversarial AppSec Auditor persona. Your focus is strictly on catching
high-impact vulnerabilities such as Path Traversal, Use-After-Free, or Injection flaws.
When an anomaly is detected, provide a secure Python patch. If validation fails,
you will receive the Pylint and Snyk logs. Analyze the errors and generate a corrected patch.
"""

MAX_RETRIES = 3


def extract_code(text: str) -> str:
    """Extract the largest fenced Python code block from markdown text."""
    code_blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if code_blocks:
        return max(code_blocks, key=len).strip()
    return text.strip()


def build_metrics(iterations: int, start_time: float, total_tokens: int) -> str:
    """Format the remediation metrics footer appended to successful patches."""
    duration = time.time() - start_time
    return (
        "\n\n--- NoirGuard Remediation Metrics ---\n"
        f"Total Iterations: {iterations}\n"
        f"Time Spent: {duration:.2f}s\n"
        f"Total Tokens Used: {total_tokens}"
    )


class RemediationOrchestrator:
    """Drives the self-correction loop between the LLM agent and validators."""

    def __init__(
        self,
        agent: QwenClient,
        validator: Validator,
        scanner: SecurityScanner | None = None,
        max_retries: int = MAX_RETRIES,
    ):
        self.agent = agent
        self.validator = validator
        self.scanner = scanner or SecurityScanner()
        self.max_retries = max_retries

    def _validate_patch(self, clean_code: str) -> dict[str, object]:
        """Write the patch to a temp file and run all validators on it."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as tmp_file:
            tmp_file.write(clean_code)
            tmp_path = tmp_file.name
        try:
            result = self.validator.run_validation(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        scan_report = self.scanner.scan(clean_code)
        result["scan_passed"] = scan_report.passed
        result["scan_summary"] = scan_report.summary()
        return result

    async def remediate(self, code_base: str, vulnerability_report: str) -> str:
        """Iteratively generate and validate a secure patch for the given code."""
        start_time = time.time()
        total_tokens = 0

        current_prompt = (
            f"Vulnerability report:\n{vulnerability_report}\n\n"
            f"Original code:\n{code_base}\n\n"
            "Provide a secure Python patch."
        )

        for attempt in range(self.max_retries):
            response = await self.agent.generate_response(
                current_prompt, system_prompt=APPSEC_SYSTEM_PROMPT
            )
            total_tokens += response.get("usage", {}).get("total_tokens", 0)
            patch = response["choices"][0]["message"]["content"]

            result = self._validate_patch(extract_code(patch))

            if result["status"] == 0 and result["scan_passed"]:
                return patch + build_metrics(attempt + 1, start_time, total_tokens)

            current_prompt += (
                f"\n\nValidation failed (Attempt {attempt + 1}). "
                f"Pylint: {result.get('pylint_log')}\n"
                f"Snyk: {result.get('snyk_log')}\n"
                f"Static scan: {result.get('scan_summary')}"
            )

        return "Remediation failed after max retries."
