"""
Batch CDC Processor

Handles batch processing of CDC data from Kafka.
"""

from typing import Optional, Dict, Any
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col

from ..factories.spark_factory import SparkFactory
from .base_processor import BaseProcessor


class BatchProcessor(BaseProcessor):
    """Batch processor for CDC data"""

    def _create_spark_session(self) -> SparkSession:
        """Create Spark session optimized for batch processing"""
        return SparkFactory.create_batch_session(self.config, self.table_name)

    def _read_kafka_data(self, max_records: Optional[int] = None) -> DataFrame:
        """
        Read data from Kafka topic in batch mode

        Args:
            max_records: Maximum number of records to read

        Returns:
            DataFrame with Kafka messages
        """
        reader = self.spark.read \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "kafka:9092") \
            .option("subscribe", self.topic_name) \
            .option("startingOffsets", "earliest")

        if max_records:
            # For batch mode, we read all available data first, then limit
            df = reader.load()
            return df.limit(max_records)
        else:
            return reader.load()

    def process(self, max_records: Optional[int] = None) -> Dict[str, Any]:
        """
        Process CDC data in batch mode

        Args:
            max_records: Maximum number of records to process

        Returns:
            Processing results dictionary
        """
        if not self.spark or not self.transformer:
            raise RuntimeError("Processor not initialized. Call initialize() first.")

        print(f"Starting batch processing for table '{self.table_name}'")
        print(f"Topic: {self.topic_name}")
        if max_records:
            print(f"Max records: {max_records}")

        # Read from Kafka
        print("Reading from Kafka...")
        raw_df = self._read_kafka_data(max_records)

        message_count = raw_df.count()
        if message_count == 0:
            print("No messages found in Kafka topic")
            return {
                'status': 'completed',
                'total_records': 0,
                'valid_records': 0,
                'invalid_records': 0,
                'messages_processed': 0
            }

        print(f"Read {message_count} messages from Kafka")

        # Transform CDC data
        print("Transforming CDC data...")
        print(f"Detected table fields: {self.transformer.get_table_fields()}")

        # Validate schema compatibility
        if not self.transformer.validate_schema_compatibility():
            print("Warning: Schema compatibility issues detected")

        transformed_df = self.transformer.transform_cdc_data(raw_df)

        # Validate results
        validation_results = self._validate_results(transformed_df)
        print(f"Transformation complete: {validation_results}")

        if validation_results['valid_records'] == 0:
            print("Warning: No valid records found after transformation")
            self._show_sample_data(transformed_df, 3)
            return {
                'status': 'completed_with_warnings',
                'messages_processed': message_count,
                **validation_results
            }

        # Filter valid records
        primary_key = validation_results['primary_key_field']
        valid_df = transformed_df.filter(col(primary_key).isNotNull())

        # Write to Bronze layer
        output_path = f"s3a://bronze/{self.table_name}"
        print(f"Writing {validation_results['valid_records']} valid records to {output_path}")

        try:
            self._write_to_storage(valid_df, output_path)
            print("✅ Successfully completed batch processing")

            # Show sample of processed data
            self._show_sample_data(valid_df)

            return {
                'status': 'completed',
                'messages_processed': message_count,
                'output_path': output_path,
                **validation_results
            }

        except Exception as e:
            print(f"❌ Error writing to storage: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'messages_processed': message_count,
                **validation_results
            }

    def process_incremental(self, checkpoint_path: str, max_records: Optional[int] = None) -> Dict[str, Any]:
        """
        Process incremental data using checkpoint

        Args:
            checkpoint_path: Path to store checkpoint information
            max_records: Maximum number of records to process

        Returns:
            Processing results dictionary
        """
        # TODO: Implement incremental processing with checkpoint management
        # This would track the last processed offset and resume from there
        print("Incremental processing not yet implemented for batch mode")
        return self.process(max_records)

    def get_kafka_metrics(self) -> Dict[str, Any]:
        """Get Kafka topic metrics"""
        try:
            # Read topic metadata
            df = self.spark.read \
                .format("kafka") \
                .option("kafka.bootstrap.servers", "kafka:9092") \
                .option("subscribe", self.topic_name) \
                .option("startingOffsets", "earliest") \
                .option("endingOffsets", "latest") \
                .load()

            total_messages = df.count()

            if total_messages > 0:
                # Get partition and offset information
                partition_info = df.select("partition", "offset").distinct().collect()
                partitions = len(set(row.partition for row in partition_info))

                return {
                    'total_messages': total_messages,
                    'partitions': partitions,
                    'topic_name': self.topic_name
                }
            else:
                return {
                    'total_messages': 0,
                    'partitions': 0,
                    'topic_name': self.topic_name
                }

        except Exception as e:
            print(f"Error getting Kafka metrics: {e}")
            return {
                'error': str(e),
                'topic_name': self.topic_name
            }