# -*- coding: utf-8 -*-
"""
从 Google Sheets 公开页面加载公司配置 → 转为 COMPANIES 列表。

优先尝试 CSV 导出（?output=csv），失败则回退到 HTML 表格解析。

env.json 中需配置:
  GOOGLE_SHEETS_CSV_URL   Google Sheets 发布后的 CSV/TSV/HTML 链接
"""
import csv
import io
import json
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))


def _get_csv_url():
    """从 env.json 或环境变量读取 Google Sheets 地址。"""
    url = os.environ.get("GOOGLE_SHEETS_CSV_URL", "").strip()
    if not url:
        env_file = os.path.join(HERE, "env.json")
        if os.path.isfile(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                env_data = json.load(f)
            url = env_data.get("GOOGLE_SHEETS_CSV_URL", "").strip()
    return url or None


def _split_pipe(val):
    """将竖线分隔的字符串拆为 list，空值返回空列表。"""
    if not val or not str(val).strip():
        return []
    return [x.strip() for x in str(val).split("|") if x.strip()]


def _ua():
    return {"User-Agent": "Mozilla/5.0 (compatible; LyellMonitor/2.1)"}


def fetch_text(url):
    """通用 HTTP GET，返回文本。失败返回 None。

    Google Sheets export 端点不声明 charset，requests 默认按 Latin-1 解码。
    此处用 r.content 强制按 UTF-8 解码，避免中文乱码。
    """
    try:
        r = requests.get(url, timeout=15, headers=_ua())
        r.raise_for_status()
        # Google Sheets CSV 导出无 charset 声明，强制 UTF-8
        r.encoding = "utf-8"
        return r.text
    except Exception as e:
        print(f"[sheets_loader] HTTP 错误 ({url[:60]}...): {e}", file=sys.stderr)
        return None


def _parse_html_table(html_text):
    """从 Google Sheets 公开 HTML 页面中提取表格内容，转为 COMPANIES 列表。

    Google 发布的 HTML 页面包含一个 <table>，表头为 <thead>、数据为 <tbody>。
    逐行匹配到已知列名后解析。
    """
    # 提取 <table> 内所有行
    table_m = re.search(r'<table[^>]*>(.*?)</table>', html_text, re.DOTALL | re.I)
    if not table_m:
        return None
    table = table_m.group(1)

    # 提取表头行（取所有 <th> 文本）
    thead_m = re.search(r'<thead[^>]*>(.*?)</thead>', table, re.DOTALL | re.I)
    headers = []
    if thead_m:
        headers = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<th[^>]*>(.*?)</th>', thead_m.group(1), re.DOTALL | re.I)]
    if not headers:
        return None

    # 建立列名到索引的映射
    col_map = {}
    for i, h in enumerate(headers):
        hl = h.lower().replace(' ', '_')
        col_map[hl] = i

    # 提取数据行
    rows_html = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL | re.I)
    companies = []
    for row_html in rows_html:
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL | re.I)]
        if len(cells) < 2:
            continue

        def cell_val(key):
            idx = col_map.get(key)
            if idx is not None and idx < len(cells):
                return cells[idx]
            return ""

        name = cell_val("name")
        if not name:
            continue

        tier = cell_val("tier") or "priority"
        company = {
            "name": name,
            "tier": tier,
            "category": cell_val("category"),
            "subject_id": cell_val("subject_id").strip().lower(),
            "subject_name": cell_val("subject_name"),
        }

        ticker = cell_val("sec_ticker")
        if ticker:
            company["sec_ticker"] = ticker

        rss = _split_pipe(cell_val("rss"))
        if rss:
            company["rss"] = rss

        news = _split_pipe(cell_val("news_pages"))
        if news:
            company["news_pages"] = news

        pk = _split_pipe(cell_val("product_keywords"))
        if pk:
            company["product_keywords"] = pk

        if not (company.get("sec_ticker") or company.get("rss") or company.get("news_pages")):
            continue

        companies.append(company)
    return companies


def fetch_csv():
    """从 Google Sheets 拉取数据。优先 CSV，失败则 HTML。"""
    url = _get_csv_url()
    if not url:
        return None

    # 模式1: 直接拉取（无论是 CSV/TSV 还是 HTML）
    text = fetch_text(url)
    if text is None:
        return None

    # 判断内容格式
    stripped = text.strip()
    if not stripped:
        return None

    # CSV 格式：以列名行开头
    if re.match(r'^(name|Name)', stripped):
        return text

    # TSV 格式
    if '\t' in stripped.split('\n', 1)[0] and re.match(r'^(name|Name)', stripped.split('\t')[0]):
        return text

    # HTML 格式：包含 <html 或 <table
    if '<html' in stripped.lower() or '<table' in stripped.lower():
        return text

    # 兜底：尝试作为 CSV 解析
    return text


def parse_csv(csv_text):
    """将 CSV/TSV 文本解析为 COMPANIES 列表。自动检测分隔符。"""
    if '<table' in csv_text.lower():
        # HTML 模式
        companies = _parse_html_table(csv_text)
        if companies:
            return companies
        # HTML 解析失败，往下尝试

    dialect = 'excel'
    if '\t' in csv_text.split('\n', 1)[0]:
        dialect = 'excel-tab'

    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
    companies = []
    for row in reader:
        name = row.get("name", "").strip()
        if not name:
            continue
        company = {
            "name": name,
            "tier": row.get("tier", "priority").strip() or "priority",
            "category": row.get("category", "").strip(),
            "subject_id": row.get("subject_id", "").strip().lower(),
            "subject_name": row.get("subject_name", "").strip(),
        }
        ticker = row.get("sec_ticker", "").strip()
        if ticker:
            company["sec_ticker"] = ticker

        rss = _split_pipe(row.get("rss", ""))
        if rss:
            company["rss"] = rss

        news = _split_pipe(row.get("news_pages", ""))
        if news:
            company["news_pages"] = news

        pk = _split_pipe(row.get("product_keywords", ""))
        if pk:
            company["product_keywords"] = pk

        if not (company.get("sec_ticker") or company.get("rss") or company.get("news_pages")):
            print(f"[sheets_loader] 跳过无信息源的行: {name}", file=sys.stderr)
            continue

        companies.append(company)
    return companies


def build_subjects(companies):
    """从公司列表按 subject_id 分组，生成 MONITORING_SUBJECTS。

    主体名称：优先 category=="监控主体"的公司名，其次 subject_name，最后 fallback 为 subject_id。
    """
    if not companies:
        return []
    by_subject = {}
    for c in companies:
        sid = c.get("subject_id", "").strip().lower()
        if not sid:
            sid = "default"
        if sid not in by_subject:
            by_subject[sid] = {"name": sid, "companies": []}
        by_subject[sid]["companies"].append(c["name"])
        # 第一个 category=="监控主体" 的公司名覆盖为主体名称
        if c.get("category", "").strip() == "监控主体":
            by_subject[sid]["name"] = c["name"]
    subjects = []
    for sid, info in by_subject.items():
        subjects.append({
            "id": sid,
            "name": info["name"],
            "description": f"{len(info['companies'])} 家公司",
            "companies": info["companies"],
        })
    return subjects


def load_companies(fallback=None):
    """主入口：从 Google Sheets 加载公司列表。"""
    csv_text = fetch_csv()
    if csv_text:
        companies = parse_csv(csv_text)
        if companies:
            print(f"[sheets_loader] 从 Google Sheets 加载了 {len(companies)} 家公司")
            return companies
    if fallback:
        print(f"[sheets_loader] 回退到本地 config.py COMPANIES ({len(fallback)} 家)")
        return fallback
    print("[sheets_loader] 警告: 无可用配置，返回空列表")
    return []


if __name__ == "__main__":
    csv_text = fetch_csv()
    if csv_text:
        companies = parse_csv(csv_text)
        print(json.dumps(companies, ensure_ascii=False, indent=2))
    elif _get_csv_url():
        print("Sheets 拉取失败，请检查网络或 URL。")
    else:
        print("未配置 GOOGLE_SHEETS_CSV_URL。")
        local_csv = os.path.join(HERE, "companies_template.csv")
        if os.path.isfile(local_csv):
            with open(local_csv, "r", encoding="utf-8") as f:
                companies = parse_csv(f.read())
            print(f"（从本地模板文件加载 {len(companies)} 家）")
            print(json.dumps(companies, ensure_ascii=False, indent=2))
