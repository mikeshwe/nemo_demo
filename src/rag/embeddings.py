"""Embedding model for RAG"""
from sentence_transformers import SentenceTransformer
from src.utils.logger import log_info

# OpenTelemetry imports
try:
    from src.observability import (
        get_tracer,
        is_initialized,
        EMBEDDING_MODEL,
        EMBEDDING_TEXT_LENGTH,
        EMBEDDING_DIMENSION
    )
    from src.observability.tracer import add_span_attributes, record_exception
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

class EmbeddingModel:
    """Wrapper for SentenceTransformer embeddings"""

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        """Initialize embedding model

        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)
                       This is a lightweight 384-dim model, good for prototypes
        """
        log_info(f"Loading embedding model: {model_name}")
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        log_info(f"✓ Embedding model loaded")

    def embed_documents(self, texts):
        """Embed multiple documents

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, text):
        """Embed a single query

        Args:
            text: Query string

        Returns:
            Embedding vector
        """
        # Create OpenTelemetry span for embedding generation
        if OTEL_AVAILABLE and is_initialized():
            tracer = get_tracer()
            with tracer.start_as_current_span("rag.embedding.query") as span:
                add_span_attributes(span, {
                    EMBEDDING_MODEL: self.model_name,
                    EMBEDDING_TEXT_LENGTH: len(text)
                })

                try:
                    embedding = self.model.encode([text], convert_to_numpy=True)[0]
                    result = embedding.tolist()
                    add_span_attributes(span, {EMBEDDING_DIMENSION: len(result)})
                    return result
                except Exception as e:
                    record_exception(span, e)
                    raise
        else:
            embedding = self.model.encode([text], convert_to_numpy=True)[0]
            return embedding.tolist()

    def __call__(self, text):
        """Allow callable syntax for ChromaDB compatibility"""
        return self.embed_query(text)
