# -*- coding: utf-8 -*-
"""摘要生成 v2：抓取全文 → DeepSeek 阅读理解式总结（含关键数据提取）。

数据流：
  1. 对每条 web/rss/pubmed 条目，抓取文章全文（最多 4000 字符）
  2. 对 clinicaltrials/sec 条目，用内置信息拼接
  3. 调用 DeepSeek API 生成中文摘要（1-2 句，关键数据优先）
  4. 结果缓存到 data/summaries.json

环境变量：
  DEEPSEEK_API_KEY — DeepSeek API 密钥（https://platform.deepseek.com）
"""
import json
import os
import re
import time
from html.parser import HTMLParser

import requests
from openai import OpenAI

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
    """抓取网页全文（去 HTML 标签），返回纯文本（最多 4000 字符）。"""
    try:
        r = requests.get(url, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; LyellMonitor/1.0)"})
        r.raise_for_status()
        html = r.text
    except Exception:
        return ""

    # 尝试提取 <article> 或主内容区
    for tag in ("article", "main", '[role="main"]'):
        m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', html, re.DOTALL | re.I)
        if m:
            html = m.group(1)
            break

    # 纯文本提取
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


def _build_prompt_text(item):
    """为不同类型的条目构建传给 LLM 的输入文本。"""
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
        return (
            f"【类型】SEC 申报文件\n"
            f"【公司】{item.company}\n"
            f"【表单】{title}\n"
            f"【详情】{detail}（提交于 {date_str}）"
        )

    if src == "pubmed":
        # PubMed 可能有 abstract 在 detail 里，再补抓全文
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


# ─── DeepSeek 调用 ──────────────────────────────────────────────

_SUMMARIZE_SYSTEM = """你是一个生物医药竞争情报分析师。你的任务是用中文撰写简洁的每日摘要。

要求：
1. 用 1-2 句话总结这条信息的核心内容。
2. 如果是临床数据更新，必须体现关键数据（ORR、CR、PFS、OS、安全性、入组人数等）。
3. 如果是监管/审批进展，必须体现监管机构、适应症、阶段。
4. 如果是合作/交易/财报，必须体现金额或交易结构。
5. 只输出摘要本身，不要加"摘要："前缀，不要加引号或其他标记。
6. 控制在 2 句话以内，中文，不超过 200 字。"""


def _deepseek_summarize(prompt_text, api_key, max_retries=2):
    """调用 DeepSeek API 生成摘要。"""
    if not api_key:
        return None
    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE)
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
            # 清理多余引号/标记
            summary = re.sub(r'^["\'\u201c\u2018]|["\'\u201d\u2019]$', '', summary)
            summary = re.sub(r'^(摘要[：:]?\s*)', '', summary)
            if len(summary) > SUMMARY_MAX_CHARS:
                summary = summary[:SUMMARY_MAX_CHARS]
            return summary
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
            else:
                print(f"    [DeepSeek 失败] {e}")
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
    """为一组 Item 生成 DeepSeek 摘要。

    参数:
      items: Item 列表
      delay: 每次 API 调用间隔（秒），DeepSeek 免费版 QPS 较低
      max_per_run: 单次最多生成条数（控制成本）

    返回: {uid: summary_str} 的缓存字典（含已有缓存）
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("    ⚠ 未设置 DEEPSEEK_API_KEY 环境变量，跳过摘要生成")
        return _load_cache()

    cache = _load_cache()
    new_count = 0

    for item in items:
        if new_count >= max_per_run:
            break
        uid = item.uid
        if uid in cache:
            continue

        prompt = _build_prompt_text(item)
        if not prompt.strip():
            continue

        time.sleep(delay)
        summary = _deepseek_summarize(prompt, api_key)

        if summary:
            cache[uid] = summary
            new_count += 1
            if new_count % 10 == 0:
                print(f"    摘要进度: {new_count} 条")

    if new_count:
        _save_cache(cache)
        print(f"    摘要生成完成: 新增 {new_count} 条，累计 {len(cache)} 条")

    return cache


def generate_daily_report(subject_name, items, summaries):
    """为某个监控主体生成日度摘要报告（Markdown + HTML）。"""
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
