import hashlib
import uuid
from collections.abc import Iterable

from sqlalchemy.orm import Session

from modules.discovery_compare.infrastructure.persistence.models import (
    CompareRun,
    LlmRun,
    Prompt,
    RunEvent,
    ToolRun,
)


def _hash_content(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RunRecorder:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self, source_url: str | None = None, agent_version: str | None = None
    ) -> CompareRun:
        run = CompareRun(source_url=source_url, status="started", agent_version=agent_version)
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def add_event(
        self,
        run_id: uuid.UUID,
        phase_name: str,
        status: str,
        message: str | None = None,
    ) -> RunEvent:
        event = RunEvent(run_id=run_id, phase_name=phase_name, status=status, message=message)
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def add_events(self, run_id: uuid.UUID, events: Iterable[RunEvent]) -> None:
        for event in events:
            event.run_id = run_id
            self.session.add(event)
        self.session.commit()

    def get_or_create_prompt(self, name: str, version: str, content: str) -> Prompt:
        existing = (
            self.session.query(Prompt)
            .filter(Prompt.name == name, Prompt.version == version)
            .order_by(Prompt.created_at.desc())
            .first()
        )
        content_hash = _hash_content(content)
        if existing is not None:
            if existing.content != content:
                raise ValueError("Prompt content mismatch for existing name/version")
            if existing.content_hash != content_hash:
                existing.content_hash = content_hash
                self.session.commit()
            return existing

        prompt = Prompt(name=name, version=version, content=content, content_hash=content_hash)
        self.session.add(prompt)
        self.session.commit()
        self.session.refresh(prompt)
        return prompt

    def add_prompt(self, name: str, version: str, content: str) -> Prompt:
        prompt = Prompt(
            name=name, version=version, content=content, content_hash=_hash_content(content)
        )
        self.session.add(prompt)
        self.session.commit()
        self.session.refresh(prompt)
        return prompt

    def add_tool_run(
        self,
        run_id: uuid.UUID,
        tool_name: str,
        status: str,
        input_json: dict | None = None,
        output_json: dict | None = None,
    ) -> ToolRun:
        tool_run = ToolRun(
            run_id=run_id,
            tool_name=tool_name,
            status=status,
            input_json=input_json,
            output_json=output_json,
        )
        self.session.add(tool_run)
        self.session.commit()
        self.session.refresh(tool_run)
        return tool_run

    def add_llm_run(
        self,
        run_id: uuid.UUID,
        model_name: str,
        status: str,
        prompt_id: uuid.UUID | None = None,
        prompt_content: str | None = None,
        prompt_hash: str | None = None,
        model_params: dict | None = None,
        json_schema: dict | None = None,
        json_schema_hash: str | None = None,
        input_json: dict | None = None,
        output_json: dict | None = None,
        output_validated_json: dict | None = None,
        validation_errors: list[str] | None = None,
    ) -> LlmRun:
        llm_run = LlmRun(
            run_id=run_id,
            prompt_id=prompt_id,
            prompt_content=prompt_content,
            prompt_hash=prompt_hash,
            model_name=model_name,
            status=status,
            model_params=model_params,
            json_schema=json_schema,
            json_schema_hash=json_schema_hash,
            input_json=input_json,
            output_json=output_json,
            output_validated_json=output_validated_json,
            validation_errors=validation_errors,
        )
        self.session.add(llm_run)
        self.session.commit()
        self.session.refresh(llm_run)
        return llm_run
