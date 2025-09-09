-- People & places
CREATE TABLE customers (
  customer_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  email VARCHAR(255) UNIQUE NOT NULL,
  full_name VARCHAR(200) NOT NULL,
  phone VARCHAR(40),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE addresses (
  address_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id),
  label VARCHAR(50),
  line1 VARCHAR(200) NOT NULL,
  line2 VARCHAR(200),
  city VARCHAR(100) NOT NULL,
  state VARCHAR(100),
  postal_code VARCHAR(20),
  country_code CHAR(2) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE
);

-- Catalog & stock
CREATE TABLE products (
  product_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  sku VARCHAR(64) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE inventory (
  product_id BIGINT PRIMARY KEY REFERENCES products(product_id),
  qty_on_hand INTEGER NOT NULL CHECK (qty_on_hand >= 0),
  qty_reserved INTEGER NOT NULL DEFAULT 0 CHECK (qty_reserved >= 0)
);

-- Orders
CREATE TABLE orders (
  order_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id),
  ship_to_address_id BIGINT NOT NULL REFERENCES addresses(address_id),
  status VARCHAR(20) NOT NULL CHECK (status IN ('PLACED','PAID','FULFILLED','CANCELED')),
  currency CHAR(3) NOT NULL,
  subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents >= 0),
  shipping_cents INTEGER NOT NULL CHECK (shipping_cents >= 0),
  tax_cents INTEGER NOT NULL CHECK (tax_cents >= 0),
  total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
  order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  product_id BIGINT NOT NULL REFERENCES products(product_id),
  qty INTEGER NOT NULL CHECK (qty > 0),
  unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
  PRIMARY KEY (order_id, product_id)
);

-- Payments & shipments (optional but realistic)
CREATE TABLE payments (
  payment_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id),
  provider VARCHAR(40) NOT NULL,
  provider_ref VARCHAR(100) NOT NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
  status VARCHAR(20) NOT NULL CHECK (status IN ('AUTHORIZED','CAPTURED','REFUNDED','FAILED')),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (provider, provider_ref)
);

CREATE TABLE shipments (
  shipment_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id),
  carrier VARCHAR(40),
  tracking_no VARCHAR(80),
  status VARCHAR(20) NOT NULL CHECK (status IN ('READY','IN_TRANSIT','DELIVERED')),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Pragmatic indexes
CREATE INDEX idx_orders_customer_created ON orders(customer_id, created_at DESC);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_payments_order ON payments(order_id);
