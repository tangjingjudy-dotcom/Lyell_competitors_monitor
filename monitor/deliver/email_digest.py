# -*- coding: utf-8 -*-
"""邮件推送：仅在有新增时发送，且遵守最小发送间隔（防打扰）。"""
import html
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import formataddr

from ..base import META_FILE, load_json, save_json, now_iso

SOURCE_LABELS = {"clinicaltrials": "临床试验", "sec": "SEC申报", "pubmed": "论文", "web": "新闻"}


def _can_send(cfg):
    min_hours = cfg.get("min_hours_between_emails", 0)
    if min_hours <= 0:
        return True
    meta = load_json(META_FILE, {})
    last = meta.get("last_email_at")
    if not last:
        return True
    try:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last)
    except (ValueError, TypeError):
        return True
    return elapsed.total_seconds() >= min_hours * 3600


def _build_html(new_items, site_url=None):
    by_company = {}
    for it in new_items:
        by_company.setdefault(it.company, []).append(it)
    parts = [f'<h2 style="font-family:sans-serif;color:#1f3b57">竞品监控更新：{len(new_items)} 条新增</h2>']
    if site_url:
        parts.append(f'<p style="font-family:sans-serif;font-size:13px">完整看板：<a href="{html.escape(site_url)}">{html.escape(site_url)}</a></p>')
    for company, items in sorted(by_company.items()):
        parts.append(f'<h3 style="font-family:sans-serif;color:#1f3b57;margin:16px 0 6px">{html.escape(company)} ({len(items)})</h3><ul style="font-family:sans-serif;font-size:13px;line-height:1.5">')
        for it in items:
            label = SOURCE_LABELS.get(it.source, it.source)
            meta = " · ".join(x for x in [it.detail, it.date] if x)
            parts.append(
                f'<li>[{html.escape(label)}] <a href="{html.escape(it.url)}">{html.escape(it.title)}</a>'
                f'{f"<br><span style=\"color:#6e6e6e;font-size:11px\">{html.escape(meta)}</span>" if meta else ""}</li>'
            )
        parts.append('</ul>')
    return "\n".join(parts)


def send_digest(cfg, new_items, site_url=None):
    if not cfg.get("enabled"):
        return False, "email disabled"
    if not new_items:
        return False, "no new items"
    if not _can_send(cfg):
        return False, "throttled by min_hours_between_emails"

    body = _build_html(new_items, site_url)
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f'{cfg.get("subject_prefix","[监控]")} {len(new_items)} 条新增 · {datetime.now().strftime("%Y-%m-%d %H:%M")}'
    msg["From"] = formataddr(("竞品监控", cfg["from_addr"]))
    msg["To"] = ", ".join(cfg["to_addrs"])

    try:
        if cfg.get("use_tls", True):
            server = smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=30)
        server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["from_addr"], cfg["to_addrs"], msg.as_string())
        server.quit()
    except Exception as e:  # noqa: BLE001
        return False, f"send failed: {e}"

    meta = load_json(META_FILE, {})
    meta["last_email_at"] = now_iso()
    save_json(META_FILE, meta)
    return True, f"sent to {len(cfg['to_addrs'])} recipient(s)"
