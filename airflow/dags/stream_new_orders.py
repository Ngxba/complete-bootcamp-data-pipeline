from __future__ import annotations

from datetime import datetime, timedelta
import random
import time

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=1),
}


def _insert_bounded_orders(count: int = 10, interval: float = 0.5, **_: dict) -> None:
    hook = PostgresHook(postgres_conn_id="postgres_oltp")
    conn = hook.get_conn()
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(
        """
        SELECT a.address_id, a.customer_id
        FROM addresses a
        ORDER BY a.address_id
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("No addresses found; seed the database first.")
        return

    try:
        for i in range(count):
            addr_id, cust_id = random.choice(rows)
            cur.execute(
                """
                INSERT INTO orders(
                    customer_id, ship_to_address_id, status, currency,
                    subtotal_cents, shipping_cents, tax_cents, total_cents
                ) VALUES (%s, %s, 'PLACED', 'USD', 0, 0, 0, 0)
                RETURNING order_id
                """,
                (cust_id, addr_id),
            )
            order_id = cur.fetchone()[0]
            conn.commit()
            print(f"Inserted order_id={order_id} for customer_id={cust_id} ship_to_address_id={addr_id} ({i+1}/{count})")
            if interval and interval > 0:
                time.sleep(interval)
    finally:
        cur.close()
        conn.close()


with DAG(
    dag_id="stream_new_orders",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    params={"count": 10, "interval": 0.5},
    tags=["tutorial", "stream"],
) as dag:

    run_stream = PythonOperator(
        task_id="run_stream",
        python_callable=lambda **ctx: _insert_bounded_orders(
            count=int(ctx["params"].get("count", 10)),
            interval=float(ctx["params"].get("interval", 0.5)),
        ),
    )
