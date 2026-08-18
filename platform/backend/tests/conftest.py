import os
import tempfile
from pathlib import Path


TEST_DATA_DIRECTORY = (
    Path(tempfile.gettempdir())
    / "dap-backend-tests"
)

os.environ.setdefault(
    "KNOWLEDGE_UPLOAD_DIRECTORY",
    str(
        TEST_DATA_DIRECTORY
        / "knowledge-uploads"
    ),
)
