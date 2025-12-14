# NeMo Retriever Setup and Configuration Guide

## Introduction

NeMo Retriever is NVIDIA's enterprise-grade Retrieval-Augmented Generation (RAG) solution. It combines state-of-the-art embedding models, vector databases, and reranking capabilities to deliver accurate, context-aware AI responses.

## What is NeMo Retriever?

NeMo Retriever consists of three main components:

1. **Embedding Microservice**: Converts text to high-quality vector embeddings
2. **Vector Database Integration**: Supports Milvus, Qdrant, and pgvector
3. **Reranking Microservice**: Improves result relevance using cross-encoder models

## System Requirements

### Minimum Requirements

- **GPU**: NVIDIA T4 or better (for embeddings)
- **Memory**: 16GB+ RAM, 8GB+ VRAM
- **Storage**: 50GB for models and indexes
- **OS**: Ubuntu 20.04+, RHEL 8+

### Recommended for Production

- **GPU**: NVIDIA A100 or H100
- **Memory**: 64GB+ RAM, 40GB+ VRAM
- **Storage**: 500GB NVMe SSD for vector index
- **Network**: 10Gbps for high-throughput scenarios

## Installation Steps

### Step 1: Install Prerequisites

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+
sudo apt install python3.10 python3-pip -y

# Install NVIDIA drivers and CUDA
sudo apt install nvidia-driver-535 cuda-toolkit-12-2 -y
```

### Step 2: Set Up Vector Database

NeMo Retriever supports multiple vector databases. Here's how to set up Milvus:

```bash
# Install Milvus using Docker Compose
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
docker-compose up -d

# Verify Milvus is running
docker-compose ps
```

### Step 3: Deploy NeMo Retriever Embeddings

```bash
# Pull the embedding microservice
docker pull nvcr.io/nvidia/nemo-retriever-embedding-microservice:latest

# Run the embedding service
docker run -d \
  --gpus all \
  --name nemo-embedding \
  -p 8080:8080 \
  -e MODEL_NAME="nvidia/nv-embed-v1" \
  nvcr.io/nvidia/nemo-retriever-embedding-microservice:latest
```

### Step 4: Deploy Reranking Microservice

```bash
# Pull the reranking microservice
docker pull nvcr.io/nvidia/nemo-retriever-reranking-microservice:latest

# Run the reranking service
docker run -d \
  --gpus all \
  --name nemo-reranking \
  -p 8081:8081 \
  -e MODEL_NAME="nvidia/nv-rerankqa-mistral-4b-v3" \
  nvcr.io/nvidia/nemo-retriever-reranking-microservice:latest
```

## Configuration

### Embedding Model Selection

NeMo Retriever supports multiple embedding models:

- **nv-embed-v1**: Best balance of quality and speed (recommended)
- **nv-embed-v2**: Highest quality, slower
- **e5-large**: Good for multilingual content

Configure via environment variable:
```bash
MODEL_NAME="nvidia/nv-embed-v1"
```

### Vector Database Configuration

Create a collection for your documents:

```python
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType

# Define schema
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
    FieldSchema(name="metadata", dtype=DataType.JSON)
]

schema = CollectionSchema(fields, description="Document embeddings")
collection = Collection("documents", schema)

# Create index
index_params = {
    "index_type": "IVF_FLAT",
    "metric_type": "IP",  # Inner product
    "params": {"nlist": 1024}
}
collection.create_index("embedding", index_params)
```

### Reranking Configuration

Adjust reranking parameters for your use case:

```yaml
reranking:
  enabled: true
  top_n: 10          # Retrieve 10 candidates
  rerank_top_k: 3    # Rerank and return top 3
  model: nvidia/nv-rerankqa-mistral-4b-v3
```

## Indexing Your Documents

### Document Preparation

1. **Clean Text**: Remove HTML, special characters
2. **Chunk Documents**: Split into 512-1024 token chunks with overlap
3. **Add Metadata**: Include source, timestamp, category

Example chunking:

```python
def chunk_document(text, chunk_size=1000, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
```

### Embedding and Indexing

```python
import requests

# Embed documents
def embed_text(text):
    response = requests.post(
        "http://localhost:8080/embed",
        json={"text": text}
    )
    return response.json()["embedding"]

# Index in Milvus
embeddings = [embed_text(chunk) for chunk in chunks]
collection.insert([embeddings, chunks, metadatas])
```

## Querying with RAG

### Basic Query Flow

1. Embed the user query
2. Search vector database for similar documents
3. Rerank results (optional but recommended)
4. Provide context to LLM

Example:

```python
def rag_query(question, top_k=3):
    # 1. Embed query
    query_embedding = embed_text(question)

    # 2. Vector search
    search_results = collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"nprobe": 10}},
        limit=10
    )

    # 3. Rerank
    reranked = requests.post(
        "http://localhost:8081/rerank",
        json={
            "query": question,
            "documents": [r.text for r in search_results[0]]
        }
    )

    # 4. Return top_k after reranking
    return reranked.json()["results"][:top_k]
```

## Performance Tuning

### Embedding Service

- **Batch Size**: Increase for higher throughput (e.g., 32-64)
- **Quantization**: Enable FP16 for 2x speedup with minimal quality loss
- **Model Selection**: Use smaller models for latency-critical applications

### Vector Database

- **Index Type**:
  - IVF_FLAT: Good balance
  - IVF_PQ: Memory-efficient for large collections
  - HNSW: Fastest search, more memory

- **Shard Configuration**: For >10M vectors, use 4+ shards

### Reranking

- **When to Use**: Always for user-facing applications
- **When to Skip**: High-throughput, latency-sensitive systems

## Security Considerations

NeMo Retriever is approved for production use under these conditions:

1. **Data Privacy**: Documents never leave your infrastructure
2. **Access Control**: Implement authentication on all microservice endpoints
3. **Network Security**: Deploy in VPC with security groups
4. **Audit Logging**: Log all queries for compliance

## Monitoring and Maintenance

### Key Metrics to Track

- Embedding latency (target: <50ms per document)
- Search latency (target: <100ms)
- Reranking latency (target: <200ms)
- GPU utilization (optimal: 60-80%)

### Maintenance Tasks

- **Weekly**: Review slow queries, optimize indexes
- **Monthly**: Retrain reranker on user feedback
- **Quarterly**: Evaluate new embedding models

## Troubleshooting

### High Latency

**Symptom**: Queries taking >500ms

**Solutions**:
1. Check GPU utilization - may need more GPUs
2. Optimize vector index (rebuild with better parameters)
3. Enable caching for common queries

### Low Relevance

**Symptom**: Retrieved documents not relevant

**Solutions**:
1. Enable reranking if not already active
2. Adjust chunk size (try 500-1500 tokens)
3. Improve document metadata for filtering

### Out of Memory

**Symptom**: Embedding service crashes

**Solutions**:
1. Reduce batch size
2. Use model quantization (FP16 or INT8)
3. Upgrade to GPU with more VRAM

## Cost Optimization

### Infrastructure Costs

- **Embeddings**: Can run on T4 GPUs (~$0.35/hr)
- **Reranking**: Needs A10+ (~$1.50/hr)
- **Vector DB**: Runs on CPU ($0.10-0.50/hr depending on size)

### Cost-Saving Strategies

1. **Model Caching**: Cache embeddings for common documents
2. **Query Caching**: Cache results for repeated queries (60-second TTL)
3. **Batch Processing**: Embed documents in large batches during off-hours
4. **Right-Sizing**: Start with T4, upgrade only if needed

## Next Steps

After successful setup:

1. Index your production documents
2. Integrate with your LLM application
3. Set up monitoring dashboards
4. Collect user feedback for reranker training

For advanced features like hybrid search or multi-modal retrieval, see the [NeMo Retriever Advanced Guide](https://docs.nvidia.com/nemo-retriever).

## Support Resources

- **Documentation**: https://docs.nvidia.com/nemo-retriever
- **GitHub**: https://github.com/NVIDIA/NeMo-Retriever
- **Forums**: https://forums.developer.nvidia.com/c/nemo
- **Support Portal**: For enterprise customers with support contracts
