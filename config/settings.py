"""Configuration management for GenAIOps Agent"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Application settings loaded from environment variables"""

    def __init__(self):
        # NVIDIA API Configuration
        self.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        self.nvidia_base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.nvidia_model = os.getenv("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")

        # Vector Store
        self.chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

        # Agent Configuration
        self.max_iterations = int(os.getenv("MAX_ITERATIONS", "10"))

        # Langfuse Configuration (optional)
        self.langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        self.langfuse_host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

        # OpenLineage Configuration (optional)
        self.lineage_enabled = os.getenv("OPENLINEAGE_ENABLED", "false").lower() == "true"
        self.lineage_url = os.getenv("OPENLINEAGE_URL", "http://localhost:5000")
        self.lineage_namespace = os.getenv("OPENLINEAGE_NAMESPACE", "genaiops-demo")

        # Trust Plane Configuration (optional)
        self.trust_plane_enabled = os.getenv("TRUST_PLANE_ENABLED", "false").lower() == "true"
        self.trust_plane_policy_file = os.getenv("TRUST_PLANE_POLICY_FILE", "src/trust_plane/policies.yaml")

    def validate(self):
        """Basic validation (MVP version)"""
        if not self.nvidia_api_key:
            print("WARNING: NVIDIA_API_KEY not set. Please add it to .env file.")
            return False
        return True

    @classmethod
    def from_env(cls):
        """Load settings from environment"""
        return cls()


# Global settings instance
settings = Settings()
