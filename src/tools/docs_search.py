"""Internal Documentation Search Tool (RAG)"""
from src.tools.base import BaseTool

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

            # Format results
            formatted_docs = []
            for i, doc in enumerate(results, 1):
                formatted_docs.append({
                    "rank": i,
                    "title": doc["metadata"].get("title", "Untitled"),
                    "content": doc["content"],
                    "source": doc["metadata"].get("source", "Unknown"),
                    "relevance_score": round(doc["score"], 3)
                })

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
