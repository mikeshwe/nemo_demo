"""ChromaDB vector store for document retrieval"""
import chromadb
from chromadb.config import Settings
from src.utils.logger import log_info, log_debug

class VectorStore:
    """ChromaDB-based vector store for semantic search"""

    def __init__(self, persist_directory, collection_name="internal_docs"):
        """Initialize ChromaDB

        Args:
            persist_directory: Directory to store ChromaDB data
            collection_name: Name of the collection
        """
        log_info(f"Initializing ChromaDB at: {persist_directory}")

        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # Create ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

        log_info(f"✓ ChromaDB initialized with collection: {collection_name}")
        log_info(f"  Collection has {self.collection.count()} documents")

    def add_documents(self, documents, embeddings, metadatas, ids):
        """Add documents to the vector store

        Args:
            documents: List of document texts
            embeddings: List of embedding vectors
            metadatas: List of metadata dicts
            ids: List of unique document IDs
        """
        log_debug(f"Adding {len(documents)} documents to vector store")

        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        log_info(f"✓ Added {len(documents)} documents")

    def similarity_search(self, query_text, embedding_function, k=3):
        """Search for similar documents

        Args:
            query_text: Query string
            embedding_function: Function to embed the query
            k: Number of results to return

        Returns:
            List of dicts with 'content', 'metadata', and 'score'
        """
        log_debug(f"Searching for: {query_text[:50]}...")

        # Embed the query
        query_embedding = embedding_function(query_text)

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        documents = []
        if results["documents"] and len(results["documents"][0]) > 0:
            for i in range(len(results["documents"][0])):
                doc = {
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "score": 1.0 - results["distances"][0][i]  # Convert distance to similarity
                }
                documents.append(doc)

        log_debug(f"Found {len(documents)} results")
        return documents

    def clear_collection(self):
        """Delete all documents from collection"""
        self.client.delete_collection(self.collection_name)
        log_info(f"✓ Cleared collection: {self.collection_name}")
