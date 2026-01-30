from __future__ import annotations

from dataclasses import dataclass

from modules.snapshot.adapters.schemas import ExtractionMethod, SnapshotStatus


@dataclass(frozen=True)
class ExtractionResult:
    method: ExtractionMethod
    status: SnapshotStatus
    extracted_json: dict
    digest_json: dict
    errors_json: dict | None = None


def extract_minimal(url: str, final_url: str, content_bytes: bytes | None) -> ExtractionResult:
    if not content_bytes:
        return ExtractionResult(
            method=ExtractionMethod.minimal,
            status=SnapshotStatus.error,
            extracted_json={"url": url, "final_url": final_url},
            digest_json={"url": final_url},
            errors_json={"reason": "empty_content"},
        )
    return ExtractionResult(
        method=ExtractionMethod.minimal,
        status=SnapshotStatus.partial,
        extracted_json={"url": url, "final_url": final_url},
        digest_json={"url": final_url},
    )
