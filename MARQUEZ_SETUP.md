# Marquez Setup Guide

## Quick Start

### 1. Start Marquez

```bash
docker-compose -f docker-compose-marquez.yml up -d
```

This starts:
- **PostgreSQL** (database backend)
- **Marquez API** on http://localhost:5001
- **Marquez Web UI** on http://localhost:3001

### 2. Verify Marquez is Running

```bash
curl http://localhost:5001/api/v1/namespaces
```

You should see namespaces including `default`, `chromadb`, `demo-data-quality`, and `filesystem`.

### 3. Run the Demo

```bash
# Normal mode
python3 demo_data_quality.py --mode both

# Verbose mode - see lineage details
python3 demo_data_quality.py --mode both --verbose

# Very verbose mode - see full JSON
python3 demo_data_quality.py --mode both --vv
```

No more 403 errors! The data flows directly to Marquez.

### 4. View Lineage in Marquez UI

Open your browser to: **http://localhost:3001**

You'll see:
- **Jobs**: `demo_stale_ingestion` (ingestion job)
- **Datasets**:
  - `chromadb/stale_docs.chunks` (output with data quality facets)
  - `filesystem/documents` (input source files)
- **Lineage Graph**: Visual flow from source → ingestion → vector DB

## Exploring the Data

### Check Namespaces
```bash
curl http://localhost:5001/api/v1/namespaces | python3 -m json.tool
```

### Check Datasets
```bash
# List all datasets in chromadb namespace
curl http://localhost:5001/api/v1/namespaces/chromadb/datasets | python3 -m json.tool

# Get specific dataset with facets
curl http://localhost:5001/api/v1/namespaces/chromadb/datasets/stale_docs.chunks | python3 -m json.tool
```

### Check Jobs
```bash
# List jobs in demo-data-quality namespace
curl http://localhost:5001/api/v1/namespaces/demo-data-quality/jobs | python3 -m json.tool
```

### View Data Quality Facets
```bash
curl http://localhost:5001/api/v1/namespaces/chromadb/datasets/stale_docs.chunks \
  | python3 -m json.tool \
  | grep -A 20 dataQualityMetrics
```

This shows the freshness metrics (max: 45.0 days) that trigger the Trust Plane violation.

## What Gets Tracked

### During Ingestion (`demo_stale_ingestion` job)

1. **START Event**
   - Input: `filesystem/documents`
   - Metadata: file count, total size

2. **COMPLETE Event**
   - Output: `chromadb/stale_docs.chunks`
   - Data Quality Facet:
     ```json
     {
       "dataQualityMetrics": {
         "_producer": "genaiops-agent/1.0",
         "rowCount": 1,
         "columnMetrics": {
           "freshness": {
             "min": 45.0,
             "max": 45.0,
             "quantiles": {"0.5": 45.0}
           }
         }
       }
     }
     ```

### Lineage Graph

```
┌──────────────────┐
│ filesystem       │
│ /documents       │
│ (input)          │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Job:             │
│ demo_stale_      │
│ ingestion        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ chromadb         │
│ stale_docs.chunks│
│ (output)         │
│ + quality facets │
└──────────────────┘
```

## Stopping Marquez

```bash
# Stop containers
docker-compose -f docker-compose-marquez.yml down

# Stop and remove all data (clean slate)
docker-compose -f docker-compose-marquez.yml down -v
```

## Troubleshooting

### Port Conflicts

If you get port conflicts:

**Port 5432 (PostgreSQL)** - Another database is running:
```bash
# Change in docker-compose-marquez.yml:
ports:
  - "5433:5432"  # Use 5433 instead
```

**Port 5001 (Marquez API)** - Change in both:
- `docker-compose-marquez.yml`: `"5002:5000"`
- `.env`: `OPENLINEAGE_URL=http://localhost:5002`

**Port 3001 (Marquez UI)** - Change in docker-compose:
```bash
ports:
  - "3002:3000"  # Use 3002 instead
```

### Container Won't Start

Check logs:
```bash
docker logs marquez
docker logs marquez-postgres
```

### Reset Everything

```bash
# Stop and remove all data
docker-compose -f docker-compose-marquez.yml down -v

# Start fresh
docker-compose -f docker-compose-marquez.yml up -d

# Wait 15 seconds for initialization
sleep 15

# Verify
curl http://localhost:5001/api/v1/namespaces
```

## Integration with Demo

The demo automatically:
1. ✅ Connects to Marquez at `http://localhost:5001`
2. ✅ Emits OpenLineage events during ingestion
3. ✅ Stores data quality metrics in dataset facets
4. ✅ Trust Plane queries metadata from Marquez
5. ✅ Falls back to local cache if Marquez unavailable

### Viewing in VV Mode

Run with `--vv` to see the complete OTel → OpenLineage correlation:

```bash
python3 demo_data_quality.py --mode reactive --vv
```

Look for:
```
Step 3: Query Dataset Facets:
  GET /api/v1/namespaces/chromadb/datasets/stale_docs.chunks
  Returns dataQualityMetrics facet:
  {
    'columnMetrics': {
      'freshness': {
        'max': 45.0,  ← VIOLATION!
      }
    }
  }
```

## Benefits of Using Marquez

### Without Marquez (Console only)
- ✅ Lineage events logged to console
- ✅ Metadata cached locally
- ✅ Trust Plane works with cache
- ❌ No persistent storage
- ❌ No visualization
- ❌ No cross-process queries

### With Marquez (Full backend)
- ✅ Lineage events logged to console
- ✅ Metadata cached locally
- ✅ Trust Plane works with cache
- ✅ **Persistent storage in PostgreSQL**
- ✅ **Web UI visualization**
- ✅ **API queries across processes**
- ✅ **Complete lineage graph**
- ✅ **Historical tracking**

## Web UI Features

Visit http://localhost:3001 to see:

1. **Jobs** - List of ingestion jobs with run history
2. **Datasets** - Input/output datasets with facets
3. **Lineage Graph** - Visual graph of data flow
4. **Run Details** - Individual run events with timestamps
5. **Facets** - Data quality metrics, schema, documentation

### Finding Your Data

1. Go to http://localhost:3001
2. Click "Datasets" in the left menu
3. Find `chromadb/stale_docs.chunks`
4. Click to see:
   - Dataset details
   - Current facets (including dataQualityMetrics)
   - Lineage graph
   - Producing jobs
   - Run history

## API Examples

### Get Dataset with Facets
```bash
curl -s http://localhost:5001/api/v1/namespaces/chromadb/datasets/stale_docs.chunks \
  | python3 -m json.tool
```

### Get Job Runs
```bash
curl -s http://localhost:5001/api/v1/namespaces/demo-data-quality/jobs/demo_stale_ingestion/runs \
  | python3 -m json.tool
```

### Query Lineage Graph
```bash
# Replace <run-id> with actual run ID from demo output
curl -s "http://localhost:5001/api/v1/lineage?nodeId=run:<run-id>" \
  | python3 -m json.tool
```

## Next Steps

1. ✅ Start Marquez: `docker-compose -f docker-compose-marquez.yml up -d`
2. ✅ Run demo: `python3 demo_data_quality.py --mode both --vv`
3. ✅ View UI: http://localhost:3001
4. ✅ Explore API: http://localhost:5001/api/v1/namespaces
5. ✅ Check lineage graph in web UI
6. ✅ Query specific datasets and jobs
