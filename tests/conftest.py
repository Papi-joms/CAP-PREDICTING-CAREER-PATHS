"""Keep each test run independent of old Windows pytest folder permissions."""

from pathlib import Path
import tempfile
from uuid import uuid4


def pytest_configure(config):
    """Use a fresh owned test directory unless the caller explicitly chooses one."""
    if config.option.basetemp is None:
        config.option.basetemp = str(Path(tempfile.gettempdir()) / f"cpp-pytest-{uuid4().hex}")
