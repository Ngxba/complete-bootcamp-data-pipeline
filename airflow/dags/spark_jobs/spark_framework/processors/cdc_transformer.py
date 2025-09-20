"""
CDC Data Transformer

Handles transformation of CDC data based on configuration.
"""

from typing import List, Dict, Any
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col, from_json, current_timestamp, coalesce, expr, when
)
from pyspark.sql.types import StructType

from ..config.cdc_config import CDCConfig, CDCDataMode
from ..config.schema_manager import SchemaManager


class CDCTransformer:
    """Transforms CDC data based on configuration"""

    def __init__(self, config: CDCConfig, table_name: str, schema: StructType):
        """
        Initialize transformer

        Args:
            config: CDC configuration object
            table_name: Name of the table being processed
            schema: Debezium schema structure
        """
        self.config = config
        self.table_name = table_name
        self.schema = schema
        self.table_fields = SchemaManager.get_table_fields_from_schema(schema, "after")

    def transform_cdc_data(self, df: DataFrame) -> DataFrame:
        """
        Transform raw Kafka messages to structured CDC data

        Args:
            df: Raw Kafka DataFrame

        Returns:
            Transformed DataFrame
        """
        # Parse JSON payload
        parsed_df = df.select(
            col("topic"),
            col("partition"),
            col("offset"),
            col("timestamp").alias("kafka_timestamp"),
            from_json(col("value").cast("string"), self.schema).alias("payload")
        )

        # Extract CDC metadata
        base_df = self._extract_cdc_metadata(parsed_df)

        # Extract record data based on CDC mode
        record_df = self._extract_record_data(base_df)

        # Apply field transformations
        transformed_df = self._apply_field_transformations(record_df)

        # Add partitioning fields
        return self._add_partitioning_fields(transformed_df)

    def _extract_cdc_metadata(self, parsed_df: DataFrame) -> DataFrame:
        """Extract CDC metadata from parsed payload"""
        return parsed_df.select(
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

            # Keep the full payload for record extraction
            col("payload"),

            # Processing metadata
            current_timestamp().alias("ingestion_timestamp")
        )

    def _extract_record_data(self, base_df: DataFrame) -> DataFrame:
        """
        Extract record data based on CDC mode configuration

        Args:
            base_df: DataFrame with CDC metadata

        Returns:
            DataFrame with record data extracted
        """
        cdc_mode = self.config.get_cdc_data_mode_enum(self.table_name)

        if cdc_mode == CDCDataMode.DATA_BEFORE:
            record_data_col = col("payload.before")
        elif cdc_mode == CDCDataMode.DATA_AFTER:
            record_data_col = col("payload.after")
        elif cdc_mode == CDCDataMode.DATA_BEFORE_AFTER:
            # Use priority-based selection
            priority = self.config.get_table_data_priority(self.table_name)
            if priority == "after":
                record_data_col = coalesce(col("payload.after"), col("payload.before"))
            else:
                record_data_col = coalesce(col("payload.before"), col("payload.after"))
        else:
            raise ValueError(f"Unsupported CDC data mode: {cdc_mode}")

        # Add record_data column and extract table fields
        select_expressions = [
            col("topic"), col("partition"), col("offset"), col("kafka_timestamp"),
            col("cdc_operation"), col("cdc_timestamp_ms"), col("source_timestamp_ms"),
            col("source_db"), col("source_schema"), col("source_table"),
            col("is_snapshot"), col("transaction_id"), col("log_sequence_number"),
            col("ingestion_timestamp"),
            record_data_col.alias("record_data")
        ]

        # Add table fields dynamically
        for field_name in self.table_fields:
            select_expressions.append(
                col(f"record_data.{field_name}").alias(field_name)
            )

        return base_df.select(*select_expressions)

    def _apply_field_transformations(self, record_df: DataFrame) -> DataFrame:
        """Apply field-specific transformations"""
        field_overrides = self.config.get_table_field_overrides(self.table_name)
        transformations = self.config.get_table_transformations(self.table_name)

        # Create list of columns to select
        select_expressions = []

        # Add all non-record_data columns
        for col_name in record_df.columns:
            if col_name != "record_data":
                select_expressions.append(col(col_name))

        # Handle timestamp conversions for created_at field
        if "created_at" in self.table_fields:
            created_at_config = field_overrides.get("created_at", {})
            if created_at_config.get("scale") == "microseconds":
                select_expressions.append(
                    (col("created_at") / 1000000).cast("timestamp").alias("created_at_timestamp")
                )
            else:
                select_expressions.append(
                    col("created_at").alias("created_at_timestamp")
                )

        # Handle monetary field transformations (convert cents to dollars)
        monetary_fields = transformations.get("monetary_fields", [])
        for field in monetary_fields:
            if field in self.table_fields:
                select_expressions.append(
                    (col(field) / 100.0).alias(f"{field}_dollars")
                )

        # Add standard timestamp conversions
        select_expressions.extend([
            (col("cdc_timestamp_ms") / 1000).cast("timestamp").alias("cdc_timestamp"),
            (col("source_timestamp_ms") / 1000).cast("timestamp").alias("source_timestamp")
        ])

        return record_df.select(*select_expressions)

    def _add_partitioning_fields(self, transformed_df: DataFrame) -> DataFrame:
        """Add partitioning fields based on strategy"""
        partition_strategy = self.config.get_table_partition_strategy(self.table_name)

        if partition_strategy == "timestamp":
            # Use CDC timestamp for partitioning
            return transformed_df.withColumn(
                "partition_year", expr("year(cdc_timestamp)")
            ).withColumn(
                "partition_month", expr("month(cdc_timestamp)")
            ).withColumn(
                "partition_day", expr("day(cdc_timestamp)")
            )
        elif partition_strategy == "created_at" and "created_at_timestamp" in transformed_df.columns:
            # Use record creation timestamp for partitioning
            return transformed_df.withColumn(
                "partition_year", expr("year(created_at_timestamp)")
            ).withColumn(
                "partition_month", expr("month(created_at_timestamp)")
            ).withColumn(
                "partition_day", expr("day(created_at_timestamp)")
            )
        else:
            # Default to CDC timestamp
            return self._add_partitioning_fields(
                transformed_df.withColumn("temp_cdc_ts", col("cdc_timestamp"))
            ).drop("temp_cdc_ts")

    def get_table_fields(self) -> List[str]:
        """Get list of table fields"""
        return self.table_fields

    def get_primary_key_field(self) -> str:
        """Get primary key field for the table"""
        return self.config.get_table_primary_key(self.table_name)

    def validate_schema_compatibility(self) -> bool:
        """Validate that the schema is compatible with the configuration"""
        # Check if primary key exists in table fields
        primary_key = self.get_primary_key_field()
        if primary_key not in self.table_fields:
            print(f"Warning: Primary key '{primary_key}' not found in table fields: {self.table_fields}")
            return False

        # Check if required timestamp fields exist for partitioning
        partition_strategy = self.config.get_table_partition_strategy(self.table_name)
        if partition_strategy == "created_at" and "created_at" not in self.table_fields:
            print(f"Warning: created_at field not found for partitioning strategy '{partition_strategy}'")
            return False

        return True