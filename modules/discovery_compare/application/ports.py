from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from modules.discovery_compare.adapters.schemas import ComparableV1, OfferV1, ProductDigestV1


@dataclass(frozen=True)
class SnapshotResult:
    requested_url: str
    url_final: str
    status_code: int | None
    html: str | None
    metadata: dict
    extracted_json: dict
    digest_json: dict
    screenshot_base64: str | None = None


@dataclass(frozen=True)
class ProductCandidate:
    candidate_url: str
    signals_json: dict


@dataclass(frozen=True)
class ProductCandidateRecall:
    candidates: list[ProductCandidate]
    request_json: dict
    response_json: dict
    status: str
    error_message: str | None = None


class SnapshotProvider(ABC):
    @abstractmethod
    def capture(self, url: str) -> SnapshotResult:
        raise NotImplementedError


class ProductCandidateProvider(ABC):
    @abstractmethod
    def recall(self, source: ProductDigestV1) -> ProductCandidateRecall:
        raise NotImplementedError


class OfferCandidateProvider(ABC):
    @abstractmethod
    def recall(self, product: ProductDigestV1) -> list[OfferV1]:
        raise NotImplementedError


class LlmJudge(ABC):
    @abstractmethod
    def judge(
        self, source: ProductDigestV1, candidates: list[ProductDigestV1]
    ) -> list[ComparableV1]:
        raise NotImplementedError
