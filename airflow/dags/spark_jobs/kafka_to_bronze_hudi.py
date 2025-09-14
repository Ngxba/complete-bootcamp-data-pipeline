"""
Spark job for ingesting CDC data from Kafka to Bronze layer using Hudi format.
This job consumes batch data from Kafka topics created by Debezium and saves them
as Hudi tables in MinIO for ACID transactions and incremental data processing.
"""

import sys
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *


def create_spark_session(app_name: str) -> SparkSession:
    """
    Create Spark session with Hudi, Kafka, and MinIO configurations.
    """
    return SparkSession.builder \
        .appName(app_name) \
        .config("spark.jars.packages",
                "org.apache.hudi:hudi-spark3.3-bundle_2.12:0.13.0,"
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0,"
                "org.apache.hadoop:hadoop-aws:3.3.2") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.hudi.catalog.HoodieCatalog") \
        .config("spark.sql.extensions",
                "org.apache.spark.sql.hudi.HoodieSparkSessionExtension") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()


def read_kafka_batch(spark: SparkSession, topic: str, max_records: int = 1000) -> DataFrame:
    """
    Read batch data from Kafka topic.

    Args:
        spark: SparkSession
        topic: Kafka topic name
        max_records: Maximum number of records to read in one batch

    Returns:
        DataFrame with Kafka messages
    """
    kafka_df = spark.read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:9092") \
        .option("subscribe", topic) \
        .option("startingOffsets", "earliest") \
        .option("maxOffsetsPerTrigger", max_records) \
        .load()

    # Parse Kafka message value as JSON and add metadata
    parsed_df = kafka_df.select(
        col("topic").alias("kafka_topic"),
        col("partition").alias("kafka_partition"),
        col("offset").alias("kafka_offset"),
        col("timestamp").alias("kafka_timestamp"),
        col("key").cast("string").alias("kafka_key"),
        from_json(col("value").cast("string"), get_debezium_schema()).alias("debezium_data"),
        current_timestamp().alias("ingestion_timestamp")
    )

    return parsed_df


def get_debezium_schema() -> StructType:
    """
    Define schema for Debezium CDC messages.
    """
    return StructType([
        StructField("op", StringType(), True),
        StructField("ts_ms", LongType(), True),
        StructField("before", MapType(StringType(), StringType()), True),
        StructField("after", MapType(StringType(), StringType()), True),
        StructField("source", StructType([
            StructField("db", StringType(), True),
            StructField("table", StringType(), True),
            StructField("lsn", LongType(), True),
            StructField("txId", LongType(), True),
            StructField("ts_ms", LongType(), True)
        ]), True)
    ])


def process_debezium_data(df: DataFrame) -> DataFrame:
    """
    Process Debezium CDC data and flatten the structure.

    Args:
        df: DataFrame with parsed Debezium data

    Returns:
        Flattened DataFrame ready for Hudi ingestion
    """
    # Extract the actual record data based on operation type
    processed_df = df.select(
        col("kafka_topic"),
        col("kafka_partition"),
        col("kafka_offset"),
        col("kafka_timestamp"),
        col("kafka_key"),
        col("ingestion_timestamp"),
        col("debezium_data.op").alias("debezium_op"),
        col("debezium_data.ts_ms").alias("debezium_ts_ms"),
        col("debezium_data.source.db").alias("source_db"),
        col("debezium_data.source.table").alias("source_table"),
        col("debezium_data.source.lsn").alias("source_lsn"),
        col("debezium_data.source.txId").alias("source_tx_id"),
        # Use CASE to select appropriate data based on operation
        when(col("debezium_data.op").isin(["c", "u", "r"]),
             col("debezium_data.after"))
        .when(col("debezium_data.op") == "d",
              col("debezium_data.before"))
        .otherwise(lit(None))
        .alias("record_data")
    )

    # Flatten the record_data map into individual columns
    # This will be table-specific, but we'll create a generic approach
    flattened_df = processed_df.select(
        "*",
        # Extract common fields from record_data map
        col("record_data")["id"].alias("record_id"),
        # Add timestamp for Hudi
        current_timestamp().alias("hudi_ts")
    )

    return flattened_df


def write_to_hudi(df: DataFrame, table_name: str, base_path: str) -> None:
    """
    Write DataFrame to Hudi table in MinIO.

    Args:
        df: DataFrame to write
        table_name: Name of the Hudi table
        base_path: S3 base path for the table
    """
    hudi_options = {
        'hoodie.table.name': f'bronze_{table_name}',
        'hoodie.datasource.write.recordkey.field': 'record_id',
        'hoodie.datasource.write.partitionpath.field': 'source_table',
        'hoodie.datasource.write.table.name': f'bronze_{table_name}',
        'hoodie.datasource.write.operation': 'upsert',
        'hoodie.datasource.write.precombine.field': 'debezium_ts_ms',
        'hoodie.upsert.shuffle.parallelism': 2,
        'hoodie.insert.shuffle.parallelism': 2,
        'hoodie.delete.shuffle.parallelism': 2,
        'hoodie.datasource.write.table.type': 'COPY_ON_WRITE',
        'hoodie.datasource.write.hive_style_partitioning': 'true',
        'hoodie.datasource.hive_sync.enable': 'false',
        # MinIO/S3 specific configurations
        'hoodie.datasource.write.storage.type': 'COPY_ON_WRITE'
    }

    df.write \
        .format("hudi") \
        .options(**hudi_options) \
        .mode("append") \
        .save(base_path)

    print(f"Successfully wrote {df.count()} records to Hudi table: {table_name}")


def ingest_table_to_bronze(spark: SparkSession, table_name: str, max_records: int = 1000) -> None:
    """
    Ingest specific table data from Kafka to Bronze Hudi table.

    Args:
        spark: SparkSession
        table_name: Name of the table to ingest
        max_records: Maximum records to process in this batch
    """
    print(f"Starting ingestion for table: {table_name}")

    # Debezium topic format: postgres-oltp.public.{table_name}
    topic_name = f"postgres-oltp.public.{table_name}"

    # Read from Kafka
    kafka_df = read_kafka_batch(spark, topic_name, max_records)

    if kafka_df.count() == 0:
        print(f"No messages found in topic: {topic_name}")
        return

    print(f"Read {kafka_df.count()} messages from Kafka topic: {topic_name}")

    # Process Debezium data
    processed_df = process_debezium_data(kafka_df)

    # Filter out records without valid record_id
    valid_df = processed_df.filter(col("record_id").isNotNull())

    if valid_df.count() == 0:
        print(f"No valid records after processing for table: {table_name}")
        return

    print(f"Processing {valid_df.count()} valid records for table: {table_name}")

    # Write to Hudi
    base_path = f"s3a://bronze/hudi/{table_name}"
    write_to_hudi(valid_df, table_name, base_path)

    print(f"Completed ingestion for table: {table_name}")


def main():
    """
    Main function to run the Kafka to Bronze Hudi ingestion job.
    """
    if len(sys.argv) < 2:
        print("Usage: spark-submit kafka_to_bronze_hudi.py <table_name> [max_records]")
        print("Example: spark-submit kafka_to_bronze_hudi.py orders 1000")
        sys.exit(1)

    table_name = sys.argv[1]
    max_records = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    print(f"Starting Kafka to Bronze Hudi ingestion job")
    print(f"Table: {table_name}, Max records: {max_records}")

    # Create Spark session
    spark = create_spark_session(f"kafka-to-bronze-hudi-{table_name}")
    spark.sparkContext.setLogLevel("INFO")

    try:
        # Ingest table data
        ingest_table_to_bronze(spark, table_name, max_records)
        print(f"Job completed successfully for table: {table_name}")

    except Exception as e:
        print(f"Error during ingestion: {str(e)}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()