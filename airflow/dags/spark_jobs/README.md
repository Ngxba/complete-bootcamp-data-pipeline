# Spark CDC Processing Framework

A comprehensive, production-ready framework for processing Change Data Capture (CDC) events from Kafka using Apache Spark, with support for both batch and streaming modes.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Framework Components](#framework-components)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🎯 Overview

The Spark CDC Processing Framework provides a robust, configurable solution for processing Debezium CDC events from Kafka topics and writing them to data lake storage (Bronze layer) using Apache Hudi format. The framework supports multiple CDC data extraction modes, configurable primary keys, and both batch and streaming processing patterns.

### Key Benefits

- **🔧 Highly Configurable**: YAML-based configuration with table-specific overrides
- **🏭 Factory Pattern**: Clean, extensible architecture using factory design patterns
- **📊 Multiple CDC Modes**: Support for before, after, or combined data extraction
- **⚡ Dual Processing**: Both batch and streaming processing capabilities
- **🛡️ Production Ready**: Comprehensive error handling, validation, and monitoring
- **🔍 Auto Schema Detection**: Automatic schema inference from Debezium messages
- **📈 Performance Optimized**: Tuned for large-scale data processing

## ✨ Features

### Core Features
- **Multiple CDC Data Modes**: `DATA_BEFORE`, `DATA_AFTER`, `DATA_BEFORE_AFTER`
- **Configurable Primary Keys**: Per-table primary key configuration
- **Automatic Schema Detection**: Extracts schema from Debezium messages
- **Flexible Partitioning**: Timestamp-based or custom partitioning strategies
- **Field Transformations**: Built-in transformations for monetary fields, timestamps
- **Batch & Streaming**: Unified interface for both processing modes

### Processing Capabilities
- **Hudi Integration**: ACID transactions with upsert capabilities
- **S3/MinIO Support**: S3-compatible storage with optimized configurations
- **Data Quality Validation**: Built-in validation rules and error handling
- **Monitoring & Metrics**: Real-time processing metrics and progress tracking
- **Checkpoint Management**: Streaming checkpoint handling for fault tolerance

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Kafka Topic   │───▶│  CDC Framework   │───▶│  Bronze Layer   │
│  (Debezium)     │    │                  │    │   (Hudi/S3)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Configuration  │
                    │   (YAML-based)   │
                    └──────────────────┘
```

### Framework Structure

```
spark_framework/
├── config/                 # Configuration management
│   ├── cdc_config.py      # Main configuration class
│   └── schema_manager.py  # Schema parsing and conversion
├── factories/             # Factory pattern implementations
│   ├── spark_factory.py   # Spark session creation
│   └── processor_factory.py # Processor instantiation
├── processors/            # Processing implementations
│   ├── base_processor.py  # Abstract base class
│   ├── batch_processor.py # Batch processing logic
│   ├── stream_processor.py # Streaming processing logic
│   └── cdc_transformer.py # CDC data transformation
└── __init__.py           # Framework entry point
```

## 🚀 Installation

### Prerequisites

- Python 3.8+
- Apache Spark 3.5+
- Kafka cluster with Debezium CDC
- S3-compatible storage (MinIO/AWS S3)
- Required Python packages (see `requirements.txt`)

### Dependencies

```bash
# Core dependencies (already in requirements.txt)
pyspark>=3.5.0
kafka-python>=2.0.0
pyyaml>=6.0
minio>=7.0.0
```

### Setup

1. **Clone or copy the framework** to your Spark jobs directory:
   ```bash
   cp -r spark_framework/ /path/to/your/spark/jobs/
   ```

2. **Install dependencies** (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your environment** by updating `config/cdc_config.yaml`

## 🚀 Quick Start

### 1. Basic Batch Processing

```bash
python kafka_to_bronze_v2.py orders debezium.public.orders --max-records 1000
```

### 2. Streaming Processing

```bash
python kafka_to_bronze_v2.py orders debezium.public.orders --mode streaming
```

### 3. Test with Console Output

```bash
python kafka_to_bronze_v2.py orders debezium.public.orders --console --duration 60
```

## ⚙️ Configuration

### Configuration File Structure

The framework uses a comprehensive YAML configuration file (`config/cdc_config.yaml`):

```yaml
spark:
  mode: "batch"  # or "streaming"
  app_name_prefix: "CDC-Processor"

debezium:
  settings:
    auto_infer_schema: true
    cdc_data_mode: "DATA_AFTER"

  tables:
    orders:
      primary_key: "order_id"
      cdc_data_mode: "DATA_BEFORE_AFTER"
      data_priority: "after"
      partition_strategy: "timestamp"
```

### CDC Data Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `DATA_BEFORE` | Uses only `before` data | Audit trails, deletion tracking |
| `DATA_AFTER` | Uses only `after` data | Standard CDC processing |
| `DATA_BEFORE_AFTER` | Combines both with priority | Complete change tracking |

### Table Configuration Options

```yaml
tables:
  your_table:
    # Required
    primary_key: "id"

    # Optional
    cdc_data_mode: "DATA_AFTER"           # Override global setting
    data_priority: "after"                # For DATA_BEFORE_AFTER mode
    partition_strategy: "timestamp"       # "timestamp" or "created_at"

    # Field transformations
    field_overrides:
      created_at:
        type: "timestamp"
        scale: "microseconds"

    transformations:
      monetary_fields:                    # Convert cents to dollars
        - price_cents
        - total_cents
```

## 📚 Usage Examples

### Command Line Options

```bash
# Show all available options
python kafka_to_bronze_v2.py --help

# Basic usage
python kafka_to_bronze_v2.py TABLE_NAME TOPIC_NAME [options]
```

### Batch Processing Examples

```bash
# Process with custom configuration
python kafka_to_bronze_v2.py orders debezium.public.orders \
  --config /path/to/custom_config.yaml \
  --max-records 5000

# Show Kafka metrics
python kafka_to_bronze_v2.py orders debezium.public.orders --metrics

# Validate configuration only
python kafka_to_bronze_v2.py orders debezium.public.orders --validate-only
```

### Streaming Processing Examples

```bash
# Start streaming with custom trigger interval
python kafka_to_bronze_v2.py orders debezium.public.orders \
  --mode streaming \
  --max-records 100

# Stream to console for debugging
python kafka_to_bronze_v2.py orders debezium.public.orders \
  --mode streaming \
  --console \
  --duration 120
```

### Programmatic Usage

```python
from spark_framework import CDCConfig, ProcessorFactory

# Load configuration
config = CDCConfig("/path/to/config.yaml")

# Create processor
processor = ProcessorFactory.create_processor(
    config,
    table_name="orders",
    topic_name="debezium.public.orders"
)

# Process data
with processor:
    results = processor.process(max_records=1000)
    print(f"Processed {results['valid_records']} records")
```

## 🧩 Framework Components

### 1. Configuration Management (`config/`)

**CDCConfig**: Main configuration class
- Loads and validates YAML configuration
- Provides type-safe access to settings
- Supports environment-specific overrides

**SchemaManager**: Schema handling utilities
- Auto-detects schema from Debezium messages
- Converts Debezium types to Spark types
- Provides fallback schemas

### 2. Factory Classes (`factories/`)

**SparkFactory**: Creates configured Spark sessions
- Optimized configurations for batch/streaming
- S3/MinIO integration
- Performance tuning

**ProcessorFactory**: Creates appropriate processors
- Instantiates batch or streaming processors
- Dependency injection for configurations

### 3. Processors (`processors/`)

**BaseProcessor**: Abstract base class
- Common functionality for all processors
- Resource management with context managers
- Validation and error handling

**BatchProcessor**: Batch processing implementation
- Reads all available Kafka data
- Processes in single batch
- Supports incremental processing

**StreamProcessor**: Streaming implementation
- Continuous processing from Kafka
- Checkpoint management
- Real-time metrics

**CDCTransformer**: Data transformation logic
- Configurable CDC data extraction
- Field-level transformations
- Partitioning strategies

## 📊 Monitoring and Metrics

### Built-in Metrics

- **Processing Statistics**: Record counts, processing time
- **Data Quality Metrics**: Validation results, error rates
- **Kafka Metrics**: Topic information, partition details
- **Streaming Metrics**: Throughput, latency, backlog

### Logging

The framework provides comprehensive logging:

```bash
# Enable verbose logging
python kafka_to_bronze_v2.py orders debezium.public.orders --verbose
```

### Sample Output

```
🔄 Kafka to Bronze CDC Processor v2
============================================================
Table: orders
Topic: debezium.public.orders
Timestamp: 2024-09-20 10:30:00
============================================================
📁 Loading configuration...
🔍 Validating configuration...
📋 Configuration Summary:
   Table: orders
   Processing Mode: batch
   CDC Data Mode: DATA_BEFORE_AFTER
   Primary Key: order_id
   Partition Strategy: timestamp
   Data Priority: after
✅ Configuration validation completed
🏭 Creating batch processor...
🚀 Starting batch processing...
Reading from Kafka...
Read 150 messages from Kafka
Transforming CDC data...
Detected table fields: ['order_id', 'customer_id', 'status', ...]
📈 Processing Results:
   total_records: 150
   valid_records: 148
   invalid_records: 2
✅ Successfully completed batch processing
🎉 Processing completed successfully!
```

## 🛠️ Best Practices

### Configuration

1. **Use table-specific configurations** for different CDC requirements
2. **Set appropriate primary keys** for each table
3. **Choose CDC data modes** based on your use case:
   - Use `DATA_AFTER` for standard ETL
   - Use `DATA_BEFORE` for audit trails
   - Use `DATA_BEFORE_AFTER` for complete change tracking

### Performance

1. **Batch Processing**:
   - Use `max_records` to control memory usage
   - Configure Spark parallelism based on data volume
   - Monitor Hudi file sizes and compaction

2. **Streaming Processing**:
   - Set appropriate trigger intervals (default: 30 seconds)
   - Monitor checkpoint lag
   - Use `maxOffsetsPerTrigger` to control throughput

### Data Quality

1. **Always validate configurations** before production deployment
2. **Monitor invalid record counts** and investigate high error rates
3. **Use console mode** for initial testing and debugging
4. **Set up alerting** on processing failures

## 🐛 Troubleshooting

### Common Issues

#### 1. No Valid Records Found

**Symptoms**: `valid_records: 0` in processing results

**Solutions**:
- Check primary key configuration matches actual field names
- Verify CDC data mode is appropriate for your use case
- Use `--console` mode to inspect raw data structure

#### 2. Schema Inference Failures

**Symptoms**: "Could not determine schema" errors

**Solutions**:
- Ensure Kafka topic has messages
- Check Debezium connector configuration
- Enable fallback schema: `use_fallback_schema: true`

#### 3. Streaming Query Failures

**Symptoms**: Streaming query stops or fails to start

**Solutions**:
- Check checkpoint location permissions
- Verify S3/MinIO connectivity
- Monitor Spark driver/executor logs

#### 4. Performance Issues

**Symptoms**: Slow processing or high resource usage

**Solutions**:
- Adjust Spark parallelism settings
- Optimize Hudi configurations
- Use appropriate trigger intervals for streaming

### Debug Commands

```bash
# Validate configuration
python kafka_to_bronze_v2.py orders debezium.public.orders --validate-only

# Check Kafka connectivity and metrics
python kafka_to_bronze_v2.py orders debezium.public.orders --metrics

# Test with console output
python kafka_to_bronze_v2.py orders debezium.public.orders --console --duration 30

# Enable verbose logging
python kafka_to_bronze_v2.py orders debezium.public.orders --verbose
```

### Log Analysis

Key log messages to monitor:

- ✅ **Success indicators**: "Configuration validation completed", "Processing completed successfully"
- ⚠️ **Warnings**: "Schema compatibility issues", "Filtered out X invalid records"
- ❌ **Errors**: "Fatal error", "Processing failed"

## 🤝 Contributing

### Development Setup

1. **Fork the repository** and create a feature branch
2. **Set up development environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run tests** (when test suite is available):
   ```bash
   pytest tests/
   ```

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Document classes and methods with docstrings
- Add unit tests for new functionality

### Adding New Features

1. **Processors**: Extend `BaseProcessor` for new processing types
2. **Transformations**: Add methods to `CDCTransformer`
3. **Configurations**: Update `CDCConfig` and YAML schema
4. **Factories**: Extend factories for new component types

---

## 📝 License

This framework is part of the complete-bootcamp-data-pipeline project.

## 📞 Support

For issues, questions, or contributions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review existing issues in the project repository
3. Create a new issue with detailed information about your problem

---

**Happy CDC Processing! 🚀**