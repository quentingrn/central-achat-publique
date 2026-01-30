from modules.discovery_compare.domain.snapshot_extraction import build_snapshot_extraction


def test_extract_jsonld_product_digest() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "brand": {"@type": "Brand", "name": "ACME"},
            "model": "X1",
            "sku": "SKU-1"
          }
        </script>
      </head>
      <body>ok</body>
    </html>
    """.strip()
    extracted, digest = build_snapshot_extraction(html)
    assert extracted["jsonld"]
    assert digest["brand"] == "ACME"
    assert digest["model"] == "X1"
    assert digest["identifiers"]["sku"] == "SKU-1"


def test_extract_dom_fallback_digest() -> None:
    html = """
    <html>
      <head>
        <title>ACME X2</title>
        <meta name="brand" content="ACME">
        <meta name="model" content="X2">
      </head>
      <body>ok</body>
    </html>
    """.strip()
    extracted, digest = build_snapshot_extraction(html)
    assert extracted["dom"]["title"] == "ACME X2"
    assert digest["brand"] == "ACME"
    assert digest["model"] == "X2"
