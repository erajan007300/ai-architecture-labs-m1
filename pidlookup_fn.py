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


def _region_catalog_sources(region):
    prefix = f"catalog_{region}"
    return sorted(
        filename
        for filename in os.listdir(os.path.dirname(__file__))
        if filename.startswith(prefix) and filename.endswith(".json")
    )


def product_list(region, filters=None):
    start_time = time.time()
    filters = filters or {}
    catalog_sources = _region_catalog_sources(region)
    products = []
    available_attributes = {}

    for catalog_source in catalog_sources:
        with open(_catalog_path(catalog_source), "r") as f:
            catalog = json.load(f)

        for product in catalog:
            for attribute in product:
                available_attributes[attribute.lower()] = attribute
            products.append(product)

    normalized_filters = {}
    for attribute, value in filters.items():
        catalog_attribute = available_attributes.get(attribute.lower())
        if catalog_attribute is None:
            return {
                "error": "invalid request: attribute not found",
                "catalogs_searched": catalog_sources,
                "region": region,
                "response_time_seconds": time.time() - start_time
            }
        normalized_filters[catalog_attribute] = value

    matching_products = [
        product
        for product in products
        if all(str(product.get(attribute)) == value for attribute, value in normalized_filters.items())
    ]

    return {
        "products": matching_products,
        "total_products": len(matching_products),
        "catalogs_searched": catalog_sources,
        "region": region,
        "response_time_seconds": time.time() - start_time
    }


def product_id(pid, region="us"):
    time.sleep(0.1)
    catalog, catalog_source = _load_catalog(region, pid)
    for product in catalog:
        if product["pID"] == pid:
            return product, catalog_source
    return None, catalog_source
