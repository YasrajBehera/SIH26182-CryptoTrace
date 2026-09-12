"""Pydantic schemas for the audit trail."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AuditEventOut(BaseModel):
    id: str
    timestamp: str
    user: str
    action: str
    resource: str
    resource_id: str
    result: str
    ip: Optional[str] = None


class AuditEventsResponse(BaseModel):
    events: List[AuditEventOut]
    total: int
    source: str


class AuditQuery(BaseModel):
    user: Optional[str] = Field(None, max_length=64)
    action: Optional[str] = Field(None, max_length=32)
    resource: Optional[str] = Field(None, max_length=64)
    result: Optional[str] = None
    from_iso: Optional[str] = None
    to_iso: Optional[str] = None
    limit: int = Field(200, ge=1, le=1000)