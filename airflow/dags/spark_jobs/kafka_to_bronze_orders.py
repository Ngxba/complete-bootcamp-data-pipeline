#!/usr/bin/env python3
"""
Spark job to read Debezium CDC messages from Kafka and write to Bronze layer in Hudi format.

This job reads CDC events from the debezium.public.orders topic and writes them
to the Bronze layer in Hudi format for ACID transactions and incremental processing.
"""

import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_timestamp, current_timestamp,
    lit, when, coalesce, expr
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType,
    IntegerType, TimestampType
)


def create_spark_session():
    """Create Spark session with Hudi and Kafka configurations."""
    return SparkSession.builder \
        .appName("KafkaToBronzeOrders") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.hudi.catalog.HoodieCatalog") \
        .config("spark.sql.extensions", "org.apache.spark.sql.hudi.HoodieSparkSessionExtension") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()


def get_debezium_schema():
    """Define schema for Debezium CDC messages."""
    # Orders table schema (before/after fields)
    orders_schema = StructType([
        StructField("order_id", LongType(), False),
        StructField("customer_id", LongType(), False),
        StructField("ship_to_address_id", LongType(), False),
        StructField("status", StringType(), False),
        StructField("currency", StringType(), False),
        StructField("subtotal_cents", IntegerType(), False),
        StructField("shipping_cents", IntegerType(), False),
        StructField("tax_cents", IntegerType(), False),
        StructField("total_cents", IntegerType(), False),
        StructField("created_at", LongType(), False)
    ])

    # Source metadata schema
    source_schema = StructType([
        StructField("version", StringType(), False),
        StructField("connector", StringType(), False),
        StructField("name", StringType(), False),
        StructField("ts_ms", LongType(), False),
        StructField("snapshot", StringType(), True),
        StructField("db", StringType(), False),
        StructField("sequence", StringType(), True),
        StructField("schema", StringType(), False),
        StructField("table", StringType(), False),
        StructField("txId", LongType(), True),
        StructField("lsn", LongType(), True),
        StructField("xmin", LongType(), True)
    ])

    # Transaction metadata schema
    transaction_schema = StructType([
        StructField("id", StringType(), False),
        StructField("total_order", LongType(), False),
        StructField("data_collection_order", LongType(), False)
    ])

    # Complete Debezium envelope schema
    return StructType([
        StructField("before", orders_schema, True),
        StructField("after", orders_schema, True),
        StructField("source", source_schema, False),
        StructField("op", StringType(), False),
        StructField("ts_ms", LongType(), True),
        StructField("transaction", transaction_schema, True)
    ])


def read_kafka_stream(spark, topic_name, max_records=1000):
    """Read CDC messages from Kafka topic."""
    return spark.read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:9092") \
        .option("subscribe", topic_name) \
        .option("startingOffsets", "earliest") \
        .option("maxOffsetsPerTrigger", max_records) \
        .load()


def transform_cdc_data(df, schema):
    """Transform raw Kafka messages to structured CDC data."""
    # Parse JSON payload
    parsed_df = df.select(
        col("topic"),
        col("partition"),
        col("offset"),
        col("timestamp").alias("kafka_timestamp"),
        from_json(col("value").cast("string"), schema).alias("payload")
    )

    # Extract CDC fields and flatten the structure
    transformed_df = parsed_df.select(
        # Kafka metadata
        col("topic"),
        col("partition"),
        col("offset"),
        col("kafka_timestamp"),

        # CDC operation metadata
        col("payload.op").alias("cdc_operation"),
        col("payload.ts_ms").alias("cdc_timestamp_ms"),
        col("payload.source.ts_ms").alias("source_timestamp_ms"),
        col("payload.source.db").alias("source_db"),
        col("payload.source.schema").alias("source_schema"),
        col("payload.source.table").alias("source_table"),
        col("payload.source.snapshot").alias("is_snapshot"),
        col("payload.source.txId").alias("transaction_id"),
        col("payload.source.lsn").alias("log_sequence_number"),

        # Use 'after' data for inserts/updates, 'before' for deletes
        coalesce(col("payload.after"), col("payload.before")).alias("record_data"),

        # Processing metadata
        current_timestamp().alias("ingestion_timestamp")
    )

    # Flatten record data and add derived fields
    final_df = transformed_df.select(
        "*",
        # Extract individual order fields
        col("record_data.order_id").alias("order_id"),
        col("record_data.customer_id").alias("customer_id"),
        col("record_data.ship_to_address_id").alias("ship_to_address_id"),
        col("record_data.status").alias("status"),
        col("record_data.currency").alias("currency"),
        col("record_data.subtotal_cents").alias("subtotal_cents"),
        col("record_data.shipping_cents").alias("shipping_cents"),
        col("record_data.tax_cents").alias("tax_cents"),
        col("record_data.total_cents").alias("total_cents"),

        # Convert microsecond timestamp to standard timestamp
        (col("record_data.created_at") / 1000000).cast("timestamp").alias("order_created_at"),
        (col("cdc_timestamp_ms") / 1000).cast("timestamp").alias("cdc_timestamp"),
        (col("source_timestamp_ms") / 1000).cast("timestamp").alias("source_timestamp")
    ).drop("record_data")

    # Add partition fields for Hudi
    return final_df.withColumn(
        "partition_year", expr("year(cdc_timestamp)")
    ).withColumn(
        "partition_month", expr("month(cdc_timestamp)")
    ).withColumn(
        "partition_day", expr("day(cdc_timestamp)")
    )


def write_to_hudi_bronze(df, output_path):
    """Write DataFrame to Bronze layer using Hudi format."""
    hudi_options = {
        # Hudi table configuration
        'hoodie.table.name': 'bronze_orders',
        'hoodie.datasource.write.recordkey.field': 'order_id',
        'hoodie.datasource.write.precombine.field': 'cdc_timestamp_ms',
        'hoodie.datasource.write.partitionpath.field': 'partition_year,partition_month,partition_day',
        'hoodie.datasource.write.table.name': 'bronze_orders',
        'hoodie.datasource.write.operation': 'upsert',
        'hoodie.datasource.write.table.type': 'COPY_ON_WRITE',

        # Partitioning
        'hoodie.datasource.write.keygenerator.class': 'org.apache.hudi.keygen.ComplexKeyGenerator',
        'hoodie.datasource.hive_sync.partition_extractor_class': 'org.apache.hudi.hive.MultiPartKeysValueExtractor',

        # Performance optimizations
        'hoodie.upsert.shuffle.parallelism': '4',
        'hoodie.insert.shuffle.parallelism': '4',
        'hoodie.bulkinsert.shuffle.parallelism': '4',

        # File management
        'hoodie.cleaner.policy': 'KEEP_LATEST_COMMITS',
        'hoodie.cleaner.commits.retained': '3',
        'hoodie.keep.min.commits': '4',
        'hoodie.keep.max.commits': '6'
    }

    print(f"Writing {df.count()} records to Bronze layer: {output_path}")

    df.write \
        .format("hudi") \
        .options(**hudi_options) \
        .mode("append") \
        .save(output_path)


def main():
    """Main execution function."""
    if len(sys.argv) != 3:
        print("Usage: kafka_to_bronze_orders.py <topic_name> <max_records>")
        print("Example: kafka_to_bronze_orders.py debezium.public.orders 1000")
        sys.exit(1)

    topic_name = sys.argv[1]
    max_records = int(sys.argv[2])

    print(f"Starting Kafka to Bronze ingestion job")
    print(f"Topic: {topic_name}")
    print(f"Max records: {max_records}")
    print(f"Timestamp: {datetime.now()}")

    # Initialize Spark
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    try:
        # Read from Kafka
        print("Reading from Kafka...")
        raw_df = read_kafka_stream(spark, topic_name, max_records)

        if raw_df.count() == 0:
            print("No new messages found in Kafka topic")
            return

        print(f"Read {raw_df.count()} messages from Kafka")

        # Transform CDC data
        print("Transforming CDC data...")
        schema = get_debezium_schema()
        transformed_df = transform_cdc_data(raw_df, schema)

        # Filter out any invalid records
        valid_df = transformed_df.filter(col("order_id").isNotNull())
        invalid_count = transformed_df.count() - valid_df.count()

        if invalid_count > 0:
            print(f"Warning: Filtered out {invalid_count} invalid records")

        print(f"Transformed {valid_df.count()} valid records")

        # Write to Bronze layer
        bronze_path = "s3a://bronze/orders"
        write_to_hudi_bronze(valid_df, bronze_path)

        print("✅ Successfully completed Kafka to Bronze ingestion")

        # Show sample of processed data
        print("\nSample of processed data:")
        valid_df.select(
            "order_id", "customer_id", "status", "total_cents",
            "cdc_operation", "cdc_timestamp", "partition_year",
            "partition_month", "partition_day"
        ).show(5, truncate=False)

    except Exception as e:
        print(f"❌ Error during processing: {str(e)}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()