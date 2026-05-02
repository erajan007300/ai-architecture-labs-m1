import json
import os
import random
import simulation_config


def place_order(region, pid, qty):
    """
    Place an order by reducing the onhand quantity for a product in the specified region's catalog.
    
    Args:
        region: "us" or "eu" to specify which catalog to use
        pid: product ID to look up
        qty: quantity to reduce from onhand
    
    Returns:
        dict with status, product data, or error message
    """
    # Validate region
    if region not in ["us", "eu"]:
        return {
            "status": "error",
            "error": f"Invalid region '{region}'. Must be 'us' or 'eu'."
        }
    
    # Construct catalog path
    catalog_filename = f"catalog_{region}.json"
    catalog_path = os.path.join(os.path.dirname(__file__), catalog_filename)
    
    # Load catalog
    try:
        with open(catalog_path, "r") as f:
            catalog = json.load(f)
    except FileNotFoundError:
        return {
            "status": "error",
            "error": f"Catalog file '{catalog_filename}' not found."
        }
    except json.JSONDecodeError:
        return {
            "status": "error",
            "error": f"Failed to parse catalog file '{catalog_filename}'."
        }
    
    # Find product
    product = None
    for item in catalog:
        if item["pID"] == pid:
            product = item
            break
    
    if product is None:
        return {
            "status": "error",
            "error": f"Product ID {pid} not found in {catalog_filename}."
        }
    
    # Store original onhand value
    original_onhand = product["OnHand"]
    
    # Update onhand (allow negative)
    if isinstance(original_onhand, int):
        product["OnHand"] = original_onhand - qty
    else:
        return {
            "status": "error",
            "error": f"Cannot process order: OnHand value is '{original_onhand}' (not a number)."
        }
    
    # Save catalog
    try:
        with open(catalog_path, "w") as f:
            json.dump(catalog, f, indent=2)
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to save catalog file: {str(e)}"
        }
    
    # Return success with product details
    return {
        "status": "success",
        "product": product,
        "original_onhand": original_onhand,
        "qty_ordered": qty,
        "new_onhand": product["OnHand"],
        "region": region
    }


def process_payment():
    """
    Simulate charging payment.
    
    Returns:
        int: 1 for successful payment
    """
    return 1


def create_order_number():
    """
    Generate a simulated order number in format "xx-xxxx-xxx".
    
    Returns:
        str: Order number in format "xx-xxxx-xxx"
    """
    part1 = str(random.randint(10, 99))
    part2 = str(random.randint(1000, 9999))
    part3 = str(random.randint(100, 999))
    return f"{part1}-{part2}-{part3}"


def checkout(region, pid, qty):
    """
    Simulate a complete checkout process: place order, process payment, and create order.
    
    Args:
        region: "us" or "eu" to specify which catalog to use
        pid: product ID to order
        qty: quantity to order
    
    Returns:
        str: Order number on success, or dict with error on failure
    """
    # Step 1: Place the order (reduce inventory)
    order_result = place_order(region, pid, qty)
    if order_result.get("status") == "error":
        return order_result
    
    # Step 2: Check for inventory failure
    if simulation_config.INV_FAIL:
        return {
            "status": "error",
            "error": "INV ERROR"
        }
    
    # Step 3: Process payment
    payment_result = process_payment()
    if payment_result != 1:
        return {
            "status": "error",
            "error": "Payment processing failed"
        }
    
    # Step 4: Create order number
    order_number = create_order_number()
    
    return order_number
