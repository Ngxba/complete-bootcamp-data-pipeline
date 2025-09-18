#!/usr/bin/env bash
set -euo pipefail

# Always run from the repository root (where docker-compose.yaml lives)
cd "$(dirname "$0")"

# Function to show usage
show_usage() {
    echo "Usage: $0 <service_name> [service_name2] [...]"
    echo ""
    echo "Restart specific Docker Compose services"
    echo ""
    echo "Available services:"
    echo "  postgres-oltp      - Main PostgreSQL OLTP database"
    echo "  postgres-airflow   - Airflow metadata database"
    echo "  zookeeper         - Kafka coordination service"
    echo "  kafka             - Message broker"
    echo "  connect           - Debezium Connect service"
    echo "  debezium-ui       - Debezium web interface"
    echo "  kafka-ui          - Kafka web interface"
    echo "  minio             - Object storage (S3-compatible)"
    echo "  minio-init        - MinIO bucket initialization"
    echo "  spark-master      - Spark cluster master"
    echo "  spark-worker      - Spark cluster worker"
    echo "  spark-history     - Spark history server"
    echo "  jupyter           - Jupyter Lab with PySpark"
    echo "  airflow-apiserver - Airflow web UI and API"
    echo "  airflow-scheduler - Airflow task scheduler"
    echo "  airflow-dag-processor - Airflow DAG processor"
    echo "  airflow-triggerer - Airflow triggerer service"
    echo ""
    echo "Examples:"
    echo "  $0 minio                    # Restart MinIO only"
    echo "  $0 kafka connect           # Restart Kafka and Debezium Connect"
    echo "  $0 spark-master spark-worker # Restart Spark cluster"
    echo "  $0 postgres-oltp kafka connect # Restart database and CDC pipeline"
}

# Check if at least one service is provided
if [ $# -eq 0 ]; then
    echo "❌ Error: No service specified"
    echo ""
    show_usage
    exit 1
fi

# Check for help flag
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_usage
    exit 0
fi

SERVICES=("$@")

echo "🔄 Restarting services: ${SERVICES[*]}"
echo ""

# Stop the specified services
echo "⏹️  Stopping services..."
docker compose stop "${SERVICES[@]}"

# Remove containers to ensure clean restart
echo "🗑️  Removing containers..."
docker compose rm -f "${SERVICES[@]}"

# Start the services again
echo "🚀 Starting services..."
docker compose up -d "${SERVICES[@]}"

echo ""
echo "✅ Successfully restarted: ${SERVICES[*]}"
echo ""

# Show status of restarted services
echo "📊 Service status:"
docker compose ps "${SERVICES[@]}"