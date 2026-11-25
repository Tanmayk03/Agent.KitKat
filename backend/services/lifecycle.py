"""
Agent KitKat - Application lifecycle.

Stages (what YOU see in the tracker). The browser-automation state lives separately in
Application.status ("filling", "paused_captcha", ...).

Every change goes through set_stage(), which validates the transition and writes an
ApplicationEvent row, so the history of each application is auditable.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Application, ApplicationEvent

STAGES: Dict[str, str] = {
    "discovered": "Discovered",
    "shortlisted": "Shortlisted",
    "eligible": "Eligible",
    "not_eligible": "Not Eligible",
    "draft_ready": "Draft Ready",
    "awaiting_approval": "Awaiting Approval",
    "submitted": "Submitted",
    "submission_unverified": "Submission Unverified",
    "application_confirmed": "Application Confirmed",
    "assessment_received": "Assessment Received",
    "interview": "Interview",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
    "offer_received": "Offer Received",
}

# Stages in which the application has (probably) reached the employer
SENT_STAGES: Set[str] = {
    "submitted", "submission_unverified", "application_confirmed",
    "assessment_received", "interview", "rejected", "offer_received",
}

_AFTER_SENT = ["application_confirmed", "assessment_received", "interview", "rejected", "offer_received", "withdrawn"]
_PRE = ["shortlisted", "eligible", "not_eligible", "draft_ready", "awaiting_approval", "submitted", "withdrawn"]

TRANSITIONS: Dict[str, List[str]] = {
    "discovered": _PRE,
    "shortlisted": _PRE,
    "eligible": _PRE,
    "not_eligible": ["shortlisted", "eligible", "draft_ready", "awaiting_approval", "withdrawn"],
    "draft_ready": ["awaiting_approval", "draft_ready", "submitted", "submission_unverified", "withdrawn"],
    "awaiting_approval": ["draft_ready", "awaiting_approval", "submitted", "submission_unverified", "withdrawn"],
    "submitted": ["submission_unverified"] + _AFTER_SENT,
    # an unverified submission may turn out not to have gone through at all
    "submission_unverified": ["submitted", "draft_ready", "awaiting_approval"] + _AFTER_SENT,
    "application_confirmed": _AFTER_SENT,
    "assessment_received": ["interview", "rejected", "offer_received", "withdrawn", "assessment_received"],
    "interview": ["interview", "rejected", "offer_received", "withdrawn"],
    "rejected": [],
    "offer_received": ["withdrawn"],
    "withdrawn": ["shortlisted", "draft_ready"],
}


class StageTransitionError(ValueError):
    pass


def stage_label(stage: Optional[str]) -> str:
    return STAGES.get(stage or "", stage or "Unknown")


def stage_from_legacy_status(status: Optional[str]) -> str:
    """Map pre-Stage-5 automation statuses onto lifecycle stages."""
    return {
        "submitted": "submitted",
        "submission_unverified": "submission_unverified",
        "submission_uncertain": "submission_unverified",
        "skipped": "withdrawn",
        "withdrawn": "withdrawn",
        "draft": "draft_ready",
        "draft_ready": "draft_ready",
        "approved": "draft_ready",
        "approved_for_submission": "draft_ready",
    }.get(status or "", "awaiting_approval")


async def set_stage(
    session: AsyncSession,
    app: Application,
    new_stage: str,
    note: Optional[str] = None,
    actor: str = "user",
    force: bool = False,
) -> ApplicationEvent:
    """Validate and apply a stage change, recording an event. Does not commit."""
    if new_stage not in STAGES:
        raise StageTransitionError(f"Unknown stage '{new_stage}'.")
    current = app.stage or "discovered"
    if not force and new_stage != current and new_stage not in TRANSITIONS.get(current, []):
        allowed = ", ".join(stage_label(s) for s in TRANSITIONS.get(current, [])) or "none (final stage)"
        raise StageTransitionError(
            f"Cannot move from '{stage_label(current)}' to '{stage_label(new_stage)}'. Allowed: {allowed}."
        )
    event = ApplicationEvent(
        id=str(uuid.uuid4()), application_id=app.id, from_stage=current, to_stage=new_stage,
        actor=actor, note=note, created_at=datetime.utcnow(),
    )
    app.stage = new_stage
    app.stage_updated_at = event.created_at
    if new_stage in SENT_STAGES and app.applied_at is None:
        app.applied_at = event.created_at
    session.add(event)
    return event


async def add_note_event(session: AsyncSession, app: Application, note: str, actor: str = "user") -> ApplicationEvent:
    event = ApplicationEvent(id=str(uuid.uuid4()), application_id=app.id, from_stage=app.stage, to_stage=app.stage,
                             actor=actor, note=note, created_at=datetime.utcnow())
    session.add(event)
    return event
