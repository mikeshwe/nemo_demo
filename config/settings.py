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
