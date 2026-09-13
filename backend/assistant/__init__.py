"""M9 Investigator Intelligence Assistant.

A deterministic, evidence-grounded layer over the existing investigation
modules. Quick actions and free-form queries map to controlled read-only tool
calls; answers always cite persisted data (evidence ids / transaction hashes)
and are marked for human review before any operational use.
"""

from assistant.api import router

__all__ = ["router"]