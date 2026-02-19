"""Click (SHOP API) signature validation helpers.

This module is written to be safe in development:
- When DEBUG=True, signature validation can be bypassed (see settings.CLICK_REQUIRE_SIGNATURE).
- When DEBUG=False, missing keys or invalid signature will be rejected.

Click's exact signature rules depend on the integration mode and parameters.
We implement the commonly used MD5 signature pattern used by Click SHOP API.
When you receive real Click test/production credentials, keep the algorithm
consistent with Click docs and adjust if needed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from django.conf import settings


@dataclass(frozen=True)
class ClickConfig:
    service_id: str
    merchant_user_id: str
    secret_key: str
    require_signature: bool


def get_click_config() -> ClickConfig:
    return ClickConfig(
        service_id=str(getattr(settings, "CLICK_SERVICE_ID", "") or "").strip(),
        merchant_user_id=str(getattr(settings, "CLICK_MERCHANT_USER_ID", "") or "").strip(),
        secret_key=str(getattr(settings, "CLICK_SECRET_KEY", "") or "").strip(),
        require_signature=bool(getattr(settings, "CLICK_REQUIRE_SIGNATURE", False)),
    )


def _md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def build_sign_string_prepare(*,
                              click_trans_id: str,
                              service_id: str,
                              secret_key: str,
                              merchant_trans_id: str,
                              amount: str,
                              action: str,
                              sign_time: str) -> str:
    # Most common pattern: click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time
    return f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{amount}{action}{sign_time}"


def build_sign_string_complete(*,
                               click_trans_id: str,
                               service_id: str,
                               secret_key: str,
                               merchant_trans_id: str,
                               merchant_prepare_id: str,
                               amount: str,
                               action: str,
                               sign_time: str) -> str:
    # Common complete pattern includes merchant_prepare_id as well.
    return f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"


def validate_signature(data: dict[str, Any], *, is_complete: bool) -> bool:
    """Validate Click's MD5 signature.

    In development, if signature is not required, returns True.
    """
    cfg = get_click_config()

    # Dev-mode bypass
    if not cfg.require_signature:
        return True

    # In prod, keys must exist
    if not (cfg.service_id and cfg.secret_key):
        return False

    click_trans_id = str(data.get("click_trans_id", ""))
    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    amount = str(data.get("amount", ""))
    action = str(data.get("action", ""))
    sign_time = str(data.get("sign_time", ""))
    provided = str(data.get("sign_string", ""))

    if not all([click_trans_id, merchant_trans_id, amount, action, sign_time, provided]):
        return False

    if is_complete:
        merchant_prepare_id = str(data.get("merchant_prepare_id", ""))
        if not merchant_prepare_id:
            return False
        raw = build_sign_string_complete(
            click_trans_id=click_trans_id,
            service_id=cfg.service_id,
            secret_key=cfg.secret_key,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount,
            action=action,
            sign_time=sign_time,
        )
    else:
        raw = build_sign_string_prepare(
            click_trans_id=click_trans_id,
            service_id=cfg.service_id,
            secret_key=cfg.secret_key,
            merchant_trans_id=merchant_trans_id,
            amount=amount,
            action=action,
            sign_time=sign_time,
        )

    expected = _md5_hex(raw)
    return expected == provided
