#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Stop services and remove orphans
docker compose down --remove-orphans

echo "🛑 Services stopped."


