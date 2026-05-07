import json
import os


BASE_DIR = os.path.dirname(__file__)
US_CATALOG_PATH = os.path.join(BASE_DIR, "catalog_us.json")
EU_CATALOG_PATH = os.path.join(BASE_DIR, "catalog_eu.json")


def _load_catalog(path):
    with open(path, "r") as f:
        return json.load(f)


def _write_catalog(path, catalog):
    with open(path, "w") as f:
        json.dump(catalog, f, indent=2)
        f.write("\n")


def sync_onhand_us_to_eu():
    us_catalog = _load_catalog(US_CATALOG_PATH)
    eu_catalog = _load_catalog(EU_CATALOG_PATH)
    us_onhand_by_pid = {product["pID"]: product["OnHand"] for product in us_catalog}

    updated_count = 0
    for product in eu_catalog:
        pid = product["pID"]
        if pid in us_onhand_by_pid:
            product["OnHand"] = us_onhand_by_pid[pid]
            updated_count += 1

    _write_catalog(EU_CATALOG_PATH, eu_catalog)
    return {
        "status": "synced",
        "source": "catalog_us.json",
        "target": "catalog_eu.json",
        "products_updated": updated_count
    }


if __name__ == "__main__":
    print(json.dumps(sync_onhand_us_to_eu()))
