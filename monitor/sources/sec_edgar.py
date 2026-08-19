# -*- coding: utf-8 -*-
"""SEC EDGAR：ticker→CIK 映射 + submissions API，只保留年报/季报（10-K / 10-Q / 20-F / 40-F）。"""
import os

from ..base import Item, DATA_DIR, load_json, save_json

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
TICKER_CACHE_FILE = os.path.join(DATA_DIR, "sec_ticker_map.json")

_ticker_cache = None

_DEFAULT_FINANCIAL_FORMS = {
    "10-K", "10-K/A", "10-Q", "10-Q/A",
    "20-F", "20-F/A", "40-F", "40-F/A",
}


def _allowed_sec_forms():
    """美国没有单独月报：10-K 年报、10-Q 季报；外国发行人对应 20-F / 40-F。"""
    try:
        from config import SETTINGS
        forms = (SETTINGS.get("milestone_filter") or {}).get("meaningful_sec_forms") or []
        out = {str(f).strip().upper() for f in forms if str(f).strip()}
        if out:
            return out
    except Exception:
        pass
    return set(_DEFAULT_FINANCIAL_FORMS)


def _load_ticker_map(http, stats=None):
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache

    # 尝试从 API 拉取（SEC 要求 User-Agent 带真实联系方式）
    try:
        data = http.get_json(TICKERS_URL,
                             headers={"User-Agent": "LyellCompetitorMonitor/1.0 (contact: tangjingjudy@gmail.com)"})
    except Exception as e:  # noqa: BLE001
        print(f"  [sec] 加载 ticker 映射失败（API）: {e}")
        # 回退：读取本地缓存（上一次成功拉取的版本）
        cached = load_json(TICKER_CACHE_FILE, None)
        if cached:
            print(f"  [sec] 回退到本地缓存（{len(cached)} 家公司）")
            _ticker_cache = cached
            if stats:
                stats.record("sec_ticker_map", ok=True, count=len(cached))
            return _ticker_cache
        # 没有任何缓存可用 → 记故障
        if stats:
            stats.record("sec_ticker_map", ok=False)
        _ticker_cache = {}
        return _ticker_cache

    m = {}
    for row in data.values():
        m[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    _ticker_cache = m

    # 成功后写入本地缓存，供后续故障时回退
    save_json(TICKER_CACHE_FILE, m)

    if stats:
        stats.record("sec_ticker_map", ok=True, count=len(m))
    return m


def fetch(http, company, recent_count=30, stats=None):
    ticker = company.get("sec_ticker")
    if not ticker:
        return []
    cikmap = _load_ticker_map(http, stats=stats)
    cik10 = cikmap.get(ticker.upper())
    if not cik10:
        return []
    try:
        data = http.get_json(SUBMISSIONS.format(cik10=cik10),
                             headers={"Host": "data.sec.gov",
                                      "User-Agent": "LyellCompetitorMonitor/1.0 (contact: tangjingjudy@gmail.com)"})
    except Exception as e:  # noqa: BLE001
        print(f"  [sec] {company['name']} ({ticker}) 失败: {e}")
        if stats:
            stats.record("sec", ok=False)
        return []

    recent = (data.get("filings", {}) or {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    descs = recent.get("primaryDocDescription", [])
    cik_int = int(cik10)

    allowed = _allowed_sec_forms()
    items = []
    skipped = 0
    for i in range(len(forms)):
        form = forms[i] if i < len(forms) else ""
        if form.strip().upper() not in allowed:
            skipped += 1
            continue
        accn = accns[i] if i < len(accns) else ""
        date = dates[i] if i < len(dates) else ""
        doc = docs[i] if i < len(docs) else ""
        desc = descs[i] if i < len(descs) else ""
        accn_nodash = accn.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/{doc}" if doc else \
              f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik10}&type=&dateb=&owner=include&count=40"
        items.append(Item(
            company=company["name"], category=company["category"], source="sec",
            title=f"{form} 申报" + (f"：{desc}" if desc else ""),
            url=url, date=date, detail=f"表单 {form}",
            uid=f"sec-{accn}",
        ))
        if len(items) >= recent_count:
            break
    if skipped:
        print(f"  [sec] {company['name']} 已过滤 {skipped} 份非财报表单，保留 {len(items)} 份年报/季报")
    if stats:
        stats.record("sec", ok=True, count=len(items))
    return items
