#!/usr/bin/env python3
"""Initialize ChromaDB vector store with documentation"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.rag.vectorstore import VectorStore
from src.rag.embeddings import EmbeddingModel
from src.utils.logger import log_info, log_error

def chunk_document(text, chunk_size=1000, overlap=200):
    """Simple document chunking

    Args:
        text: Document text
        chunk_size: Characters per chunk
        overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at paragraph
        if end < len(text):
            last_newline = chunk.rfind('\n\n')
            if last_newline > chunk_size // 2:
                end = start + last_newline
                chunk = text[start:end]

        chunks.append(chunk.strip())
        start += chunk_size - overlap

    return chunks

def extract_title(content, filename):
    """Extract title from markdown first heading or filename

    Args:
        content: Document content
        filename: Fallback filename

    Returns:
        Document title
    """
    lines = content.split('\n')
    for line in lines:
        if line.startswith('# '):
            return line[2:].strip()

    # Fallback to filename
    return filename.replace('.md', '').replace('_', ' ').title()

def index_documents(vectorstore, embedding_model, docs_dir):
    """Index all markdown files from directory

    Args:
        vectorstore: VectorStore instance
        embedding_model: EmbeddingModel instance
        docs_dir: Path to documents directory

    Returns:
        Number of chunks indexed
    """
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        log_error(f"Documentation directory not found: {docs_dir}")
        return 0

    markdown_files = list(docs_path.glob("*.md"))

    if not markdown_files:
        log_error(f"No markdown files found in: {docs_dir}")
        return 0

    log_info(f"Found {len(markdown_files)} documentation files")

    all_documents = []
    all_metadatas = []
    all_ids = []

    for file_path in markdown_files:
        log_info(f"Processing: {file_path.name}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract title
        title = extract_title(content, file_path.name)

        # Chunk document
        chunks = chunk_document(content, chunk_size=1000, overlap=200)
        log_info(f"  Split into {len(chunks)} chunks")

        # Add to batch
        for chunk_idx, chunk in enumerate(chunks):
            all_documents.append(chunk)
            all_metadatas.append({
                "title": title,
                "source": file_path.name,
                "chunk_index": chunk_idx,
                "total_chunks": len(chunks)
            })
            all_ids.append(f"{file_path.stem}_{chunk_idx}")

    # Generate embeddings
    log_info(f"Generating embeddings for {len(all_documents)} chunks...")
    embeddings = embedding_model.embed_documents(all_documents)

    # Add to vector store
    log_info("Adding documents to ChromaDB...")
    vectorstore.add_documents(
        documents=all_documents,
        embeddings=embeddings,
        metadatas=all_metadatas,
        ids=all_ids
    )

    return len(all_documents)

def test_search(vectorstore, embedding_model):
    """Test the vector store with a sample query

    Args:
        vectorstore: VectorStore instance
        embedding_model: EmbeddingModel instance
    """
    test_query = "How do I deploy NeMo Retriever?"
    log_info(f"\nTesting search with query: '{test_query}'")

    results = vectorstore.similarity_search(
        query_text=test_query,
        embedding_function=embedding_model,
        k=3
    )

    print("\n" + "=" * 60)
    print("Search Results:")
    print("=" * 60)

    for i, doc in enumerate(results, 1):
        print(f"\n{i}. {doc['metadata']['title']} (score: {doc['score']:.3f})")
        print(f"   Source: {doc['metadata']['source']}")
        print(f"   Preview: {doc['content'][:150]}...")

    print("\n" + "=" * 60)

def main():
    print("=" * 60)
    print("ChromaDB Vector Store Setup")
    print("=" * 60)

    # Create persist directory if it doesn't exist
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)

    # Initialize components
    log_info("Initializing embedding model...")
    embedding_model = EmbeddingModel()

    log_info("Initializing vector store...")
    vectorstore = VectorStore(
        persist_directory=settings.chroma_persist_dir
    )

    # Check if already has documents
    existing_count = vectorstore.collection.count()
    if existing_count > 0:
        response = input(f"\nVector store already has {existing_count} documents. Clear and re-index? (y/N): ")
        if response.lower() == 'y':
            vectorstore.clear_collection()
            # Reinitialize
            vectorstore = VectorStore(persist_directory=settings.chroma_persist_dir)
        else:
            log_info("Keeping existing documents")
            return 0

    # Index documents
    docs_dir = Path(__file__).parent.parent / "data" / "docs"
    num_chunks = index_documents(vectorstore, embedding_model, docs_dir)

    if num_chunks == 0:
        log_error("No documents were indexed!")
        return 1

    log_info(f"\n✓ Successfully indexed {num_chunks} document chunks!")

    # Test search
    test_search(vectorstore, embedding_model)

    log_info("\n✓ Vector store setup complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
