import json
import socket
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime


# Configuration
LOAD_BALANCER_PORT = 8000
BACKEND_START_PORT = 8001
BACKEND_MAX_PORT = 8010
LOG_FILE = "loadbalancerLog"

# Load balancing state
backends = []
current_backend_index = 0
_lock = threading.Lock()


def discover_backends():
    """Discover which app service backends are running"""
    global backends
    discovered = []
    for port in range(BACKEND_START_PORT, BACKEND_MAX_PORT + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if result == 0:
                discovered.append(port)
        except Exception:
            pass
    return discovered


def log_request(request_type, path, backend_port, status, response_time_ms):
    """Log request to loadbalancerLog file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_entry = {
        "timestamp": timestamp,
        "type": request_type,
        "path": path,
        "routed_to": f"http://127.0.0.1:{backend_port}",
        "status": status,
        "response_time_ms": response_time_ms
    }
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"Error writing to log: {e}")


def get_next_backend():
    """Get the next backend in round-robin fashion"""
    global current_backend_index, backends
    with _lock:
        if not backends:
            return None
        backend = backends[current_backend_index % len(backends)]
        current_backend_index += 1
        return backend


class LoadBalancerHandler(BaseHTTPRequestHandler):
    def forward_request(self, method, path, body=None, headers=None):
        """Forward request to backend and return response"""
        # Discover backends on each request (to handle dynamic scaling)
        global backends
        backends = discover_backends()
        
        if not backends:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No backends available"}).encode())
            log_request(method, path, "none", 503, 0)
            return
        
        backend_port = get_next_backend()
        backend_url = f"http://127.0.0.1:{backend_port}{path}"
        
        start_time = time.time()
        try:
            if method == "GET":
                with urllib.request.urlopen(backend_url) as resp:
                    response_body = resp.read()
                    status = resp.status
            elif method == "POST":
                req = urllib.request.Request(
                    backend_url,
                    data=body,
                    headers=headers or {}
                )
                with urllib.request.urlopen(req) as resp:
                    response_body = resp.read()
                    status = resp.status
            else:
                self.send_response(405)
                self.end_headers()
                return
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Send response back to client
            self.send_response(status)
            self.end_headers()
            self.wfile.write(response_body)
            
            # Log request
            log_request(method, path, backend_port, status, elapsed_ms)
        
        except urllib.error.HTTPError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            log_request(method, path, backend_port, e.code, elapsed_ms)
        
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Backend error: {str(e)}"}).encode())
            log_request(method, path, backend_port, 500, elapsed_ms)

    def do_GET(self):
        """Handle GET requests"""
        path = self.path
        self.forward_request("GET", path)

    def do_POST(self):
        """Handle POST requests"""
        path = self.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        
        headers = {"Content-Type": "application/json"}
        self.forward_request("POST", path, body, headers)

    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        pass


def main():
    global backends
    
    print("Load Balancer starting...")
    print(f"Scanning for backends on ports {BACKEND_START_PORT}-{BACKEND_MAX_PORT}...")
    
    backends = discover_backends()
    
    if backends:
        print(f"Found {len(backends)} backend(s): {backends}")
    else:
        print("Warning: No backends found. Please start app services before making requests.")
    
    try:
        server = HTTPServer(("127.0.0.1", LOAD_BALANCER_PORT), LoadBalancerHandler)
        print(f"Load Balancer running on http://127.0.0.1:{LOAD_BALANCER_PORT}")
        print(f"Routing requests using round-robin to discovered backends.")
        print(f"Logging to: {LOG_FILE}")
        server.serve_forever()
    except OSError as e:
        print(f"Error: Could not bind to port {LOAD_BALANCER_PORT}. {e}")


if __name__ == "__main__":
    main()
