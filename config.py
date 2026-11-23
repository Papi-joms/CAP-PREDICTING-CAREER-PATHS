"""Validate local MySQL settings without connecting or revealing secrets."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent


class ConfigurationError(ValueError):
    """Configuration is missing or invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    """Validated settings; the password is excluded from representations."""

    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)


def load_config(env_path: Path | None = None) -> DatabaseConfig:
    """Read .env; existing process environment variables take precedence."""
    load_dotenv(env_path if env_path is not None else PROJECT_ROOT / ".env", override=False)
    names = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value.strip()]
    if missing:
        raise ConfigurationError("Set these variables in your local .env: " + ", ".join(missing))
    try:
        port = int(values["MYSQL_PORT"])
    except ValueError:
        raise ConfigurationError("MYSQL_PORT must be an integer from 1 to 65535.") from None
    if not 1 <= port <= 65535:
        raise ConfigurationError("MYSQL_PORT must be an integer from 1 to 65535.")
    database = values["MYSQL_DATABASE"].strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", database):
        raise ConfigurationError("MYSQL_DATABASE must start with a letter and contain only letters, digits, or underscores (maximum 64 characters).")
    return DatabaseConfig(
        host=values["MYSQL_HOST"].strip(),
        port=port,
        database=database,
        user=values["MYSQL_USER"].strip(),
        password=values["MYSQL_PASSWORD"],
    )


def main() -> int:
    """Check configuration only; database connectivity is a separate check."""
    try:
        load_config()
    except ConfigurationError as error:
        print(f"Configuration error: {error}")
        return 1
    print("Configuration valid. MySQL connectivity has not been tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
