# -*- coding: utf-8 -*-
"""通用网页/RSS 监控：
   - rss        : 用 feedparser 解析订阅源
   - news_pages : 抓取页面锚文本，做“链接集合差异”检测（适配无 RSS 的 IR 新闻页）
"""
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from ..base import Item

_SKIP_PREFIXES = ("javascript:", "mailto:", "tel:", "#")
_MIN_LEN, _MAX_LEN = 20, 220


def fetch_rss(http, company):
    items = []
    for feed_url in company.get("rss") or []:
        try:
            raw = http.get(feed_url).content
            parsed = feedparser.parse(raw)
        except Exception as e:  # noqa: BLE001
            print(f"  [rss] {company['name']} {feed_url} 失败: {e}")
            continue
        for entry in parsed.entries[:40]:
            title = (entry.get("title") or "").strip()
            link = entry.get("link") or feed_url
            date = entry.get("published", "") or entry.get("updated", "")
            if not title:
                continue
            items.append(Item(
                company=company["name"], category=company["category"], source="web",
                title=title, url=link, date=date, detail="RSS",
            ))
    return items


def fetch_web(http, company):
    items = []
    seen_local = set()
    for page in company.get("news_pages") or []:
        try:
            html = http.get(page).text
        except Exception as e:  # noqa: BLE001
            print(f"  [web] {company['name']} {page} 失败: {e}")
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a"):
            href = (a.get("href") or "").strip()
            text = " ".join(a.get_text().split())
            if not href or href.startswith(_SKIP_PREFIXES):
                continue
            if not (_MIN_LEN <= len(text) <= _MAX_LEN):
                continue
            url = urljoin(page, href)
            key = (text, url)
            if key in seen_local:
                continue
            seen_local.add(key)
            items.append(Item(
                company=company["name"], category=company["category"], source="web",
                title=text, url=url, date="", detail=f"来源页: {page}",
            ))
    return items
