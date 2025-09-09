from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List

from faker import Faker


fake = Faker()


@dataclass
class CustomerGenerator:
    def generate(self) -> Dict[str, Any]:
        return {
            "email": fake.unique.safe_email(),
            "full_name": fake.name(),
            "phone": fake.phone_number(),
        }


@dataclass
class AddressGenerator:
    def generate(self, customer_id: int) -> Dict[str, Any]:
        address = fake.address()
        lines = [l.strip() for l in address.split("\n") if l.strip()]
        line1 = lines[0] if lines else fake.street_address()
        city = fake.city()
        state = fake.state()
        postal_code = fake.postcode()
        country_code = fake.country_code()
        return {
            "customer_id": customer_id,
            "label": random.choice(["home", "work", "other"]),
            "line1": line1[:200],
            "line2": None,
            "city": city[:100],
            "state": state[:100],
            "postal_code": postal_code[:20],
            "country_code": country_code[:2],
            "is_default": random.choice([True, False]),
        }


@dataclass
class ProductGenerator:
    def generate(self) -> Dict[str, Any]:
        name = fake.unique.catch_phrase()
        sku = f"SKU-{fake.unique.bothify(text='????-########')}"
        price_cents = random.randint(100, 50_000)
        return {
            "sku": sku[:64],
            "name": name[:200],
            "price_cents": price_cents,
            "active": random.choice([True, True, True, False]),
        }


@dataclass
class InventoryGenerator:
    def generate(self, product_id: int) -> Dict[str, Any]:
        qty_on_hand = random.randint(0, 1_000)
        qty_reserved = random.randint(0, max(0, qty_on_hand // 2))
        return {
            "product_id": product_id,
            "qty_on_hand": qty_on_hand,
            "qty_reserved": qty_reserved,
        }


@dataclass
class OrderGenerator:
    def generate(self, customer_id: int, ship_to_address_id: int) -> Dict[str, Any]:
        currency = random.choice(["USD", "EUR", "GBP", "JPY", "AUD"])
        status = random.choice(["PLACED", "PAID", "FULFILLED", "CANCELED"]) 
        # Monetary fields are set by caller based on items
        return {
            "customer_id": customer_id,
            "ship_to_address_id": ship_to_address_id,
            "status": status,
            "currency": currency,
            "subtotal_cents": 0,
            "shipping_cents": 0,
            "tax_cents": 0,
            "total_cents": 0,
        }


@dataclass
class OrderItemGenerator:
    def generate(self, order_id: int, product_id: int, unit_price_cents: int) -> Dict[str, Any]:
        qty = random.randint(1, 5)
        return {
            "order_id": order_id,
            "product_id": product_id,
            "qty": qty,
            "unit_price_cents": unit_price_cents,
        }


@dataclass
class PaymentGenerator:
    def generate(self, order_id: int, amount_cents: int) -> Dict[str, Any]:
        provider = random.choice(["stripe", "paypal", "adyen", "square"])
        status = random.choice(["AUTHORIZED", "CAPTURED", "REFUNDED", "FAILED"])
        provider_ref = f"{provider[:3]}_{fake.unique.bothify(text='????????########')}"
        return {
            "order_id": order_id,
            "provider": provider,
            "provider_ref": provider_ref[:100],
            "amount_cents": amount_cents,
            "status": status,
        }


@dataclass
class ShipmentGenerator:
    def generate(self, order_id: int) -> Dict[str, Any]:
        status = random.choice(["READY", "IN_TRANSIT", "DELIVERED"])
        return {
            "order_id": order_id,
            "carrier": random.choice(["UPS", "FedEx", "DHL", "USPS", None]),
            "tracking_no": fake.bothify(text="TRK##########"),
            "status": status,
        }


def compute_order_totals(items: List[Dict[str, Any]]) -> Dict[str, int]:
    subtotal = sum(i["qty"] * i["unit_price_cents"] for i in items)
    shipping = 0 if subtotal > 5_000 else 999
    tax = int(subtotal * 0.1)
    total = subtotal + shipping + tax
    return {
        "subtotal_cents": subtotal,
        "shipping_cents": shipping,
        "tax_cents": tax,
        "total_cents": total,
    }


