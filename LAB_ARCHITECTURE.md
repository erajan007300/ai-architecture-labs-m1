# Lab Architecture: Simulated E-Commerce System

## 1. Purpose

This lab simulates a **multi-region e-commerce backend** demonstrating:
- HTTP service with request queuing and worker threads
- In-memory caching layer for read optimization
- Multi-tenant data (US and EU regional catalogs)
- Inventory state machine with error handling
- Simulated database latency (100ms per lookup)
- Client-driven testing scenarios

It is designed to teach distributed systems concepts: caching strategies, concurrency patterns, regional data partitioning, and fault tolerance simulation.

---

## 2. File-by-File Summary

| File | Role | Key Responsibility |
|------|------|-------------------|
| **appservice.py** | HTTP Server | Main entry point. Runs ThreadPoolExecutor-style worker with request queue. Handles GET /product/{pid}, POST /place_order, and POST /clear_cache endpoints. Maintains in-memory cache and enriches inventory responses. |
| **pidlookup_fn.py** | Data Access (Read) | Simulates database lookup. Returns product record by pID and region or None. Injects 100ms artificial latency via `time.sleep(0.1)`. Loads catalog_us.json or catalog_eu.json for each lookup. |
| **place_order_fn.py** | Data Access (Write) | Reduces OnHand inventory by qty. Supports region parameter to select catalog file (us/eu). Writes updated catalog back to JSON file. Handles non-numeric OnHand as error case. |
| **replication_sync.py** | Replication Utility | Copies OnHand values from catalog_us.json to catalog_eu.json for matching pID values. No conflict resolution. |
| **clientsimulator.py** | Test Client | Interactive CLI. Two workflows: (1) sequential product lookups with timing, (2) single order placement. Appends results to testoutput file. |
| **simulation_config.py** | Configuration | Defines environment toggles: `PARTITION_ERROR` (unused), `INV_FAIL=True` (unused—intended to trigger inventory failures). |
| **catalog_us.json** | Data Store | JSON array of 5 products (pID 1-5). US region catalog. Persistent storage for inventory state. |
| **catalog_eu.json** | Data Store | JSON array of 5 products (pID 1-5). EU region catalog. Mirror of US with different OnHand values. |
| **test.py** | Stub | Single-line comment placeholder for future tax calculation logic. Not yet integrated. |
| **testoutput** | Results Log | Line-delimited JSON appended by appservice and clientsimulator. Logs product lookups and order operations with timestamps. |

---

## 3. Request / Data Flow

### Product Lookup Flow (GET /product/{pid}?region={us|eu})
```
ClientSimulator
    ↓
GET /product/{pid}?region={us|eu}
    ↓
appservice.do_GET()
    ├─ Parse {pid} from URL
    ├─ Parse region query parameter (defaults to us)
    ├─ Create request ID and event
    ├─ Enqueue (req_id, pid, region) to REQUEST_QUEUE
    ├─ Wait on event (blocks request thread)
    ↓
worker thread (background)
    ├─ Dequeue (req_id, pid, region)
    ├─ Check CACHE[(region, pid)]
    │  ├─ If hit: use cached result
    │  └─ If miss: call product_id(pid, region) → 100ms sleep + catalog lookup
    ├─ Store result in RESPONSE_MAP[req_id]
    ├─ Signal event
    ↓
appservice.do_GET() (resumed)
    ├─ Retrieve result from RESPONSE_MAP
    ├─ Enrich: compute inventory_status, purchase_allowed, userMessage
    ├─ Return JSON 200 or 404
    ↓
ClientSimulator
    └─ Append to testoutput with timestamp
```

### Order Placement Flow (POST /place_order)
```
ClientSimulator
    ↓
POST /place_order {region, pid, qty}
    ↓
appservice.do_POST()
    ├─ Parse JSON payload
    ├─ Validate required fields
    ├─ Call place_order(region, pid, qty)
    ↓
place_order_fn.place_order()
    ├─ Validate region ∈ {us, eu}
    ├─ Load catalog_{region}.json
    ├─ Find product by pID
    ├─ Compute new_onhand = OnHand - qty (allows negative)
    ├─ Write updated catalog back to JSON file
    ├─ Return {status, product, original_onhand, new_onhand}
    ↓
appservice.do_POST() (continued)
    ├─ Write result to testoutput file
    ├─ Return JSON 200 {status: "confirmed"}
    ↓
ClientSimulator
    └─ Print completion message
```

### Cache Clear Flow (POST /clear_cache)
```
Client/Admin
    ↓
POST /clear_cache
    ↓
appservice.do_POST()
    ├─ Clear all entries from CACHE under lock
    ├─ Return JSON 200 {status: "cache_cleared", entries_cleared: <count>}
```

### Replication Sync Flow (python3 replication_sync.py)
```
Operator
    ↓
python3 replication_sync.py
    ↓
replication_sync.sync_onhand_us_to_eu()
    ├─ Load catalog_us.json and catalog_eu.json
    ├─ Match products by pID
    ├─ Copy each matching US OnHand value into the EU product record
    ├─ Write updated catalog_eu.json
    ├─ Return {status: "synced", source, target, products_updated}
```

---

## 4. Current Capabilities

1. **Product Lookup with Caching**
   - First request for a product ID incurs 100ms latency
   - `GET /product/{pid}?region=us` reads from catalog_us.json
   - `GET /product/{pid}?region=eu` reads from catalog_eu.json
   - Requests without a region default to the US catalog
   - Subsequent requests served instantly from CACHE for the same region and product ID
   - `POST /clear_cache` clears all cached product lookup entries
   - Cache is per-appservice instance (no TTL, no eviction)

2. **Inventory Status Computation**
   - OnHand > 0 → inventory_status = "InStock", purchase_allowed = True
   - OnHand = 0 → inventory_status = "OutofStock", purchase_allowed = False
   - OnHand = "ERROR" → inventory_status = "Inventory Unavailable", purchase_allowed = False + user message
   - OnHand < 0 → purchase_allowed = True (negative inventory allowed)

3. **Regional Order Placement**
   - Route orders to US or EU catalog independently
   - Inventory reduced immediately and persisted to JSON file

4. **One-Way Inventory Replication**
   - `python3 replication_sync.py` copies OnHand values from catalog_us.json to catalog_eu.json for matching pID values
   - EU product metadata remains unchanged; only OnHand is overwritten
   - No conflict resolution, merge policy, or order placement changes

5. **Concurrent Request Handling**
   - Worker thread processes product lookups asynchronously
   - Multiple GET requests can queue and are served sequentially by single worker

6. **Result Logging**
   - All operations (product fetch, order place) logged to testoutput with timestamp
   - JSON format for programmatic analysis

---

## 5. Configuration Flags and Modes

Located in **simulation_config.py**:

| Flag | Current | Purpose | Status |
|------|---------|---------|--------|
| `PARTITION_ERROR` | False | Would simulate catalog partition failure / unavailability | Defined but **not used** in code |
| `INV_FAIL` | True | Would trigger "ERROR" OnHand value to test inventory service degradation | Defined but **not used** in code |

These flags are placeholders for future enhancement—configuration is parsed but not consumed by any module.

---

## 6. Data Model Fields

### Product Record (JSON schema)
```json
{
  "pID": <int>,                    // Product ID (1-indexed, unique per catalog)
  "Name": <string>,                // Product name (e.g., "Surface 13\"")
  "Seller": <string>,              // Merchant name (e.g., "Microsoft", "Amazon")
  "Price": <int>,                  // USD/EUR price
  "Country": <string>,             // Geolocation (e.g., "US", "UK", "ES")
  "is_searchable": <0 | 1>,        // Flag for search inclusion (not yet used)
  "OnHand": <int | "ERROR">        // Inventory quantity; can be negative; "ERROR" triggers unavailability
}
```

### Enriched Response (computed by appservice on GET)
```json
{
  // ... all product fields above ...
  "inventory_status": <"InStock" | "OutofStock" | "Inventory Unavailable">,
  "purchase_allowed": <true | false>,
  "userMessage": <string | omitted>   // Only populated when inventory unavailable
}
```

### Order Request Payload
```json
{
  "region": "us" | "eu",
  "pid": <int>,
  "qty": <int>
}
```

### Order Response
```json
{
  "status": "success" | "error",
  "product": { /* product record */ },
  "original_onhand": <int>,
  "qty_ordered": <int>,
  "new_onhand": <int>,
  "region": <string>,
  "error": <string>  // if status = error
}
```

---

## 7. Behaviors Already Simulated

1. **Database Latency**: 100ms artificial sleep in pidlookup_fn before each cache miss
2. **Inventory Depletion**: OnHand decremented by order qty; can go negative (overselling)
3. **System Failure Mode**: OnHand = "ERROR" string triggers inventory unavailability response
4. **Multi-Tenant Isolation**: US and EU catalogs maintained separately; product lookups and orders routed by region
5. **Eventual Consistency**: Order writes sync to disk immediately (no staged commits)
6. **Client-Side Timing**: clientsimulator records elapsed time for request batches
7. **Request Queuing**: Multiple concurrent GET requests queue and serialize through worker thread

---

## 8. Known Limitations & Messy Areas

### Critical Gaps
- **Unused Config Flags**: `PARTITION_ERROR` and `INV_FAIL` are defined but never consulted. No code path triggers failures based on these toggles.
- **Race Condition in Cache**: CACHE dictionary accessed under `_lock`, but cache-check-then-use pattern could theoretically race if cache is cleared externally (unlikely but fragile).
- **No Transaction Semantics**: If order placement crashes after OnHand reduction but before file write, state is corrupted. No rollback mechanism.
- **Negative Inventory Allowed**: System allows overselling; no validation that qty ≤ OnHand.

### Design Debt
- **Single Worker Thread**: All GET requests serialize through one worker. Bottleneck under high concurrency; no thread pool.
- **In-Memory Cache Without Eviction**: Cache grows unbounded. No TTL, no LRU, no max-size policy.
- **Hard-Coded Port**: Service bound to `127.0.0.1:8000` with no configuration.
- **Blocking I/O**: File read/write operations block the worker thread. No async I/O or connection pooling.
- **Stub Functions**: `process_payment()` in place_order_fn.py returns hardcoded 1 (unused).
- **Missing Error Handling**: No validation of product fields (e.g., Name, Price could be missing or malformed).
- **Implicit Regional Mapping**: Country field in product record is independent of region (us/eu) parameter; no validation that products belong to correct region.

### Experimental / Unfinished
- **test.py**: Single-line comment about tax calculation. Not integrated into order flow.
- **is_searchable Field**: Defined in catalog but never consulted. No search endpoint exists.

---

## 9. Where Future Labs Should Extend

### Immediate Extensions
1. **Activate Config Flags**
   - Implement PARTITION_ERROR to return 500 errors for a time window
   - Implement INV_FAIL to randomly set OnHand = "ERROR" in responses
   - Add TTL-based flag reset to simulate recovery

2. **Add Thread Pool**
   - Replace single worker with ThreadPoolExecutor
   - Measure concurrency improvement

3. **Implement Transaction Safety**
   - Wrap order placement in try/except with file backup
   - Demonstrate rollback on failure

4. **Search Endpoint**
   - Use is_searchable field to filter products
   - Support filtering by Country, Seller, or price range
   - Teach query optimization

### Distributed Systems Topics
5. **Cache Invalidation**
   - Add endpoint to clear cache
   - Implement TTL-based expiration
   - Explore cache stampede / thundering herd

6. **Replication**
   - Replicate orders to audit log (separate file or database)
   - Extend the one-way OnHand sync with conflict resolution
   - Demonstrate eventual consistency

7. **Load Balancing**
   - Run multiple appservice instances
   - Add a reverse proxy (nginx/HAProxy) to distribute requests
   - Measure failover behavior

8. **Monitoring & Observability**
   - Add metrics: request latency, cache hit rate, error rate
   - Export to Prometheus or statsd
   - Create dashboards

9. **Fault Injection**
   - Randomly corrupt OnHand values during order placement
   - Simulate network timeouts in clientsimulator
   - Demo resilience patterns (retry, circuit breaker, bulkhead)

10. **API Versioning & Backward Compatibility**
    - Rename fields or add optional fields
    - Test client compatibility

### Data Integrity
11. **Inventory Reconciliation**
    - Implement audit log scan to detect discrepancies
    - Add checksum validation to catalog JSON
    - Teach optimistic locking or version vectors

### Payment Integration
12. **Complete process_payment()**
    - Integrate with a mock payment API
    - Handle declined cards, timeout scenarios
    - Teach saga pattern for distributed transactions

---

## Quick Start

```bash
# Terminal 1: Start the app service
python3 appservice.py

# Terminal 2: Run interactive client
python3 clientsimulator.py
# Follow prompts to run product lookup or place order

# View results
cat testoutput
```

---

## Summary for Architecture Review

This lab is a **teaching-first simulation** of an e-commerce system. It demonstrates:
- **Concurrency**: Request queuing and worker pattern
- **Caching**: Simple in-memory cache with no eviction
- **State Management**: File-based inventory storage with eventual consistency
- **Error Handling**: Graceful degradation via OnHand = "ERROR" state
- **Observability**: Timestamped JSON logging of all operations

The architecture is intentionally simplified (single worker, no transactions, no TTL) to leave room for students to extend and improve it through successive labs.
