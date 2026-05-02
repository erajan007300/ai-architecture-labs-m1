import json
import time
import urllib.request


CATALOG_PATH = "catalog_us.json"
SERVICE_URL = "http://127.0.0.1:8000"


def load_pids():
    with open(CATALOG_PATH, "r") as f:
        catalog = json.load(f)
    return [p["pID"] for p in catalog]


def fetch_product(pid):
    url = f"{SERVICE_URL}/product/{pid}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def product_lookup():
    """Run product lookup workflow"""
    x = int(input("Enter number of requests: "))
    pids = load_pids()
    start = time.perf_counter()
    with open('testoutput', 'a') as f:
        for i in range(x):
            pid = pids[i % len(pids)]
            resp = fetch_product(pid)
            resp['timestamp'] = time.time()
            f.write(json.dumps(resp) + '\n')
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"Completed {x} requests in {elapsed_ms:.2f} ms")


def place_order():
    """Run place order workflow"""
    region = input("Enter region (us/eu): ").strip().lower()
    pid = int(input("Enter product ID: "))
    qty = int(input("Enter quantity: "))
    
    payload = {
        "region": region,
        "pid": pid,
        "qty": qty
    }
    
    url = f"{SERVICE_URL}/place_order"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print("Order placed successfully. Check testoutput for details.")
    except urllib.error.HTTPError as e:
        print(f"Error: {e.reason}")


def main():
    print("=== Client Simulator ===")
    print("1. Product Lookup")
    print("2. Place Order")
    choice = input("Select operation (1 or 2): ").strip()
    
    if choice == "1":
        product_lookup()
    elif choice == "2":
        place_order()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
