"""OpenLineage client with local caching for Trust Plane"""
from datetime import datetime
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Global state
_lineage_client: Optional['LineageClientWrapper'] = None
_lineage_enabled: bool = False


class LineageClientWrapper:
    """Wrapper around OpenLineage client with metadata caching

    This client provides:
    1. OpenLineage event emission (to Marquez or console)
    2. Metadata caching for fast Trust Plane queries
    3. Graceful degradation if backend unavailable
    """

    def __init__(self, url: str = "http://localhost:5000", namespace: str = "genaiops-demo"):
        """Initialize OpenLineage client

        Args:
            url: OpenLineage backend URL (Marquez server)
            namespace: Default namespace for this application
        """
        self.namespace = namespace
        self.url = url
        self.backend_available = False

        # Try to import and initialize OpenLineage client
        try:
            from openlineage.client import OpenLineageClient
            from openlineage.client.transport.http import HttpTransport, HttpConfig
            from openlineage.client.transport.console import ConsoleTransport, ConsoleConfig

            # Try HTTP transport first (for Marquez)
            # We'll test connectivity later when emitting events
            try:
                import requests
                # Quick connectivity test
                response = requests.get(f"{url}/api/v1/namespaces", timeout=2)
                if response.status_code == 200:
                    http_config = HttpConfig(url=url)
                    transport = HttpTransport(http_config)
                    self.client = OpenLineageClient(transport=transport)
                    self.backend_available = True
                    logger.info(f"✓ OpenLineage HTTP client initialized (backend: {url})")
                else:
                    raise ConnectionError(f"Backend returned {response.status_code}")
            except Exception as http_error:
                # Fallback to console transport
                logger.warning(f"OpenLineage backend not available at {url}, using console: {http_error}")
                console_config = ConsoleConfig()
                transport = ConsoleTransport(console_config)
                self.client = OpenLineageClient(transport=transport)
                self.backend_available = False
                logger.info("✓ OpenLineage console client initialized")

        except ImportError as e:
            logger.error(f"OpenLineage library not installed: {e}")
            raise

        # Metadata cache for Trust Plane queries
        # Format: {"namespace/dataset_name": {"metadata": {...}, "timestamp": datetime}}
        self._metadata_cache: Dict[str, Dict] = {}

    def emit_event(self, event):
        """Emit OpenLineage event

        Args:
            event: OpenLineage RunEvent
        """
        try:
            self.client.emit(event)
            logger.debug(f"Emitted lineage event: {event.job.name} ({event.eventType.value})")
        except Exception as e:
            logger.error(f"Failed to emit lineage event: {e}")

    def cache_dataset_metadata(self, namespace: str, name: str, metadata: Dict):
        """Cache dataset metadata for Trust Plane queries

        This is called after ingestion to store data quality metrics
        that the Trust Plane will query before allowing data access.

        Args:
            namespace: Dataset namespace (e.g., "chromadb")
            name: Dataset name (e.g., "internal_docs.chunks")
            metadata: Metadata dict with 'metrics' key containing data quality metrics
        """
        key = f"{namespace}/{name}"
        self._metadata_cache[key] = {
            "metadata": metadata,
            "timestamp": datetime.now()
        }
        logger.info(f"✓ Cached metadata for {key}")
        logger.debug(f"  Metrics: {metadata.get('metrics', {})}")

    def query_marquez_api(self, namespace: str, name: str) -> Optional[Dict]:
        """Query Marquez API for dataset metadata

        Fetches the latest dataset version from Marquez to get data quality facets.

        Args:
            namespace: Dataset namespace
            name: Dataset name

        Returns:
            Metadata dict with metrics, or None if unavailable
        """
        if not self.backend_available:
            logger.debug("Marquez backend not available, skipping API query")
            return None

        try:
            import requests
            from src.observability.lineage.metrics import extract_metrics_from_facet

            # Query dataset endpoint
            # Marquez API: GET /api/v1/namespaces/{namespace}/datasets/{dataset}
            api_url = f"{self.url}/api/v1/namespaces/{namespace}/datasets/{name}"

            logger.debug(f"Querying Marquez API: {api_url}")
            response = requests.get(api_url, timeout=5)

            if response.status_code == 404:
                logger.debug(f"Dataset not found in Marquez: {namespace}/{name}")
                return None

            response.raise_for_status()
            dataset_info = response.json()

            # Extract data quality facets from latest version
            facets = dataset_info.get("facets", {})
            quality_facet = facets.get("dataQualityMetrics")

            if not quality_facet:
                logger.debug(f"No dataQualityMetrics facet found for {namespace}/{name}")
                return None

            # Extract metrics from facet
            metrics = extract_metrics_from_facet(quality_facet)
            if metrics:
                metadata = {
                    "metrics": metrics,
                    "computed_at": dataset_info.get("createdAt", datetime.now().isoformat()),
                    "source": "marquez_api"
                }

                # Cache it locally for faster subsequent queries
                self.cache_dataset_metadata(namespace, name, metadata)

                logger.info(f"✓ Retrieved metadata from Marquez API for {namespace}/{name}")
                logger.debug(f"  Metrics: {metrics}")
                return metadata
            else:
                logger.warning(f"Failed to extract metrics from facet for {namespace}/{name}")
                return None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Marquez API query failed for {namespace}/{name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error querying Marquez API: {e}", exc_info=True)
            return None

    def get_dataset_metadata(self, namespace: str, name: str) -> Optional[Dict]:
        """Get dataset metadata with fallback chain

        This is called by Trust Plane to check data quality before
        allowing tool execution.

        Fallback order:
        1. Local cache (fast, in-memory)
        2. Marquez API (persistent, authoritative)
        3. None (no metadata available)

        Args:
            namespace: Dataset namespace
            name: Dataset name

        Returns:
            Metadata dict or None if not found
        """
        key = f"{namespace}/{name}"

        # Try local cache first (fastest)
        cached = self._metadata_cache.get(key)
        if cached:
            # Check if cache is stale (> 1 hour)
            age_seconds = (datetime.now() - cached["timestamp"]).total_seconds()
            if age_seconds <= 3600:  # 1 hour
                logger.debug(f"Retrieved metadata from local cache for {key} ({age_seconds:.0f}s old)")
                return cached["metadata"]
            else:
                logger.debug(f"Local cache stale for {key} ({age_seconds:.0f}s old), querying Marquez")

        # Cache miss or stale - try Marquez API
        marquez_metadata = self.query_marquez_api(namespace, name)
        if marquez_metadata:
            return marquez_metadata

        # No metadata available
        logger.debug(f"No metadata available for {key}")
        return None


def initialize_lineage(
    enabled: bool = True,
    url: str = "http://localhost:5000",
    namespace: str = "genaiops-demo"
) -> bool:
    """Initialize OpenLineage client

    Args:
        enabled: Whether to enable lineage tracking
        url: Backend URL (Marquez server or other OpenLineage backend)
        namespace: Default namespace for this application

    Returns:
        True if initialized successfully, False otherwise
    """
    global _lineage_client, _lineage_enabled

    if not enabled:
        _lineage_enabled = False
        logger.info("OpenLineage disabled")
        return False

    try:
        _lineage_client = LineageClientWrapper(url=url, namespace=namespace)
        _lineage_enabled = True
        logger.info(f"✓ OpenLineage enabled (namespace: {namespace})")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize OpenLineage: {e}")
        _lineage_enabled = False
        return False


def shutdown_lineage():
    """Shutdown lineage client"""
    global _lineage_client, _lineage_enabled

    if _lineage_client:
        logger.info("OpenLineage shutdown")
        _lineage_client = None
        _lineage_enabled = False


def get_lineage_client() -> Optional[LineageClientWrapper]:
    """Get lineage client instance

    Returns:
        LineageClientWrapper instance or None if not enabled
    """
    return _lineage_client if _lineage_enabled else None


def is_lineage_enabled() -> bool:
    """Check if lineage is enabled

    Returns:
        True if lineage client is initialized and enabled
    """
    return _lineage_enabled and _lineage_client is not None
