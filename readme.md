# Lab 1 - Simulated Database Requests with Load Balancing

## Architecture

```
clientsimulator (http://127.0.0.1:8000)
    ↓
loadbalancer (port 8000) — round-robin routing
    ├── appservice (port 8001)
    │       ├── (GET /product/{pid}) → pidlookup_fn → catalog_us.json / catalog_eu.json
    │       └── (POST /place_order) → place_order_fn → catalog_us.json / catalog_eu.json
    ├── appservice (port 8002)
    │       ├── (GET /product/{pid}) → pidlookup_fn → catalog_us.json / catalog_eu.json
    │       └── (POST /place_order) → place_order_fn → catalog_us.json / catalog_eu.json
    └── appservice (port 8003, etc.)
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
Lightweight HTTP server that automatically selects an available port starting from `8001`. Multiple instances can run simultaneously, each on their own port (8001, 8002, 8003, etc.). Auto-detects occupied ports and claims the next available one.

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
Interactive client simulator that sends requests to the load balancer on port 8000. Prompts the user to select an operation:
- **Option 1 - Product Lookup**: Simulates multiple sequential requests. Prompts for number of requests, fetches product data via GET /product endpoint, and writes results to testoutput file.
- **Option 2 - Place Order**: Places an order by prompting for region (us/eu), product ID, and quantity. Sends POST request to /place_order endpoint and writes operation summary to testoutput file.

Exits after one operation completes.

### loadbalancer.py
Load balancer that listens on port 8000 and distributes requests to discovered backend app services using **round-robin** routing. 

**Features:**
- Automatically discovers running app service instances on ports 8001-8010
- Routes each request to the next available backend in round-robin order
- Discovers backends dynamically, allowing on-the-fly scaling
- Logs all requests to `loadbalancerLog` file with timestamps, request details, routing decisions, and response times
- Returns 503 error if no backends are available

**Log Format:**
Each entry in `loadbalancerLog` contains:
- `timestamp`: When the request was received
- `type`: Request method (GET or POST)
- `path`: The request path
- `routed_to`: Which backend handled the request
- `status`: HTTP response status code
- `response_time_ms`: Time to complete the request

## Usage

### Basic Setup (1 App Service + Load Balancer)

```bash
# Terminal 1: Start the load balancer (port 8000)
python3 loadbalancer.py

# Terminal 2: Start an app service (auto-selects port 8001)
python3 appservice.py

# Terminal 3: Run the client simulator
python3 clientsimulator.py
```

### Multi-Instance Setup (2+ App Services + Load Balancer)

```bash
# Terminal 1: Start the load balancer (port 8000)
python3 loadbalancer.py

# Terminal 2: Start first app service (auto-selects port 8001)
python3 appservice.py

# Terminal 3: Start second app service (auto-selects port 8002)
python3 appservice.py

# Terminal 4: Start third app service (auto-selects port 8003)
python3 appservice.py

# Terminal 5: Run the client simulator
python3 clientsimulator.py
```

The load balancer will automatically discover all running app services and distribute requests round-robin across them.

## Output Files

- **testoutput**: Results from product lookups and order operations (appended by app services)
- **loadbalancerLog**: Load balancer request routing log with timestamps and response metrics
