from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook


def _build_sqlalchemy_url(conn_id: str) -> str:
    conn = BaseHook.get_connection(conn_id)
    user = conn.login or "postgres"
    password = conn.password or "postgres"
    host = conn.host or "localhost"
    port = conn.port or 5432
    schema = conn.schema or "main"
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{schema}"


def _create_schema(**_: dict) -> None:
    from script.db_sqlalchemy import create_schema

    url = _build_sqlalchemy_url("postgres_oltp")
    create_schema(url=url)


def _seed_sample(**_: dict) -> None:
    from script.db_sqlalchemy import seed_sample

    url = _build_sqlalchemy_url("postgres_oltp")
    seed_sample(url=url)


DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="init_and_seed_oltp",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["tutorial", "bootstrap"],
) as dag:

    create_schema = PythonOperator(
        task_id="create_schema",
        python_callable=_create_schema,
    )

    seed_sample = PythonOperator(
        task_id="seed_sample",
        python_callable=_seed_sample,
    )

    create_schema >> seed_sample
