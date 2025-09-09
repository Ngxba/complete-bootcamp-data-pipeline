## Complete Bootcamp Data Pipeline

This project spins up PostgreSQL and provides Python scripts to create schema, seed data, and stream new orders for testing ingestion pipelines.

### Prerequisites
- Docker + Docker Compose
- Python managed by `uv` (recommended)

### Services
Start/stop PostgreSQL locally:
```bash
./start.sh
# ... later
./stop.sh
```

The database URL used by scripts defaults to:
```
postgresql+psycopg2://postgres:postgres@localhost:5432/main
```
You can override via the `DATABASE_URL` environment variable.

### Python Environment
Install dependencies (if needed):
```bash
uv sync
```

### Scripts

#### script/db_sqlalchemy.py
- **Purpose**: ORM models and utilities to create schema and seed the database.
- **What it does**:
  - Defines tables: `customers`, `addresses`, `products`, `inventory`, `orders`, `order_items`, `payments`, `shipments`.
  - `create_schema()` creates tables if they don’t exist.
  - `seed_sample()` inserts a small realistic dataset.
- **Usage**:
```bash
uv run python script/db_sqlalchemy.py

# or explicitly
uv run python -c "from script.db_sqlalchemy import create_schema, seed_sample; create_schema(); seed_sample()"
```

#### script/data_generators.py
- **Purpose**: Helper generators for fake data (customers, addresses, products, orders, items, payments, shipments).
- **Usage**: Imported by other scripts; rarely run directly.

#### script/generate_sample.py
- **Purpose**: Generate an in-memory sample dataset (does not write to DB). Useful to inspect what the fake data looks like.
- **Output**: Prints counts and one example order with its items.
- **Usage**:
```bash
uv run python script/generate_sample.py
```

#### script/stream_orders.py
- **Purpose**: Continuously insert new `orders` rows every few seconds using existing `customers` and `addresses`. It does not create new customers or order items.
- **Flags**:
  - `--interval`: seconds between inserts (default: 3.0)
  - `--count`: number of orders to insert; `0` means run until interrupted
  - `--url`: database URL (defaults to `DATABASE_URL` env or the local default)
- **Usage**:
```bash
uv run python script/stream_orders.py --interval 3 --count 0

# Insert 10 orders quickly
uv run python script/stream_orders.py --interval 0.5 --count 10

# Custom connection string
uv run python script/stream_orders.py --url postgresql+psycopg2://postgres:postgres@localhost:5432/main
```

### Environment variables
- **DATABASE_URL**: SQLAlchemy URL to the Postgres database. Example:
```
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/main
```

### Notes
- `order_items` has a composite primary key `(order_id, product_id)`. Scripts avoid duplicating products within the same order.
- Use DBeaver or `psql` to inspect the `main` database after seeding/streaming.

