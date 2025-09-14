# Data Lakehouse Tutorial Series

This comprehensive tutorial series teaches you how to build a modern data lakehouse using Apache Spark, Delta Lake, Kafka, and other cloud-native technologies.

## 🎯 Learning Objectives

By completing this tutorial series, you will learn:

- **Modern Data Architecture**: Build a complete lakehouse with Bronze, Silver, and Gold layers
- **Real-time Data Processing**: Implement Change Data Capture (CDC) with Debezium and Kafka
- **Distributed Computing**: Use Apache Spark for large-scale data transformation
- **Data Quality**: Implement comprehensive validation and monitoring
- **ACID Transactions**: Leverage Delta Lake for reliable data operations
- **Container Orchestration**: Deploy the entire stack using Docker Compose

## 📚 Tutorial Structure

### Interactive Notebooks
Access these at http://localhost:8888 after starting the environment:

1. **[01_Setup_and_Architecture.ipynb](../spark/notebooks/01_Setup_and_Architecture.ipynb)**
   - Environment setup and health checks
   - Architecture overview and component interaction
   - Service connectivity testing

2. **[02_Bronze_Layer_Ingestion.ipynb](../spark/notebooks/02_Bronze_Layer_Ingestion.ipynb)**
   - Understanding Change Data Capture (CDC)
   - Kafka message structure and Debezium format
   - Bronze layer partitioning and storage patterns
   - Performance characteristics and query optimization

3. **[03_Silver_Layer_Transformations.ipynb](../spark/notebooks/03_Silver_Layer_Transformations.ipynb)**
   - CDC resolution and deduplication
   - Data cleaning and validation rules
   - Delta Lake ACID transactions
   - Data quality monitoring and alerting

## 🚀 Getting Started

### Prerequisites
- Docker Desktop with at least 8GB RAM allocated
- Basic understanding of SQL and Python
- Familiarity with data concepts (ETL, data warehousing)

### Quick Start
1. **Start the Environment**:
   ```bash
   ./start.sh
   ```

2. **Initialize Sample Data**:
   - Go to Airflow UI: http://localhost:8088
   - Run the `init_and_seed_oltp` DAG
   - Run the `stream_new_orders` DAG

3. **Open Jupyter Lab**:
   - Navigate to: http://localhost:8888
   - Start with notebook `01_Setup_and_Architecture.ipynb`

4. **Explore the Architecture**:
   - **Spark UI**: http://localhost:8082
   - **MinIO Console**: http://localhost:9001
   - **Kafka UI**: http://localhost:8081
   - **Debezium UI**: http://localhost:8080

## 🏗️ Architecture Overview

```
OLTP Database (PostgreSQL)
       ↓ CDC (Debezium)
   Kafka Streaming
       ↓ Batch Ingestion (Airflow)
   Bronze Layer (Raw Parquet)
       ↓ Transformation (Spark)
   Silver Layer (Delta Tables)
       ↓ Aggregation
   Gold Layer (Business Views)
```

### Technology Stack
- **Storage**: MinIO (S3-compatible object storage)
- **Processing**: Apache Spark with Delta Lake
- **Streaming**: Apache Kafka + Debezium CDC
- **Orchestration**: Apache Airflow
- **Database**: PostgreSQL with logical replication
- **Development**: Jupyter Lab with PySpark
- **Containerization**: Docker Compose

## 📊 Data Flow

1. **Source System**: E-commerce database with customers, orders, products
2. **Change Capture**: Debezium captures all database changes
3. **Message Queue**: Kafka streams change events
4. **Bronze Layer**: Raw ingestion preserving full audit trail
5. **Silver Layer**: Cleaned, validated, current-state data
6. **Gold Layer**: Business metrics and aggregated views

## 🛠️ Development Workflow

### Daily Development
1. Start environment: `./start.sh`
2. Check service health in Jupyter notebook
3. Monitor data pipeline in Airflow UI
4. Develop and test transformations
5. Review data quality metrics

### Data Pipeline Management
- **Monitor**: Airflow DAGs run automatically every 10-30 minutes
- **Debug**: Check individual task logs in Airflow
- **Explore**: Use Jupyter notebooks for ad-hoc analysis
- **Quality**: Review data quality checks and alerts

## 🎓 Advanced Topics

Once you complete the basic tutorials, explore:

- **Performance Tuning**: Optimize Spark jobs and Delta operations
- **Schema Evolution**: Handle changing data schemas gracefully
- **Data Governance**: Implement data lineage and cataloging
- **Real-time Analytics**: Build streaming aggregations
- **Machine Learning**: Prepare data for ML workloads
- **Cost Optimization**: Implement data lifecycle policies

## 🐛 Troubleshooting

### Common Issues

**Services won't start**:
- Check Docker resource allocation (8GB+ RAM recommended)
- Run `docker compose down && docker compose up -d --build`

**No data in notebooks**:
- Ensure you've run `init_and_seed_oltp` DAG first
- Check that `stream_new_orders` DAG has generated data
- Verify Debezium connector is running

**Spark jobs fail**:
- Check Spark Master UI for worker status
- Review individual task logs in Airflow
- Verify MinIO connectivity

**Performance issues**:
- Increase Docker resource limits
- Use partition pruning in queries
- Monitor resource usage in service UIs

### Getting Help
- Check service logs: `docker compose logs [service-name]`
- Review Spark UI for job details: http://localhost:8082
- Monitor data quality in Airflow: http://localhost:8088
- Explore object storage in MinIO: http://localhost:9001

## 📝 Best Practices

### Data Engineering
- Always include data quality validation
- Use proper partitioning strategies
- Implement comprehensive monitoring
- Document data transformations
- Version control all code

### Performance
- Leverage partition pruning for queries
- Use appropriate file sizes (128MB-1GB)
- Monitor resource utilization
- Cache frequently accessed datasets
- Optimize Spark configuration for workload

### Operations
- Monitor all pipeline components
- Implement proper alerting
- Use version control for configurations
- Document troubleshooting procedures
- Regular backup and recovery testing

## 🔗 Additional Resources

- [Apache Spark Documentation](https://spark.apache.org/docs/latest/)
- [Delta Lake Documentation](https://docs.delta.io/)
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Debezium Documentation](https://debezium.io/documentation/)
- [Modern Data Stack Best Practices](https://www.moderndatastack.xyz/)

---

**Happy Learning!** 🎉

Start your data lakehouse journey with the first notebook and build your expertise step by step.