# -*- coding: utf-8 -*-
"""摘要生成 v3：抓取全文 → DeepSeek 理解式总结 + 提取式兜底。

策略改进（v2 → v3）：
  1. 创建一次 OpenAI client，复用给所有请求
  2. 每次 DeepSeek 失败时打印具体错误（标题+异常），方便排查
  3. DeepSeek 失败时，fallback 到提取式摘要（meta description → 首段 → 截断）
  4. SEC 跳过摘要，clinicaltrials 用 detail 字段生成

环境变量：
  DEEPSEEK_API_KEY — DeepSeek API 密钥
"""
import json
import os
import re
import time
from html.parser import HTMLParser

import requests
# openai 懒加载（仅 DeepSeek 需要，避免 --no-summary 时崩溃）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SUMMARIES_FILE = os.path.join(DATA_DIR, "summaries.json")
SUMMARY_MAX_CHARS = 260

DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ─── HTML 正文提取 ──────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self._depth = 0
        self._skip_tags = {"script", "style", "noscript", "nav", "footer", "header"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._depth += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._depth > 0:
            self._depth -= 1

    def handle_data(self, data):
        if self._depth == 0:
            t = data.strip()
            if t and len(t) > 8:
                self.texts.append(t)


def _fetch_article_text(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; LyellMonitor/1.0)"})
        r.raise_for_status()
        html = r.text
    except Exception:
        return ""

    for tag in ("article", "main", '[role="main"]'):
        m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', html, re.DOTALL | re.I)
        if m:
            html = m.group(1)
            break

    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass

    text = " ".join(parser.texts)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 4000:
        text = text[:4000]
    return text


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


def _truncate(text, max_chars=SUMMARY_MAX_CHARS):
    if len(text) <= max_chars:
        return text
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    result = ""
    for s in sentences:
        if len(result) + len(s) > max_chars:
            break
        result += s
    if not result:
        result = text[:max_chars]
    return result.strip()


def _extractive_summary(item):
    """提取式摘要（DeepSeek 失败时兜底）。"""
    if item.source == "clinicaltrials":
        return item.detail or "临床试验更新"
    if item.source == "sec":
        return None  # SEC 跳过
    if item.source == "pubmed":
        return item.detail or item.title
    # web / rss
    try:
        r = requests.get(item.url, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; LyellMonitor/1.0)"})
        r.raise_for_status()
        html = r.text
        result = _extract_meta_description(html) or _extract_first_paragraph(html)
        if result:
            return _truncate(result)
    except Exception:
        pass
    return item.title  # 最终兜底


def _build_prompt_text(item):
    src = item.source
    title = item.title
    detail = item.detail or ""
    date_str = item.date or ""

    if src == "clinicaltrials":
        return (
            f"【类型】临床试验更新\n"
            f"【公司】{item.company}\n"
            f"【标题】{title}\n"
            f"【详情】{detail}（更新于 {date_str}）"
        )

    if src == "sec":
        return None  # 不需要 LLM 摘要

    if src == "pubmed":
        article_text = _fetch_article_text(item.url)
        combined = f"{title}\n{detail}"
        if article_text:
            combined = f"{title}\n\n【摘要/正文】{article_text[:2000]}"
        return (
            f"【类型】学术论文\n"
            f"【公司】{item.company}\n"
            f"【内容】{combined}\n"
            f"【日期】{date_str}"
        )

    # web / rss
    article_text = _fetch_article_text(item.url)
    combined = f"{title}\n{detail}"
    if article_text:
        combined = f"{title}\n\n【正文】{article_text[:3000]}"
    return (
        f"【类型】新闻稿\n"
        f"【公司】{item.company}\n"
        f"【内容】{combined}\n"
        f"【日期】{date_str}"
    )


# ─── DeepSeek ───────────────────────────────────────────────────

_SUMMARIZE_SYSTEM = (
    "你是生物医药竞争情报分析师。用 1-2 句中文总结信息核心内容。"
    "临床数据必须体现关键数字（ORR、CR、PFS、OS、安全性、入组人数等）。"
    "监管/审批必须体现机构、适应症、阶段。合作/交易必须体现金额。"
    "只输出摘要本身，不加前缀、引号或标记。2 句内，≤200 字。"
)

_ds_client = None  # 模块级复用


def _get_deepseek_client(api_key):
    global _ds_client
    if _ds_client is None:
        from openai import OpenAI
        _ds_client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE)
    return _ds_client


def _deepseek_summarize(prompt_text, api_key, max_retries=2):
    if not api_key or not prompt_text:
        return None
    client = _get_deepseek_client(api_key)
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": _SUMMARIZE_SYSTEM},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            summary = resp.choices[0].message.content.strip()
            summary = re.sub(r'^["\'\u201c\u2018]|["\'\u201d\u2019]$', '', summary)
            summary = re.sub(r'^(摘要[：:]?\s*)', '', summary)
            if len(summary) > SUMMARY_MAX_CHARS:
                summary = summary[:SUMMARY_MAX_CHARS]
            return summary
        except Exception as e:
            if attempt < max_retries:
                time.sleep(3 * (attempt + 1))
            else:
                print(f"    [DS失败] retries exhausted: {type(e).__name__}")
                return None
    return None


# ─── 缓存 ───────────────────────────────────────────────────────

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


# ─── 主入口 ─────────────────────────────────────────────────────

def summarize_items(items, delay=1.2, max_per_run=60):
    """为一组 Item 生成摘要。DeepSeek 优先，失败则提取式兜底。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    cache = _load_cache()
    new_count = 0
    ds_ok = 0
    ds_fail = 0
    fallback_ok = 0

    for item in items:
        if new_count >= max_per_run:
            break
        uid = item.uid
        if uid in cache:
            continue

        summary = None

        # SEC 跳过
        if item.source == "sec":
            continue

        # 尝试 DeepSeek
        if api_key:
            prompt = _build_prompt_text(item)
            if prompt:
                time.sleep(delay)
                summary = _deepseek_summarize(prompt, api_key)
                if summary:
                    ds_ok += 1
                else:
                    ds_fail += 1
        else:
            ds_fail += 1

        # DeepSeek 失败则提取式兜底
        if not summary:
            fallback = _extractive_summary(item)
            if fallback:
                summary = _truncate(fallback)
                fallback_ok += 1

        if summary:
            cache[uid] = summary
            new_count += 1
            if new_count % 10 == 0:
                print(f"    摘要进度: {new_count} 条")

    if new_count:
        _save_cache(cache)
        print(f"    摘要完成: DeepSeek {ds_ok} 条, 兜底 {fallback_ok} 条, 失败 {ds_fail - fallback_ok} 条, 累计 {len(cache)} 条")

    return cache


def generate_daily_report(subject_name, items, summaries):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).astimezone()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M %Z")

    by_company = {}
    for it in items:
        co = it.company
        by_company.setdefault(co, []).append(it)

    total_items = len(items)
    companies_count = len(by_company)

    md_lines = [
        f"# {subject_name} 竞品监控日报",
        "",
        f"**生成时间**: {date_str} {time_str}",
        f"**监控条目**: {total_items} 条 · {companies_count} 家公司",
        "",
        "---",
        "",
    ]
    html_lines = [
        '<div class="report">',
        f'<h2>{subject_name} 竞品监控日报</h2>',
        f'<div class="report-meta">生成时间: {date_str} {time_str} · {total_items} 条 · {companies_count} 家公司</div>',
        '<hr>',
    ]

    for co, co_items in sorted(by_company.items(), key=lambda x: (not any((getattr(it, "tier", None) or it.get("tier", "")) == "priority" for it in x[1]), x[0])):
        star = "★ " if any((getattr(it, "tier", None) or it.get("tier", "")) == "priority" for it in co_items) else ""
        md_lines.append(f"## {star}{co}  ({len(co_items)} 条)")
        md_lines.append("")
        html_lines.append('<div class="report-company">')
        html_lines.append(f'<h3>{"★ " if star else ""}{co} ({len(co_items)} 条)</h3>')

        for it in co_items:
            src_label = {"clinicaltrials": "临床试验", "sec": "SEC", "pubmed": "论文",
                         "web": "新闻", "rss": "新闻"}.get(it.source, it.source)
            summary = summaries.get(it.uid, "")
            date_disp = it.date or ""

            md_lines.append(f"- **[{src_label}]** [{it.title}]({it.url})")
            if date_disp:
                md_lines.append(f"  _{date_disp}_")
            if summary:
                md_lines.append(f"  > {summary}")
            md_lines.append("")

            html_lines.append(
                f'<div class="report-item">'
                f'<span class="src src-{it.source}">{src_label}</span> '
                f'<a href="{it.url}" target="_blank">{it.title}</a>'
            )
            if date_disp:
                html_lines.append(f'<span class="report-date">{date_disp}</span>')
            if summary:
                html_lines.append(f'<p class="report-summary">{summary}</p>')
            html_lines.append('</div>')
        html_lines.append('</div>')
    html_lines.append('</div>')

    stats = {"total": total_items, "companies": companies_count, "date": date_str, "time": time_str}
    return "\n".join(html_lines), "\n".join(md_lines), stats
