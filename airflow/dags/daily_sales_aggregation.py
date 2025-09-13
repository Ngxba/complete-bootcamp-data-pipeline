from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

def create_table(**context):
    hook = PostgresHook(postgres_conn_id="postgres_oltp")
    conn = hook.get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_sales (
            day date not null,
            product_id bigint not null,
            orders integer not null,
            qty integer not null,
            revenue_cents integer not null,
            primary key (day, product_id)
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()


def upsert_yesterday(**context):
    hook = PostgresHook(postgres_conn_id="postgres_oltp")
    conn = hook.get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        WITH base AS (
            SELECT
                DATE(o.created_at) AS day,
                oi.product_id,
                COUNT(DISTINCT o.order_id) AS orders,
                SUM(oi.qty) AS qty,
                SUM(oi.qty * oi.unit_price_cents) AS revenue_cents
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE DATE(o.created_at) = DATE(%s)
            GROUP BY 1, 2
        )
        INSERT INTO daily_sales(day, product_id, orders, qty, revenue_cents)
        SELECT day, product_id, orders, qty, revenue_cents FROM base
        ON CONFLICT (day, product_id)
        DO UPDATE SET
          orders = EXCLUDED.orders,
          qty = EXCLUDED.qty,
          revenue_cents = EXCLUDED.revenue_cents;
    """, (context['ds'],))
    conn.commit()
    cursor.close()
    conn.close()


with DAG(
    dag_id="daily_sales_aggregation",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["tutorial", "analytics"],
) as dag:

    create_table_task = PythonOperator(
        task_id="create_table",
        python_callable=create_table,
    )

    upsert_yesterday_task = PythonOperator(
        task_id="upsert_yesterday",
        python_callable=upsert_yesterday,
    )

    create_table_task >> upsert_yesterday_task
