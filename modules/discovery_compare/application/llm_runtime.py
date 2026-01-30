from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class AgentConfig:
    version: str
    model_name: str
    prompt_hashes: list[str]
    schema_hashes: list[str]


class AgentRegistry:
    def __init__(self) -> None:
        self._current: AgentConfig | None = None

    def get_or_create(
        self, model_name: str, prompt_hashes: list[str], schema_hashes: list[str]
    ) -> AgentConfig:
        version = compute_agent_version(model_name, prompt_hashes, schema_hashes)
        if self._current and self._current.version == version:
            return self._current
        self._current = AgentConfig(
            version=version,
            model_name=model_name,
            prompt_hashes=prompt_hashes,
            schema_hashes=schema_hashes,
        )
        return self._current


_agent_registry = AgentRegistry()


def get_agent_config(
    model_name: str, prompt_hashes: list[str], schema_hashes: list[str]
) -> AgentConfig:
    return _agent_registry.get_or_create(model_name, prompt_hashes, schema_hashes)


def compute_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_agent_version(
    model_name: str, prompt_hashes: list[str], schema_hashes: list[str]
) -> str:
    payload = {
        "model": model_name,
        "prompts": sorted(prompt_hashes),
        "schemas": sorted(schema_hashes),
    }
    serialized = json.dumps(payload, sort_keys=True)
    return compute_hash(serialized)


def json_schema_for_model(model_cls) -> dict:
    return model_cls.model_json_schema()


def schema_hash(schema: dict) -> str:
    serialized = json.dumps(schema, sort_keys=True)
    return compute_hash(serialized)


def validate_against_schema(schema: dict, payload: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = [error.message for error in validator.iter_errors(payload)]
    return errors


class LlmClient:
    def generate_json(
        self,
        prompt: str,
        schema: dict,
        input_json: dict,
        model_name: str,
        params: dict,
        expected_output: dict | None = None,
    ) -> dict:
        raise NotImplementedError


class StubLlmClient(LlmClient):
    def generate_json(
        self,
        prompt: str,
        schema: dict,
        input_json: dict,
        model_name: str,
        params: dict,
        expected_output: dict | None = None,
    ) -> dict:
        if expected_output is not None:
            return expected_output
        return {"comparables": []}
