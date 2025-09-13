from __future__ import annotations

from datetime import datetime, timedelta
import csv
import os

from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

OUTPUT_DIR = "/opt/airflow/dags/exports"


def export_orders(ds: str, **_: dict) -> None:
    hook = PostgresHook(postgres_conn_id="postgres_oltp")
    conn = hook.get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT o.order_id, o.customer_id, o.status, o.currency,
               o.subtotal_cents, o.shipping_cents, o.tax_cents, o.total_cents,
               o.created_at
        FROM orders o
        WHERE DATE(o.created_at) = DATE(%s)
        ORDER BY o.order_id
        """,
        (ds,),
    )
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"orders_{ds}.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "order_id", "customer_id", "status", "currency",
            "subtotal_cents", "shipping_cents", "tax_cents", "total_cents",
            "created_at",
        ])
        for row in cursor.fetchall():
            writer.writerow(row)


with DAG(
    dag_id="export_orders_csv",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["tutorial", "export"],
) as dag:

    run_export = PythonOperator(
        task_id="run_export",
        python_callable=export_orders,
    )
