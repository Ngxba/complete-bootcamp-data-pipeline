"""
CDC Configuration Management

Handles loading and validation of CDC processing configuration.
"""

import os
import yaml
from typing import Dict, Any, Optional
from enum import Enum


class CDCDataMode(Enum):
    """Enumeration of CDC data extraction modes"""
    DATA_BEFORE = "DATA_BEFORE"      # Use only 'before' data
    DATA_AFTER = "DATA_AFTER"        # Use only 'after' data
    DATA_BEFORE_AFTER = "DATA_BEFORE_AFTER"  # Combine both with priority


class CDCConfig:
    """Configuration manager for CDC processing"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize CDC configuration

        Args:
            config_path: Path to YAML configuration file
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "cdc_config.yaml"
            )

        self.config_path = config_path
        self._config = self._load_config()
        self._validate_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config or {}
        except FileNotFoundError:
            print(f"Warning: Config file {self.config_path} not found, using defaults")
            return self._get_default_config()
        except Exception as e:
            print(f"Warning: Error loading config {self.config_path}: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "spark": {
                "mode": "batch",
                "app_name_prefix": "CDC-Processor"
            },
            "debezium": {
                "settings": {
                    "auto_infer_schema": True,
                    "use_fallback_schema": True,
                    "cdc_data_mode": "DATA_AFTER",
                    "timezone": "UTC"
                },
                "tables": {}
            }
        }

    def _validate_config(self):
        """Validate configuration values"""
        # Validate spark mode
        spark_mode = self.get_spark_mode()
        if spark_mode not in ["batch", "streaming"]:
            raise ValueError(f"Invalid spark mode: {spark_mode}. Must be 'batch' or 'streaming'")

        # Validate global CDC data mode
        global_mode = self.get_global_cdc_mode()
        try:
            CDCDataMode(global_mode)
        except ValueError:
            raise ValueError(f"Invalid global CDC data mode: {global_mode}")

        # Validate table-specific CDC modes
        for table_name in self.get_table_names():
            table_mode = self.get_table_cdc_mode(table_name)
            try:
                CDCDataMode(table_mode)
            except ValueError:
                raise ValueError(f"Invalid CDC data mode for table {table_name}: {table_mode}")

    # Spark Configuration
    def get_spark_mode(self) -> str:
        """Get Spark processing mode (batch or streaming)"""
        return self._config.get("spark", {}).get("mode", "batch")

    def get_app_name_prefix(self) -> str:
        """Get application name prefix"""
        return self._config.get("spark", {}).get("app_name_prefix", "CDC-Processor")

    def get_spark_config(self) -> Dict[str, Any]:
        """Get Spark-specific configuration"""
        return self._config.get("spark", {})

    # Global Debezium Configuration
    def get_global_settings(self) -> Dict[str, Any]:
        """Get global Debezium settings"""
        return self._config.get("debezium", {}).get("settings", {})

    def get_global_cdc_mode(self) -> str:
        """Get global CDC data mode"""
        return self.get_global_settings().get("cdc_data_mode", "DATA_AFTER")

    def is_auto_infer_schema(self) -> bool:
        """Check if schema auto-inference is enabled"""
        return self.get_global_settings().get("auto_infer_schema", True)

    def is_use_fallback_schema(self) -> bool:
        """Check if fallback schema should be used"""
        return self.get_global_settings().get("use_fallback_schema", True)

    def get_timezone(self) -> str:
        """Get timezone for timestamp conversions"""
        return self.get_global_settings().get("timezone", "UTC")

    # Table-specific Configuration
    def get_table_names(self) -> list:
        """Get list of configured table names"""
        return list(self._config.get("debezium", {}).get("tables", {}).keys())

    def get_table_config(self, table_name: str) -> Dict[str, Any]:
        """Get configuration for a specific table"""
        return self._config.get("debezium", {}).get("tables", {}).get(table_name, {})

    def get_table_primary_key(self, table_name: str) -> str:
        """Get primary key field for a table"""
        table_config = self.get_table_config(table_name)
        # Default to table_name + "_id" but for orders table, use "order_id"
        if table_name == "orders":
            return table_config.get("primary_key", "order_id")
        else:
            return table_config.get("primary_key", f"{table_name}_id")

    def get_table_cdc_mode(self, table_name: str) -> str:
        """Get CDC data mode for a specific table"""
        table_config = self.get_table_config(table_name)
        return table_config.get("cdc_data_mode", self.get_global_cdc_mode())

    def get_table_data_priority(self, table_name: str) -> str:
        """Get data priority for DATA_BEFORE_AFTER mode"""
        table_config = self.get_table_config(table_name)
        return table_config.get("data_priority", "after")

    def get_table_field_overrides(self, table_name: str) -> Dict[str, Any]:
        """Get field overrides for a table"""
        table_config = self.get_table_config(table_name)
        return table_config.get("field_overrides", {})

    def get_table_transformations(self, table_name: str) -> Dict[str, Any]:
        """Get transformations for a table"""
        table_config = self.get_table_config(table_name)
        return table_config.get("transformations", {})

    def get_table_partition_strategy(self, table_name: str) -> str:
        """Get partitioning strategy for a table"""
        table_config = self.get_table_config(table_name)
        return table_config.get("partition_strategy", "timestamp")

    # Utility methods
    def is_streaming_mode(self) -> bool:
        """Check if running in streaming mode"""
        return self.get_spark_mode() == "streaming"

    def is_batch_mode(self) -> bool:
        """Check if running in batch mode"""
        return self.get_spark_mode() == "batch"

    def get_cdc_data_mode_enum(self, table_name: str = None) -> CDCDataMode:
        """Get CDC data mode as enum"""
        if table_name:
            mode_str = self.get_table_cdc_mode(table_name)
        else:
            mode_str = self.get_global_cdc_mode()
        return CDCDataMode(mode_str)

    def should_use_before_data(self, table_name: str = None) -> bool:
        """Check if 'before' data should be used"""
        mode = self.get_cdc_data_mode_enum(table_name)
        return mode in [CDCDataMode.DATA_BEFORE, CDCDataMode.DATA_BEFORE_AFTER]

    def should_use_after_data(self, table_name: str = None) -> bool:
        """Check if 'after' data should be used"""
        mode = self.get_cdc_data_mode_enum(table_name)
        return mode in [CDCDataMode.DATA_AFTER, CDCDataMode.DATA_BEFORE_AFTER]

    def __str__(self) -> str:
        """String representation of configuration"""
        return f"CDCConfig(mode={self.get_spark_mode()}, tables={self.get_table_names()})"