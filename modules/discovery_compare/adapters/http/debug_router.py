import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, tuple_

from apps.api.guards import require_debug_access
from modules.discovery_compare.adapters.schemas.debug_run_diff_v1 import (
    CompareRunDiffResponseV1,
    DiffSeverityV1,
    RunCountsDiffV1,
    RunErrorTopDiffV1,
    RunFieldDiffV1,
    RunPhaseDiffItemV1,
    RunRefSetDiffV1,
)
from modules.discovery_compare.adapters.schemas.debug_run_v1 import (
    CompareRunListItemV1,
    CompareRunListResponseV1,
    CompareRunSummaryResponseV1,
    RunErrorTopV1,
    RunPhaseCountsV1,
    RunRefsV1,
    RunTimelineItemV1,
)
from modules.discovery_compare.adapters.schemas.v1 import PhaseNameV1
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
_STATUS_SEVERITY = {"error": 3, "warning": 2, "ok": 1, "skipped": 0}
_PHASE_ORDER = {phase.value: index for index, phase in enumerate(PhaseNameV1)}


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


def _diff_severity(left: object | None, right: object | None) -> DiffSeverityV1:
    if left == right:
        return DiffSeverityV1.same
    if left is None and right is not None:
        return DiffSeverityV1.added
    if left is not None and right is None:
        return DiffSeverityV1.removed
    return DiffSeverityV1.changed


def _build_phase_index(events: list[RunEvent]) -> dict[str, RunEvent]:
    phases: dict[str, RunEvent] = {}
    for event in events:
        current = phases.get(event.phase_name)
        if current is None:
            phases[event.phase_name] = event
            continue
        current_severity = _STATUS_SEVERITY.get(current.status, 0)
        new_severity = _STATUS_SEVERITY.get(event.status, 0)
        if new_severity > current_severity:
            phases[event.phase_name] = event
            continue
        if new_severity == current_severity and event.created_at >= current.created_at:
            phases[event.phase_name] = event
    return phases


def _build_ref_diff(left_ids: list[uuid.UUID], right_ids: list[uuid.UUID]) -> RunRefSetDiffV1:
    left_set = {str(value) for value in left_ids}
    right_set = {str(value) for value in right_ids}
    added = sorted(right_set - left_set)
    removed = sorted(left_set - right_set)
    common_count = len(left_set & right_set)
    return RunRefSetDiffV1(
        added_ids=added,
        removed_ids=removed,
        common_count=common_count,
    )


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


@router.get("/compare-runs:diff", response_model=CompareRunDiffResponseV1)
def diff_compare_runs(
    left_run_id: str | None = Query(default=None),
    right_run_id: str | None = Query(default=None),
    left: str | None = Query(default=None),
    right: str | None = Query(default=None),
) -> CompareRunDiffResponseV1:
    left_id = left_run_id or left
    right_id = right_run_id or right
    if not left_id or not right_id:
        raise HTTPException(status_code=400, detail="left_run_id and right_run_id required")

    session = get_session()
    try:
        left_run = session.get(CompareRun, left_id)
        right_run = session.get(CompareRun, right_id)
        if left_run is None or right_run is None:
            raise HTTPException(status_code=404, detail="run not found")

        left_events = (
            session.query(RunEvent)
            .filter(RunEvent.run_id == left_run.id)
            .order_by(RunEvent.created_at.asc())
            .all()
        )
        right_events = (
            session.query(RunEvent)
            .filter(RunEvent.run_id == right_run.id)
            .order_by(RunEvent.created_at.asc())
            .all()
        )

        left_phase_counts = _build_phase_counts(left_events).get(left_run.id, RunPhaseCountsV1())
        right_phase_counts = _build_phase_counts(right_events).get(right_run.id, RunPhaseCountsV1())
        phase_counts = RunCountsDiffV1(
            left=left_phase_counts,
            right=right_phase_counts,
            severity=_diff_severity(left_phase_counts, right_phase_counts),
        )

        left_error_top = _build_error_top(left_events).get(left_run.id)
        right_error_top = _build_error_top(right_events).get(right_run.id)
        error_top = RunErrorTopDiffV1(
            left=left_error_top,
            right=right_error_top,
            severity=_diff_severity(left_error_top, right_error_top),
        )

        left_index = _build_phase_index(left_events)
        right_index = _build_phase_index(right_events)
        phase_names = sorted(
            set(left_index.keys()) | set(right_index.keys()),
            key=lambda phase: (_PHASE_ORDER.get(phase, 999), phase),
        )
        timeline: list[RunPhaseDiffItemV1] = []
        for phase_name in phase_names:
            left_event = left_index.get(phase_name)
            right_event = right_index.get(phase_name)
            left_status = left_event.status if left_event else None
            right_status = right_event.status if right_event else None
            timeline.append(
                RunPhaseDiffItemV1(
                    phase_name=phase_name,
                    left_status=left_status,
                    right_status=right_status,
                    severity=_diff_severity(left_status, right_status),
                    left_message=left_event.message if left_event else None,
                    right_message=right_event.message if right_event else None,
                )
            )

        left_snapshot_ids = [
            row[0]
            for row in session.query(PageSnapshot.id)
            .filter(PageSnapshot.run_id == left_run.id)
            .all()
        ]
        right_snapshot_ids = [
            row[0]
            for row in session.query(PageSnapshot.id)
            .filter(PageSnapshot.run_id == right_run.id)
            .all()
        ]
        left_tool_run_ids = [
            row[0] for row in session.query(ToolRun.id).filter(ToolRun.run_id == left_run.id).all()
        ]
        right_tool_run_ids = [
            row[0] for row in session.query(ToolRun.id).filter(ToolRun.run_id == right_run.id).all()
        ]
        left_llm_run_ids = [
            row[0] for row in session.query(LlmRun.id).filter(LlmRun.run_id == left_run.id).all()
        ]
        right_llm_run_ids = [
            row[0] for row in session.query(LlmRun.id).filter(LlmRun.run_id == right_run.id).all()
        ]
        left_prompt_ids = [
            row[0]
            for row in session.query(func.distinct(LlmRun.prompt_id))
            .filter(LlmRun.run_id == left_run.id)
            .filter(LlmRun.prompt_id.isnot(None))
            .all()
        ]
        right_prompt_ids = [
            row[0]
            for row in session.query(func.distinct(LlmRun.prompt_id))
            .filter(LlmRun.run_id == right_run.id)
            .filter(LlmRun.prompt_id.isnot(None))
            .all()
        ]

        refs = {
            "snapshots": _build_ref_diff(left_snapshot_ids, right_snapshot_ids),
            "tool_runs": _build_ref_diff(left_tool_run_ids, right_tool_run_ids),
            "llm_runs": _build_ref_diff(left_llm_run_ids, right_llm_run_ids),
            "prompts": _build_ref_diff(left_prompt_ids, right_prompt_ids),
        }

        status_diff = RunFieldDiffV1(
            left=left_run.status,
            right=right_run.status,
            severity=_diff_severity(left_run.status, right_run.status),
        )
        source_url_diff = RunFieldDiffV1(
            left=left_run.source_url,
            right=right_run.source_url,
            severity=_diff_severity(left_run.source_url, right_run.source_url),
        )
        agent_version_diff = RunFieldDiffV1(
            left=left_run.agent_version,
            right=right_run.agent_version,
            severity=_diff_severity(left_run.agent_version, right_run.agent_version),
        )

        notes = ["timeline built from run_events only"]

        return CompareRunDiffResponseV1(
            left_run_id=str(left_run.id),
            right_run_id=str(right_run.id),
            left_created_at=left_run.created_at,
            right_created_at=right_run.created_at,
            status_diff=status_diff,
            source_url_diff=source_url_diff,
            agent_version_diff=agent_version_diff,
            phase_counts=phase_counts,
            error_top=error_top,
            timeline=timeline,
            refs=refs,
            notes=notes,
        )
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
