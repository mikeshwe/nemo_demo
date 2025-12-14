"""NVIDIA NIM client wrapper using OpenAI-compatible API"""
from openai import OpenAI
from src.utils.logger import log_info, log_error, log_debug

class NVIDIAClient:
    """Client for NVIDIA NIM API using OpenAI-compatible interface"""

    def __init__(self, api_key, base_url, model_name):
        """Initialize the NVIDIA client

        Args:
            api_key: NVIDIA API key from API Catalog
            base_url: NVIDIA API endpoint (default: https://integrate.api.nvidia.com/v1)
            model_name: Model to use (e.g., nvidia/llama-3.1-nemotron-70b-instruct)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

        # Initialize OpenAI client pointing to NVIDIA endpoint
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        log_info(f"Initialized NVIDIA client with model: {model_name}")

    def chat_completion(self, messages, tools=None, temperature=0.2, max_tokens=1024):
        """Call NVIDIA NIM with optional tool calling

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions in OpenAI format
            temperature: Sampling temperature (default: 0.2 for more deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            OpenAI ChatCompletion response object
        """
        try:
            log_debug(f"Calling NVIDIA API with {len(messages)} messages")

            kwargs = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Add tools if provided
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
                log_debug(f"Including {len(tools)} tools in request")

            response = self.client.chat.completions.create(**kwargs)

            log_debug(f"Received response with {len(response.choices)} choices")
            return response

        except Exception as e:
            log_error(f"NVIDIA API call failed: {e}")
            raise

    def validate_connection(self):
        """Test if the API connection is working

        Returns:
            bool: True if connection successful
        """
        try:
            log_info("Testing NVIDIA API connection...")

            test_messages = [
                {"role": "user", "content": "Hello, please respond with 'OK' if you can read this."}
            ]

            response = self.chat_completion(test_messages, max_tokens=50)

            if response.choices and response.choices[0].message:
                log_info("✓ NVIDIA API connection successful!")
                return True
            else:
                log_error("✗ NVIDIA API returned unexpected response")
                return False

        except Exception as e:
            log_error(f"✗ NVIDIA API connection failed: {e}")
            return False
