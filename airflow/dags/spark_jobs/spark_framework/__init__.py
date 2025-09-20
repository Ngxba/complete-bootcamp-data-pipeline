"""
Spark CDC Processing Framework

A comprehensive framework for processing Change Data Capture (CDC) events
from Kafka using Apache Spark, with support for both batch and streaming modes.
"""

__version__ = "1.0.0"
__author__ = "Data Engineering Team"

from .factories.spark_factory import SparkFactory
from .factories.processor_factory import ProcessorFactory
from .config.schema_manager import SchemaManager
from .config.cdc_config import CDCConfig

__all__ = [
    "SparkFactory",
    "ProcessorFactory",
    "SchemaManager",
    "CDCConfig"
]