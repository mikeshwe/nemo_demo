"""Embedding model for RAG"""
from sentence_transformers import SentenceTransformer
from src.utils.logger import log_info

class EmbeddingModel:
    """Wrapper for SentenceTransformer embeddings"""

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        """Initialize embedding model

        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)
                       This is a lightweight 384-dim model, good for prototypes
        """
        log_info(f"Loading embedding model: {model_name}")
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
        embedding = self.model.encode([text], convert_to_numpy=True)[0]
        return embedding.tolist()

    def __call__(self, text):
        """Allow callable syntax for ChromaDB compatibility"""
        return self.embed_query(text)
