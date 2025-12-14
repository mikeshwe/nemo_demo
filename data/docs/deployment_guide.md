# NVIDIA GenAIOps Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying NVIDIA AI services in production environments. Whether you're deploying inference microservices (NIMs) or building custom GenAI applications, this guide covers the essential setup and configuration steps.

## Prerequisites

Before deploying NVIDIA AI services, ensure you have:

- **GPU Infrastructure**: NVIDIA GPUs (A100, H100, or newer recommended)
- **CUDA Toolkit**: Version 12.0 or higher
- **Docker**: Version 24.0+ with NVIDIA Container Toolkit
- **Network**: Outbound internet access for container registry
- **Authentication**: NVIDIA NGC API key

## Deployment Architecture

### Recommended Setup

For production deployments, we recommend a hybrid architecture:

1. **Orchestration Layer**: Run your application logic and LangGraph workflows locally or on CPU nodes
2. **Inference Layer**: Deploy NVIDIA NIMs on GPU-accelerated nodes
3. **Storage Layer**: Use persistent storage for model caches and conversation history

This hybrid approach optimizes cost by using expensive GPU resources only for inference, while orchestration runs on cheaper compute.

## Step-by-Step Deployment

### 1. Set Up NVIDIA Container Toolkit

```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Authenticate with NGC

```bash
# Log in to NGC container registry
docker login nvcr.io
Username: $oauthtoken
Password: <your-ngc-api-key>
```

### 3. Pull and Run NIM Containers

```bash
# Example: Deploy Nemotron NIM
docker run -d \
  --gpus all \
  --name nemotron-nim \
  -p 8000:8000 \
  -e NGC_API_KEY=<your-key> \
  nvcr.io/nvidia/nemotron:latest
```

### 4. Configure Load Balancing

For production traffic, deploy multiple NIM instances behind a load balancer:

- Use NGINX or HAProxy for load balancing
- Implement health checks on `/health` endpoint
- Configure connection pooling for efficiency

### 5. Monitor and Scale

Monitor GPU utilization with:

```bash
# Real-time GPU monitoring
nvidia-smi --loop=1

# Or use Prometheus + Grafana for production
```

Scale horizontally by adding more GPU nodes when utilization exceeds 70%.

## Security Best Practices

1. **Network Isolation**: Deploy NIMs in private subnets
2. **API Authentication**: Always use API keys or OAuth tokens
3. **Model Access Control**: Restrict which teams can deploy which models
4. **Audit Logging**: Enable request/response logging for compliance

## Performance Optimization

### GPU Selection Guidelines

- **Small Models (7B-13B)**: A10 or A30 GPUs are cost-effective
- **Medium Models (70B)**: A100 80GB recommended
- **Large Models (340B+)**: H100 or multi-GPU setup required

### Batching Configuration

Enable dynamic batching in NIM configuration for higher throughput:

```yaml
batching:
  enabled: true
  max_batch_size: 32
  timeout_ms: 50
```

## Troubleshooting

### Common Issues

**Issue: Out of Memory (OOM)**
- Solution: Reduce batch size or use model quantization

**Issue: Slow Cold Start**
- Solution: Keep model loaded in memory between requests

**Issue: Network Timeout**
- Solution: Increase client timeout to 60+ seconds for large models

## Cost Optimization

To minimize GPU costs:

1. Use smaller models when possible (70B vs 340B)
2. Implement request queuing to batch effectively
3. Auto-scale GPU nodes during low-traffic periods
4. Cache common responses

Estimated costs:
- A100: ~$2-4/hour
- H100: ~$6-10/hour
- Multi-GPU setups: Scale accordingly

## Next Steps

After successful deployment:
1. Set up monitoring dashboards
2. Configure auto-scaling policies
3. Implement A/B testing for model versions
4. Review security posture quarterly

For additional help, contact your NVIDIA solutions architect or visit the [NVIDIA Developer Forums](https://forums.developer.nvidia.com).
