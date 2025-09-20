"""
Streaming CDC Processor

Handles streaming processing of CDC data from Kafka.
"""

from typing import Optional, Dict, Any
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.streaming import StreamingQuery
from pyspark.sql.functions import col

from ..factories.spark_factory import SparkFactory
from .base_processor import BaseProcessor


class StreamProcessor(BaseProcessor):
    """Streaming processor for CDC data"""

    def __init__(self, config, table_name: str, topic_name: str):
        super().__init__(config, table_name, topic_name)
        self.streaming_query: Optional[StreamingQuery] = None

    def _create_spark_session(self) -> SparkSession:
        """Create Spark session optimized for streaming processing"""
        return SparkFactory.create_streaming_session(self.config, self.table_name)

    def _read_kafka_data(self, max_records: Optional[int] = None) -> DataFrame:
        """
        Read data from Kafka topic in streaming mode

        Args:
            max_records: Maximum records per trigger (maxOffsetsPerTrigger)

        Returns:
            Streaming DataFrame with Kafka messages
        """
        reader = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "kafka:9092") \
            .option("subscribe", self.topic_name) \
            .option("startingOffsets", "earliest")

        if max_records:
            reader = reader.option("maxOffsetsPerTrigger", max_records)

        return reader.load()

    def process(self, max_records: Optional[int] = None) -> Dict[str, Any]:
        """
        Process CDC data in streaming mode

        Args:
            max_records: Maximum records per trigger

        Returns:
            Processing results dictionary
        """
        if not self.spark or not self.transformer:
            raise RuntimeError("Processor not initialized. Call initialize() first.")

        print(f"Starting streaming processing for table '{self.table_name}'")
        print(f"Topic: {self.topic_name}")
        if max_records:
            print(f"Max records per trigger: {max_records}")

        # Read from Kafka
        print("Setting up Kafka streaming...")
        raw_df = self._read_kafka_data(max_records)

        # Transform CDC data
        print("Setting up CDC transformation...")
        print(f"Detected table fields: {self.transformer.get_table_fields()}")

        # Validate schema compatibility
        if not self.transformer.validate_schema_compatibility():
            print("Warning: Schema compatibility issues detected")

        transformed_df = self.transformer.transform_cdc_data(raw_df)

        # Filter valid records
        primary_key = self.transformer.get_primary_key_field()
        valid_df = transformed_df.filter(col(primary_key).isNotNull())

        # Start streaming query
        output_path = f"s3a://bronze/{self.table_name}"
        checkpoint_path = f"s3a://bronze/checkpoints/{self.table_name}"

        print(f"Starting streaming query with output to {output_path}")

        try:
            self.streaming_query = self._start_streaming_query(valid_df, output_path, checkpoint_path)

            return {
                'status': 'streaming_started',
                'output_path': output_path,
                'checkpoint_path': checkpoint_path,
                'query_id': self.streaming_query.id,
                'primary_key_field': primary_key
            }

        except Exception as e:
            print(f"❌ Error starting streaming query: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'primary_key_field': primary_key
            }

    def _start_streaming_query(self, df: DataFrame, output_path: str, checkpoint_path: str) -> StreamingQuery:
        """Start the streaming query with Hudi output"""

        # Configure Hudi options for streaming
        hudi_options = {
            'hoodie.table.name': f'bronze_{self.table_name}',
            'hoodie.datasource.write.recordkey.field': self.transformer.get_primary_key_field(),
            'hoodie.datasource.write.precombine.field': 'cdc_timestamp_ms',
            'hoodie.datasource.write.partitionpath.field': 'partition_year,partition_month,partition_day',
            'hoodie.datasource.write.table.name': f'bronze_{self.table_name}',
            'hoodie.datasource.write.operation': 'upsert',
            'hoodie.datasource.write.table.type': 'COPY_ON_WRITE',

            # Streaming specific
            'hoodie.datasource.write.streaming.retry.count': '3',
            'hoodie.datasource.write.streaming.ignore.failed.batch': 'true',

            # Performance optimizations for streaming
            'hoodie.upsert.shuffle.parallelism': '2',
            'hoodie.insert.shuffle.parallelism': '2',
            'hoodie.bulkinsert.shuffle.parallelism': '2',

            # File management
            'hoodie.clean.policy': 'KEEP_LATEST_COMMITS',
            'hoodie.clean.commits.retained': '3',
            'hoodie.keep.min.commits': '4',
            'hoodie.keep.max.commits': '6'
        }

        return df.writeStream \
            .outputMode("append") \
            .format("hudi") \
            .options(**hudi_options) \
            .option("checkpointLocation", checkpoint_path) \
            .trigger(processingTime='30 seconds') \
            .start(output_path)

    def process_console_output(self, max_records: Optional[int] = None, duration_seconds: int = 60) -> Dict[str, Any]:
        """
        Process data with console output for testing/debugging

        Args:
            max_records: Maximum records per trigger
            duration_seconds: How long to run the streaming query

        Returns:
            Processing results dictionary
        """
        if not self.spark or not self.transformer:
            raise RuntimeError("Processor not initialized. Call initialize() first.")

        print(f"Starting console streaming for table '{self.table_name}' (duration: {duration_seconds}s)")

        # Read and transform data
        raw_df = self._read_kafka_data(max_records)
        transformed_df = self.transformer.transform_cdc_data(raw_df)

        primary_key = self.transformer.get_primary_key_field()
        valid_df = transformed_df.filter(col(primary_key).isNotNull())

        # Show sample fields for console output
        display_fields = [primary_key, "cdc_operation", "cdc_timestamp"]
        for field in ["customer_id", "status", "total_cents"]:
            if field in transformed_df.columns:
                display_fields.append(field)

        try:
            query = valid_df.select(*display_fields).writeStream \
                .outputMode("append") \
                .format("console") \
                .option("truncate", False) \
                .option("numRows", 10) \
                .trigger(processingTime='10 seconds') \
                .start()

            print(f"Streaming to console for {duration_seconds} seconds...")
            query.awaitTermination(duration_seconds)
            query.stop()

            return {
                'status': 'completed',
                'duration_seconds': duration_seconds,
                'primary_key_field': primary_key
            }

        except Exception as e:
            print(f"❌ Error in console streaming: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'primary_key_field': primary_key
            }

    def stop_streaming(self) -> bool:
        """Stop the current streaming query"""
        if self.streaming_query and self.streaming_query.isActive:
            try:
                self.streaming_query.stop()
                print("✅ Streaming query stopped successfully")
                return True
            except Exception as e:
                print(f"❌ Error stopping streaming query: {e}")
                return False
        else:
            print("No active streaming query to stop")
            return True

    def get_streaming_status(self) -> Dict[str, Any]:
        """Get status of the current streaming query"""
        if not self.streaming_query:
            return {'status': 'no_query', 'message': 'No streaming query initialized'}

        try:
            progress = self.streaming_query.lastProgress
            return {
                'status': 'active' if self.streaming_query.isActive else 'inactive',
                'query_id': self.streaming_query.id,
                'run_id': self.streaming_query.runId,
                'batch_id': progress.get('batchId', 'unknown') if progress else 'unknown',
                'input_rows_per_second': progress.get('inputRowsPerSecond', 0) if progress else 0,
                'processed_rows_per_second': progress.get('processedRowsPerSecond', 0) if progress else 0,
                'last_progress': progress
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def await_termination(self, timeout_seconds: Optional[int] = None):
        """Wait for streaming query to terminate"""
        if self.streaming_query and self.streaming_query.isActive:
            if timeout_seconds:
                self.streaming_query.awaitTermination(timeout_seconds)
            else:
                self.streaming_query.awaitTermination()

    def cleanup(self):
        """Cleanup resources including stopping streaming query"""
        self.stop_streaming()
        super().cleanup()