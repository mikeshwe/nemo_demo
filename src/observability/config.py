"""OpenTelemetry configuration for GenAIOps agent"""
import os
from typing import Optional

class ObservabilityConfig:
    """Configuration for OpenTelemetry observability"""

    def __init__(
        self,
        service_name: Optional[str] = None,
        service_version: Optional[str] = None,
        environment: Optional[str] = None,
        enable_console_exporter: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = True
    ):
        """Initialize observability configuration

        Args:
            service_name: Name of the service (defaults to OTEL_SERVICE_NAME env var)
            service_version: Version of the service (defaults to OTEL_SERVICE_VERSION env var)
            environment: Deployment environment (dev/staging/prod)
            enable_console_exporter: Enable console output for traces/metrics
            enable_metrics: Enable metrics collection
            enable_tracing: Enable distributed tracing
        """
        self.service_name = service_name or os.getenv("OTEL_SERVICE_NAME", "genaiops-agent")
        self.service_version = service_version or os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
        self.environment = environment or os.getenv("OTEL_ENVIRONMENT", "development")

        self.enable_console_exporter = enable_console_exporter
        self.enable_metrics = enable_metrics
        self.enable_tracing = enable_tracing

        # Console exporter settings
        self.console_export_interval_millis = int(
            os.getenv("OTEL_CONSOLE_EXPORT_INTERVAL", "1000")
        )

    def get_resource_attributes(self) -> dict:
        """Get resource attributes for OpenTelemetry

        Returns:
            Dictionary of resource attributes following semantic conventions
        """
        return {
            "service.name": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.environment,
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
        }
