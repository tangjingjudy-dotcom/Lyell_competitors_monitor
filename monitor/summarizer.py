# -*- coding: utf-8 -*-
"""摘要生成：抓取新闻/论文页面内容，提取 1-2 句关键信息作为摘要。

策略（无 LLM API 依赖）：
  - 新闻稿 / RSS：抓取网页 HTML，尝试提取 <meta description>、<article> 首段、
    或页面首个有意义的 <p> 标签内容，截取前 2 句
  - ClinicalTrials.gov：从 item.detail 直接生成（已有状态/分期/更新日期）
  - SEC EDGAR：跳过（申报文件无摘要价值）
  - PubMed：优先用 PubMed API 获取 abstract，否则跳过

结果缓存到 data/summaries.json，避免重复抓取。
"""
import json
import os
import re
import time
from html.parser import HTMLParser

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SUMMARIES_FILE = os.path.join(DATA_DIR, "summaries.json")
SUMMARY_MAX_CHARS = 280


class _TextExtractor(HTMLParser):
    """从 HTML 中提取可见文本片段。"""
    def __init__(self):
        super().__init__()
        self.texts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "nav", "footer", "header"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t and len(t) > 10:
                self.texts.append(t)


def _extract_meta_description(html):
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html, re.I)
    return m.group(1).strip() if m else None


def _extract_first_paragraph(html):
    art_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL | re.I)
    target = art_match.group(1) if art_match else html
    ps = re.findall(r'<p[^>]*>(.*?)</p>', target, re.DOTALL | re.I)
    for p in ps:
        clean = re.sub(r'<[^>]+>', '', p).strip()
        clean = re.sub(r'\s+', ' ', clean)
        if len(clean) > 30:
            return clean
    return None


def _truncate_summary(text, max_chars=SUMMARY_MAX_CHARS):
    if len(text) <= max_chars:
        return text
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    result = ""
    for s in sentences:
        if len(result) + len(s) > max_chars:
            break
        result += s
    if not result:
        result = text[:max_chars] + "..."
    return result.strip()


def _load_cache():
    if not os.path.exists(SUMMARIES_FILE):
        return {}
    try:
        with open(SUMMARIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SUMMARIES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SUMMARIES_FILE)


def summarize_items(items, timeout=10, delay=0.5):
    cache = _load_cache()
    new_count = 0
    for item in items:
        uid = item.uid
        if uid in cache:
            continue
        summary = None
        if item.source == "clinicaltrials":
            summary = item.detail or "临床试验更新"
        elif item.source == "sec":
            summary = f"SEC申报: {item.detail}" if item.detail else "SEC申报更新"
        elif item.source == "pubmed":
            summary = item.detail or item.title
        elif item.source in ("web", "rss"):
            try:
                time.sleep(delay)
                r = requests.get(item.url, timeout=timeout,
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; LyellMonitor/1.0)"})
                r.raise_for_status()
                html = r.text
                summary = _extract_meta_description(html) or _extract_first_paragraph(html)
                if summary:
                    summary = _truncate_summary(summary)
            except Exception:
                pass
        if summary:
            cache[uid] = summary
            new_count += 1
    if new_count:
        _save_cache(cache)
    return cache


def generate_daily_report(subject_name, items, summaries):
    now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).astimezone()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M %Z")
    by_company = {}
    for it in items:
        co = it.company
        if co not in by_company:
            by_company[co] = []
        by_company[co].append(it)
    total_items = len(items)
    companies_count = len(by_company)

    md_lines = [
        f"# {subject_name} 竞品监控日报",
        f"",
        f"**生成时间**: {date_str} {time_str}",
        f"**监控条目**: {total_items} 条 · {companies_count} 家公司",
        f"",
        f"---",
        f"",
    ]

    html_lines = [
        '<div class="report">',
        f'<h2>{subject_name} 竞品监控日报</h2>',
        f'<div class="report-meta">生成时间: {date_str} {time_str} · {total_items} 条 · {companies_count} 家公司</div>',
        '<hr>',
    ]

    for co, co_items in sorted(by_company.items()):
        star = "★ " if any(it.tier == "priority" for it in co_items) else ""
        md_lines.append(f"## {star}{co}  ({len(co_items)} 条)")
        md_lines.append("")
        html_lines.append('<div class="report-company">')
        html_lines.append(f'<h3>{"★ " if star else ""}{co} ({len(co_items)} 条)</h3>')

        for it in co_items:
            src_label = {"clinicaltrials": "临床试验", "sec": "SEC", "pubmed": "论文", "web": "新闻", "rss": "新闻"}.get(it.source, it.source)
            summary = summaries.get(it.uid, "")
            date_display = it.date or ""

            md_lines.append(f"- **[{src_label}]** [{it.title}]({it.url})")
            if date_display:
                md_lines.append(f"  _{date_display}_")
            if summary:
                md_lines.append(f"  > {summary}")
            md_lines.append("")

            html_lines.append(
                f'<div class="report-item">'
                f'<span class="src src-{it.source}">{src_label}</span> '
                f'<a href="{it.url}" target="_blank">{it.title}</a>'
            )
            if date_display:
                html_lines.append(f'<span class="report-date">{date_display}</span>')
            if summary:
                html_lines.append(f'<p class="report-summary">{summary}</p>')
            html_lines.append('</div>')
        html_lines.append('</div>')
    html_lines.append('</div>')

    stats = {"total": total_items, "companies": companies_count, "date": date_str, "time": time_str}
    return "\n".join(html_lines), "\n".join(md_lines), stats
