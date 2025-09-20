#!/usr/bin/env python3
"""
Kafka to Bronze CDC Processor v2

Enhanced CDC processing using the Spark Framework with configurable
data modes, primary keys, and processing strategies.

Usage:
    python kafka_to_bronze_v2.py <table_name> <topic_name> [options]

Examples:
    # Batch processing with default config
    python kafka_to_bronze_v2.py orders debezium.public.orders --max-records 1000

    # Streaming processing
    python kafka_to_bronze_v2.py orders debezium.public.orders --mode streaming

    # Custom configuration
    python kafka_to_bronze_v2.py orders debezium.public.orders --config /path/to/config.yaml

    # Console output for testing
    python kafka_to_bronze_v2.py orders debezium.public.orders --console --duration 60
"""

import sys
import argparse
from datetime import datetime
from typing import Optional

# Import the Spark Framework
from spark_framework import SparkFactory, ProcessorFactory, CDCConfig
from spark_framework.processors.base_processor import BaseProcessor


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="CDC Processor v2 - Enhanced Kafka to Bronze processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Required arguments
    parser.add_argument("table_name", help="Name of the table being processed")
    parser.add_argument("topic_name", help="Kafka topic name")

    # Optional arguments
    parser.add_argument(
        "--config", "-c",
        help="Path to configuration YAML file",
        default=None
    )

    parser.add_argument(
        "--mode", "-m",
        choices=["batch", "streaming"],
        help="Processing mode (overrides config file)"
    )

    parser.add_argument(
        "--max-records",
        type=int,
        help="Maximum number of records to process (batch mode) or per trigger (streaming mode)",
        default=None
    )

    parser.add_argument(
        "--console",
        action="store_true",
        help="Output to console instead of storage (useful for testing)"
    )

    parser.add_argument(
        "--duration",
        type=int,
        help="Duration in seconds for console output (default: 60)",
        default=60
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate configuration and schema compatibility"
    )

    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Show Kafka topic metrics"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args()


def setup_logging(verbose: bool):
    """Setup logging configuration"""
    if verbose:
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def validate_configuration(config: CDCConfig, table_name: str) -> bool:
    """Validate configuration for the specified table"""
    print("🔍 Validating configuration...")

    # Check if table is configured
    if table_name not in config.get_table_names():
        print(f"⚠️  Warning: Table '{table_name}' not found in configuration")
        print(f"Available tables: {config.get_table_names()}")
        print("Using default configuration for this table")

    # Validate CDC mode
    cdc_mode = config.get_table_cdc_mode(table_name)
    primary_key = config.get_table_primary_key(table_name)

    print(f"📋 Configuration Summary:")
    print(f"   Table: {table_name}")
    print(f"   Processing Mode: {config.get_spark_mode()}")
    print(f"   CDC Data Mode: {cdc_mode}")
    print(f"   Primary Key: {primary_key}")
    print(f"   Partition Strategy: {config.get_table_partition_strategy(table_name)}")

    if cdc_mode == "DATA_BEFORE_AFTER":
        priority = config.get_table_data_priority(table_name)
        print(f"   Data Priority: {priority}")

    print("✅ Configuration validation completed")
    return True


def show_kafka_metrics(processor: BaseProcessor):
    """Show Kafka topic metrics"""
    if hasattr(processor, 'get_kafka_metrics'):
        print("\n📊 Kafka Topic Metrics:")
        metrics = processor.get_kafka_metrics()
        for key, value in metrics.items():
            print(f"   {key}: {value}")
    else:
        print("⚠️  Kafka metrics not available for this processor type")


def run_batch_processing(processor: BaseProcessor, args) -> bool:
    """Run batch processing"""
    print(f"🚀 Starting batch processing...")

    try:
        if args.metrics:
            show_kafka_metrics(processor)

        results = processor.process(max_records=args.max_records)

        print(f"\n📈 Processing Results:")
        for key, value in results.items():
            print(f"   {key}: {value}")

        return results.get('status') in ['completed', 'completed_with_warnings']

    except Exception as e:
        print(f"❌ Batch processing failed: {str(e)}")
        return False


def run_streaming_processing(processor: BaseProcessor, args) -> bool:
    """Run streaming processing"""
    from spark_framework.processors.stream_processor import StreamProcessor

    if not isinstance(processor, StreamProcessor):
        print("❌ Streaming mode requires StreamProcessor")
        return False

    print(f"🌊 Starting streaming processing...")

    try:
        if args.console:
            print(f"📺 Console output mode for {args.duration} seconds")
            results = processor.process_console_output(
                max_records=args.max_records,
                duration_seconds=args.duration
            )
        else:
            print("💾 Storage output mode")
            results = processor.process(max_records=args.max_records)

            if results.get('status') == 'streaming_started':
                print("✅ Streaming query started successfully")
                print("Press Ctrl+C to stop the streaming...")

                try:
                    processor.await_termination()
                except KeyboardInterrupt:
                    print("\n🛑 Stopping streaming query...")
                    processor.stop_streaming()

        print(f"\n📈 Streaming Results:")
        for key, value in results.items():
            print(f"   {key}: {value}")

        return results.get('status') in ['completed', 'streaming_started']

    except Exception as e:
        print(f"❌ Streaming processing failed: {str(e)}")
        return False


def main():
    """Main execution function"""
    args = parse_arguments()

    print("=" * 60)
    print("🔄 Kafka to Bronze CDC Processor v2")
    print("=" * 60)
    print(f"Table: {args.table_name}")
    print(f"Topic: {args.topic_name}")
    print(f"Timestamp: {datetime.now()}")
    print("=" * 60)

    setup_logging(args.verbose)

    try:
        # Load configuration
        print("📁 Loading configuration...")
        config = CDCConfig(args.config)

        # Override mode if specified
        if args.mode:
            config._config['spark']['mode'] = args.mode

        # Validate configuration
        if not validate_configuration(config, args.table_name):
            return 1

        # Validation-only mode
        if args.validate_only:
            print("✅ Validation completed successfully")
            return 0

        # Create and initialize processor
        print(f"🏭 Creating {config.get_spark_mode()} processor...")
        processor = ProcessorFactory.create_processor(config, args.table_name, args.topic_name)

        success = False

        with processor:  # Use context manager for proper cleanup
            # Run processing based on mode
            if config.is_batch_mode():
                success = run_batch_processing(processor, args)
            elif config.is_streaming_mode():
                success = run_streaming_processing(processor, args)
            else:
                print(f"❌ Unknown processing mode: {config.get_spark_mode()}")
                return 1

        if success:
            print("\n🎉 Processing completed successfully!")
            return 0
        else:
            print("\n⚠️  Processing completed with errors")
            return 1

    except KeyboardInterrupt:
        print("\n🛑 Processing interrupted by user")
        return 130  # Standard exit code for Ctrl+C

    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())