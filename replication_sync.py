import json
import os


BASE_DIR = os.path.dirname(__file__)
US_CATALOG_PATH = os.path.join(BASE_DIR, "catalog_us.json")
EU_CATALOG_PATH = os.path.join(BASE_DIR, "catalog_eu.json")
US_CATALOG2_PATH = os.path.join(BASE_DIR, "catalog_us2.json")
EU_CATALOG2_PATH = os.path.join(BASE_DIR, "catalog_eu2.json")


def _load_catalog(path):
    with open(path, "r") as f:
        return json.load(f)


def _write_catalog(path, catalog):
    with open(path, "w") as f:
        json.dump(catalog, f, indent=2)
        f.write("\n")


def sync_catalog(source_path, target_path):
    source_catalog = _load_catalog(source_path)
    target_catalog = [dict(product) for product in source_catalog]

    _write_catalog(target_path, target_catalog)
    return {
        "status": "synced",
        "source": os.path.basename(source_path),
        "target": os.path.basename(target_path),
        "products_updated": len(target_catalog)
    }


def sync_catalog_us_to_eu():
    return sync_catalog(US_CATALOG_PATH, EU_CATALOG_PATH)


def sync_onhand_us_to_eu():
    return sync_catalog_us_to_eu()


def sync_all_us_to_eu():
    return [
        sync_catalog(US_CATALOG_PATH, EU_CATALOG_PATH),
        sync_catalog(US_CATALOG2_PATH, EU_CATALOG2_PATH)
    ]


if __name__ == "__main__":
    print(json.dumps(sync_all_us_to_eu()))
