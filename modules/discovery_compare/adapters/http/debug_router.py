from fastapi import APIRouter, Depends, HTTPException

from apps.api.guards import require_debug_access
from modules.discovery_compare.infrastructure.persistence.models import (
    CompareRun,
    LlmRun,
    PageSnapshot,
    Prompt,
    RunEvent,
    ToolRun,
)
from shared.db.session import get_session

router = APIRouter(
    prefix="/v1/debug",
    tags=["debug"],
    dependencies=[Depends(require_debug_access)],
)


def _serialize_run(run: CompareRun, events: list[RunEvent]) -> dict:
    return {
        "id": str(run.id),
        "status": run.status,
        "source_url": run.source_url,
        "agent_version": run.agent_version,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "events": [
            {
                "id": str(event.id),
                "phase_name": event.phase_name,
                "status": event.status,
                "message": event.message,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    }


def _serialize_prompt(prompt: Prompt) -> dict:
    return {
        "id": str(prompt.id),
        "name": prompt.name,
        "version": prompt.version,
        "content": prompt.content,
        "created_at": prompt.created_at.isoformat(),
    }


def _serialize_tool_run(tool_run: ToolRun) -> dict:
    return {
        "id": str(tool_run.id),
        "run_id": str(tool_run.run_id),
        "tool_name": tool_run.tool_name,
        "status": tool_run.status,
        "input_json": tool_run.input_json,
        "output_json": tool_run.output_json,
        "created_at": tool_run.created_at.isoformat(),
    }


def _serialize_llm_run(llm_run: LlmRun) -> dict:
    return {
        "id": str(llm_run.id),
        "run_id": str(llm_run.run_id),
        "prompt_id": str(llm_run.prompt_id) if llm_run.prompt_id else None,
        "prompt_content": llm_run.prompt_content,
        "prompt_hash": llm_run.prompt_hash,
        "model_name": llm_run.model_name,
        "status": llm_run.status,
        "model_params": llm_run.model_params,
        "json_schema": llm_run.json_schema,
        "json_schema_hash": llm_run.json_schema_hash,
        "input_json": llm_run.input_json,
        "output_json": llm_run.output_json,
        "output_validated_json": llm_run.output_validated_json,
        "validation_errors": llm_run.validation_errors,
        "created_at": llm_run.created_at.isoformat(),
    }


def _serialize_snapshot(snapshot: PageSnapshot) -> dict:
    return {
        "id": str(snapshot.id),
        "product_id": str(snapshot.product_id),
        "url": snapshot.url,
        "extracted_json": snapshot.extracted_json,
        "created_at": snapshot.created_at.isoformat(),
        "updated_at": snapshot.updated_at.isoformat(),
    }


@router.get("/compare-runs/{run_id}")
def get_compare_run(run_id: str) -> dict:
    session = get_session()
    try:
        run = session.get(CompareRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        events = (
            session.query(RunEvent)
            .filter(RunEvent.run_id == run.id)
            .order_by(RunEvent.created_at.asc())
            .all()
        )
        return _serialize_run(run, events)
    finally:
        session.close()


@router.get("/llm-runs/{run_id}")
def get_llm_run(run_id: str) -> dict:
    session = get_session()
    try:
        llm_run = session.get(LlmRun, run_id)
        if llm_run is None:
            raise HTTPException(status_code=404, detail="llm run not found")
        return _serialize_llm_run(llm_run)
    finally:
        session.close()


@router.get("/tool-runs/{run_id}")
def get_tool_run(run_id: str) -> dict:
    session = get_session()
    try:
        tool_run = session.get(ToolRun, run_id)
        if tool_run is None:
            raise HTTPException(status_code=404, detail="tool run not found")
        return _serialize_tool_run(tool_run)
    finally:
        session.close()


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str) -> dict:
    session = get_session()
    try:
        snapshot = session.get(PageSnapshot, snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="snapshot not found")
        return _serialize_snapshot(snapshot)
    finally:
        session.close()


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: str) -> dict:
    session = get_session()
    try:
        prompt = session.get(Prompt, prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="prompt not found")
        return _serialize_prompt(prompt)
    finally:
        session.close()
