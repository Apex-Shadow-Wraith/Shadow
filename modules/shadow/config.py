"""Shadow orchestrator module settings schema.

Distinct from `shadow/config/` (the top-level centralized config package)
— this is `modules/shadow/config.py`, settings specific to the Shadow
orchestrator module (routing, state).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ShadowModuleSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    db_path: str = "data/shadow_tasks.db"
