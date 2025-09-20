"""
Processor Factory

Creates appropriate processors based on configuration.
"""

from typing import Type
from ..config.cdc_config import CDCConfig
from ..processors.base_processor import BaseProcessor
from ..processors.batch_processor import BatchProcessor
from ..processors.stream_processor import StreamProcessor


class ProcessorFactory:
    """Factory for creating CDC processors"""

    @staticmethod
    def create_processor(config: CDCConfig, table_name: str, topic_name: str) -> BaseProcessor:
        """
        Create appropriate processor based on configuration

        Args:
            config: CDC configuration object
            table_name: Name of the table being processed
            topic_name: Kafka topic name

        Returns:
            Configured processor instance
        """
        if config.is_batch_mode():
            return BatchProcessor(config, table_name, topic_name)
        elif config.is_streaming_mode():
            return StreamProcessor(config, table_name, topic_name)
        else:
            raise ValueError(f"Unknown processing mode: {config.get_spark_mode()}")

    @staticmethod
    def get_processor_class(config: CDCConfig) -> Type[BaseProcessor]:
        """
        Get processor class based on configuration

        Args:
            config: CDC configuration object

        Returns:
            Processor class
        """
        if config.is_batch_mode():
            return BatchProcessor
        elif config.is_streaming_mode():
            return StreamProcessor
        else:
            raise ValueError(f"Unknown processing mode: {config.get_spark_mode()}")

    @staticmethod
    def create_batch_processor(config: CDCConfig, table_name: str, topic_name: str) -> BatchProcessor:
        """Create a batch processor"""
        return BatchProcessor(config, table_name, topic_name)

    @staticmethod
    def create_stream_processor(config: CDCConfig, table_name: str, topic_name: str) -> StreamProcessor:
        """Create a streaming processor"""
        return StreamProcessor(config, table_name, topic_name)