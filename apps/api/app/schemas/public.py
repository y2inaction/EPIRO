"""Response shapes for the public portal.

Deliberately separate from the internal schemas rather than reused. An
internal schema grows a field whenever the domain does, and reusing one here
would mean every such addition is published to the world by default. These are
allow-lists: a field appears on the portal because someone decided it should.

Nothing here carries an internal identity. Not the author, the verifier, the
approver or the publisher, and not the person who asked a question — spec
section 20 limits what may be collected about citizens, and publishing it
would be worse than collecting it.
"""

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PublicOrganisation(BaseModel):
    """The body answering for a piece of published information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str


class PublicStory(BaseModel):
    """A published story."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    headline: Optional[str] = None
    summary: Optional[str] = None
    body: str
    language: str
    featured: bool
    published_date: Optional[datetime] = None
    # The evidence the story rests on, so a reader can follow the claim back
    # to the record it came from. This is the point of the platform.
    evidence_reference: Optional[str] = None
    organisation: Optional[PublicOrganisation] = None


class PublicEvidence(BaseModel):
    """A published evidence record.

    Carries the verification state but never the verifier's identity or their
    notes: the reader is entitled to know how far review got, not who signed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str
    title: str
    description: Optional[str] = None
    outcome: Optional[str] = None
    evidence_date: Optional[date] = None
    verification_status: str
    beneficiaries: Optional[int] = None
    document_url: Optional[str] = None
    tags: List[str] = []
    organisation: Optional[PublicOrganisation] = None


class PublicQuestion(BaseModel):
    """A published question and the answer given to it.

    The submitter is never identified, whatever they chose when they asked:
    is_anonymous governs whether the body may contact them, not whether their
    identity may be published. It may not.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: Optional[str] = None
    question_text: str
    response: Optional[str] = None
    response_date: Optional[datetime] = None
    language: str
    organisation: Optional[PublicOrganisation] = None


class PublicPage(BaseModel):
    """A page of public results."""

    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[dict]
