import time
from app.agent import QwenClient
from app.validator import Validator

APPSEC_SYSTEM_PROMPT = """
You are a hardened, adversarial AppSec Auditor persona. Your focus is strictly on catching
high-impact vulnerabilities such as Path Traversal, Use-After-Free, or Injection flaws.
When an anomaly is detected, provide a secure Python patch. If validation fails,
you will receive the Pylint and Snyk logs. Analyze the errors and generate a corrected patch.
"""

class RemediationOrchestrator:
    def __init__(self, agent: QwenClient, validator: Validator):
        self.agent = agent
        self.validator = validator

    async def remediate(self, code_base: str, vulnerability_report: str) -> str:
        # Metrics initialization
        start_time = time.time()
        total_tokens = 0
        max_retries = 3

        prompt = (f"Vulnerability report:\n{vulnerability_report}\n\n"
                  f"Original code:\n{code_base}\n\n"
                  "Provide a secure Python patch.")

        current_prompt = prompt

        for attempt in range(max_retries):
            # Generate patch/fix
            response = await self.agent.generate_response(current_prompt,
                                                          system_prompt=APPSEC_SYSTEM_PROMPT)

            # Metrics update (mocked)
            total_tokens += response.get("usage", {}).get("total_tokens", 0)
            patch = response["choices"][0]["message"]["content"]

            # Run validation
            validation_result = self.validator.run_validation("/target")

            # Check if successful
            if not validation_result["status"]:
                duration = time.time() - start_time
                metrics = (f"\n\n--- NoirGuard Remediation Metrics ---\n"
                           f"Total Iterations: {attempt + 1}\n"
                           f"Time Spent: {duration:.2f}s\n"
                           f"Total Tokens Used: {total_tokens}")
                return patch + metrics

            # Feedback
            feedback = (f"\n\nValidation failed (Attempt {attempt+1}). "
                        f"Pylint: {validation_result.get('pylint_log')}\n"
                        f"Snyk: {validation_result.get('snyk_log')}")
            current_prompt += feedback

        return "Remediation failed after max retries."
