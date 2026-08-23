"""Credential-time Gmail/iCloud read-only contract smoke test."""

from __future__ import annotations

import json

from .config import Config
from .email_reader import EmailReadError, EmailReader


def main() -> int:
    config = Config.from_env()
    reader = EmailReader(
        config.email_accounts,
        timeout_seconds=config.request_timeout_seconds,
        max_body_bytes=config.email_max_body_bytes,
        max_body_chars=config.email_max_body_chars,
    )
    try:
        result = reader.verify_contract()
    except EmailReadError as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
