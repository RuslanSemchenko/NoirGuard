import re
import time
import tempfile
from pathlib import Path
from app.agent import QwenClient
from app.validator import Validator

APPSEC_SYSTEM_PROMPT = """
You are a hardened, adversarial AppSec Auditor persona. Your focus is strictly on catching
high-impact vulnerabilities such as Path Traversal, Use-After-Free, or Injection flaws.
When an anomaly is detected, provide a secure Python patch. If validation fails,
you will receive the Pylint and Snyk logs. Analyze the errors and generate a corrected patch.
"""


def extract_code(text: str) -> str:
    code_blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if code_blocks:
        return max(code_blocks, key=len).strip()
    return text.strip()


class RemediationOrchestrator:
    def __init__(self, agent: QwenClient, validator: Validator):
        self.agent = agent
        self.validator = validator

    async def remediate(self, code_base: str, vulnerability_report: str) -> str:
        start_time = time.time()
        total_tokens = 0
        max_retries = 3

        prompt = (f"Vulnerability report:\n{vulnerability_report}\n\n"
                  f"Original code:\n{code_base}\n\n"
                  "Provide a secure Python patch.")

        current_prompt = prompt

        for attempt in range(max_retries):
            response = await self.agent.generate_response(current_prompt,
                                                          system_prompt=APPSEC_SYSTEM_PROMPT)

            total_tokens += response.get("usage", {}).get("total_tokens", 0)
            patch = response["choices"][0]["message"]["content"]
            clean_code = extract_code(patch)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                             delete=False) as f:
                f.write(clean_code)
                tmp_path = f.name

            try:
                validation_result = self.validator.run_validation(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            if not validation_result["status"]:
                duration = time.time() - start_time
                metrics = (f"\n\n--- NoirGuard Remediation Metrics ---\n"
                           f"Total Iterations: {attempt + 1}\n"
                           f"Time Spent: {duration:.2f}s\n"
                           f"Total Tokens Used: {total_tokens}")
                return patch + metrics

            feedback = (f"\n\nValidation failed (Attempt {attempt+1}). "
                        f"Pylint: {validation_result.get('pylint_log')}\n"
                        f"Snyk: {validation_result.get('snyk_log')}")
            current_prompt += feedback

        return "Remediation failed after max retries."
