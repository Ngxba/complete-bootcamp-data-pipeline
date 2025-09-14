from __future__ import annotations

import os
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
SPARK_APP_PATH = "/opt/airflow/dags/spark_jobs/kafka_to_bronze_hudi.py"


# DAG Definition
with DAG(
    dag_id="kafka_to_bronze_hudi",
    default_args=DEFAULT_ARGS,
    description="Ingest CDC data from Kafka to Bronze layer using Spark and Hudi format",
    schedule=timedelta(minutes=10),  # Run every 10 minutes
    start_date=datetime(2024, 9, 14),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "bronze", "kafka", "spark", "hudi", "ingestion"],
) as dag:

    # Common Spark configuration
    spark_packages = [
        "org.apache.hudi:hudi-spark3.3-bundle_2.12:0.13.0",
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0",
        "org.apache.hadoop:hadoop-aws:3.3.2"
    ]

    spark_conf = {
        "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
        "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.hudi.catalog.HoodieCatalog",
        "spark.sql.extensions": "org.apache.spark.sql.hudi.HoodieSparkSessionExtension",
        "spark.hadoop.fs.s3a.endpoint": "http://minio:9000",
        "spark.hadoop.fs.s3a.access.key": "minioadmin",
        "spark.hadoop.fs.s3a.secret.key": "minioadmin123",
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
    }

    # Task to ingest orders using Spark
    ingest_orders_spark = SparkSubmitOperator(
        task_id="ingest_orders_to_bronze_hudi",
        application=SPARK_APP_PATH,
        application_args=["orders", "1000"],
        packages=",".join(spark_packages),
        conf=spark_conf,
        conn_id="spark_default",
        verbose=True,
        doc_md="""
        ### Ingest Orders to Bronze Layer with Hudi

        This task uses Spark to consume CDC messages from Kafka for the orders table
        and saves them as Hudi tables in the Bronze layer (MinIO) for ACID transactions
        and incremental data processing.

        **Features:**
        - Batch processing with configurable record limits
        - Hudi COPY_ON_WRITE table type for fast queries
        - Automatic partitioning by source table
        - Upsert operations based on record ID and timestamp
        """
    )

    # Task to ingest customers using Spark
    ingest_customers_spark = SparkSubmitOperator(
        task_id="ingest_customers_to_bronze_hudi",
        application=SPARK_APP_PATH,
        application_args=["customers", "500"],
        packages=",".join(spark_packages),
        conf=spark_conf,
        conn_id="spark_default",
        verbose=True,
        doc_md="Ingest customer CDC data from Kafka to Bronze Hudi tables using Spark."
    )

    # Task to ingest products using Spark
    ingest_products_spark = SparkSubmitOperator(
        task_id="ingest_products_to_bronze_hudi",
        application=SPARK_APP_PATH,
        application_args=["products", "500"],
        packages=",".join(spark_packages),
        conf=spark_conf,
        conn_id="spark_default",
        verbose=True,
        doc_md="Ingest product CDC data from Kafka to Bronze Hudi tables using Spark."
    )

    # Task to ingest order_items using Spark
    ingest_order_items_spark = SparkSubmitOperator(
        task_id="ingest_order_items_to_bronze_hudi",
        application=SPARK_APP_PATH,
        application_args=["order_items", "1500"],
        packages=",".join(spark_packages),
        conf=spark_conf,
        conn_id="spark_default",
        verbose=True,
        doc_md="Ingest order_items CDC data from Kafka to Bronze Hudi tables using Spark."
    )

    # Task to ingest payments using Spark
    ingest_payments_spark = SparkSubmitOperator(
        task_id="ingest_payments_to_bronze_hudi",
        application=SPARK_APP_PATH,
        application_args=["payments", "800"],
        packages=",".join(spark_packages),
        conf=spark_conf,
        conn_id="spark_default",
        verbose=True,
        doc_md="Ingest payments CDC data from Kafka to Bronze Hudi tables using Spark."
    )

    # All ingestion tasks can run in parallel
    [
        ingest_orders_spark,
        ingest_customers_spark,
        ingest_products_spark,
        ingest_order_items_spark,
        ingest_payments_spark
    ]