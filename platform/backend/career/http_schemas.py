from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from career.schemas import (
    CareerApplicationEvent,
    CareerApplicationMaterial,
    CareerApplicationMaterialEvent,
    CareerApplicationMaterialVersion,
    CareerApplicationState,
    CareerMaterialContentFormat,
    CareerMaterialKind,
)


def _required_text(
    value: str,
    *,
    label: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{label} must not be blank"
        )

    return normalized


class CareerCreateApplicationRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    reason: str = Field(
        min_length=1,
        max_length=4000,
    )
    notes: str | None = Field(
        default=None,
        max_length=4000,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerCreateApplicationRequest:
        object.__setattr__(
            self,
            "reason",
            _required_text(
                self.reason,
                label="reason",
            ),
        )

        if self.notes is not None:
            normalized = self.notes.strip()

            object.__setattr__(
                self,
                "notes",
                normalized or None,
            )

        return self


class CareerTransitionRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    to_state: CareerApplicationState
    reason: str = Field(
        min_length=1,
        max_length=4000,
    )
    evidence_id: str | None = Field(
        default=None,
        max_length=300,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerTransitionRequest:
        object.__setattr__(
            self,
            "reason",
            _required_text(
                self.reason,
                label="reason",
            ),
        )

        return self


class CareerAdvanceToReviewRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    reason: str = Field(
        min_length=1,
        max_length=4000,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerAdvanceToReviewRequest:
        object.__setattr__(
            self,
            "reason",
            _required_text(
                self.reason,
                label="reason",
            ),
        )

        return self


class CareerApproveApplicationRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    reason: str = Field(
        min_length=1,
        max_length=4000,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerApproveApplicationRequest:
        object.__setattr__(
            self,
            "reason",
            _required_text(
                self.reason,
                label="reason",
            ),
        )

        return self


class CareerCreateMaterialRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    material_kind: CareerMaterialKind
    label: str = Field(
        min_length=1,
        max_length=200,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerCreateMaterialRequest:
        object.__setattr__(
            self,
            "label",
            _required_text(
                self.label,
                label="label",
            ),
        )

        return self


class CareerCreateMaterialVersionRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source_snapshot_id: str = Field(
        min_length=1,
        max_length=300,
    )
    content_format: CareerMaterialContentFormat
    content_text: str = Field(
        min_length=1,
    )
    parent_material_version_id: str | None = Field(
        default=None,
        pattern=(
            r"^career-material-version-"
            r"[0-9a-f]{24}$"
        ),
    )
    profile_version: str | None = Field(
        default=None,
        max_length=200,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerCreateMaterialVersionRequest:
        if not self.content_text.strip():
            raise ValueError(
                "content_text must not be blank"
            )

        object.__setattr__(
            self,
            "source_snapshot_id",
            _required_text(
                self.source_snapshot_id,
                label="source_snapshot_id",
            ),
        )

        if self.profile_version is not None:
            normalized = (
                self.profile_version.strip()
            )

            object.__setattr__(
                self,
                "profile_version",
                normalized or None,
            )

        return self


class CareerMarkMaterialReadyRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    reason: str = Field(
        min_length=1,
        max_length=4000,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerMarkMaterialReadyRequest:
        object.__setattr__(
            self,
            "reason",
            _required_text(
                self.reason,
                label="reason",
            ),
        )

        return self


CareerMaterialDecisionValue = Literal[
    "approve",
    "reject",
]


class CareerMaterialDecisionRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    decision: CareerMaterialDecisionValue
    reason: str = Field(
        default="",
        max_length=4000,
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> CareerMaterialDecisionRequest:
        normalized = self.reason.strip()

        if (
            self.decision == "reject"
            and len(normalized) < 2
        ):
            raise ValueError(
                "rejection requires a short "
                "owner reason"
            )

        object.__setattr__(
            self,
            "reason",
            normalized,
        )

        return self

class CareerApplicationEventListResponse(
    BaseModel
):
    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    items: tuple[
        CareerApplicationEvent,
        ...,
    ]


class CareerApplicationMaterialListResponse(
    BaseModel
):
    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    items: tuple[
        CareerApplicationMaterial,
        ...,
    ]


class CareerMaterialVersionListResponse(
    BaseModel
):
    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    items: tuple[
        CareerApplicationMaterialVersion,
        ...,
    ]


class CareerMaterialEventListResponse(
    BaseModel
):
    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    items: tuple[
        CareerApplicationMaterialEvent,
        ...,
    ]
