import json
import os
import time


def _catalog_filename(region, pid):
    shard_suffix = "" if pid % 2 == 1 else "2"
    return f"catalog_{region}{shard_suffix}.json"


def _catalog_path(catalog_source):
    return os.path.join(os.path.dirname(__file__), catalog_source)


def _load_catalog(region, pid):
    catalog_source = _catalog_filename(region, pid)
    data_path = _catalog_path(catalog_source)
    with open(data_path, "r") as f:
        return json.load(f), catalog_source


def product_id(pid, region="us"):
    time.sleep(0.1)
    catalog, catalog_source = _load_catalog(region, pid)
    for product in catalog:
        if product["pID"] == pid:
            return product, catalog_source
    return None, catalog_source
