# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive data lakehouse bootcamp project that demonstrates a modern data architecture using:
- **PostgreSQL** as OLTP database with WAL-level logical replication enabled
- **Kafka + Debezium** for Change Data Capture (CDC) streaming
- **Apache Spark + Delta Lake** for distributed data processing and ACID transactions
- **MinIO** as S3-compatible object storage for data lake layers
- **Apache Airflow 3.0** for orchestration and batch processing
- **Jupyter Lab** for interactive data analysis and development
- **Docker Compose** for complete local development environment

## Architecture

### Core Components

1. **OLTP Database** (`postgres-oltp:5432`):
   - Main transactional database with e-commerce schema
   - Tables: customers, addresses, products, inventory, orders, order_items, payments, shipments
   - WAL configured for logical replication to support Debezium CDC

2. **Streaming Layer**:
   - **Kafka** (`kafka:9092`) - Message broker
   - **Zookeeper** (`zookeeper:2181`) - Kafka coordination
   - **Debezium Connect** (`connect:8083`) - CDC connector for PostgreSQL
   - **Debezium UI** (`localhost:8080`) - Connector management interface
   - **Kafka UI** (`localhost:8081`) - Kafka topic and message inspection

3. **Data Lake Storage** (MinIO S3-Compatible):
   - **MinIO** (`localhost:9000`) - Object storage API
   - **MinIO Console** (`localhost:9001`) - Web-based management UI
   - **Buckets**: bronze, silver, gold, warehouse
   - **Credentials**: minioadmin/minioadmin123

4. **Distributed Processing** (Apache Spark):
   - **Spark Master** (`localhost:8082`) - Cluster coordination and Web UI
   - **Spark Worker** - Processing nodes (scalable)
   - **Spark History Server** (`localhost:18080`) - Job monitoring and history
   - **Delta Lake** - ACID transactions and versioning for data lake

5. **Interactive Development**:
   - **Jupyter Lab** (`localhost:8888`) - Interactive notebooks with PySpark
   - **Tutorial Notebooks** - Step-by-step data lakehouse learning

6. **Orchestration** (Apache Airflow 3.0):
   - **API Server** (`localhost:8088`) - Web UI and API
   - **Scheduler** - Task scheduling and execution
   - **DAG Processor** - DAG parsing and validation
   - **Triggerer** - Handles deferred tasks
   - **Metadata DB** (`postgres-airflow`) - Separate PostgreSQL instance

### Data Generation Scripts

Located in `airflow/dags/script/`:
- `db_sqlalchemy.py` - Database models and connection utilities
- `data_generators.py` - Faker-based data generators for customers, products, orders
- `generate_sample.py` - Sample data creation scripts
- `stream_orders.py` - Continuous order generation for streaming

## Common Commands

### Environment Management
```bash
# Start all services (builds images, pulls updates)
./start.sh

# Stop all services and cleanup
./stop.sh

# Manual Docker Compose operations
docker compose up -d --build
docker compose down --remove-orphans
```

### Service Access
- **Airflow Web UI**: http://localhost:8088 (airflow/airflow)
- **Jupyter Lab**: http://localhost:8888 (no password required)
- **Spark Master UI**: http://localhost:8082
- **Spark History Server**: http://localhost:18080
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin123)
- **MinIO API**: http://localhost:9000
- **Debezium UI**: http://localhost:8080
- **Kafka UI**: http://localhost:8081
- **Kafka Connect API**: http://localhost:8083

### Development Workflow

1. **Python Environment**: Uses `uv` for dependency management
   ```bash
   # Install dependencies locally (for IDE support)
   uv sync
   ```

2. **Database Initialization**:
   - Run `init_and_seed_oltp` DAG in Airflow to create schema and seed sample data
   - Schema automatically created from `postgresql/init/init.sql`

3. **Data Generation**:
   - Use `stream_new_orders` DAG for continuous order generation
   - Use `export_orders_csv` DAG for batch data exports

### Airflow DAGs

**Initial Setup:**
- `init_and_seed_oltp` - One-time database setup and sample data generation
- `stream_new_orders` - Continuous order generation for testing CDC

**Data Pipeline:**
- `kafka_to_bronze` - Batch ingestion from Kafka CDC events to Bronze layer (every 10 minutes)
- `bronze_to_silver` - Data transformation and cleaning to Silver layer (every 15 minutes)
- `data_quality_checks` - Comprehensive data quality monitoring (every 30 minutes)

**Legacy/Utilities:**
- `export_orders_csv` - Batch export of orders to CSV format

## Development Notes

### Database Configuration
- OLTP database configured with `wal_level=logical` for Debezium CDC
- Connection details for scripts: `postgres_oltp` connection ID in Airflow
- Database models defined in SQLAlchemy 1.4 style in `db_sqlalchemy.py`

### Debezium Setup
- PostgreSQL connector uses `pgoutput` plugin (set in connector configuration)
- Connectors configured via Debezium UI or REST API at port 8083

### Python Dependencies
- **Core**: `faker`, `psycopg2-binary`, `sqlalchemy`
- **Spark & Data Processing**: `pyspark`, `delta-spark`, `pandas`, `pyarrow`
- **Object Storage**: `minio`, `kafka-python`
- **Data Quality**: `great-expectations`
- **Interactive**: `jupyterlab`, `matplotlib`, `seaborn`
- **Airflow**: Uses custom Dockerfile extending `apache/airflow:3.0.0-python3.12`
- **Providers**: `apache-airflow-providers-postgres`

## Data Lakehouse Architecture

### Data Layers
- **Bronze Layer** (`s3a://bronze/`): Raw CDC data from Kafka, partitioned by ingestion time (year/month/day/hour)
- **Silver Layer** (`s3a://silver/`): Cleaned, validated, deduplicated data in Delta format with quality flags
- **Gold Layer** (`s3a://gold/`): Business-ready aggregated data and metrics (future implementation)

### Tutorial Structure
Interactive Jupyter notebooks available at `http://localhost:8888`:
1. **01_Setup_and_Architecture.ipynb** - Environment setup and architecture overview
2. **02_Bronze_Layer_Ingestion.ipynb** - Understanding raw data ingestion and CDC events
3. **03_Silver_Layer_Transformations.ipynb** - Data cleaning, validation, and Delta Lake features

### File Structure
```
├── spark/
│   ├── apps/           # Spark application code
│   ├── notebooks/      # Jupyter tutorial notebooks
│   └── Dockerfile      # Custom Spark image with Delta Lake
├── airflow/
│   ├── dags/           # Airflow DAG definitions
│   │   ├── kafka_to_bronze.py      # CDC to Bronze ingestion
│   │   ├── bronze_to_silver.py     # Data transformation
│   │   ├── data_quality_checks.py  # Quality monitoring
│   │   └── script/     # Python data generation modules
│   ├── config/         # Airflow configuration
│   ├── logs/           # Airflow logs
│   └── Dockerfile      # Custom Airflow image
├── postgresql/
│   └── init/           # Database initialization scripts
├── tutorials/          # Additional tutorial materials
└── docker-compose.yaml # Full service orchestration
```

## Common Development Tasks

### Starting the Environment
1. **Full Environment**: `./start.sh` - Builds and starts all services
2. **Selective Start**: `docker compose up -d [service-names]`
3. **Rebuild**: `docker compose up -d --build [service-names]`

### Data Pipeline Workflow
1. **Initialize**: Run `init_and_seed_oltp` DAG in Airflow
2. **Generate Data**: Run `stream_new_orders` DAG to create test data
3. **Setup CDC**: Configure Debezium connector via UI at http://localhost:8080
4. **Monitor Pipeline**: Check Bronze→Silver→Quality pipeline execution
5. **Explore Data**: Use Jupyter notebooks for interactive analysis

### Troubleshooting
- **Check Service Health**: Use `docker compose ps` and individual service logs
- **Spark Issues**: Check Spark Master UI at http://localhost:8082
- **Data Issues**: Review data quality checks in Airflow
- **Storage Issues**: Check MinIO console at http://localhost:9001