"""Simple policy checker for MVP (regex-based)"""
import re
from src.utils.logger import log_debug, log_warning

class SimplePolicyChecker:
    """Simple regex-based guardrails for MVP

    Checks for:
    - Password/API key leaks
    - Potentially harmful content
    - Security violations
    """

    # Patterns that should trigger warnings
    BLOCKED_PATTERNS = [
        # Credential exposure patterns (specific: looking for actual credentials)
        (r"password\s*[:=]\s*['\"]?\S+", "Potential password exposure"),
        (r"api[_-]?key\s*[:=]\s*['\"]?\S+", "Potential API key exposure"),
        (r"secret[_-]?key\s*[:=]\s*['\"]?\S+", "Potential secret key exposure"),

        # Harmful action requests (broad: looking for malicious intent)
        (r"\b(hack|hacking|hacked)\b", "Security violation: hacking"),
        (r"\bexploit\b.*\b(vulnerability|system|server|application)", "Security violation: exploitation"),
        (r"\b(bypass|circumvent)\b.*\b(security|authentication|auth)", "Security violation: bypassing security"),
        (r"\bcrack\b.*\b(password|encryption|system)", "Security violation: cracking"),
        (r"\b(backdoor|rootkit|malware)\b", "Security violation: malicious software"),
    ]

    def check(self, text):
        """Check text against policies

        Args:
            text: Text to check

        Returns:
            tuple: (passed: bool, violations: list of strings)
        """
        if not text:
            return True, []

        violations = []

        # Check each pattern
        for pattern, description in self.BLOCKED_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                log_warning(f"Guardrail violation detected: {description}")
                violations.append(f"{description} (found: {len(matches)} instance(s))")

        if violations:
            return False, violations

        return True, []

    def add_disclaimer(self, text):
        """Add a disclaimer to the response

        Args:
            text: Original response

        Returns:
            Response with disclaimer
        """
        disclaimer = "\n\n---\n_Note: This response has been reviewed by automated security guardrails._"
        return text + disclaimer
