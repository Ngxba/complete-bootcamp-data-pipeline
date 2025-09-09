#!/usr/bin/env bash
set -euo pipefail

# Always run from the repository root (where docker-compose.yaml lives)
cd "$(dirname "$0")"

# Pull latest base images (non-fatal if offline)
docker compose pull || true

# Build and start in detached mode
docker compose up -d --build

echo "✅ Services started. Use ./stop.sh to stop them."


