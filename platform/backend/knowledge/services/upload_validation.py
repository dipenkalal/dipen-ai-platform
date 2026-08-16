from dataclasses import dataclass, field
from inspect import signature
from pathlib import Path

from fastapi import HTTPException

from knowledge.config import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
)

MAX_UPLOAD_FILENAME_LENGTH = 512
MAX_UPLOAD_CONTENT_TYPE_LENGTH = 255


@dataclass(slots=True)
class PreparedUpload:
    filename: str
    extension: str
    content_type: str
    content: bytes
    _position: int = field(
        default=0,
        init=False,
        repr=False,
    )

    async def read(
        self,
        size: int = -1,
    ) -> bytes:
        if self._position >= len(self.content):
            return b""

        if size < 0:
            end = len(self.content)
        else:
            end = min(
                self._position + size,
                len(self.content),
            )

        chunk = self.content[
            self._position:end
        ]
        self._position = end
        return chunk


def _sanitize_filename(
    value: str | None,
) -> str:
    raw = (
        value or "document"
    ).replace("\\", "/")

    filename = raw.rsplit(
        "/",
        1,
    )[-1].strip()

    filename = "".join(
        character
        for character in filename
        if character >= " "
        and character != "\x7f"
    )

    if not filename:
        filename = "document"

    if len(filename) > MAX_UPLOAD_FILENAME_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=(
                "The uploaded filename is too long"
            ),
        )

    return filename


def _normalize_content_type(
    value: str | None,
) -> str:
    if not value:
        return "application/octet-stream"

    media_type = (
        value.split(
            ";",
            1,
        )[0]
        .strip()
        .lower()
    )

    if not media_type:
        return "application/octet-stream"

    if (
        len(media_type)
        > MAX_UPLOAD_CONTENT_TYPE_LENGTH
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "The uploaded content type is too long"
            ),
        )

    return media_type


async def _read_upload(
    upload,
    limit: int,
) -> bytes:
    read = upload.read

    try:
        supports_sized_read = bool(
            signature(read).parameters
        )
    except (TypeError, ValueError):
        supports_sized_read = True

    if supports_sized_read:
        return await read(limit + 1)

    # Compatibility for legacy internal test doubles that
    # predate UploadFile.read(size). HTTP uploads use the
    # sized-read path above and remain bounded to limit + 1.
    return await read()


async def prepare_upload(
    upload,
    *,
    max_size_bytes: int | None = None,
    validate_extension: bool = True,
) -> PreparedUpload:
    filename = _sanitize_filename(
        upload.filename
    )
    extension = Path(filename).suffix.lower()
    content_type = _normalize_content_type(
        upload.content_type
    )

    if (
        validate_extension
        and extension not in ALLOWED_EXTENSIONS
    ):
        allowed = ", ".join(
            sorted(ALLOWED_EXTENSIONS)
        )

        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. "
                f"Allowed extensions: {allowed}"
            ),
        )

    limit = (
        MAX_FILE_SIZE_BYTES
        if max_size_bytes is None
        else max_size_bytes
    )

    if limit < 0:
        raise ValueError(
            "max_size_bytes cannot be negative"
        )

    try:
        content = await _read_upload(
            upload,
            limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unable to read the uploaded file"
            ),
        ) from exc

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )

    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=(
                "The uploaded file exceeds the "
                f"{limit} byte limit"
            ),
        )

    return PreparedUpload(
        filename=filename,
        extension=extension,
        content_type=content_type,
        content=content,
    )
