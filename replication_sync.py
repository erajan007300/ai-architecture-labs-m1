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
    target_catalog = _load_catalog(target_path)
    source_product_by_pid = {product["pID"]: product for product in source_catalog}

    updated_count = 0
    for index, product in enumerate(target_catalog):
        source_product = source_product_by_pid.get(product["pID"])
        if source_product is not None:
            target_catalog[index] = dict(source_product)
            updated_count += 1

    _write_catalog(target_path, target_catalog)
    return {
        "status": "synced",
        "source": os.path.basename(source_path),
        "target": os.path.basename(target_path),
        "products_updated": updated_count
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
