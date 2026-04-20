"""Observability (Langfuse) settings schema.

Commit 1: empty stub. Commit 6 adds SecretStr fields for Langfuse
public/secret keys and replaces `os.environ.get` calls in
`modules/shadow/observability.py`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ObservabilitySettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    langfuse_host: str = "https://cloud.langfuse.com"
