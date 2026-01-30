from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any

_JSON_LD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self._title_parts: list[str] = []
        self.meta: dict[str, str] = {}

    @property
    def title(self) -> str | None:
        title = "".join(self._title_parts).strip()
        return title or None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
            return
        if tag != "meta":
            return
        attr_map = {key.lower(): value for key, value in attrs if value is not None}
        content = attr_map.get("content")
        if not content:
            return
        key = attr_map.get("property") or attr_map.get("name") or attr_map.get("itemprop")
        if key:
            self.meta.setdefault(key.lower(), content.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)


def _load_json(value: str) -> Any | None:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def extract_jsonld(html: str) -> list[dict]:
    jsonld_blocks = []
    for raw_block in _JSON_LD_RE.findall(html):
        block = raw_block.strip()
        if not block:
            continue
        parsed = _load_json(block)
        if parsed is None:
            continue
        if isinstance(parsed, list):
            jsonld_blocks.extend([item for item in parsed if isinstance(item, dict)])
        elif isinstance(parsed, dict):
            jsonld_blocks.append(parsed)
    return jsonld_blocks


def extract_dom_metadata(html: str) -> dict:
    parser = _MetaParser()
    parser.feed(html)
    parser.close()
    return {"title": parser.title, "meta": parser.meta}


def _normalize_types(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).lower() for item in value]
    if isinstance(value, str):
        return [value.lower()]
    return []


def _iter_jsonld_nodes(entries: list[dict]) -> list[dict]:
    nodes: list[dict] = []
    for entry in entries:
        if "@graph" in entry and isinstance(entry["@graph"], list):
            for node in entry["@graph"]:
                if isinstance(node, dict):
                    nodes.append(node)
        else:
            nodes.append(entry)
    return nodes


def _extract_from_jsonld(entries: list[dict]) -> dict:
    brand = None
    model = None
    identifiers: dict[str, str] = {}

    for node in _iter_jsonld_nodes(entries):
        types = _normalize_types(node.get("@type"))
        if "product" not in types:
            continue
        raw_brand = node.get("brand")
        if isinstance(raw_brand, dict):
            brand = raw_brand.get("name") or brand
        elif isinstance(raw_brand, str):
            brand = raw_brand or brand
        raw_model = node.get("model")
        if isinstance(raw_model, str):
            model = raw_model or model
        for key in ("sku", "mpn", "gtin8", "gtin12", "gtin13", "gtin14"):
            value = node.get(key)
            if isinstance(value, str) and value:
                identifiers.setdefault(key, value)
        if brand and model:
            break

    digest: dict[str, Any] = {}
    if brand:
        digest["brand"] = brand
    if model:
        digest["model"] = model
    if identifiers:
        digest["identifiers"] = identifiers
    return digest


def _extract_from_dom(dom: dict) -> dict:
    meta = dom.get("meta") or {}
    brand_keys = ("product:brand", "brand", "itemprop:brand")
    model_keys = ("model", "product:model", "itemprop:model")
    brand = next((meta.get(key) for key in brand_keys if meta.get(key)), None)
    model = next((meta.get(key) for key in model_keys if meta.get(key)), None)
    digest: dict[str, Any] = {}
    if brand:
        digest["brand"] = brand
    if model:
        digest["model"] = model
    return digest


def build_snapshot_extraction(html: str) -> tuple[dict, dict]:
    jsonld = extract_jsonld(html)
    dom = extract_dom_metadata(html)
    digest = _extract_from_jsonld(jsonld)
    if not digest:
        digest = _extract_from_dom(dom)
    extracted = {"jsonld": jsonld, "dom": dom}
    return extracted, digest
