"""
Outbound email over SMTP (stdlib smtplib).

For Gmail you must use an App Password (requires 2-Step Verification on the
Google account) — a normal login password will be rejected.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

from . import config


def _client() -> smtplib.SMTP:
    smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
    smtp.ehlo()
    if config.SMTP_STARTTLS:
        ctx = ssl.create_default_context()
        smtp.starttls(context=ctx)
        smtp.ehlo()
    if config.SMTP_USER and config.SMTP_PASS:
        smtp.login(config.SMTP_USER, config.SMTP_PASS)
    return smtp


def send(to: str, subject: str, text: str, html: str = None) -> None:
    """Send one message. Raises on failure so callers can log / fall back."""
    if not to:
        raise ValueError("no recipient")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((config.MAIL_FROM_NAME, config.MAIL_FROM))
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))

    with _client() as smtp:
        smtp.sendmail(config.MAIL_FROM, [to], msg.as_string())


def _key_html(key: str, tier: str, redeem_url: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;
      background:#0d0d10;color:#e8e8ea;padding:24px;">
      <div style="max-width:560px;margin:auto;background:#15151b;border:1px solid #2a2a33;
        border-radius:12px;padding:28px;">
        <h2 style="margin:0 0 4px;color:#fff;">Your {tier.title()} license key</h2>
        <p style="color:#9a9aa5;font-size:13px;margin-top:0;">ETS2 Photorealism preset pack</p>
        <p style="margin:22px 0 6px;color:#9a9aa5;font-size:12px;letter-spacing:.08em;">
          YOUR KEY (one-time use)</p>
        <div style="font-family:ui-monospace,Menlo,Consolas,monospace;font-size:24px;
          letter-spacing:.12em;color:#7CFFB2;background:#0b0b0e;border:1px solid #26262f;
          border-radius:8px;padding:16px;text-align:center;">{key}</div>
        <p style="margin:22px 0 8px;">
          <a href="{redeem_url}" style="background:#7CFFB2;color:#0b0b0e;text-decoration:none;
             padding:12px 20px;border-radius:8px;font-weight:bold;">Redeem &amp; download</a>
        </p>
        <p style="color:#9a9aa5;font-size:12px;line-height:1.6;">
          Enter the key above on the site to unlock your download. The key works once.
          Once downloaded, the files are yours to keep and use forever.<br><br>
          Keep this email — it is the only place your key appears. Do not post it publicly.
        </p>
      </div></body></html>"""


def _key_text(key: str, tier: str, redeem_url: str) -> str:
    return f"""Your {tier.title()} license key - ETS2 Photorealism

YOUR KEY (one-time use):
  {key}

Redeem it here:
  {redeem_url}

Enter the key on the site to unlock your download. The key works once.
Once downloaded, the files are yours to keep and use forever.

Keep this email - it is the only place your key appears. Do not post it publicly.
"""


def send_key(to: str, key: str, tier: str) -> None:
    redeem_url = f"{config.SITE_URL}/#redeem"
    send(
        to,
        f"Your ETS2 Photorealism {tier.title()} key",
        _key_text(key, tier, redeem_url),
        _key_html(key, tier, redeem_url),
    )


def notify_admin(subject: str, body: str) -> None:
    if not config.ADMIN_EMAIL:
        return
    try:
        send(config.ADMIN_EMAIL, f"[store] {subject}", body)
    except Exception:
        pass  # admin notices are best-effort
