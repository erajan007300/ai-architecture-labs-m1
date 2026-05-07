import json
import os
import time


def _load_catalog(region):
    data_path = os.path.join(os.path.dirname(__file__), f"catalog_{region}.json")
    with open(data_path, "r") as f:
        return json.load(f)


def product_id(pid, region="us"):
    time.sleep(0.1)
    catalog = _load_catalog(region)
    for product in catalog:
        if product["pID"] == pid:
            return product
    return None
