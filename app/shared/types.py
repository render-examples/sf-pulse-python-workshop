"""Pydantic models — port of shared/types.ts."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DatePrecision = Literal["day", "day_range", "month", "season", "year", "unknown"]
HighlightKind = Literal["opening", "michelin"]


class Restaurant(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    neighborhood: str
    cuisine: str
    address: str | None = None
    opened_date: str
    opened_start_date: str | None = None
    opened_end_date: str | None = None
    opened_date_precision: DatePrecision
    is_upcoming: bool
    highlight_kind: HighlightKind
    source_url: str | None = None


class InitialData(BaseModel):
    restaurants: list[Restaurant]
    last_updated: str | None = Field(default=None, alias="lastUpdated")


class PushPreferences(BaseModel):
    neighborhoods: list[str] = Field(default_factory=list)
    cuisines: list[str] = Field(default_factory=list)


T = TypeVar("T")


class RealtimeCollectionEvent(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    version: str | None = None
    upserted: list[T] = Field(default_factory=list)
    deleted: list[int] = Field(default_factory=list)
    summary: str | None = None
