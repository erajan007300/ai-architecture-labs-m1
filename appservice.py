import json
import queue
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pidlookup_fn import product_id
from place_order_fn import place_order

REQUEST_QUEUE = queue.Queue()
RESPONSE_MAP = {}
RESPONSE_EVENTS = {}
CACHE = {}
_lock = threading.Lock()


def worker():
    while True:
        req_id, pid = REQUEST_QUEUE.get()
        with _lock:
            if pid in CACHE:
                result = CACHE[pid]
            else:
                result = product_id(pid)
                CACHE[pid] = result
        with _lock:
            RESPONSE_MAP[req_id] = result
            RESPONSE_EVENTS[req_id].set()
        REQUEST_QUEUE.task_done()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        if not path.startswith("/product/"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
            return

        pid_str = path[len("/product/"):]
        try:
            pid = int(pid_str)
        except ValueError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid product ID"}).encode())
            return

        req_id = id(self)
        event = threading.Event()
        with _lock:
            RESPONSE_EVENTS[req_id] = event

        REQUEST_QUEUE.put((req_id, pid))
        event.wait()

        with _lock:
            result = RESPONSE_MAP.pop(req_id)
            del RESPONSE_EVENTS[req_id]

        if result is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Product {pid} not found"}).encode())
        else:
            response = dict(result)
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
                response["purchase_allowed"] = True
            else:
                response["inventory_status"] = onhand
                response["purchase_allowed"] = True

            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        path = self.path
        if path != "/place_order":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
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

    def log_message(self, format, *args):
        pass


def main():
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    server = HTTPServer(("127.0.0.1", 8000), Handler)
    print("App service running on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
