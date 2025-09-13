from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="data_quality_checks",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule_interval="@daily",
    catchup=False,
    tags=["tutorial", "dq"],
) as dag:

    dq_checks = PostgresOperator(
        task_id="dq_checks",
        postgres_conn_id="postgres_oltp",
        sql="""
        -- Fail if negative totals
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM orders WHERE total_cents < 0 OR subtotal_cents < 0 OR shipping_cents < 0 OR tax_cents < 0) THEN
                RAISE EXCEPTION 'Found negative monetary values in orders';
            END IF;
        END
        $$;

        -- Fail if any order items have non-positive qty or negative price
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM order_items WHERE qty <= 0 OR unit_price_cents < 0) THEN
                RAISE EXCEPTION 'Found invalid order_items (qty<=0 or negative price)';
            END IF;
        END
        $$;

        -- Fail if any order references missing customer or address
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM orders o
                LEFT JOIN customers c ON c.customer_id = o.customer_id
                LEFT JOIN addresses a ON a.address_id = o.ship_to_address_id
                WHERE c.customer_id IS NULL OR a.address_id IS NULL
            ) THEN
                RAISE EXCEPTION 'Found orders referencing missing customer or address';
            END IF;
        END
        $$;
        """,
    )
