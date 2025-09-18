from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator


DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
}

# Spark application path
SPARK_APP_PATH = "/opt/airflow/dags/spark_jobs/kafka_to_bronze_orders.py"


# DAG Definition
with DAG(
    dag_id="kafka_to_bronze_orders",
    default_args=DEFAULT_ARGS,
    description="Ingest CDC data from Kafka debezium.public.orders topic to Bronze layer using Spark and Hudi format",
    schedule=timedelta(minutes=10),  # Run every 10 minutes
    start_date=datetime(2024, 9, 17),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "bronze", "kafka", "spark", "hudi", "orders", "cdc"],
) as dag:

    # Spark packages required for Hudi, Kafka, and S3
    spark_packages = [
        "org.apache.hudi:hudi-spark3.5-bundle_2.12:0.14.1",
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
        "org.apache.hadoop:hadoop-aws:3.3.4",
        "org.apache.kafka:kafka-clients:3.5.1"
    ]

    # Spark configuration for Hudi and MinIO
    spark_conf = {
        "spark.master": "spark://spark-master:7077",
        "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
        "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.hudi.catalog.HoodieCatalog",
        "spark.sql.extensions": "org.apache.spark.sql.hudi.HoodieSparkSessionExtension",
        "spark.hadoop.fs.s3a.endpoint": "http://minio:9000",
        "spark.hadoop.fs.s3a.access.key": "minioadmin",
        "spark.hadoop.fs.s3a.secret.key": "minioadmin123",
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
        "spark.sql.adaptive.enabled": "true",
        "spark.sql.adaptive.coalescePartitions.enabled": "true",
    }

    # Task to ingest orders from Kafka to Bronze using Spark and Hudi
    ingest_orders_to_bronze = SparkSubmitOperator(
        task_id="ingest_orders_from_kafka_to_bronze",
        application=SPARK_APP_PATH,
        application_args=["debezium.public.orders", "1000"],
        packages=",".join(spark_packages),
        conf=spark_conf,
        deploy_mode="client",
        verbose=True,
        driver_memory="1g",
        doc_md="""
        ### Ingest Orders from Kafka to Bronze Layer with Hudi

        This task uses Spark to consume CDC messages from the `debezium.public.orders` Kafka topic
        and saves them as Hudi tables in the Bronze layer (MinIO) for ACID transactions
        and incremental data processing.

        **Features:**
        - Batch processing with configurable record limits (1000 records per run)
        - Hudi COPY_ON_WRITE table type for fast queries
        - Automatic partitioning by year/month/day based on CDC timestamp
        - Upsert operations based on order_id and CDC timestamp
        - Complete CDC metadata preservation including operation type, transaction info
        - Robust error handling and data validation
        - S3-compatible storage integration with MinIO

        **Data Flow:**
        1. Read CDC messages from Kafka topic `debezium.public.orders`
        2. Parse Debezium JSON envelope structure
        3. Extract order data from before/after payloads
        4. Add processing metadata and partition fields
        5. Write to Bronze layer at `s3a://bronze/orders` in Hudi format

        **Monitoring:**
        - Check Spark UI for job progress and performance metrics
        - Review task logs for data quality issues and processing statistics
        - Monitor MinIO console for Bronze layer data growth
        """
    )