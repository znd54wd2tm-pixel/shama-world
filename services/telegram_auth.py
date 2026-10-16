"""Telegram WebApp initData validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    """Raised when Telegram initData cannot be trusted."""


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86_400,
    allow_dev: bool = False,
) -> dict[str, Any]:
    if not init_data:
        if allow_dev:
            return {"id": 900000001, "username": "dev_user", "first_name": "Dev", "last_name": "User"}
        raise TelegramAuthError("Telegram initData is required")

    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", "")
    if not received_hash:
        raise TelegramAuthError("Telegram initData hash is missing")
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        raise TelegramAuthError("Telegram initData signature is invalid")

    auth_date = fields.get("auth_date")
    if not auth_date:
        raise TelegramAuthError("Telegram auth_date is missing")
    try:
        age = time.time() - int(auth_date)
    except ValueError as error:
        raise TelegramAuthError("Telegram auth_date is invalid") from error
    if age > max_age_seconds or age < -60:
        raise TelegramAuthError("Telegram initData has expired")

    try:
        user = json.loads(fields["user"])
    except (KeyError, json.JSONDecodeError) as error:
        raise TelegramAuthError("Telegram user data is missing or invalid") from error
    if not isinstance(user, dict) or not user.get("id") or not user.get("first_name"):
        raise TelegramAuthError("Telegram user data is incomplete")
    return user
