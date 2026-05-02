# Lab 1 - Simulated Database Requests

## Architecture

```
clientsimulator → appservice
                    ├── (GET /product/{pid}) → pidlookup_fn → catalog_us.json / catalog_eu.json
                    └── (POST /place_order) → place_order_fn → catalog_us.json / catalog_eu.json
```

## Files

### pidlookup_fn.py
Data access module. Contains the `product_id(pid)` function which simulates a synchronous database lookup with a 100ms delay. Loads catalog data from `catalog_us.json` at startup.

### place_order_fn.py
Data access module. Contains the `place_order(region, pid, qty)` function which:
- Validates the region parameter ("us" or "eu")
- Loads the appropriate catalog file (catalog_us.json or catalog_eu.json)
- Finds the product by ID
- Reduces the OnHand value by the requested quantity (allows negative values)
- Saves the updated catalog back to file
- Returns success or error details

### catalog_us.json
Simulated database table ("catalog") with 5 US product records. Columns: pID, Name, Seller, Price, Country, is_searchable, OnHand.

### catalog_eu.json
Simulated database table ("catalog") with EU product records. Same structure as catalog_us.json.

### appservice.py
Lightweight HTTP server running on `http://127.0.0.1:8000`. Handles both product lookup and order placement operations.

**Endpoints:**
- `GET /product/{pid}` — Product lookup. Returns the product record as JSON, or a 404 error if not found. Uses service-level cache for performance.
  - **Cache**: Stores results in memory. First request for a product ID incurs 100ms database lookup; subsequent requests are served from cache.
  - **Response enrichment**:
    - `inventory_status` is set to `Inventory Unavailable` when `OnHand` is `ERROR`.
    - If `OnHand` is a number greater than `0`, `inventory_status` is `InStock`.
    - If `OnHand` is `0`, `inventory_status` is `OutofStock`.
    - `purchase_allowed` is `FALSE` when `inventory_status` is `Inventory Unavailable`, otherwise `TRUE`.
    - `userMessage` is added when inventory state is unavailable.

- `POST /place_order` — Place an order. Accepts JSON payload with `region`, `pid`, and `qty`. Returns confirmation and writes operation details to testoutput file (JSON format with status, product details, original and new inventory levels).

### clientsimulator.py
Interactive client simulator that prompts the user to select an operation:
- **Option 1 - Product Lookup**: Simulates multiple sequential requests. Prompts for number of requests, fetches product data via GET /product endpoint, and writes results to testoutput file.
- **Option 2 - Place Order**: Places an order by prompting for region (us/eu), product ID, and quantity. Sends POST request to /place_order endpoint and writes operation summary to testoutput file.

Exits after one operation completes.

## Usage

```bash
# 1. Start the app service
python3 appservice.py

# 2. In a separate terminal, run the client simulator
python3 clientsimulator.py
```

Follow the on-screen prompts to select and execute an operation. Results are written to the `testoutput` file.
