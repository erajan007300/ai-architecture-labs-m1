import json
import queue
import socket
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pidlookup_fn import product_id, product_list
from place_order_fn import place_order

REQUEST_QUEUE = queue.Queue()
RESPONSE_MAP = {}
RESPONSE_EVENTS = {}
CACHE = {}
RATE_LIMITS = {
    "products": {"limit": 5, "window": 1, "penalty": 10},
    "place_order": {"limit": 1, "window": 1, "penalty": 10},
}
RATE_STATE = {}
REQUEST_LOG = "request_log.json"
RATE_LIMIT_MESSAGE = "you've made too many requests.  Please try again shortly."
_lock = threading.Lock()


def worker():
    while True:
        req_id, pid, region = REQUEST_QUEUE.get()
        cache_key = (region, pid)
        with _lock:
            if cache_key in CACHE:
                result, catalog_source = CACHE[cache_key]
                cache_status = "HIT"
            else:
                result, catalog_source = product_id(pid, region)
                CACHE[cache_key] = (result, catalog_source)
                cache_status = "MISS"
        with _lock:
            RESPONSE_MAP[req_id] = (result, cache_status, catalog_source)
            RESPONSE_EVENTS[req_id].set()
        REQUEST_QUEUE.task_done()


def check_rate_limit(client_ip, bucket):
    config = RATE_LIMITS[bucket]
    now = time.time()
    key = (client_ip, bucket)

    with _lock:
        state = RATE_STATE.get(key, {"window_start": now, "count": 0, "penalty_until": 0})

        if now < state["penalty_until"]:
            return False

        if now - state["window_start"] >= config["window"]:
            state["window_start"] = now
            state["count"] = 0

        state["count"] += 1
        if state["count"] > config["limit"]:
            state["penalty_until"] = now + config["penalty"]
            RATE_STATE[key] = state
            return False

        RATE_STATE[key] = state
        return True


def append_request_log(endpoint, client_ip, response_code):
    now = datetime.now()
    log_entry = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "endpoint": endpoint,
        "client_ip": client_ip,
        "response_code": response_code,
    }
    try:
        with open(REQUEST_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Error writing to request log: {e}")


class Handler(BaseHTTPRequestHandler):
    def send_response(self, code, message=None):
        self._response_code = code
        super().send_response(code, message)

    def client_ip(self):
        forwarded_for = self.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return self.client_address[0]

    def send_rate_limit_response(self):
        self.send_response(429)
        self.end_headers()
        self.wfile.write(json.dumps({"error": RATE_LIMIT_MESSAGE}).encode())

    def log_current_request(self):
        append_request_log(
            urlparse(self.path).path,
            self.client_ip(),
            getattr(self, "_response_code", 500),
        )

    def do_GET(self):
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            if path == "/products":
                if not check_rate_limit(self.client_ip(), "products"):
                    self.send_rate_limit_response()
                    return

                query_params = parse_qs(parsed_url.query)
                region_values = query_params.get("region")
                if not region_values or not region_values[0]:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "invalid request: region value missing"}).encode())
                    return

                region = region_values[0].lower()
                if region not in ("us", "eu"):
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid region"}).encode())
                    return

                filters = {
                    key: values[0]
                    for key, values in query_params.items()
                    if key != "region" and values
                }
                result = product_list(region, filters)

                if "error" in result:
                    self.send_response(400)
                else:
                    self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
                return

            if not path.startswith("/product/"):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Not found"}).encode())
                return

            if not check_rate_limit(self.client_ip(), "products"):
                self.send_rate_limit_response()
                return

            pid_str = path[len("/product/"):]
            try:
                pid = int(pid_str)
            except ValueError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid product ID"}).encode())
                return
            region = parse_qs(parsed_url.query).get("region", ["us"])[0].lower()
            if region not in ("us", "eu"):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid region"}).encode())
                return

            req_id = id(self)
            event = threading.Event()
            with _lock:
                RESPONSE_EVENTS[req_id] = event

            REQUEST_QUEUE.put((req_id, pid, region))
            event.wait()

            with _lock:
                result, cache_status, catalog_source = RESPONSE_MAP.pop(req_id)
                del RESPONSE_EVENTS[req_id]

            handled_by_port = self.server.server_address[1]

            if result is None:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"Product {pid} not found",
                    "cache_status": cache_status,
                    "catalog_source": catalog_source,
                    "handled_by_port": handled_by_port
                }).encode())
            else:
                response = dict(result)
                response["cache_status"] = cache_status
                response["catalog_source"] = catalog_source
                response["handled_by_port"] = handled_by_port
                onhand = response.get("OnHand")
                if onhand == "ERROR":
                    response["inventory_status"] = "Inventory Unavailable"
                    response["purchase_allowed"] = False
                    response["userMessage"] = "Sorry, our inventory system is down. We're working to restore service soon."
                elif isinstance(onhand, int) and onhand > 0:
                    response["inventory_status"] = "InStock"
                    response["purchase_allowed"] = True
                elif onhand == 0:
                    response["inventory_status"] = "OutofStock"
                    response["purchase_allowed"] = False
                else:
                    response["inventory_status"] = onhand
                    response["purchase_allowed"] = True

                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
        finally:
            self.log_current_request()

    def do_POST(self):
        try:
            path = self.path
            if path == "/clear_cache":
                with _lock:
                    entries_cleared = len(CACHE)
                    CACHE.clear()

                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "cache_cleared",
                    "entries_cleared": entries_cleared
                }).encode())
                return

            if path != "/place_order":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Not found"}).encode())
                return

            if not check_rate_limit(self.client_ip(), "place_order"):
                self.send_rate_limit_response()
                return

            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body.decode())
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return

            # Extract parameters
            region = data.get("region")
            pid = data.get("pid")
            qty = data.get("qty")

            if region is None or pid is None or qty is None:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing parameters: region, pid, qty required"}).encode())
                return

            # Call place_order function
            result = place_order(region, pid, qty)

            # Write result to testoutput file
            output_data = {
                "timestamp": time.time(),
                "operation": "place_order",
                "request": {"region": region, "pid": pid, "qty": qty},
                "response": result
            }

            try:
                with open("testoutput", "a") as f:
                    f.write(json.dumps(output_data, indent=2) + "\n")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Failed to write to testoutput: {str(e)}"}).encode())
                return

            # Send response
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "confirmed"}).encode())
        finally:
            self.log_current_request()

    def log_message(self, format, *args):
        pass


def find_available_port(start_port=8001, max_port=8010):
    """Find the first available port starting from start_port"""
    for port in range(start_port, max_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", port))
            sock.close()
            return port
        except OSError:
            # Port is in use, try next one
            continue
    raise RuntimeError(f"No available ports found between {start_port} and {max_port}")


def main():
    # Auto-detect the port to use
    port = find_available_port()
    
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"App service running on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
