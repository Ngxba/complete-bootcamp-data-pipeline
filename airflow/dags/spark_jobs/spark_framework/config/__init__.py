"""Configuration management for Spark CDC Framework"""

from .schema_manager import SchemaManager
from .cdc_config import CDCConfig

__all__ = ["SchemaManager", "CDCConfig"]