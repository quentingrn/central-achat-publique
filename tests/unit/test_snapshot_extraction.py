from modules.snapshot.domain.extraction import extract_structured_v1

HTML_JSONLD_OK = """
<html>
  <head>
    <script type="application/ld+json">
      {"@context": "https://schema.org", "@type": "Product", "name": "ACME Widget",
       "brand": {"@type": "Brand", "name": "ACME"}, "gtin13": "0123456789012"}
    </script>
  </head>
  <body></body>
</html>
"""

HTML_JSONLD_INVALID_DOM_OK = """
<html>
  <head>
    <script type="application/ld+json">{invalid json</script>
    <meta property="og:title" content="Fallback Title" />
  </head>
  <body></body>
</html>
"""

HTML_NO_JSONLD_NO_DOM = "<html><body><div>Nothing here</div></body></html>"


def test_extract_jsonld_ok() -> None:
    result = extract_structured_v1(
        url="https://example.com",
        final_url="https://example.com",
        content_bytes=HTML_JSONLD_OK.encode("utf-8"),
        content_type="text/html; charset=utf-8",
    )
    assert result.method.value == "jsonld"
    assert result.status.value == "ok"
    assert result.extracted_json["method"] == "jsonld"
    assert result.extracted_json["product"]["brand"] == "ACME"
    assert result.extracted_json["product"]["gtin"] == "0123456789012"
    assert result.digest_hash


def test_extract_dom_fallback_when_jsonld_invalid() -> None:
    result = extract_structured_v1(
        url="https://example.com",
        final_url="https://example.com",
        content_bytes=HTML_JSONLD_INVALID_DOM_OK.encode("utf-8"),
        content_type="text/html; charset=utf-8",
    )
    assert result.method.value == "dom"
    assert result.status.value in {"ok", "partial"}
    assert result.extracted_json["method"] == "dom"
    assert result.extracted_json["product"]["title"] == "Fallback Title"
    assert result.digest_hash


def test_extract_minimal_when_no_dom_signals() -> None:
    result = extract_structured_v1(
        url="https://example.com",
        final_url="https://example.com",
        content_bytes=HTML_NO_JSONLD_NO_DOM.encode("utf-8"),
        content_type="text/html; charset=utf-8",
    )
    assert result.method.value == "minimal"
    assert result.status.value in {"partial", "indeterminate"}
    assert result.extracted_json["method"] == "minimal"
    assert result.digest_hash
