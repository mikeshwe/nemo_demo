"""Security Policy Checker Tool"""
from datetime import datetime
from src.tools.base import BaseTool

class SecurityPolicyChecker(BaseTool):
    """Check if a library or component is approved for deployment"""

    def __init__(self, approved_list):
        """Initialize with approved libraries list

        Args:
            approved_list: List of approved library names
        """
        self.approved_libraries = set(approved_list)

    @property
    def name(self):
        return "security_policy_checker"

    @property
    def description(self):
        return "Check if a library or component is approved for production deployment according to security policies. Returns approval status and policy information."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "library_name": {
                    "type": "string",
                    "description": "Name of the library or component to check (e.g., 'NeMo Retriever', 'TensorRT')"
                }
            },
            "required": ["library_name"]
        }

    def execute(self, library_name):
        """Check if library is approved

        Args:
            library_name: Name of the library to check

        Returns:
            dict with success, data (approval info), and error fields
        """
        try:
            # Normalize library name for comparison
            normalized = library_name.strip()

            # Check against approved list (case-insensitive)
            is_approved = any(
                normalized.lower() == lib.lower()
                for lib in self.approved_libraries
            )

            return {
                "success": True,
                "data": {
                    "library_name": library_name,
                    "is_approved": is_approved,
                    "status": "APPROVED" if is_approved else "NOT_APPROVED",
                    "policy_version": "1.0",
                    "checked_at": datetime.utcnow().isoformat(),
                    "message": f"{'✓' if is_approved else '✗'} {library_name} is {'approved' if is_approved else 'not approved'} for production deployment."
                },
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
