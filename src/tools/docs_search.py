"""Internal Documentation Search Tool (RAG)"""
from src.tools.base import BaseTool
from src.trust_plane import authorize_dataset_access, is_trust_plane_enabled
import logging

# OpenTelemetry imports for lineage correlation
try:
    from opentelemetry import trace
    from src.observability import is_initialized as is_otel_initialized
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)

class InternalDocsSearch(BaseTool):
    """Search internal documentation using RAG"""

    def __init__(self, vectorstore, embedding_function):
        """Initialize with vector store

        Args:
            vectorstore: VectorStore instance
            embedding_function: Function to embed queries
        """
        self.vectorstore = vectorstore
        self.embedding_function = embedding_function

    @property
    def name(self):
        return "internal_docs_search"

    @property
    def description(self):
        return "Search internal DevOps documentation for deployment guides, setup instructions, troubleshooting tips, and best practices. Returns relevant documentation excerpts."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query describing what information you need (e.g., 'How to deploy NeMo Retriever', 'GPU optimization tips')"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of documentation sections to return (default: 3)",
                    "default": 3
                }
            },
            "required": ["query"]
        }

    def execute(self, query, top_k=3):
        """Search documentation

        Args:
            query: Search query string
            top_k: Number of results to return

        Returns:
            dict with success, data (search results), and error fields
        """
        try:
            # Trust Plane: Check authorization before accessing data
            if is_trust_plane_enabled():
                decision = authorize_dataset_access(
                    namespace="chromadb",
                    dataset_name="internal_docs.chunks",
                    tool_name="internal_docs_search"
                )

                if not decision.allowed:
                    logger.error(f"Trust Plane DENIED access: {decision.reason}")
                    return {
                        "success": False,
                        "data": None,
                        "error": (
                            f"Access to documentation data denied by Trust Plane: "
                            f"{decision.reason}. Please refresh the documentation dataset."
                        ),
                        "trust_plane_decision": decision.to_dict()
                    }

                if decision.action == "WARN":
                    logger.warning(f"Trust Plane WARNING: {decision.reason}")

            # Query vector store
            results = self.vectorstore.similarity_search(
                query_text=query,
                embedding_function=self.embedding_function,
                k=top_k
            )

            if not results:
                return {
                    "success": True,
                    "data": {
                        "query": query,
                        "documents": [],
                        "message": "No relevant documentation found for this query."
                    },
                    "error": None
                }

            # Format results and extract lineage correlation
            formatted_docs = []
            producer_run_ids = set()
            for i, doc in enumerate(results, 1):
                formatted_docs.append({
                    "rank": i,
                    "title": doc["metadata"].get("title", "Untitled"),
                    "content": doc["content"],
                    "source": doc["metadata"].get("source", "Unknown"),
                    "relevance_score": round(doc["score"], 3)
                })
                # Collect producer_run_id for lineage correlation
                if "lineage.producer_run_id" in doc["metadata"]:
                    producer_run_ids.add(doc["metadata"]["lineage.producer_run_id"])

            # Add lineage correlation to OTel span for OpenLineage emission
            if OTEL_AVAILABLE and is_otel_initialized() and producer_run_ids:
                current_span = trace.get_current_span()
                if current_span and current_span.is_recording():
                    # Add input run IDs to span for bidirectional traceability
                    current_span.set_attribute(
                        "lineage.input_run_ids",
                        ",".join(list(producer_run_ids)[:5])  # Limit to 5
                    )
                    logger.debug(f"Added lineage correlation to span: {len(producer_run_ids)} producer run IDs")

            return {
                "success": True,
                "data": {
                    "query": query,
                    "num_results": len(formatted_docs),
                    "documents": formatted_docs
                },
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": f"Documentation search failed: {str(e)}"
            }
