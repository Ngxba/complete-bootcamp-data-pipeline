from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

def dq_checks(**context):
    hook = PostgresHook(postgres_conn_id="postgres_oltp")
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    # Fail if negative totals
    cursor.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM orders WHERE total_cents < 0 OR subtotal_cents < 0 OR shipping_cents < 0 OR tax_cents < 0) THEN
                RAISE EXCEPTION 'Found negative monetary values in orders';
            END IF;
        END
        $$;
    """)
    
    # Fail if any order items have non-positive qty or negative price
    cursor.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM order_items WHERE qty <= 0 OR unit_price_cents < 0) THEN
                RAISE EXCEPTION 'Found invalid order_items (qty<=0 or negative price)';
            END IF;
        END
        $$;
    """)
    
    # Fail if any order references missing customer or address
    cursor.execute("""
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
    """)
    
    conn.commit()
    cursor.close()
    conn.close()


with DAG(
    dag_id="data_quality_checks",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["tutorial", "dq"],
) as dag:

    dq_checks_task = PythonOperator(
        task_id="dq_checks",
        python_callable=dq_checks,
    )
