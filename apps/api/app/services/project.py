"""Project lifecycle rules."""

from datetime import date
from typing import Optional

from fastapi import HTTPException, status

from app.models import Project, ProjectStatus

# Spec section 51: a project cannot be marked completed without the
# information that makes the claim checkable.
COMPLETION_REQUIRES_DATE = frozenset({ProjectStatus.COMPLETED})


def apply_status_change(
    project: Project,
    new_status: ProjectStatus,
    actual_completion: Optional[date] = None,
) -> None:
    """Move a project to a new lifecycle state, enforcing the entry rules.

    Mutates the project; the caller commits.
    """
    if project.status is ProjectStatus.ARCHIVED and new_status is not ProjectStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An archived project cannot be reopened. Create a successor "
                "project instead, so the archived record stays as it was."
            ),
        )

    if new_status in COMPLETION_REQUIRES_DATE:
        completion = actual_completion or project.actual_completion
        if completion is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A project cannot be marked completed without an actual " "completion date"
                ),
            )
        if project.start_date is not None and completion < project.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The completion date cannot fall before the project started",
            )
        project.actual_completion = completion

    project.status = new_status
