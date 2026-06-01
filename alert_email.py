"""SMTP alert delivery for the StockPicker POC."""

from __future__ import annotations

import os

# import smtplib
# from email.message import EmailMessage


def _smtp_settings() -> dict[str, str | int] | None:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    to_email = os.environ.get("ALERT_TO_EMAIL", "").strip()
    if not all([host, user, password, to_email]):
        return None
    port_raw = os.environ.get("SMTP_PORT", "587").strip()
    return {
        "host": host,
        "port": int(port_raw),
        "user": user,
        "password": password,
        "to_email": to_email,
    }


def send_alert_email(
    symbol: str,
    rule_name: str,
    value: float,
    threshold: float,
    *,
    timestamp: int,
) -> bool:
    """
    Log alert email details to stdout. SMTP send is disabled until configured.

    When enabling SMTP, uncomment the smtplib block and set:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_TO_EMAIL.
    """
    subject = f"[StockPicker POC] {symbol} {rule_name} triggered"
    body = (
        f"Symbol: {symbol}\n"
        f"Rule: {rule_name}\n"
        f"Measured value: {value:.4f}\n"
        f"Threshold: {threshold}\n"
        f"Event timestamp: {timestamp}\n"
    )

    to_email = os.environ.get("ALERT_TO_EMAIL", "not configured").strip() or "not configured"
    smtp_host = os.environ.get("SMTP_HOST", "not configured").strip() or "not configured"
    smtp_port = os.environ.get("SMTP_PORT", "587").strip() or "587"
    smtp_user = os.environ.get("SMTP_USER", "not configured").strip() or "not configured"

    print(
        f"EMAIL preparing alert: symbol={symbol} rule={rule_name} "
        f"measured={value:.4f} threshold={threshold} timestamp={timestamp}",
        flush=True,
    )
    print(
        f"EMAIL would send via {smtp_host}:{smtp_port} from={smtp_user} "
        f"to={to_email} subject={subject!r}",
        flush=True,
    )
    print(f"EMAIL body:\n{body}", flush=True)

    # --- SMTP connectivity (disabled — uncomment when server is set up) ---
    # settings = _smtp_settings()
    # if settings is None:
    #     print(
    #         "EMAIL alert failed: SMTP not configured "
    #         "(set SMTP_HOST, SMTP_USER, SMTP_PASS, ALERT_TO_EMAIL)",
    #         flush=True,
    #     )
    #     return False
    #
    # message = EmailMessage()
    # message["Subject"] = subject
    # message["From"] = str(settings["user"])
    # message["To"] = str(settings["to_email"])
    # message.set_content(body)
    #
    # host = str(settings["host"])
    # port = int(settings["port"])
    # user = str(settings["user"])
    # password = str(settings["password"])
    # to_email = str(settings["to_email"])
    #
    # try:
    #     if port == 465:
    #         with smtplib.SMTP_SSL(host, port, timeout=30) as server:
    #             server.login(user, password)
    #             server.send_message(message)
    #     else:
    #         with smtplib.SMTP(host, port, timeout=30) as server:
    #             server.starttls()
    #             server.login(user, password)
    #             server.send_message(message)
    # except Exception as exc:
    #     print(
    #         f"EMAIL alert failed: symbol={symbol} rule={rule_name} error={exc}",
    #         flush=True,
    #     )
    #     return False
    #
    # print(
    #     f"EMAIL alert sent: symbol={symbol} rule={rule_name} to={to_email}",
    #     flush=True,
    # )
    # return True

    print(
        f"EMAIL alert logged (SMTP send disabled): symbol={symbol} rule={rule_name}",
        flush=True,
    )
    return True
