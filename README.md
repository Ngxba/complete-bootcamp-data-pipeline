VIDEO 1:
- Add dockerfile for PostgreSQL
- Add docker-compose
- Test init script and check data in dbeaver

VIDEO 2
- init python project/env
- create class to make data
- interact with those data class
- create sample data
- create stream data

VIDEO 3:
kafka + debezium docker setup
have to set "plugin.name": "pgoutput" in extra attribute. docs: https://debezium.io/documentation/reference/stable/connectors/postgresql.html
run stream or create sample data.
-> run oke, view stream, etc

VIDEO 4:
Ensure the Airflow Postgres provider is available. The official apache/airflow:2.9.3 image typically includes it; if not, install apache-airflow-providers-postgres in the image.
