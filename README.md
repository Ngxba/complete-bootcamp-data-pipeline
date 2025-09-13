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

### ** Current Status:**

All services are now running successfully:
- **Airflow API Server**: `http://localhost:8088` (port 8088)
- **Debezium UI**: `http://localhost:8080` (port 8080) 
- **Kafka UI**: `http://localhost:8081` (port 8081)
- **Kafka Connect**: `http://localhost:8083` (port 8083)

### **🔑 Access Information:**

- **Airflow Web UI**: http://localhost:8088
- **Username**: `airflow` (or `admin` if you set custom credentials)
- **Password**: `airflow` (or `admin` if you set custom credentials)

### **📋 Services Running:**

- ✅ **airflow-apiserver** - API server (port 8088)
- ✅ **airflow-scheduler** - Task scheduler
- ✅ **airflow-dag-processor** - DAG processor
- ✅ **airflow-triggerer** - Triggerer service
- ✅ **airflow-init** - Database initialization (completed successfully)
- ✅ **postgres-airflow** - Airflow metadata database
- ✅ **postgres-oltp** - Your OLTP database
- ✅ **kafka, zookeeper, connect** - Kafka infrastructure
- ✅ **debezium-ui, kafka-ui** - Management UIs
