from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, count, sum as spark_sum, avg, max as spark_max, min as spark_min,
    when
)
import great_expectations as ge


DEFAULT_ARGS = {
    "owner": "data-quality",
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
    "depends_on_past": False,
}


def get_spark_session() -> SparkSession:
    """Initialize Spark session for data quality checks."""
    spark = SparkSession.builder \
        .appName("DataQualityChecks") \
        .config("spark.master", "spark://spark-master:7077") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_silver_data(spark: SparkSession, table_name: str, date_filter: str = None) -> DataFrame:
    """Read data from Silver layer."""
    silver_path = f"s3a://silver/{table_name}"

    try:
        df = spark.read.format("delta").load(silver_path)

        if date_filter:
            df = df.filter(
                (col("year") == date_filter[:4]) &
                (col("month") == date_filter[5:7]) &
                (col("day") == date_filter[8:10])
            )

        return df

    except Exception as e:
        print(f"Error reading Silver data for {table_name}: {e}")
        return spark.createDataFrame([], schema="")


def calculate_data_freshness(spark: SparkSession) -> Dict[str, Any]:
    """Calculate data freshness metrics for all tables."""
    freshness_metrics = {}

    tables = ["orders", "customers", "products"]

    for table in tables:
        try:
            df = read_silver_data(spark, table)

            if df.count() > 0:
                # Find the most recent ingestion timestamp
                latest_ingestion = df.agg(spark_max("ingestion_timestamp")).collect()[0][0]
                latest_processing = df.agg(spark_max("silver_processed_at")).collect()[0][0]

                # Calculate lag in minutes
                current_time = datetime.utcnow()
                if latest_processing:
                    processing_lag_minutes = (current_time - latest_processing).total_seconds() / 60
                else:
                    processing_lag_minutes = None

                freshness_metrics[table] = {
                    "latest_ingestion": str(latest_ingestion) if latest_ingestion else None,
                    "latest_processing": str(latest_processing) if latest_processing else None,
                    "processing_lag_minutes": processing_lag_minutes,
                    "record_count": df.count()
                }
            else:
                freshness_metrics[table] = {
                    "latest_ingestion": None,
                    "latest_processing": None,
                    "processing_lag_minutes": None,
                    "record_count": 0
                }

        except Exception as e:
            print(f"Error calculating freshness for {table}: {e}")
            freshness_metrics[table] = {"error": str(e)}

    return freshness_metrics


def validate_orders_quality(spark: SparkSession) -> Dict[str, Any]:
    """Perform comprehensive data quality checks on orders table."""
    quality_results = {}

    try:
        df = read_silver_data(spark, "orders")
        total_records = df.count()

        if total_records == 0:
            return {"error": "No orders data found in Silver layer"}

        # Basic completeness checks
        completeness_checks = df.agg(
            (count("*")).alias("total_records"),
            (count("order_id")).alias("order_id_count"),
            (count("customer_id")).alias("customer_id_count"),
            (count("status")).alias("status_count"),
            (count("total_cents")).alias("total_cents_count")
        ).collect()[0]

        # Data quality status distribution
        quality_status = df.groupBy("data_quality_status").count().collect()
        quality_distribution = {row["data_quality_status"]: row["count"] for row in quality_status}

        # Business logic validation
        invalid_totals = df.filter(
            col("total_cents") != (col("subtotal_cents") + col("shipping_cents") + col("tax_cents"))
        ).count()

        # Status distribution
        status_distribution = df.groupBy("status").count().collect()
        status_counts = {row["status"]: row["count"] for row in status_distribution}

        # Monetary amount checks
        monetary_stats = df.select(
            avg("total_dollars").alias("avg_total"),
            spark_min("total_dollars").alias("min_total"),
            spark_max("total_dollars").alias("max_total"),
            avg("subtotal_cents").alias("avg_subtotal_cents")
        ).collect()[0]

        # Null/negative checks
        data_issues = df.agg(
            spark_sum(when(col("customer_id").isNull(), 1).otherwise(0)).alias("null_customer_id"),
            spark_sum(when(col("total_cents") < 0, 1).otherwise(0)).alias("negative_total"),
            spark_sum(when(col("subtotal_cents") < 0, 1).otherwise(0)).alias("negative_subtotal")
        ).collect()[0]

        quality_results = {
            "table": "orders",
            "total_records": total_records,
            "completeness": {
                "order_id_completeness": completeness_checks["order_id_count"] / total_records,
                "customer_id_completeness": completeness_checks["customer_id_count"] / total_records,
                "status_completeness": completeness_checks["status_count"] / total_records,
                "total_cents_completeness": completeness_checks["total_cents_count"] / total_records,
            },
            "quality_distribution": quality_distribution,
            "business_validation": {
                "invalid_total_calculations": invalid_totals,
                "invalid_total_percentage": (invalid_totals / total_records) * 100
            },
            "status_distribution": status_counts,
            "monetary_statistics": {
                "average_total_dollars": float(monetary_stats["avg_total"]) if monetary_stats["avg_total"] else 0,
                "min_total_dollars": float(monetary_stats["min_total"]) if monetary_stats["min_total"] else 0,
                "max_total_dollars": float(monetary_stats["max_total"]) if monetary_stats["max_total"] else 0,
                "average_subtotal_cents": float(monetary_stats["avg_subtotal_cents"]) if monetary_stats["avg_subtotal_cents"] else 0,
            },
            "data_issues": {
                "null_customer_id_count": data_issues["null_customer_id"],
                "negative_total_count": data_issues["negative_total"],
                "negative_subtotal_count": data_issues["negative_subtotal"],
            }
        }

    except Exception as e:
        quality_results = {"error": f"Error validating orders quality: {str(e)}"}

    return quality_results


def validate_customers_quality(spark: SparkSession) -> Dict[str, Any]:
    """Perform data quality checks on customers table."""
    quality_results = {}

    try:
        df = read_silver_data(spark, "customers")
        total_records = df.count()

        if total_records == 0:
            return {"error": "No customers data found in Silver layer"}

        # Email validation (basic pattern check)
        invalid_emails = df.filter(
            ~col("email").rlike("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
        ).count()

        # Completeness checks
        completeness = df.agg(
            (count("customer_id")).alias("customer_id_count"),
            (count("email")).alias("email_count"),
            (count("full_name")).alias("full_name_count"),
            (count("phone")).alias("phone_count")
        ).collect()[0]

        # Data quality distribution
        quality_status = df.groupBy("data_quality_status").count().collect()
        quality_distribution = {row["data_quality_status"]: row["count"] for row in quality_status}

        quality_results = {
            "table": "customers",
            "total_records": total_records,
            "completeness": {
                "customer_id_completeness": completeness["customer_id_count"] / total_records,
                "email_completeness": completeness["email_count"] / total_records,
                "full_name_completeness": completeness["full_name_count"] / total_records,
                "phone_completeness": completeness["phone_count"] / total_records,
            },
            "quality_distribution": quality_distribution,
            "email_validation": {
                "invalid_email_count": invalid_emails,
                "invalid_email_percentage": (invalid_emails / total_records) * 100
            }
        }

    except Exception as e:
        quality_results = {"error": f"Error validating customers quality: {str(e)}"}

    return quality_results


def validate_products_quality(spark: SparkSession) -> Dict[str, Any]:
    """Perform data quality checks on products table."""
    quality_results = {}

    try:
        df = read_silver_data(spark, "products")
        total_records = df.count()

        if total_records == 0:
            return {"error": "No products data found in Silver layer"}

        # Price validation
        price_stats = df.agg(
            spark_sum(when(col("price_cents") < 0, 1).otherwise(0)).alias("negative_prices"),
            spark_sum(when(col("price_cents") == 0, 1).otherwise(0)).alias("zero_prices"),
            avg("price_dollars").alias("avg_price"),
            spark_max("price_dollars").alias("max_price")
        ).collect()[0]

        # SKU validation (check for duplicates)
        duplicate_skus = df.groupBy("sku").count().filter(col("count") > 1).count()

        # Active/inactive distribution
        active_distribution = df.groupBy("active").count().collect()
        active_counts = {row["active"]: row["count"] for row in active_distribution}

        # Completeness
        completeness = df.agg(
            (count("product_id")).alias("product_id_count"),
            (count("sku")).alias("sku_count"),
            (count("name")).alias("name_count"),
            (count("price_cents")).alias("price_cents_count")
        ).collect()[0]

        # Data quality distribution
        quality_status = df.groupBy("data_quality_status").count().collect()
        quality_distribution = {row["data_quality_status"]: row["count"] for row in quality_status}

        quality_results = {
            "table": "products",
            "total_records": total_records,
            "completeness": {
                "product_id_completeness": completeness["product_id_count"] / total_records,
                "sku_completeness": completeness["sku_count"] / total_records,
                "name_completeness": completeness["name_count"] / total_records,
                "price_completeness": completeness["price_cents_count"] / total_records,
            },
            "quality_distribution": quality_distribution,
            "price_validation": {
                "negative_price_count": price_stats["negative_prices"],
                "zero_price_count": price_stats["zero_prices"],
                "average_price_dollars": float(price_stats["avg_price"]) if price_stats["avg_price"] else 0,
                "max_price_dollars": float(price_stats["max_price"]) if price_stats["max_price"] else 0,
            },
            "sku_validation": {
                "duplicate_sku_count": duplicate_skus
            },
            "active_distribution": active_counts
        }

    except Exception as e:
        quality_results = {"error": f"Error validating products quality: {str(e)}"}

    return quality_results


def run_data_freshness_check(**context) -> str:
    """Check data freshness across all tables."""
    spark = get_spark_session()

    try:
        freshness_metrics = calculate_data_freshness(spark)

        # Log results
        print("=== DATA FRESHNESS REPORT ===")
        for table, metrics in freshness_metrics.items():
            print(f"\n{table.upper()} Table:")
            if "error" in metrics:
                print(f"  Error: {metrics['error']}")
            else:
                print(f"  Records: {metrics['record_count']}")
                print(f"  Latest Ingestion: {metrics['latest_ingestion']}")
                print(f"  Latest Processing: {metrics['latest_processing']}")
                if metrics['processing_lag_minutes'] is not None:
                    print(f"  Processing Lag: {metrics['processing_lag_minutes']:.1f} minutes")

        # Store results in XCom for potential alerting
        context['task_instance'].xcom_push(key='freshness_metrics', value=freshness_metrics)

        return json.dumps(freshness_metrics, indent=2)

    finally:
        spark.stop()


def run_comprehensive_quality_check(**context) -> str:
    """Run comprehensive data quality checks on all Silver layer tables."""
    spark = get_spark_session()

    try:
        # Run quality checks for each table
        orders_quality = validate_orders_quality(spark)
        customers_quality = validate_customers_quality(spark)
        products_quality = validate_products_quality(spark)

        quality_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "orders": orders_quality,
            "customers": customers_quality,
            "products": products_quality
        }

        # Log summary
        print("=== DATA QUALITY REPORT ===")
        for table, results in quality_report.items():
            if table == "timestamp":
                continue

            print(f"\n{table.upper()} Quality Check:")
            if "error" in results:
                print(f"  Error: {results['error']}")
            else:
                print(f"  Total Records: {results['total_records']}")
                if "quality_distribution" in results:
                    print(f"  Quality Distribution: {results['quality_distribution']}")

        # Store results for potential alerting
        context['task_instance'].xcom_push(key='quality_report', value=quality_report)

        return json.dumps(quality_report, indent=2)

    finally:
        spark.stop()


def check_data_quality_alerts(**context) -> str:
    """Check if any data quality issues require alerting."""
    quality_report = context['task_instance'].xcom_pull(key='quality_report')

    alerts = []

    if quality_report:
        for table, results in quality_report.items():
            if table == "timestamp":
                continue

            if "error" in results:
                alerts.append(f"ERROR: {table} table has processing errors: {results['error']}")
                continue

            # Check for high failure rates
            if "quality_distribution" in results and "FAILED" in results["quality_distribution"]:
                total_records = results["total_records"]
                failed_records = results["quality_distribution"]["FAILED"]
                failure_rate = (failed_records / total_records) * 100

                if failure_rate > 10:  # Alert if more than 10% failure rate
                    alerts.append(f"HIGH FAILURE RATE: {table} has {failure_rate:.1f}% failed quality checks")

            # Check specific issues
            if table == "orders" and "business_validation" in results:
                invalid_percentage = results["business_validation"]["invalid_total_percentage"]
                if invalid_percentage > 5:
                    alerts.append(f"BUSINESS LOGIC ERROR: {invalid_percentage:.1f}% of orders have invalid total calculations")

    if alerts:
        alert_message = "DATA QUALITY ALERTS:\n" + "\n".join(alerts)
        print(alert_message)
        context['task_instance'].xcom_push(key='alerts', value=alerts)
        return alert_message
    else:
        print("No data quality alerts found.")
        return "No alerts"


# DAG Definition
with DAG(
    dag_id="data_quality_checks",
    default_args=DEFAULT_ARGS,
    description="Comprehensive data quality monitoring and alerting",
    schedule=timedelta(minutes=30),  # Run every 30 minutes
    start_date=datetime(2024, 9, 14),
    catchup=False,
    max_active_runs=1,
    tags=["data-quality", "monitoring", "silver-layer"],
) as dag:

    # Task to check data freshness
    freshness_check_task = PythonOperator(
        task_id="check_data_freshness",
        python_callable=run_data_freshness_check,
        doc_md="""
        ### Data Freshness Check

        Monitors the timeliness of data processing by checking:
        - Latest ingestion timestamp for each table
        - Latest Silver layer processing timestamp
        - Processing lag in minutes
        - Record counts per table

        Helps identify if the data pipeline is running smoothly and data is being processed in a timely manner.
        """
    )

    # Task to run comprehensive quality checks
    quality_check_task = PythonOperator(
        task_id="run_quality_checks",
        python_callable=run_comprehensive_quality_check,
        doc_md="""
        ### Comprehensive Quality Check

        Performs detailed data quality validation including:

        **Orders:**
        - Completeness checks for required fields
        - Business logic validation (total amount calculations)
        - Status value validation
        - Monetary amount validation (non-negative values)
        - Data quality flag distribution

        **Customers:**
        - Email format validation
        - Completeness checks
        - Data quality flag distribution

        **Products:**
        - Price validation (non-negative, not zero)
        - SKU uniqueness checks
        - Completeness validation
        - Active/inactive distribution
        """
    )

    # Task to evaluate alerts
    alert_check_task = PythonOperator(
        task_id="check_quality_alerts",
        python_callable=check_data_quality_alerts,
        doc_md="Evaluates quality check results and generates alerts for issues requiring attention."
    )

    # Define task dependencies
    freshness_check_task >> quality_check_task >> alert_check_task