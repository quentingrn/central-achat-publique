import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, tuple_

from apps.api.guards import require_debug_access
from modules.discovery_compare.adapters.schemas.debug_run_v1 import (
    CompareRunListItemV1,
    CompareRunListResponseV1,
    CompareRunSummaryResponseV1,
    RunErrorTopV1,
    RunPhaseCountsV1,
    RunRefsV1,
    RunTimelineItemV1,
)
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

_CURSOR_SEPARATOR = "|"
_ERROR_STATUSES = {"error", "warning"}
_PHASE_STATUS_KEYS = ("ok", "warning", "error", "skipped")


def _encode_cursor(created_at: datetime, run_id: uuid.UUID) -> str:
    return f"{created_at.isoformat()}{_CURSOR_SEPARATOR}{run_id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_raw, run_raw = cursor.split(_CURSOR_SEPARATOR, 1)
        created_at = datetime.fromisoformat(created_raw)
        run_id = uuid.UUID(run_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc
    return created_at, run_id


def _build_phase_counts(events: list[RunEvent]) -> dict[uuid.UUID, RunPhaseCountsV1]:
    counts: dict[uuid.UUID, RunPhaseCountsV1] = {}
    for event in events:
        run_counts = counts.setdefault(event.run_id, RunPhaseCountsV1())
        if event.status in _PHASE_STATUS_KEYS:
            setattr(run_counts, event.status, getattr(run_counts, event.status) + 1)
    return counts


def _build_error_top(events: list[RunEvent]) -> dict[uuid.UUID, RunErrorTopV1]:
    error_top: dict[uuid.UUID, RunErrorTopV1] = {}
    sorted_events = sorted(events, key=lambda evt: evt.created_at)
    for event in sorted_events:
        if event.status not in _ERROR_STATUSES:
            continue
        if event.run_id in error_top:
            continue
        error_top[event.run_id] = RunErrorTopV1(
            phase_name=event.phase_name,
            status=event.status,
            message=event.message or "",
        )
    return error_top


def _duration_ms(run: CompareRun) -> int | None:
    if not run.created_at or not run.updated_at:
        return None
    delta = run.updated_at - run.created_at
    return int(delta.total_seconds() * 1000)


def _build_list_item(
    run: CompareRun,
    phase_counts: RunPhaseCountsV1 | None,
    error_top: RunErrorTopV1 | None,
) -> CompareRunListItemV1:
    return CompareRunListItemV1(
        run_id=run.id,
        created_at=run.created_at,
        status=run.status,
        source_url=run.source_url,
        agent_version=run.agent_version,
        duration_ms=_duration_ms(run),
        phase_counts=phase_counts or RunPhaseCountsV1(),
        error_top=error_top,
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


@router.get("/compare-runs", response_model=CompareRunListResponseV1)
def list_compare_runs(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> CompareRunListResponseV1:
    session = get_session()
    try:
        query = session.query(CompareRun).order_by(
            CompareRun.created_at.desc(), CompareRun.id.desc()
        )
        if cursor:
            cursor_created_at, cursor_run_id = _decode_cursor(cursor)
            query = query.filter(
                tuple_(CompareRun.created_at, CompareRun.id) < (cursor_created_at, cursor_run_id)
            )
        runs = query.limit(limit + 1).all()
        page = runs[:limit]
        next_cursor = None
        if len(runs) > limit and page:
            last = page[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)

        run_ids = [run.id for run in page]
        phase_counts_map: dict[uuid.UUID, RunPhaseCountsV1] = {}
        error_top_map: dict[uuid.UUID, RunErrorTopV1] = {}
        if run_ids:
            events = (
                session.query(RunEvent)
                .filter(RunEvent.run_id.in_(run_ids))
                .order_by(RunEvent.created_at.asc())
                .all()
            )
            phase_counts_map = _build_phase_counts(events)
            error_top_map = _build_error_top(events)

        items = [
            _build_list_item(run, phase_counts_map.get(run.id), error_top_map.get(run.id))
            for run in page
        ]
        return CompareRunListResponseV1(items=items, next_cursor=next_cursor)
    finally:
        session.close()


@router.get("/compare-runs/{run_id}:summary", response_model=CompareRunSummaryResponseV1)
def get_compare_run_summary(run_id: str) -> CompareRunSummaryResponseV1:
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
        phase_counts_map = _build_phase_counts(events)
        error_top_map = _build_error_top(events)
        item = _build_list_item(
            run,
            phase_counts_map.get(run.id),
            error_top_map.get(run.id),
        )
        timeline = [
            RunTimelineItemV1(
                phase_name=event.phase_name,
                status=event.status,
                created_at=event.created_at,
                message=event.message,
            )
            for event in events
        ]

        snapshot_ids = [
            row[0]
            for row in session.query(PageSnapshot.id).filter(PageSnapshot.run_id == run.id).all()
        ]
        tool_run_ids = [
            row[0] for row in session.query(ToolRun.id).filter(ToolRun.run_id == run.id).all()
        ]
        llm_run_ids = [
            row[0] for row in session.query(LlmRun.id).filter(LlmRun.run_id == run.id).all()
        ]
        prompt_ids = [
            row[0]
            for row in session.query(func.distinct(LlmRun.prompt_id))
            .filter(LlmRun.run_id == run.id)
            .filter(LlmRun.prompt_id.isnot(None))
            .all()
        ]

        refs = RunRefsV1(
            snapshot_ids=snapshot_ids,
            tool_run_ids=tool_run_ids,
            llm_run_ids=llm_run_ids,
            prompt_ids=prompt_ids,
        )

        return CompareRunSummaryResponseV1(item=item, timeline=timeline, refs=refs)
    finally:
        session.close()


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
