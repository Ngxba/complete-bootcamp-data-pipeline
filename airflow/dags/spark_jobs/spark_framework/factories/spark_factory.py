"""
Spark Session Factory

Creates configured Spark sessions for CDC processing.
"""

from pyspark.sql import SparkSession
from typing import Dict, Any, Optional
from ..config.cdc_config import CDCConfig


class SparkFactory:
    """Factory for creating Spark sessions with appropriate configurations"""

    @staticmethod
    def create_session(config: CDCConfig, app_name_suffix: str = "") -> SparkSession:
        """
        Create a Spark session with CDC processing configurations

        Args:
            config: CDC configuration object
            app_name_suffix: Optional suffix to add to app name

        Returns:
            Configured Spark session
        """
        app_name = config.get_app_name_prefix()
        if app_name_suffix:
            app_name = f"{app_name}-{app_name_suffix}"

        builder = SparkSession.builder \
            .appName(app_name) \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.hudi.catalog.HoodieCatalog") \
            .config("spark.sql.extensions", "org.apache.spark.sql.hudi.HoodieSparkSessionExtension")

        # Add S3/MinIO configurations
        builder = SparkFactory._add_s3_config(builder)

        # Add streaming-specific configurations if needed
        if config.is_streaming_mode():
            builder = SparkFactory._add_streaming_config(builder)

        # Add any custom Spark configurations from config
        custom_config = config.get_spark_config().get("custom_config", {})
        for key, value in custom_config.items():
            builder = builder.config(key, value)

        return builder.getOrCreate()

    @staticmethod
    def _add_s3_config(builder: SparkSession.Builder) -> SparkSession.Builder:
        """Add S3/MinIO configuration to Spark session builder"""
        return builder \
            .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
            .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
            .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
            .config("spark.hadoop.fs.s3a.path.style.access", "true") \
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")

    @staticmethod
    def _add_streaming_config(builder: SparkSession.Builder) -> SparkSession.Builder:
        """Add streaming-specific configuration to Spark session builder"""
        return builder \
            .config("spark.sql.streaming.checkpointLocation", "s3a://bronze/checkpoints") \
            .config("spark.sql.streaming.stateStore.providerClass",
                   "org.apache.spark.sql.execution.streaming.state.HDFSBackedStateStoreProvider")

    @staticmethod
    def create_batch_session(config: CDCConfig, table_name: str) -> SparkSession:
        """Create a Spark session optimized for batch processing"""
        return SparkFactory.create_session(config, f"Batch-{table_name}")

    @staticmethod
    def create_streaming_session(config: CDCConfig, table_name: str) -> SparkSession:
        """Create a Spark session optimized for streaming processing"""
        return SparkFactory.create_session(config, f"Stream-{table_name}")