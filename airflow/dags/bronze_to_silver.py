from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import List, Optional

from airflow import DAG
from airflow.operators.python import PythonOperator
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, when, regexp_replace, trim, upper, lower,
    to_timestamp, current_timestamp, lit, row_number, desc
)
from pyspark.sql.types import *
from pyspark.sql.window import Window


DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "depends_on_past": False,
}


def get_spark_session() -> SparkSession:
    """
    Initialize Spark session with Delta Lake and MinIO configuration.
    """
    spark = SparkSession.builder \
        .appName("BronzeToSilverTransformation") \
        .config("spark.master", "spark://spark-master:7077") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()

    # Set log level to reduce verbosity
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_bronze_data(spark: SparkSession, table_name: str, date_filter: Optional[str] = None) -> DataFrame:
    """
    Read data from Bronze layer with optional date filtering.

    Args:
        spark: Spark session
        table_name: Name of the table (e.g., 'orders', 'customers')
        date_filter: Optional date filter in format 'YYYY-MM-DD'

    Returns:
        Spark DataFrame with Bronze layer data
    """
    bronze_path = f"s3a://bronze/{table_name}/"

    try:
        df = spark.read.format("parquet").load(bronze_path)

        if date_filter:
            df = df.filter(
                (col("year") == date_filter[:4]) &
                (col("month") == date_filter[5:7]) &
                (col("day") == date_filter[8:10])
            )

        print(f"Read {df.count()} records from Bronze layer for table: {table_name}")
        return df

    except Exception as e:
        print(f"Error reading Bronze data for {table_name}: {e}")
        # Return empty DataFrame with expected schema if no data exists
        return spark.createDataFrame([], StructType([]))


def clean_orders_data(df: DataFrame) -> DataFrame:
    """
    Clean and transform orders data from Bronze to Silver.

    Transformations:
    - Remove duplicate records (keep latest based on debezium timestamp)
    - Handle soft deletes (debezium_op = 'd')
    - Clean and validate monetary amounts
    - Standardize status values
    - Add computed columns
    """
    if df.count() == 0:
        return df

    # Remove duplicates - keep the latest record for each order_id
    window_spec = Window.partitionBy("order_id").orderBy(desc("debezium_ts_ms"))
    df_deduped = df.withColumn("row_num", row_number().over(window_spec)) \
                   .filter(col("row_num") == 1) \
                   .drop("row_num")

    # Filter out soft deletes (keep only current records)
    df_active = df_deduped.filter(col("debezium_op") != "d")

    # Data cleaning and transformations
    df_clean = df_active.select(
        col("order_id").cast(LongType()).alias("order_id"),
        col("customer_id").cast(LongType()).alias("customer_id"),
        col("ship_to_address_id").cast(LongType()).alias("ship_to_address_id"),

        # Clean and standardize status
        when(col("status").isNull(), "UNKNOWN")
        .when(upper(trim(col("status"))) == "PLACED", "PLACED")
        .when(upper(trim(col("status"))) == "PAID", "PAID")
        .when(upper(trim(col("status"))) == "FULFILLED", "FULFILLED")
        .when(upper(trim(col("status"))) == "CANCELED", "CANCELED")
        .otherwise("UNKNOWN").alias("status"),

        # Clean currency
        when(col("currency").isNull(), "USD")
        .otherwise(upper(trim(col("currency")))).alias("currency"),

        # Validate and clean monetary amounts (ensure non-negative)
        when(col("subtotal_cents").isNull() | (col("subtotal_cents") < 0), 0)
        .otherwise(col("subtotal_cents").cast(IntegerType())).alias("subtotal_cents"),

        when(col("shipping_cents").isNull() | (col("shipping_cents") < 0), 0)
        .otherwise(col("shipping_cents").cast(IntegerType())).alias("shipping_cents"),

        when(col("tax_cents").isNull() | (col("tax_cents") < 0), 0)
        .otherwise(col("tax_cents").cast(IntegerType())).alias("tax_cents"),

        when(col("total_cents").isNull() | (col("total_cents") < 0), 0)
        .otherwise(col("total_cents").cast(IntegerType())).alias("total_cents"),

        # Convert timestamps
        to_timestamp(col("created_at")).alias("created_at"),
        to_timestamp(col("ingestion_timestamp")).alias("ingestion_timestamp"),

        # Add computed columns
        ((col("subtotal_cents") + col("shipping_cents") + col("tax_cents")) / 100.0).alias("calculated_total_dollars"),
        (col("total_cents") / 100.0).alias("total_dollars"),

        # Add data quality flags
        when(
            (col("total_cents") != (col("subtotal_cents") + col("shipping_cents") + col("tax_cents"))) |
            col("customer_id").isNull() |
            col("ship_to_address_id").isNull(),
            "FAILED"
        ).otherwise("PASSED").alias("data_quality_status"),

        # Metadata columns
        col("debezium_op").alias("cdc_operation"),
        col("debezium_ts_ms").alias("cdc_timestamp_ms"),
        current_timestamp().alias("silver_processed_at")
    )

    return df_clean


def clean_customers_data(df: DataFrame) -> DataFrame:
    """
    Clean and transform customers data from Bronze to Silver.
    """
    if df.count() == 0:
        return df

    # Remove duplicates and soft deletes
    window_spec = Window.partitionBy("customer_id").orderBy(desc("debezium_ts_ms"))
    df_deduped = df.withColumn("row_num", row_number().over(window_spec)) \
                   .filter(col("row_num") == 1) \
                   .drop("row_num") \
                   .filter(col("debezium_op") != "d")

    df_clean = df_deduped.select(
        col("customer_id").cast(LongType()).alias("customer_id"),

        # Clean email (lowercase, trim)
        when(col("email").isNull(), "unknown@unknown.com")
        .otherwise(trim(lower(col("email")))).alias("email"),

        # Clean full_name (trim, title case)
        when(col("full_name").isNull(), "Unknown Customer")
        .otherwise(trim(col("full_name"))).alias("full_name"),

        # Clean phone (remove non-digits except + and -)
        when(col("phone").isNull(), None)
        .otherwise(regexp_replace(col("phone"), "[^+\\-0-9]", "")).alias("phone"),

        to_timestamp(col("created_at")).alias("created_at"),
        to_timestamp(col("ingestion_timestamp")).alias("ingestion_timestamp"),

        # Data quality checks
        when(
            col("email").rlike("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$") &
            col("full_name").isNotNull() &
            (col("full_name") != ""),
            "PASSED"
        ).otherwise("FAILED").alias("data_quality_status"),

        col("debezium_op").alias("cdc_operation"),
        col("debezium_ts_ms").alias("cdc_timestamp_ms"),
        current_timestamp().alias("silver_processed_at")
    )

    return df_clean


def clean_products_data(df: DataFrame) -> DataFrame:
    """
    Clean and transform products data from Bronze to Silver.
    """
    if df.count() == 0:
        return df

    # Remove duplicates and soft deletes
    window_spec = Window.partitionBy("product_id").orderBy(desc("debezium_ts_ms"))
    df_deduped = df.withColumn("row_num", row_number().over(window_spec)) \
                   .filter(col("row_num") == 1) \
                   .drop("row_num") \
                   .filter(col("debezium_op") != "d")

    df_clean = df_deduped.select(
        col("product_id").cast(LongType()).alias("product_id"),

        # Clean SKU (uppercase, trim)
        when(col("sku").isNull(), "UNKNOWN-SKU")
        .otherwise(trim(upper(col("sku")))).alias("sku"),

        # Clean product name
        when(col("name").isNull(), "Unknown Product")
        .otherwise(trim(col("name"))).alias("name"),

        # Validate price
        when(col("price_cents").isNull() | (col("price_cents") < 0), 0)
        .otherwise(col("price_cents").cast(IntegerType())).alias("price_cents"),

        (col("price_cents") / 100.0).alias("price_dollars"),

        # Clean active flag
        when(col("active").isNull(), False)
        .otherwise(col("active").cast(BooleanType())).alias("active"),

        # Data quality checks
        when(
            col("sku").isNotNull() &
            col("name").isNotNull() &
            (col("name") != "") &
            (col("price_cents") >= 0),
            "PASSED"
        ).otherwise("FAILED").alias("data_quality_status"),

        col("debezium_op").alias("cdc_operation"),
        col("debezium_ts_ms").alias("cdc_timestamp_ms"),
        current_timestamp().alias("silver_processed_at")
    )

    return df_clean


def write_silver_data(df: DataFrame, table_name: str, execution_date: datetime) -> None:
    """
    Write cleaned data to Silver layer using Delta format.
    """
    if df.count() == 0:
        print(f"No data to write for table {table_name}")
        return

    # Create partitioned path for Silver layer
    year = execution_date.year
    month = f"{execution_date.month:02d}"
    day = f"{execution_date.day:02d}"

    silver_path = f"s3a://silver/{table_name}"

    try:
        # Write as Delta table with partitioning
        df.write \
          .format("delta") \
          .mode("append") \
          .option("mergeSchema", "true") \
          .partitionBy("year", "month", "day") \
          .save(silver_path)

        record_count = df.count()
        print(f"Successfully wrote {record_count} records to Silver layer: {silver_path}")

    except Exception as e:
        print(f"Error writing Silver data for {table_name}: {e}")
        raise


def transform_orders_to_silver(**context) -> None:
    """
    Transform orders from Bronze to Silver layer.
    """
    execution_date = context['execution_date']
    date_filter = execution_date.strftime('%Y-%m-%d')

    spark = get_spark_session()

    try:
        # Read Bronze data
        bronze_df = read_bronze_data(spark, "orders", date_filter)

        if bronze_df.count() > 0:
            # Clean and transform
            silver_df = clean_orders_data(bronze_df)

            # Add partition columns
            silver_df_partitioned = silver_df.withColumn("year", lit(execution_date.year)) \
                                            .withColumn("month", lit(f"{execution_date.month:02d}")) \
                                            .withColumn("day", lit(f"{execution_date.day:02d}"))

            # Write to Silver
            write_silver_data(silver_df_partitioned, "orders", execution_date)

            print(f"Orders transformation completed. Processed {silver_df.count()} records.")
        else:
            print("No orders data found in Bronze layer for the specified date")

    finally:
        spark.stop()


def transform_customers_to_silver(**context) -> None:
    """
    Transform customers from Bronze to Silver layer.
    """
    execution_date = context['execution_date']
    date_filter = execution_date.strftime('%Y-%m-%d')

    spark = get_spark_session()

    try:
        bronze_df = read_bronze_data(spark, "customers", date_filter)

        if bronze_df.count() > 0:
            silver_df = clean_customers_data(bronze_df)
            silver_df_partitioned = silver_df.withColumn("year", lit(execution_date.year)) \
                                            .withColumn("month", lit(f"{execution_date.month:02d}")) \
                                            .withColumn("day", lit(f"{execution_date.day:02d}"))

            write_silver_data(silver_df_partitioned, "customers", execution_date)
            print(f"Customers transformation completed. Processed {silver_df.count()} records.")
        else:
            print("No customers data found in Bronze layer for the specified date")

    finally:
        spark.stop()


def transform_products_to_silver(**context) -> None:
    """
    Transform products from Bronze to Silver layer.
    """
    execution_date = context['execution_date']
    date_filter = execution_date.strftime('%Y-%m-%d')

    spark = get_spark_session()

    try:
        bronze_df = read_bronze_data(spark, "products", date_filter)

        if bronze_df.count() > 0:
            silver_df = clean_products_data(bronze_df)
            silver_df_partitioned = silver_df.withColumn("year", lit(execution_date.year)) \
                                            .withColumn("month", lit(f"{execution_date.month:02d}")) \
                                            .withColumn("day", lit(f"{execution_date.day:02d}"))

            write_silver_data(silver_df_partitioned, "products", execution_date)
            print(f"Products transformation completed. Processed {silver_df.count()} records.")
        else:
            print("No products data found in Bronze layer for the specified date")

    finally:
        spark.stop()


# DAG Definition
with DAG(
    dag_id="bronze_to_silver",
    default_args=DEFAULT_ARGS,
    description="Transform data from Bronze to Silver layer with cleaning and validation",
    schedule=timedelta(minutes=15),  # Run every 15 minutes after Bronze ingestion
    start_date=datetime(2024, 9, 14),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "silver", "transformation", "spark"],
) as dag:

    # Task to transform orders
    transform_orders_task = PythonOperator(
        task_id="transform_orders_to_silver",
        python_callable=transform_orders_to_silver,
        doc_md="""
        ### Transform Orders to Silver Layer

        This task performs the following transformations on orders data:

        1. **Deduplication**: Keeps the latest record for each order_id based on CDC timestamp
        2. **Data Cleaning**:
           - Validates and cleans monetary amounts (non-negative values)
           - Standardizes status values (PLACED, PAID, FULFILLED, CANCELED)
           - Normalizes currency codes (uppercase)
        3. **Data Quality**:
           - Flags records with inconsistent total amounts
           - Validates required foreign keys
        4. **Computed Columns**:
           - Converts cents to dollars
           - Calculates expected total from components
        5. **Storage**: Saves as Delta format in Silver layer with date partitioning
        """
    )

    # Task to transform customers
    transform_customers_task = PythonOperator(
        task_id="transform_customers_to_silver",
        python_callable=transform_customers_to_silver,
        doc_md="""
        ### Transform Customers to Silver Layer

        Transformations include:
        - Email normalization (lowercase, validation)
        - Name standardization
        - Phone number cleaning
        - Data quality validation
        """
    )

    # Task to transform products
    transform_products_task = PythonOperator(
        task_id="transform_products_to_silver",
        python_callable=transform_products_to_silver,
        doc_md="""
        ### Transform Products to Silver Layer

        Transformations include:
        - SKU normalization (uppercase)
        - Price validation (non-negative)
        - Product name cleaning
        - Active status validation
        """
    )

    # All transformation tasks can run in parallel
    [transform_orders_task, transform_customers_task, transform_products_task]