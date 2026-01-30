from __future__ import annotations

from modules.discovery_compare.adapters.schemas import ComparableV1, OfferV1, ProductDigestV1
from modules.discovery_compare.application.ports import (
    LlmJudge,
    OfferCandidateProvider,
    ProductCandidate,
    ProductCandidateProvider,
    ProductCandidateRecall,
    SnapshotProvider,
    SnapshotResult,
)


class StubSnapshotProvider(SnapshotProvider):
    def capture(self, url: str) -> SnapshotResult:
        html = """
        <html>
          <head>
            <title>ACME X1</title>
            <script type="application/ld+json">
              {"@context":"https://schema.org","@type":"Product","brand":{"@type":"Brand","name":"ACME"},"model":"X1"}
            </script>
          </head>
          <body>stub</body>
        </html>
        """.strip()
        extracted = {
            "brand": "ACME",
            "model": "X1",
            "url": url,
        }
        digest = {
            "brand": "ACME",
            "model": "X1",
        }
        return SnapshotResult(
            requested_url=url,
            url_final=url,
            status_code=200,
            html=html,
            metadata={"source": "stub"},
            extracted_json=extracted,
            digest_json=digest,
        )


class StubProductCandidateProvider(ProductCandidateProvider):
    def recall(self, source: ProductDigestV1) -> ProductCandidateRecall:
        candidates = [
            ProductCandidate(
                candidate_url="https://example.com/p1",
                signals_json={
                    "title": f"{source.brand} {source.model} Pro",
                    "snippet": "stub candidate 1",
                    "score": 0.91,
                },
            ),
            ProductCandidate(
                candidate_url="https://example.com/p2",
                signals_json={
                    "title": f"{source.brand} X2",
                    "snippet": "stub candidate 2",
                    "score": 0.84,
                },
            ),
        ]
        return ProductCandidateRecall(
            candidates=candidates,
            request_json={"source": source.model_dump(mode="json")},
            response_json={"results": [c.__dict__ for c in candidates]},
            status="ok",
        )


class StubOfferCandidateProvider(OfferCandidateProvider):
    def recall(self, product: ProductDigestV1) -> list[OfferV1]:
        return [
            OfferV1(
                offer_url=f"https://example.com/o/{product.model}",
                seller="StubSeller",
                price_amount=199.99,
                price_currency="EUR",
            )
        ]


class StubLlmJudge(LlmJudge):
    def judge(
        self, source: ProductDigestV1, candidates: list[ProductDigestV1]
    ) -> list[ComparableV1]:
        comparables: list[ComparableV1] = []
        for candidate in candidates:
            comparables.append(
                ComparableV1(
                    product=candidate,
                    comparability_score=0.9,
                    reasons_short=["stub_match"],
                    signals_used=["brand", "model"],
                    missing_critical=[],
                )
            )
        return comparables
