import json
import os
import time


# Load catalog data from file
_data_path = os.path.join(os.path.dirname(__file__), "catalog_us.json")
with open(_data_path, "r") as f:
    catalog = json.load(f)


def product_id(pid):
    time.sleep(0.1)
    for product in catalog:
        if product["pID"] == pid:
            return product
    return None
