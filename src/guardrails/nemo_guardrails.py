"""NeMo Guardrails integration for LangGraph agent"""
import os
from typing import Tuple, Optional, Dict, Any
from pathlib import Path

try:
    from nemoguardrails import RailsConfig, LLMRails
    NEMO_AVAILABLE = True
except ImportError:
    NEMO_AVAILABLE = False

from src.utils.logger import log_info, log_warning, log_debug, log_verbose
from src.guardrails.policy_checker import SimplePolicyChecker

# OpenTelemetry imports
try:
    from src.observability import (
        get_tracer,
        is_initialized,
        GUARDRAILS_TYPE,
        GUARDRAILS_CHECK_TYPE,
        GUARDRAILS_PASSED,
        GUARDRAILS_REJECTION_REASON,
        GUARDRAILS_INPUT_LENGTH,
        GUARDRAILS_OUTPUT_LENGTH,
        EVENT_INPUT_BLOCKED,
        EVENT_OUTPUT_BLOCKED
    )
    from src.observability.tracer import add_span_attributes, record_exception
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

class NemoGuardrailsWrapper:
    """Wrapper for NeMo Guardrails with fallback to SimplePolicyChecker

    This class provides enterprise-grade safety validation using NVIDIA's
    NeMo Guardrails. If NeMo is not available, it falls back to the simple
    regex-based policy checker.
    """

    def __init__(self):
        """Initialize NeMo Guardrails or fallback"""
        self.rails = None
        self.enabled = False
        self.fallback_checker = SimplePolicyChecker()

        if NEMO_AVAILABLE:
            self._initialize_rails()
        else:
            log_warning("NeMo Guardrails not installed. Using simple policy checker fallback.")

    def _initialize_rails(self):
        """Initialize NeMo Guardrails from config"""
        try:
            # Get config path
            config_path = Path(__file__).parent.parent.parent / "config" / "nemo_guardrails"

            if not config_path.exists():
                log_warning(f"Guardrails config not found at {config_path}")
                return

            log_info("Initializing NeMo Guardrails...")

            # Set NVIDIA API credentials from environment
            nvidia_api_key = os.getenv("NVIDIA_API_KEY")
            nvidia_base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

            if not nvidia_api_key:
                log_warning("NVIDIA_API_KEY not found in environment")
                return

            # NeMo Guardrails' OpenAI provider expects OPENAI_API_KEY and OPENAI_API_BASE
            # Set them temporarily to point to NVIDIA's API
            os.environ["OPENAI_API_KEY"] = nvidia_api_key
            os.environ["OPENAI_API_BASE"] = nvidia_base_url

            # Load configuration
            rails_config = RailsConfig.from_path(str(config_path))

            # Create LLMRails instance
            self.rails = LLMRails(rails_config)
            self.enabled = True

            log_info("✓ NeMo Guardrails initialized successfully")

        except Exception as e:
            log_warning(f"Failed to initialize NeMo Guardrails: {e}")
            log_debug(f"Error details: {type(e).__name__}: {str(e)}")
            self.enabled = False

    def check_input(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """Check user input against guardrails

        Args:
            user_input: User's query

        Returns:
            Tuple of (passed: bool, rejection_reason: Optional[str])
        """
        if not user_input:
            return True, None

        log_verbose(f"Checking input: {user_input[:100]}...")

        # Create OpenTelemetry span for input validation
        if OTEL_AVAILABLE and is_initialized():
            tracer = get_tracer()
            with tracer.start_as_current_span("guardrails.input_check") as span:
                add_span_attributes(span, {
                    GUARDRAILS_CHECK_TYPE: "input",
                    GUARDRAILS_INPUT_LENGTH: len(user_input),
                    GUARDRAILS_TYPE: "nemo" if (self.enabled and self.rails) else "fallback"
                })

                # Use NeMo Guardrails if available
                if self.enabled and self.rails:
                    log_info("🛡️  Checking input with NeMo Guardrails...")
                    passed, reason = self._check_input_with_nemo(user_input)
                else:
                    # Fallback to simple checker
                    log_info("🛡️  Checking input with fallback guardrails...")
                    passed, reason = self._check_input_with_fallback(user_input)

                # Add result to span
                add_span_attributes(span, {GUARDRAILS_PASSED: passed})
                if not passed:
                    add_span_attributes(span, {GUARDRAILS_REJECTION_REASON: reason})
                    span.add_event(EVENT_INPUT_BLOCKED, {"reason": reason})

                return passed, reason
        else:
            # Use NeMo Guardrails if available
            if self.enabled and self.rails:
                log_info("🛡️  Checking input with NeMo Guardrails...")
                return self._check_input_with_nemo(user_input)

            # Fallback to simple checker
            log_info("🛡️  Checking input with fallback guardrails...")
            return self._check_input_with_fallback(user_input)

    def _check_input_with_nemo(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """Check input using NeMo Guardrails"""
        try:
            log_verbose("=" * 60)
            log_verbose("NEMO GUARDRAILS INPUT CHECK:")
            log_verbose("-" * 60)
            log_verbose(f"Input: {user_input[:200]}")

            # Generate response using NeMo Guardrails
            # NeMo will apply configured rails and block if necessary
            result = self.rails.generate(messages=[{
                "role": "user",
                "content": user_input
            }])

            # Check if NeMo blocked the input
            # When blocked, NeMo typically returns specific messages or metadata
            response_text = result.get("content", "") if isinstance(result, dict) else str(result)

            log_verbose(f"NeMo Response: {response_text[:200] if response_text else '(empty)'}")
            log_verbose("=" * 60)

            # Check for blocking indicators in NeMo's response
            blocking_phrases = [
                "cannot help with that",
                "cannot provide",
                "cannot assist",
                "against our policies",
                "not appropriate",
                "i'm not able to"
            ]

            lower_response = response_text.lower()
            for phrase in blocking_phrases:
                if phrase in lower_response:
                    reason = "Input blocked by NeMo Guardrails policy"
                    log_warning(f"NeMo Guardrails blocked input: {phrase}")
                    return False, reason

            # Additional pattern-based validation (defense in depth)
            # Use SimplePolicyChecker as backup to NeMo
            passed, violations = self.fallback_checker.check(user_input)
            if not passed:
                reason = "; ".join(violations)
                log_warning(f"Input blocked by pattern matching: {reason}")
                return False, reason

            log_verbose("Input passed NeMo Guardrails check")
            return True, None

        except Exception as e:
            log_warning(f"Error in NeMo Guardrails input check: {e}")
            # Fail open - allow the request
            return True, None

    def _check_input_with_fallback(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """Check input using SimplePolicyChecker fallback"""
        passed, violations = self.fallback_checker.check(user_input)

        if not passed:
            reason = "; ".join(violations)
            log_warning(f"Input blocked by fallback checker: {reason}")
            return False, reason

        return True, None

    def check_output(self, llm_response: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """Check LLM output against guardrails

        Args:
            llm_response: LLM's generated response
            context: Optional context information

        Returns:
            Tuple of (passed: bool, violation_reason: Optional[str])
        """
        if not llm_response:
            return True, None

        log_verbose(f"Checking output: {llm_response[:100]}...")

        # Create OpenTelemetry span for output validation
        if OTEL_AVAILABLE and is_initialized():
            tracer = get_tracer()
            with tracer.start_as_current_span("guardrails.output_check") as span:
                add_span_attributes(span, {
                    GUARDRAILS_CHECK_TYPE: "output",
                    GUARDRAILS_OUTPUT_LENGTH: len(llm_response),
                    GUARDRAILS_TYPE: "nemo" if (self.enabled and self.rails) else "fallback"
                })

                # Use NeMo Guardrails if available
                if self.enabled and self.rails:
                    log_info("🛡️  Checking output with NeMo Guardrails...")
                    passed, reason = self._check_output_with_nemo(llm_response, context)
                else:
                    # Fallback to simple checker
                    log_info("🛡️  Checking output with fallback guardrails...")
                    passed, reason = self._check_output_with_fallback(llm_response)

                # Add result to span
                add_span_attributes(span, {GUARDRAILS_PASSED: passed})
                if not passed:
                    add_span_attributes(span, {GUARDRAILS_REJECTION_REASON: reason})
                    span.add_event(EVENT_OUTPUT_BLOCKED, {"reason": reason})

                return passed, reason
        else:
            # Use NeMo Guardrails if available
            if self.enabled and self.rails:
                log_info("🛡️  Checking output with NeMo Guardrails...")
                return self._check_output_with_nemo(llm_response, context)

            # Fallback to simple checker
            log_info("🛡️  Checking output with fallback guardrails...")
            return self._check_output_with_fallback(llm_response)

    def _check_output_with_nemo(self, llm_response: str, context: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """Check output using NeMo Guardrails"""
        try:
            log_verbose("=" * 60)
            log_verbose("NEMO GUARDRAILS OUTPUT CHECK:")
            log_verbose("-" * 60)
            log_verbose(f"Output to validate: {llm_response[:200]}")

            # Use NeMo to validate the output
            # Pass as an assistant message and check if NeMo flags it
            result = self.rails.generate(messages=[
                {"role": "user", "content": "Check if the following response is safe"},
                {"role": "assistant", "content": llm_response}
            ])

            # Get NeMo's assessment
            response_text = result.get("content", "") if isinstance(result, dict) else str(result)

            log_verbose(f"NeMo Assessment: {response_text[:200] if response_text else '(empty)'}")
            log_verbose("=" * 60)

            # Check if NeMo flagged any issues
            flagging_phrases = [
                "not safe",
                "inappropriate",
                "violates",
                "should not",
                "cannot be shared"
            ]

            lower_response = response_text.lower()
            for phrase in flagging_phrases:
                if phrase in lower_response:
                    reason = "Output flagged by NeMo Guardrails"
                    log_warning(f"NeMo flagged output: {phrase}")
                    return False, reason

            # Additional pattern-based checks (defense in depth)
            # Use SimplePolicyChecker as backup to NeMo
            passed, violations = self.fallback_checker.check(llm_response)
            if not passed:
                reason = "; ".join(violations)
                log_warning(f"Output blocked by pattern matching: {reason}")
                return False, reason

            log_verbose("Output passed NeMo Guardrails check")
            return True, None

        except Exception as e:
            log_warning(f"Error in NeMo Guardrails output check: {e}")
            # Fail open - allow the response
            return True, None

    def _check_output_with_fallback(self, llm_response: str) -> Tuple[bool, Optional[str]]:
        """Check output using SimplePolicyChecker fallback"""
        passed, violations = self.fallback_checker.check(llm_response)

        if not passed:
            reason = "; ".join(violations)
            log_warning(f"Output blocked by fallback checker: {reason}")
            return False, reason

        return True, None

    def is_enabled(self) -> bool:
        """Check if NeMo Guardrails are enabled

        Returns:
            True if NeMo Guardrails are active, False if using fallback
        """
        return self.enabled

    def get_status(self) -> Dict[str, Any]:
        """Get guardrails status information

        Returns:
            Dictionary with status information
        """
        return {
            "nemo_available": NEMO_AVAILABLE,
            "nemo_enabled": self.enabled,
            "using_fallback": not self.enabled,
            "fallback_type": "SimplePolicyChecker"
        }
