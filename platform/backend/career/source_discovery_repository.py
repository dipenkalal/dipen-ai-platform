from __future__ import annotations

from datetime import datetime
import sqlite3
from typing import Any

from career.source_discovery import (
    CareerSourceDiscoveryCandidate,
    DiscoveryState,
    transition_candidate,
)


class DiscoveryRepositoryError(
    RuntimeError
):
    pass


class DiscoveryRepositoryConflictError(
    DiscoveryRepositoryError
):
    pass


class DiscoveryRepositoryAuthorityError(
    DiscoveryRepositoryError
):
    pass


_COLUMNS = (
    "discovery_candidate_id",
    "provider_identity_key",
    "employer_name",
    "provider_kind",
    "canonical_career_url",
    "provider_identity_json",
    "provider_identity_sha256",
    "state",
    "discovery_research_evidence_id",
    "listing_research_evidence_id",
    "detail_research_evidence_id",
    "last_error_code",
    "first_seen_at",
    "last_seen_at",
    "state_changed_at",
    "admitted_source_id",
    "created_at",
    "updated_at",
)


_WRITE_COLUMNS = tuple(
    name
    for name in _COLUMNS
    if name != "discovery_candidate_id"
)


_SELECT_COLUMNS = ", ".join(
    _COLUMNS
)


def _datetime_text(
    value: datetime,
) -> str:

    return value.isoformat()


def _parse_datetime(
    value: str,
) -> datetime:

    return datetime.fromisoformat(
        value
    )


def _candidate_values(
    candidate: CareerSourceDiscoveryCandidate,
) -> tuple[Any, ...]:

    values = []

    for column in _COLUMNS:

        value = getattr(
            candidate,
            column,
        )

        if isinstance(
            value,
            DiscoveryState,
        ):
            value = value.value

        elif isinstance(
            value,
            datetime,
        ):
            value = _datetime_text(
                value
            )

        values.append(value)

    return tuple(values)


def _candidate_write_values(
    candidate: CareerSourceDiscoveryCandidate,
) -> tuple[Any, ...]:

    full = dict(
        zip(
            _COLUMNS,
            _candidate_values(candidate),
            strict=True,
        )
    )

    return tuple(
        full[column]
        for column in _WRITE_COLUMNS
    )


def _row_to_candidate(
    row: sqlite3.Row,
) -> CareerSourceDiscoveryCandidate:

    return CareerSourceDiscoveryCandidate(
        discovery_candidate_id=
            row["discovery_candidate_id"],

        provider_identity_key=
            row["provider_identity_key"],

        employer_name=
            row["employer_name"],

        provider_kind=
            row["provider_kind"],

        canonical_career_url=
            row["canonical_career_url"],

        provider_identity_json=
            row["provider_identity_json"],

        provider_identity_sha256=
            row["provider_identity_sha256"],

        state=DiscoveryState(
            row["state"]
        ),

        discovery_research_evidence_id=
            row[
                "discovery_research_evidence_id"
            ],

        listing_research_evidence_id=
            row[
                "listing_research_evidence_id"
            ],

        detail_research_evidence_id=
            row[
                "detail_research_evidence_id"
            ],

        last_error_code=
            row["last_error_code"],

        first_seen_at=_parse_datetime(
            row["first_seen_at"]
        ),

        last_seen_at=_parse_datetime(
            row["last_seen_at"]
        ),

        state_changed_at=_parse_datetime(
            row["state_changed_at"]
        ),

        admitted_source_id=
            row["admitted_source_id"],

        created_at=_parse_datetime(
            row["created_at"]
        ),

        updated_at=_parse_datetime(
            row["updated_at"]
        ),
    )


class CareerSourceDiscoveryRepository:

    def __init__(
        self,
        connection: sqlite3.Connection,
    ) -> None:

        if not isinstance(
            connection,
            sqlite3.Connection,
        ):
            raise TypeError(
                "connection must be sqlite3.Connection"
            )

        self._connection = connection

        self._connection.row_factory = (
            sqlite3.Row
        )

    @property
    def connection(
        self,
    ) -> sqlite3.Connection:

        return self._connection

    def insert(
        self,
        candidate:
            CareerSourceDiscoveryCandidate,
    ) -> CareerSourceDiscoveryCandidate:

        if (
            candidate.state
            == DiscoveryState.ADMITTED
        ):
            raise (
                DiscoveryRepositoryAuthorityError(
                    "discovery repository may "
                    "not insert ADMITTED rows"
                )
            )

        placeholders = ", ".join(
            "?"
            for _ in _COLUMNS
        )

        columns = ", ".join(
            _COLUMNS
        )

        sql = (
            "INSERT INTO "
            "career_source_discovery_candidates "
            f"({columns}) "
            f"VALUES ({placeholders})"
        )

        try:

            self._connection.execute(
                sql,
                _candidate_values(
                    candidate
                ),
            )

        except sqlite3.IntegrityError as exc:

            raise DiscoveryRepositoryError(
                "discovery candidate insert "
                "violated persistence constraints"
            ) from exc

        return candidate

    def get(
        self,
        discovery_candidate_id: str,
    ) -> CareerSourceDiscoveryCandidate | None:

        row = self._connection.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM career_source_discovery_candidates
            WHERE discovery_candidate_id = ?
            """,
            (
                discovery_candidate_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return _row_to_candidate(
            row
        )

    def list_by_state(
        self,
        state: DiscoveryState,
        *,
        limit: int = 100,
    ) -> tuple[
        CareerSourceDiscoveryCandidate,
        ...,
    ]:

        normalized_state = (
            DiscoveryState(state)
        )

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > 1000
        ):
            raise ValueError(
                "limit must be integer 1..1000"
            )

        rows = self._connection.execute(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM career_source_discovery_candidates
            WHERE state = ?
            ORDER BY
                first_seen_at ASC,
                discovery_candidate_id ASC
            LIMIT ?
            """,
            (
                normalized_state.value,
                limit,
            ),
        ).fetchall()

        return tuple(
            _row_to_candidate(row)
            for row in rows
        )

    def transition(
        self,
        discovery_candidate_id: str,
        target: DiscoveryState,
        *,
        expected_state: DiscoveryState,
        expected_updated_at: datetime,
        at: datetime,
        last_error_code: str | None = None,
        **updates: Any,
    ) -> CareerSourceDiscoveryCandidate:

        target_state = DiscoveryState(
            target
        )

        expected_state = DiscoveryState(
            expected_state
        )

        if target_state == DiscoveryState.ADMITTED:
            raise (
                DiscoveryRepositoryAuthorityError(
                    "ADMITTED transition requires "
                    "separate admission authority"
                )
            )

        current = self.get(
            discovery_candidate_id
        )

        if current is None:
            raise DiscoveryRepositoryConflictError(
                "discovery candidate does not exist"
            )

        if current.state != expected_state:
            raise DiscoveryRepositoryConflictError(
                "expected_state does not match "
                "current persisted state"
            )

        if (
            current.updated_at
            != expected_updated_at
        ):
            raise DiscoveryRepositoryConflictError(
                "expected_updated_at does not match "
                "current persisted version"
            )

        transitioned = transition_candidate(
            current,
            target_state,
            at=at,
            last_error_code=
                last_error_code,
            **updates,
        )

        assignments = ", ".join(
            f"{column} = ?"
            for column in _WRITE_COLUMNS
        )

        sql = (
            "UPDATE "
            "career_source_discovery_candidates "
            f"SET {assignments} "
            "WHERE discovery_candidate_id = ? "
            "AND state = ? "
            "AND updated_at = ?"
        )

        parameters = (
            *_candidate_write_values(
                transitioned
            ),
            current.discovery_candidate_id,
            current.state.value,
            _datetime_text(
                current.updated_at
            ),
        )

        try:

            cursor = self._connection.execute(
                sql,
                parameters,
            )

        except sqlite3.IntegrityError as exc:

            raise DiscoveryRepositoryError(
                "discovery transition violated "
                "persistence constraints"
            ) from exc

        if cursor.rowcount != 1:
            raise DiscoveryRepositoryConflictError(
                "optimistic discovery transition "
                "conflict"
            )

        return transitioned
