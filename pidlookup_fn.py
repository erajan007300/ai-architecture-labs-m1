import json
import os
import time


def _catalog_path(region, pid):
    shard_suffix = "" if pid % 2 == 1 else "2"
    return os.path.join(os.path.dirname(__file__), f"catalog_{region}{shard_suffix}.json")


def _load_catalog(region, pid):
    data_path = _catalog_path(region, pid)
    with open(data_path, "r") as f:
        return json.load(f)


def product_id(pid, region="us"):
    time.sleep(0.1)
    catalog = _load_catalog(region, pid)
    for product in catalog:
        if product["pID"] == pid:
            return product
    return None
