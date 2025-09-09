from __future__ import annotations

import random
from typing import List, Dict, Any

from faker import Faker

from data_generators import (
    CustomerGenerator,
    AddressGenerator,
    ProductGenerator,
    InventoryGenerator,
    OrderGenerator,
    OrderItemGenerator,
    PaymentGenerator,
    ShipmentGenerator,
    compute_order_totals,
)


fake = Faker()


def main() -> None:
    num_customers = 5
    num_products = 10

    customer_gen = CustomerGenerator()
    address_gen = AddressGenerator()
    product_gen = ProductGenerator()
    inventory_gen = InventoryGenerator()
    order_gen = OrderGenerator()
    order_item_gen = OrderItemGenerator()
    payment_gen = PaymentGenerator()
    shipment_gen = ShipmentGenerator()

    customers: List[Dict[str, Any]] = []
    addresses: List[Dict[str, Any]] = []
    products: List[Dict[str, Any]] = []
    inventories: List[Dict[str, Any]] = []
    orders: List[Dict[str, Any]] = []
    order_items: List[Dict[str, Any]] = []
    payments: List[Dict[str, Any]] = []
    shipments: List[Dict[str, Any]] = []

    # Generate customers and addresses
    for cid in range(1, num_customers + 1):
        customers.append({"customer_id": cid, **customer_gen.generate()})
        # 1-2 addresses per customer
        for _ in range(random.randint(1, 2)):
            addr = address_gen.generate(customer_id=cid)
            addr_id = len(addresses) + 1
            addresses.append({"address_id": addr_id, **addr})

    # Generate products and inventory
    for pid in range(1, num_products + 1):
        prod = product_gen.generate()
        products.append({"product_id": pid, **prod})
        inventories.append(inventory_gen.generate(product_id=pid))

    # Orders per customer
    for cid in range(1, num_customers + 1):
        # pick a default address for shipping
        cust_addrs = [a for a in addresses if a["customer_id"] == cid]
        if not cust_addrs:
            continue
        ship_addr_id = cust_addrs[0]["address_id"]

        # 0-3 orders per customer
        for _ in range(random.randint(0, 3)):
            order_id = len(orders) + 1
            order = order_gen.generate(customer_id=cid, ship_to_address_id=ship_addr_id)
            orders.append({"order_id": order_id, **order})

            # 1-5 unique items per order (avoid duplicate product per order)
            num_items = random.randint(1, 5)
            items_for_order: List[Dict[str, Any]] = []
            selected_products = random.sample(products, k=min(num_items, len(products)))
            for product in selected_products:
                item = order_item_gen.generate(
                    order_id=order_id,
                    product_id=product["product_id"],
                    unit_price_cents=product["price_cents"],
                )
                order_items.append(item)
                items_for_order.append(item)

            # totals and related records
            totals = compute_order_totals(items_for_order)
            orders[-1].update(totals)

            # payments and shipments (optional)
            if orders[-1]["status"] in ("PAID", "FULFILLED"):
                payments.append(payment_gen.generate(order_id=order_id, amount_cents=totals["total_cents"]))
            if orders[-1]["status"] in ("PLACED", "PAID", "FULFILLED"):
                shipments.append(shipment_gen.generate(order_id=order_id))

    # Print a tiny preview
    print(f"customers: {len(customers)} | addresses: {len(addresses)} | products: {len(products)} | orders: {len(orders)}")

    # Example: show one order with items
    if orders:
        oid = orders[0]["order_id"]
        items = [i for i in order_items if i["order_id"] == oid]
        print("Example order:", orders[0])
        print("Items:", items)


if __name__ == "__main__":
    main()


