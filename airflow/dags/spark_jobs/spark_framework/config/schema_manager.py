"""
Schema Management

Handles Debezium schema parsing and conversion to Spark types.
"""

import json
from typing import Dict, Any, Optional, List
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType,
    IntegerType, BooleanType, FloatType, DoubleType
)


class SchemaManager:
    """Manages schema parsing and conversion for CDC processing"""

    @staticmethod
    def debezium_type_to_spark_type(debezium_type: str, optional: bool = True) -> Any:
        """Convert Debezium schema type to Spark DataType"""
        type_mapping = {
            "int8": IntegerType(),
            "int16": IntegerType(),
            "int32": IntegerType(),
            "int64": LongType(),
            "float32": FloatType(),
            "float64": DoubleType(),
            "boolean": BooleanType(),
            "string": StringType(),
            "bytes": StringType()  # Handle as string for now
        }
        return type_mapping.get(debezium_type, StringType())

    @staticmethod
    def parse_debezium_struct_schema(schema_def: Dict[str, Any]) -> StructType:
        """Parse a Debezium struct schema definition into Spark StructType"""
        fields = []

        for field_def in schema_def.get("fields", []):
            field_name = field_def["field"]
            field_type = field_def["type"]
            optional = field_def.get("optional", True)

            if field_type == "struct":
                # Recursively parse nested struct
                spark_type = SchemaManager.parse_debezium_struct_schema(field_def)
            else:
                # Handle special Debezium types
                if field_def.get("name") == "io.debezium.time.MicroTimestamp":
                    spark_type = LongType()  # Will convert to timestamp later
                else:
                    spark_type = SchemaManager.debezium_type_to_spark_type(field_type, optional)

            fields.append(StructField(field_name, spark_type, optional))

        return StructType(fields)

    @staticmethod
    def extract_schema_from_kafka_message(spark, topic_name: str) -> Optional[StructType]:
        """Extract schema from a sample Kafka message"""
        try:
            print("Attempting to extract schema from Kafka message...")

            # Read a single message to get schema
            sample_df = spark.read \
                .format("kafka") \
                .option("kafka.bootstrap.servers", "kafka:9092") \
                .option("subscribe", topic_name) \
                .option("startingOffsets", "earliest") \
                .option("endingOffsets", "latest") \
                .load() \
                .limit(1)

            if sample_df.count() == 0:
                print("No messages found in topic for schema extraction")
                return None

            # Get the message value and parse as JSON to extract schema
            from pyspark.sql.functions import col as spark_col
            message_row = sample_df.select(spark_col("value").cast("string")).collect()[0]
            message_json = json.loads(message_row["value"])

            if "schema" not in message_json:
                print("No schema found in Kafka message")
                return None

            schema_def = message_json["schema"]
            print(f"Found schema in message: {schema_def['name']}")

            # Parse the Debezium envelope schema
            return SchemaManager.parse_debezium_struct_schema(schema_def)

        except Exception as e:
            print(f"Error extracting schema from message: {e}")
            return None

    @staticmethod
    def get_fallback_debezium_schema() -> StructType:
        """Get fallback hardcoded schema for orders table"""
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

    @staticmethod
    def get_table_fields_from_schema(schema: StructType, data_section: str = "after") -> List[str]:
        """
        Extract field names from the 'after' or 'before' part of Debezium schema

        Args:
            schema: The Debezium envelope schema
            data_section: Which section to extract fields from ('after' or 'before')
        """
        fields = []

        # Look for the specified field in the schema (which contains the table structure)
        for field in schema.fields:
            if field.name == data_section and isinstance(field.dataType, StructType):
                for table_field in field.dataType.fields:
                    fields.append(table_field.name)
                break

        return fields

    @staticmethod
    def resolve_schema(spark, topic_name: str, auto_infer: bool = True,
                      use_fallback: bool = True) -> StructType:
        """
        Resolve schema using auto-inference or fallback

        Args:
            spark: Spark session
            topic_name: Kafka topic name
            auto_infer: Whether to attempt auto-inference
            use_fallback: Whether to use fallback if auto-inference fails
        """
        schema = None

        if auto_infer:
            schema = SchemaManager.extract_schema_from_kafka_message(spark, topic_name)

        if schema is None and use_fallback:
            print("Using fallback hardcoded schema")
            schema = SchemaManager.get_fallback_debezium_schema()
        elif schema is not None:
            print("Successfully extracted schema from Kafka message")

        if schema is None:
            raise ValueError("Could not determine schema for Kafka messages")

        return schema