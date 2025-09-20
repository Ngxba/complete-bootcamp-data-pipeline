"""
Base CDC Processor

Abstract base class for all CDC processors.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import StructType

from ..config.cdc_config import CDCConfig
from ..config.schema_manager import SchemaManager
from ..factories.spark_factory import SparkFactory
from .cdc_transformer import CDCTransformer


class BaseProcessor(ABC):
    """Abstract base class for CDC processors"""

    def __init__(self, config: CDCConfig, table_name: str, topic_name: str):
        """
        Initialize processor

        Args:
            config: CDC configuration object
            table_name: Name of the table being processed
            topic_name: Kafka topic name
        """
        self.config = config
        self.table_name = table_name
        self.topic_name = topic_name
        self.spark: Optional[SparkSession] = None
        self.schema: Optional[StructType] = None
        self.transformer: Optional[CDCTransformer] = None

    def initialize(self):
        """Initialize the processor with Spark session and schema"""
        # Create Spark session
        self.spark = self._create_spark_session()
        self.spark.sparkContext.setLogLevel("WARN")

        # Resolve schema
        self.schema = self._resolve_schema()

        # Create transformer
        self.transformer = CDCTransformer(self.config, self.table_name, self.schema)

        print(f"Initialized {self.__class__.__name__} for table '{self.table_name}'")
        print(f"Schema fields: {[f.name for f in self.schema.fields]}")

    def cleanup(self):
        """Cleanup resources"""
        if self.spark:
            self.spark.stop()
            self.spark = None

    @abstractmethod
    def _create_spark_session(self) -> SparkSession:
        """Create appropriate Spark session for this processor type"""
        pass

    @abstractmethod
    def process(self, max_records: Optional[int] = None) -> Dict[str, Any]:
        """
        Process CDC data

        Args:
            max_records: Maximum number of records to process (batch mode)

        Returns:
            Processing results dictionary
        """
        pass

    def _resolve_schema(self) -> StructType:
        """Resolve schema using configuration settings"""
        return SchemaManager.resolve_schema(
            self.spark,
            self.topic_name,
            auto_infer=self.config.is_auto_infer_schema(),
            use_fallback=self.config.is_use_fallback_schema()
        )

    def _read_kafka_data(self, max_records: Optional[int] = None) -> DataFrame:
        """Read data from Kafka topic (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement _read_kafka_data")

    def _write_to_storage(self, df: DataFrame, output_path: str) -> None:
        """Write DataFrame to storage using Hudi format"""
        primary_key = self.config.get_table_primary_key(self.table_name)

        hudi_options = {
            # Hudi table configuration
            'hoodie.table.name': f'bronze_{self.table_name}',
            'hoodie.datasource.write.recordkey.field': primary_key,
            'hoodie.datasource.write.precombine.field': 'cdc_timestamp_ms',
            'hoodie.datasource.write.partitionpath.field': 'partition_year,partition_month,partition_day',
            'hoodie.datasource.write.table.name': f'bronze_{self.table_name}',
            'hoodie.datasource.write.operation': 'upsert',
            'hoodie.datasource.write.table.type': 'COPY_ON_WRITE',

            # Partitioning
            'hoodie.datasource.write.keygenerator.class': 'org.apache.hudi.keygen.ComplexKeyGenerator',
            'hoodie.datasource.hive_sync.partition_extractor_class': 'org.apache.hudi.hive.MultiPartKeysValueExtractor',

            # Performance optimizations
            'hoodie.upsert.shuffle.parallelism': '4',
            'hoodie.insert.shuffle.parallelism': '4',
            'hoodie.bulkinsert.shuffle.parallelism': '4',

            # File management (updated config keys)
            'hoodie.clean.policy': 'KEEP_LATEST_COMMITS',
            'hoodie.clean.commits.retained': '3',
            'hoodie.keep.min.commits': '4',
            'hoodie.keep.max.commits': '6'
        }

        print(f"Writing records to Bronze layer: {output_path}")

        df.write \
            .format("hudi") \
            .options(**hudi_options) \
            .mode("append") \
            .save(output_path)

    def _validate_results(self, df: DataFrame) -> Dict[str, Any]:
        """Validate processing results"""
        total_count = df.count()
        primary_key = self.config.get_table_primary_key(self.table_name)

        # Check for valid records (non-null primary key)
        valid_df = df.filter(df[primary_key].isNotNull())
        valid_count = valid_df.count()
        invalid_count = total_count - valid_count

        return {
            'total_records': total_count,
            'valid_records': valid_count,
            'invalid_records': invalid_count,
            'primary_key_field': primary_key
        }

    def _show_sample_data(self, df: DataFrame, num_rows: int = 5):
        """Show sample of processed data"""
        print(f"\nSample of processed data ({num_rows} rows):")

        # Determine which fields to display
        all_fields = df.columns
        display_fields = []

        # Add common fields if they exist
        preferred_fields = [
            self.config.get_table_primary_key(self.table_name),
            "customer_id", "status", "total_cents",
            "cdc_operation", "cdc_timestamp",
            "partition_year", "partition_month", "partition_day"
        ]

        for field in preferred_fields:
            if field in all_fields:
                display_fields.append(field)

        # Add more fields if we don't have enough
        if len(display_fields) < 8:
            for field in all_fields:
                if field not in display_fields and len(display_fields) < 8:
                    display_fields.append(field)

        if display_fields:
            df.select(*display_fields).show(num_rows, truncate=False)
        else:
            print("No fields available to display")

    def __enter__(self):
        """Context manager entry"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()