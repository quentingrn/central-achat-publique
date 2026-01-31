from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from modules.snapshot.adapters.schemas import ExtractionMethod, SnapshotStatus


@dataclass(frozen=True)
class ExtractionResult:
    method: ExtractionMethod
    status: SnapshotStatus
    extracted_json: dict
    digest_json: dict
    digest_hash: str | None
    errors_json: dict | None = None
    missing_critical_json: dict | None = None


class _HtmlSignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.jsonld_blocks: list[str] = []
        self._in_jsonld = False
        self._jsonld_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
            return
        if tag == "meta":
            attr_map = {key.lower(): (value or "") for key, value in attrs}
            content = attr_map.get("content", "").strip()
            if not content:
                return
            if "property" in attr_map:
                key = f"property:{attr_map['property'].lower()}"
                self.meta[key] = content
            if "name" in attr_map:
                key = f"name:{attr_map['name'].lower()}"
                self.meta[key] = content
            return
        if tag == "script":
            attr_map = {key.lower(): (value or "") for key, value in attrs}
            if attr_map.get("type", "").lower() == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            return
        if tag == "script" and self._in_jsonld:
            content = "".join(self._jsonld_chunks).strip()
            if content:
                self.jsonld_blocks.append(content)
            self._in_jsonld = False
            self._jsonld_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_title and self.title is None:
            stripped = data.strip()
            if stripped:
                self.title = stripped
        if self._in_jsonld:
            self._jsonld_chunks.append(data)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _first_str(value: Any) -> str | None:
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                normalized = _normalize_text(item)
                if normalized:
                    return normalized
    return None


def _extract_brand(value: Any) -> str | None:
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, dict):
        return _normalize_text(value.get("name"))
    if isinstance(value, list):
        for item in value:
            brand = _extract_brand(item)
            if brand:
                return brand
    return None


def _iter_jsonld_nodes(obj: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        nodes.append(obj)
        for value in obj.values():
            nodes.extend(_iter_jsonld_nodes(value))
    elif isinstance(obj, list):
        for item in obj:
            nodes.extend(_iter_jsonld_nodes(item))
    return nodes


def _has_type(node: dict[str, Any], type_name: str) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, str):
        return node_type == type_name
    if isinstance(node_type, list):
        return type_name in node_type
    return False


def _extract_product_from_jsonld(nodes: list[dict[str, Any]]) -> tuple[dict | None, list[str]]:
    signals: list[str] = []
    for node in nodes:
        if not _has_type(node, "Product"):
            continue
        signals.append("jsonld:Product")
        title = _normalize_text(node.get("name"))
        brand = _extract_brand(node.get("brand"))
        model = _normalize_text(node.get("model"))
        mpn = _normalize_text(node.get("mpn"))
        sku = _normalize_text(node.get("sku"))
        gtin = None
        for key in ("gtin13", "gtin14", "gtin12", "gtin8", "gtin"):
            gtin = _normalize_text(node.get(key))
            if gtin:
                break
        product = {
            "title": title,
            "brand": brand,
            "model": model,
            "mpn": mpn,
            "gtin": gtin,
            "sku": sku,
        }
        return product, signals
    return None, signals


def _extract_product_from_dom(parser: _HtmlSignalParser) -> tuple[dict | None, list[str]]:
    signals: list[str] = []
    title = None
    if parser.meta.get("property:og:title"):
        title = _normalize_text(parser.meta.get("property:og:title"))
        if title:
            signals.append("dom:meta:og:title")
    if not title and parser.meta.get("name:twitter:title"):
        title = _normalize_text(parser.meta.get("name:twitter:title"))
        if title:
            signals.append("dom:meta:twitter:title")
    if not title and parser.title:
        title = _normalize_text(parser.title)
        if title:
            signals.append("dom:title")

    brand = None
    if parser.meta.get("property:product:brand"):
        brand = _normalize_text(parser.meta.get("property:product:brand"))
        if brand:
            signals.append("dom:meta:product:brand")

    if not title and not brand:
        return None, signals
    product = {
        "title": title,
        "brand": brand,
        "model": None,
        "mpn": None,
        "gtin": None,
        "sku": None,
    }
    return product, signals


def _missing_critical(product: dict | None) -> list[str]:
    missing: list[str] = []
    if product is None:
        return ["product.title", "product.brand"]
    if not product.get("title"):
        missing.append("product.title")
    if not product.get("brand"):
        missing.append("product.brand")
    return missing


def _is_jsonld_exploitable(product: dict | None) -> bool:
    if not product:
        return False
    if not product.get("title"):
        return False
    if product.get("brand") or product.get("model"):
        return True
    if product.get("mpn") or product.get("gtin") or product.get("sku"):
        return True
    return False


def _build_extracted_json(
    method: ExtractionMethod,
    product: dict | None,
    offers: list[dict],
    signals: list[str],
    missing: list[str],
    errors: list[dict],
) -> dict:
    return {
        "extraction_version": "v1",
        "method": method.value,
        "product": product,
        "offers": offers,
        "signals": sorted(set(signals)),
        "missing_critical": missing,
        "errors": errors,
    }


def _build_digest_v1(extracted_json: dict) -> tuple[dict, str]:
    product = extracted_json.get("product") or {}
    digest = {
        "digest_version": "v1",
        "product_identity": {
            "brand": product.get("brand"),
            "model": product.get("model"),
            "mpn": product.get("mpn"),
            "gtin": product.get("gtin"),
            "sku": product.get("sku"),
            "title": product.get("title"),
        },
        "category_hint": None,
        "key_attributes": None,
        "source_signals": extracted_json.get("signals", []),
    }
    canonical = json.dumps(digest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return digest, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def extract_structured_v1(
    url: str,
    final_url: str,
    content_bytes: bytes | None,
    content_type: str | None,
) -> ExtractionResult:
    if not content_bytes:
        extracted = _build_extracted_json(
            ExtractionMethod.minimal,
            product=None,
            offers=[],
            signals=[],
            missing=["product.title", "product.brand"],
            errors=[{"code": "no_content", "message": "no content bytes"}],
        )
        digest_json, digest_hash = _build_digest_v1(extracted)
        return ExtractionResult(
            method=ExtractionMethod.minimal,
            status=SnapshotStatus.indeterminate,
            extracted_json=extracted,
            digest_json=digest_json,
            digest_hash=digest_hash,
            errors_json={"errors": extracted["errors"]},
            missing_critical_json={"missing": extracted["missing_critical"]},
        )

    if content_type and "html" not in content_type.lower():
        extracted = _build_extracted_json(
            ExtractionMethod.minimal,
            product=None,
            offers=[],
            signals=[],
            missing=["product.title", "product.brand"],
            errors=[{"code": "unsupported_content_type", "message": content_type}],
        )
        digest_json, digest_hash = _build_digest_v1(extracted)
        return ExtractionResult(
            method=ExtractionMethod.minimal,
            status=SnapshotStatus.indeterminate,
            extracted_json=extracted,
            digest_json=digest_json,
            digest_hash=digest_hash,
            errors_json={"errors": extracted["errors"]},
            missing_critical_json={"missing": extracted["missing_critical"]},
        )

    parser = _HtmlSignalParser()
    html_text = content_bytes.decode("utf-8", errors="ignore")
    parser.feed(html_text)

    errors: list[dict] = []
    jsonld_nodes: list[dict[str, Any]] = []
    for block in parser.jsonld_blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            errors.append({"code": "jsonld_parse_error", "message": "invalid JSON-LD"})
            continue
        jsonld_nodes.extend(_iter_jsonld_nodes(parsed))

    product, signals = _extract_product_from_jsonld(jsonld_nodes)
    if _is_jsonld_exploitable(product):
        missing = _missing_critical(product)
        extracted = _build_extracted_json(
            ExtractionMethod.jsonld,
            product=product,
            offers=[],
            signals=signals,
            missing=missing,
            errors=errors,
        )
        digest_json, digest_hash = _build_digest_v1(extracted)
        status = SnapshotStatus.ok if not missing else SnapshotStatus.partial
        return ExtractionResult(
            method=ExtractionMethod.jsonld,
            status=status,
            extracted_json=extracted,
            digest_json=digest_json,
            digest_hash=digest_hash,
            errors_json={"errors": errors} if errors else None,
            missing_critical_json={"missing": missing} if missing else None,
        )

    dom_product, dom_signals = _extract_product_from_dom(parser)
    if dom_product and dom_product.get("title"):
        missing = _missing_critical(dom_product)
        extracted = _build_extracted_json(
            ExtractionMethod.dom,
            product=dom_product,
            offers=[],
            signals=signals + dom_signals,
            missing=missing,
            errors=errors,
        )
        digest_json, digest_hash = _build_digest_v1(extracted)
        status = SnapshotStatus.ok if not missing else SnapshotStatus.partial
        return ExtractionResult(
            method=ExtractionMethod.dom,
            status=status,
            extracted_json=extracted,
            digest_json=digest_json,
            digest_hash=digest_hash,
            errors_json={"errors": errors} if errors else None,
            missing_critical_json={"missing": missing} if missing else None,
        )

    minimal_product = {
        "title": _normalize_text(parser.title),
        "brand": None,
        "model": None,
        "mpn": None,
        "gtin": None,
        "sku": None,
    }
    missing = _missing_critical(minimal_product)
    extracted = _build_extracted_json(
        ExtractionMethod.minimal,
        product=minimal_product,
        offers=[],
        signals=signals,
        missing=missing,
        errors=errors,
    )
    digest_json, digest_hash = _build_digest_v1(extracted)
    status = (
        SnapshotStatus.partial if minimal_product.get("title") else SnapshotStatus.indeterminate
    )
    return ExtractionResult(
        method=ExtractionMethod.minimal,
        status=status,
        extracted_json=extracted,
        digest_json=digest_json,
        digest_hash=digest_hash,
        errors_json={"errors": errors} if errors else None,
        missing_critical_json={"missing": missing} if missing else None,
    )
