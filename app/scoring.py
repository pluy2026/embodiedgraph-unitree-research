from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field, model_validator


def corroboration_points(source_urls: Iterable[str | None]) -> int:
    """Score only distinct, usable source URLs for one relationship.

    A single announcement may legitimately name several counterparties.  It can
    support each relationship, but must not become cross-validation merely
    because it is reused elsewhere in the graph.
    """
    unique_urls = {url.strip() for url in source_urls if url and url.strip()}
    if len(unique_urls) >= 3:
        return 15
    if len(unique_urls) == 2:
        return 8
    return 0


class ScoreInput(BaseModel):
    source_authority: int = Field(ge=0, le=35)
    directness: int = Field(ge=0, le=25)
    cross_validation: int = Field(ge=0, le=15)
    recency: int = Field(ge=0, le=15)
    entity_accuracy: int = Field(ge=0, le=10)
    conflict_penalty: int = Field(default=0, ge=0, le=25)
    evidence_count: int = Field(default=1, ge=0)

    @property
    def score(self) -> int:
        return max(0, self.source_authority + self.directness + self.cross_validation + self.recency + self.entity_accuracy - self.conflict_penalty)

    @property
    def status(self) -> str:
        if self.evidence_count == 0:
            return "unknown"
        if self.score >= 80 and self.directness >= 18 and self.conflict_penalty == 0:
            return "confirmed"
        if self.score >= 60:
            return "probable"
        return "unverified"


class RelationshipInput(BaseModel):
    evidence_ids: list[str]
    score: ScoreInput
    status: str

    @model_validator(mode="after")
    def confirmed_requires_evidence(self):
        if self.status == "confirmed" and not self.evidence_ids:
            raise ValueError("缺少证据的关系不能标记为 confirmed")
        return self
