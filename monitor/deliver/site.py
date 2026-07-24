# -*- coding: utf-8 -*-
"""静态站点 v5：内联摘要生成 —— 读 items.json → 生成摘要 → 渲染页面，一步完成。

摘要策略（按来源）：
  clinicaltrials → 用 detail 字段（状态/分期/更新日期）
  SEC → 跳过
  pubmed/web/rss → 抓取网页元描述或正文前500字符 → 截取前2句
  全部 fail → 摘要为 "-"

不再依赖 run.py 的 summarize_items 调用链。
"""
import html, json, os, re, io, sys
from datetime import datetime, timezone, timedelta

import requests

# DeepSeek 懒加载（仅 api_key 存在时 import）
_DS_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
if _DS_API_KEY:
    try:
        from openai import OpenAI
        _DS_CLIENT = OpenAI(api_key=_DS_API_KEY, base_url="https://api.deepseek.com")
    except Exception:
        _DS_CLIENT = None
else:
    _DS_CLIENT = None

from ..base import ITEMS_DB, RUN_LOG, load_json, save_json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SOURCE_LABELS = {
    "clinicaltrials": "临床试验",
    "sec": "SEC申报",
    "pubmed": "论文",
    "web": "新闻",
    "rss": "新闻",
}
HEALTH_SOURCE_LABELS = {
    "clinicaltrials": "ClinicalTrials.gov",
    "sec": "SEC EDGAR",
    "sec_ticker_map": "SEC代码映射表",
    "pubmed": "PubMed",
    "rss": "RSS订阅",
    "web": "官网新闻页",
}
STALE_HOURS = 36
SUMMARY_MAX_LEN = 200

_GARBAGE = ("we use cookies", "this website uses", "we and our", "click here to",
            "please enable javascript", "your browser does not support",
            "comprehensive up-to-date news", "aggregated from sources all over")

# ─── 摘要生成（内联） ───────────────────────────────────────────

def _is_garbage(text):
    t = text.lower().strip()
    if not t or len(t) < 15:
        return True
    return any(g in t for g in _GARBAGE)

def _similar_to_title(text, title, threshold=0.85):
    """标题和摘要是否过于相似（重复比例>threshold）。"""
    if not text or not title:
        return False
    # 简化为：标题是否完整出现在摘要开头
    clean_title = re.sub(r'\s+', ' ', title).strip().lower()
    clean_text = re.sub(r'\s+', ' ', text).strip().lower()
    if len(clean_title) < 20:
        return False
    return clean_text.startswith(clean_title[:min(len(clean_title), len(clean_text))])

def _generate_summary(item):
    """为单条 item 生成摘要文本。优先 DeepSeek，失败则提取式兜底。"""
    src = item.get("source", "")
    title = item.get("title", "")
    detail = item.get("detail", "")
    url = item.get("url", "")

    # clinicaltrials: 人性化格式化（含药品名/适应症简短描述）
    if src == "clinicaltrials":
        ct_short = _fmt_ct(detail)
        drug_hint = _extract_drug_hint(title)
        if drug_hint:
            return f"{drug_hint} —— {ct_short}"
        return ct_short

    # SEC: 跳过
    if src == "sec":
        return None

    # pubmed/web/rss: 提取正文
    full_text = _try_fetch_extract(url, title) or _deep_extract(url) or ""
    if full_text and (_is_garbage(full_text) or _similar_to_title(full_text, title)):
        full_text = ""  # 无效内容跳过

    # —— DeepSeek 路径（仅周一执行，其他日子读缓存） ——
    if _DS_CLIENT and (full_text or title) and _ds_due_today():
        result = _ds_summarize(full_text, title, item.get("company", ""), src)
        if result:
            return result

    # —— 提取式兜底 ——
    if full_text:
        return _truncate(full_text)
    return None

_DS_SYSTEM = (
    "你是生物医药竞争情报分析师。用1-2句中文总结信息核心内容。"
    "临床数据必须体现关键数字（ORR、CR、PFS、OS、安全性、入组人数等）。"
    "监管/审批必须体现机构、适应症。合作/交易必须体现金额。"
    "只输出摘要本身，不加前缀、引号或标记。≤180字。"
)

def _ds_due_today():
    """周一自动执行；FORCE_DS_SUMMARY 环境变量强制执行。"""
    if os.environ.get("FORCE_DS_SUMMARY", "").strip() == "1":
        return True
    return datetime.now(timezone.utc).astimezone().weekday() == 0


def _ds_summarize(body_text, title, company, source):
    """调用 DeepSeek 生成摘要。失败返回 None。"""
    if not _DS_CLIENT:
        return None
    src_label = {"pubmed": "学术论文", "web": "新闻稿", "rss": "新闻稿"}.get(source, "新闻稿")
    user_text = f"【公司】{company}\n【类型】{src_label}\n【标题】{title}"
    if body_text:
        user_text += f"\n【正文】{body_text[:2500]}"
    try:
        resp = _DS_CLIENT.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _DS_SYSTEM},
                {"role": "user", "content": user_text},
            ],
            temperature=0.3, max_tokens=300,
        )
        summary = resp.choices[0].message.content.strip()
        summary = re.sub(r'''^["'\u201c\u2018]|["'\u201d\u2019]$''', '', summary)
        summary = re.sub(r'^(摘要[：:]?\s*)', '', summary)
        if len(summary) > 200:
            summary = summary[:200]
        return summary if summary else None
    except Exception:
        return None

def _extract_drug_hint(title):
    """从临床试验标题中提取药品名和适应症简短提示。
    如: 'A Study to Evaluate AZD5492, a T Cell-engaging Antibody...
    → 'AZD5492 (抗CD20 T细胞衔接双抗)'"""
    t = title.strip()
    # 抓大写字母+数字组合（药品代码）
    codes = re.findall(r'\b([A-Z]{2,}\d{2,})\b', t)
    # 抓常见药品名模式
    names = re.findall(r'\b([A-Z][a-z]+-?cel|[A-Z][a-z]+-?mab|[A-Z][a-z]+-?cept|[A-Z][a-z]+-?nib|[A-Z][a-z]+-?stat)\b', t, re.I)
    product = codes[0] if codes else (names[0] if names else "")
    if not product:
        return ""
    # 适应症关键词
    indications = {
        "multiple myeloma": "多发性骨髓瘤", "myeloma": "多发性骨髓瘤",
        "lymphoma": "淋巴瘤", "dlbcl": "弥漫大B细胞淋巴瘤",
        "leukemia": "白血病", "melanoma": "黑色素瘤",
        "nsclc": "非小细胞肺癌", "lung": "肺癌",
        "breast": "乳腺癌", "ovarian": "卵巢癌",
        "colorectal": "结直肠癌", "mCRC": "转移性结直肠癌",
        "solid tumor": "实体瘤", "glioblastoma": "胶质母细胞瘤",
        "autoimmune": "自身免疫病", "diabetes": "糖尿病",
    }
    indication = ""
    tlower = t.lower()
    for eng, cn in indications.items():
        if eng in tlower:
            indication = cn
            break
    if indication:
        return f"{product}（{indication}）"
    return product

_PHASE_CN = {"PHASE1": "I", "PHASE2": "II", "PHASE3": "III", "PHASE4": "IV"}
_STATUS_CN = {"RECRUITING": "招募中", "ACTIVE_NOT_RECRUITING": "进行中",
              "COMPLETED": "已完成", "NOT_YET_RECRUITING": "即将启动",
              "TERMINATED": "已终止", "WITHDRAWN": "已撤回", "SUSPENDED": "暂停中"}

def _fmt_ct(detail):
    """格式化临床试验 detail 字段。"""
    status = re.search(r'状态:\s*(\S+)', detail)
    phase = re.search(r'分期:\s*(.+?)(?:\s*·|$)', detail)
    update = re.search(r'更新:\s*(\d{4}-\d{2}-\d{2})', detail)
    parts = []
    if phase:
        ph = [_PHASE_CN.get(p.strip(), p.strip()) for p in phase.group(1).split(",")]
        parts.append("/".join(ph) + "期")
    if status:
        parts.append(_STATUS_CN.get(status.group(1), status.group(1)))
    if update:
        parts.append(update.group(1))
    return "，".join(parts) if parts else detail

_USER_AGENT = "Mozilla/5.0 (compatible; LyellMonitor/1.1)"

def _try_fetch_extract(url, title=""):
    """第一层提取：meta og:description / description / 首段 <p>。
    优先 og:description（新闻页面常见），其次普通 meta description。"""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": _USER_AGENT})
        r.raise_for_status()
        body = r.text
    except Exception:
        return None

    # 1) og:description
    m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{30,})["\']', body, re.I)
    if m:
        return re.sub(r'\s+', ' ', m.group(1).strip())

    # 2) 普通 meta description
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{30,})["\']', body, re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']{30,})["\'][^>]+name=["\']description["\']', body, re.I)
    if m:
        return re.sub(r'\s+', ' ', m.group(1).strip())

    # 3) 正文首段 <p>
    ps = re.findall(r'<p[^>]*>(.*?)</p>', body, re.DOTALL | re.I)
    for p in ps:
        clean = re.sub(r'<[^>]+>', '', p).strip()
        clean = re.sub(r'\s+', ' ', clean)
        if len(clean) > 30:
            return clean

    return None

def _deep_extract(url):
    """第二层提取：找页面正文主体（article/main/新闻稿内容区），跳过 meta。
    用于 meta description 与标题重复时兜底。"""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": _USER_AGENT})
        r.raise_for_status()
        body = r.text
    except Exception:
        return None

    # 找内容区：article > main > div[class含content/release/body/news] > body
    for pat in (r'<article[^>]*>(.*?)</article>',
                r'<main[^>]*>(.*?)</main>',
                r'<div[^>]*class="[^"]*(?:content|release|body|news|press)[^"]*"[^>]*>(.*?)(?:</div>)',
                r'<body[^>]*>(.*?)</body>'):
        m = re.search(pat, body, re.DOTALL | re.I)
        if not m:
            continue
        inner = m.group(1)
        # 找该区域第一个有意义的 <p>
        ps = re.findall(r'<p[^>]*>(.*?)</p>', inner, re.DOTALL | re.I)
        for p in ps:
            clean = re.sub(r'<[^>]+>', '', p).strip()
            clean = re.sub(r'\s+', ' ', clean)
            clean = re.sub(r'&amp;', '&', clean)
            clean = re.sub(r'&[a-z]{2,6};', ' ', clean)  # &nbsp; &mdash; etc
            if len(clean) > 40:
                return clean
    return None

def _truncate(text):
    """截取前 1-2 句，不超过 SUMMARY_MAX_LEN 字。"""
    if len(text) <= SUMMARY_MAX_LEN:
        return text
    # 按中英文句号切分
    parts = re.split(r'(?<=[。！？.!?])\s*', text)
    result = ""
    for p in parts:
        if len(result) + len(p) > SUMMARY_MAX_LEN:
            break
        result += p
    if not result:
        result = text[:SUMMARY_MAX_LEN]
    return result.strip()


# ─── 健康面板 ───────────────────────────────────────────────────

def _fmt_dt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso or ""

def _build_health_panel():
    log = load_json(RUN_LOG, [])
    if not log:
        return '<div class="health health-warn"><div class="health-badge">⚠️ 未检测到运行记录</div><div class="health-text">爬虫从未成功运行，请检查 GitHub Actions。</div></div>'
    last = log[-1]
    now = datetime.now(timezone.utc)
    try:
        last_dt = datetime.fromisoformat(last["timestamp"])
    except (ValueError, TypeError, KeyError):
        last_dt = None
    stale = last_dt is None or (now - last_dt).total_seconds() > STALE_HOURS * 3600
    src = last.get("sources", {})
    error_items = [(HEALTH_SOURCE_LABELS.get(k, k), v["error"]) for k, v in src.items() if v.get("error", 0) > 0]
    raw_total = sum(v.get("raw", 0) for k, v in src.items() if k != "sec_ticker_map")
    if stale: badge, cls = f"⚠️ 距上次运行已超过{STALE_HOURS}小时", "health-warn"
    elif error_items: badge, cls = "⚠️ 上次运行存在信息源故障", "health-warn"
    else: badge, cls = "✅ 系统运行正常", "health-ok"
    last_str = _fmt_dt(last.get("timestamp", ""))
    parts = [f'上次运行：<b>{html.escape(last_str)}</b>（耗时{last.get("duration_sec","?")}秒）']
    parts.append(f'扫描 <b>{last.get("companies","?")}</b> 家公司，抓取原始信息 <b>{raw_total}</b> 条')
    parts.append(f'过滤噪音 <b>{last.get("filtered_noise",0)}</b> 条，保留里程碑新增 <b>{last.get("kept_new",0)}</b> 条')
    if error_items:
        err_text = "、".join(f"{name}×{n}" for name, n in error_items)
        parts.append(f'<span class="health-err">故障源：{html.escape(err_text)}</span>')
    if last.get("first_run"):
        parts.append("（本次为首次运行 / 静默建立基线）")
    rows = []
    for entry in reversed(log[-10:]):
        e_src = entry.get("sources", {})
        e_err = sum(v.get("error", 0) for v in e_src.values())
        e_raw = sum(v.get("raw", 0) for k, v in e_src.items() if k != "sec_ticker_map")
        rows.append(
            '<tr>'
            f'<td>{html.escape(_fmt_dt(entry.get("timestamp","")))}</td>'
            f'<td>{entry.get("companies","?")}</td>'
            f'<td>{e_raw}</td>'
            f'<td>{entry.get("filtered_noise",0)}</td>'
            f'<td>{entry.get("kept_new",0)}</td>'
            f'<td class="{"health-err-cell" if e_err else ""}">{e_err}</td>'
            '</tr>')
    history_table = ('<details class="health-history"><summary>查看最近 {} 次运行趋势 ▾</summary>'
        '<table class="mini"><thead><tr><th>时间</th><th>公司数</th><th>原始抓取</th>'
        '<th>过滤噪音</th><th>保留新增</th><th>故障次数</th></tr></thead>'
        '<tbody>{}</tbody></table></details>').format(len(rows), "".join(rows))
    return (f'<div class="health {cls}"><div class="health-badge">{badge}</div>'
        f'<div class="health-text">{" · ".join(parts)}</div>{history_table}</div>')


# ─── 主入口 ─────────────────────────────────────────────────────

def generate(settings, subjects=None):
    site_cfg = settings["site"]
    out_dir = os.path.join(ROOT, site_cfg["output_dir"])
    os.makedirs(out_dir, exist_ok=True)
    highlight_days = site_cfg.get("recent_days_highlight", 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=highlight_days)

    # subjects
    if subjects is None:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", os.path.join(ROOT, "config.py"))
            cfg_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfg_mod)
            subjects = getattr(cfg_mod, "MONITORING_SUBJECTS", [])
        except Exception:
            subjects = []

    # items
    db = load_json(ITEMS_DB, [])
    db.sort(key=lambda r: r.get("first_seen", ""), reverse=True)

    # ── 内联摘要生成 ──
    summaries_file = os.path.join(ROOT, "data", "summaries.json")
    summaries = load_json(summaries_file, {})
    new_count, clean_count = 0, 0
    for r in db:
        uid = r.get("uid", "")
        if not uid:
            continue
        cached = summaries.get(uid)
        # 清理垃圾缓存（旧代码写入的 Google News 描述 / 标题重复）
        if cached and (_is_garbage(cached) or _similar_to_title(cached, r.get("title", ""))):
            del summaries[uid]
            clean_count += 1
            cached = None
        if not cached:
            s = _generate_summary(r)
            if s:
                summaries[uid] = s
                new_count += 1
    if new_count or clean_count:
        save_json(summaries_file, summaries)
        msg = f"  [site] 摘要: 新生成 {new_count} 条"
        if clean_count:
            msg += f", 清理过期缓存 {clean_count} 条"
        msg += f"（累计 {len(summaries)}）"
        print(msg)
    else:
        print(f"  [site] 摘要完整（{len(summaries)} 条）")

    # subjects.json / js
    with open(os.path.join(out_dir, "subjects.json"), "w", encoding="utf-8") as f:
        json.dump(subjects, f, ensure_ascii=False, indent=2)

    # roadmap.json
    try:
        import importlib.util as _iu
        spec = _iu.spec_from_file_location("config", os.path.join(ROOT, "config.py"))
        cfg_mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(cfg_mod)
        roadmap = getattr(cfg_mod, "ROADMAP", [])
    except Exception:
        roadmap = []
    with open(os.path.join(out_dir, "roadmap.json"), "w", encoding="utf-8") as f:
        json.dump(roadmap, f, ensure_ascii=False, indent=2)

    js_subjects = "var SUBJECTS = " + json.dumps(subjects, ensure_ascii=False) + ";"

    # report pages
    report_pages = {}
    for subj in subjects:
        sid = subj["id"]
        subj_companies = set(subj.get("companies", []))
        subj_items = [r for r in db if r.get("company") in subj_companies]
        now = datetime.now(timezone.utc).astimezone()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M %Z")
        total = len(subj_items)
        by_co = {}
        for r in subj_items:
            co = r.get("company", "")
            by_co.setdefault(co, []).append(r)

        md_lines = [f"# {subj['name']} 竞品监控日报", "",
            f"**生成时间**: {date_str} {time_str}",
            f"**监控条目**: {total} 条 · {len(by_co)} 家公司", "", "---", ""]
        rpt_parts = [f'<div class="report">', f'<h2>{html.escape(subj["name"])} 竞品监控日报</h2>',
            f'<div class="report-meta">生成时间: {date_str} {time_str} · {total} 条 · {len(by_co)} 家公司</div>', '<hr>']

        for co, co_items in sorted(by_co.items(), key=lambda x: (
            not any(xx.get("tier") == "priority" for xx in x[1]), x[0])):
            star = "★ " if any(xx.get("tier") == "priority" for xx in co_items) else ""
            md_lines.append(f"## {star}{co}  ({len(co_items)} 条)")
            md_lines.append("")
            rpt_parts.append(f'<div class="report-company">')
            rpt_parts.append(f'<h3>{"★ " if star else ""}{html.escape(co)} ({len(co_items)} 条)</h3>')
            for it in co_items:
                src_label = SOURCE_LABELS.get(it.get("source", ""), it.get("source", ""))
                summary = summaries.get(it.get("uid", ""), "")
                date_disp = it.get("date", "")

                md_lines.append(f"- **[{src_label}]** [{it['title']}]({it['url']})")
                if date_disp: md_lines.append(f"  _{date_disp}_")
                if summary: md_lines.append(f"  > {summary}")
                md_lines.append("")

                rpt_parts.append(f'<div class="report-item">'
                    f'<span class="src src-{it["source"]}">{html.escape(src_label)}</span> '
                    f'<a href="{html.escape(it["url"])}" target="_blank">{html.escape(it["title"])}</a>')
                if date_disp: rpt_parts.append(f'<span class="report-date">{html.escape(date_disp)}</span>')
                if summary: rpt_parts.append(f'<p class="report-summary">{html.escape(summary)}</p>')
                rpt_parts.append('</div>')
            rpt_parts.append('</div>')
        rpt_parts.append('</div>')
        report_html = "\n".join(rpt_parts)
        report_md = "\n".join(md_lines)

        with open(os.path.join(out_dir, f"report_{sid}.html"), "w", encoding="utf-8") as f:
            f.write(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                    f'<title>{html.escape(subj["name"])} 监控日报</title>'
                    f'<link rel="stylesheet" href="report.css"></head><body>{report_html}</body></html>')
        with open(os.path.join(out_dir, f"report_{sid}.md"), "w", encoding="utf-8") as f:
            f.write(report_md)

        report_pages[sid] = {
            "id": sid, "name": subj["name"], "description": subj["description"],
            "total": total, "priority": sum(1 for rr in subj_items if rr.get("tier") == "priority"),
            "companies": len(by_co),
            "html_url": f"report_{sid}.html", "md_url": f"report_{sid}.md",
        }

    # table rows
    rows_html = []
    for r in db:
        try: is_new = datetime.fromisoformat(r.get("first_seen", "")) >= cutoff
        except: is_new = False
        is_prio = r.get("tier") == "priority"
        badge = '<span class="badge">NEW</span>' if is_new else ""
        star = '<span class="star" title="重点监控对象">★</span> ' if is_prio else ""
        summary = summaries.get(r.get("uid", ""), "")
        summary_html = f'<div class="item-summary">{html.escape(summary)}</div>' if summary else ""
        rows_html.append(
            f'<tr data-co="{html.escape(r["company"])}" data-src="{r["source"]}" data-tier="{r.get("tier","standard")}">'
            f'<td class="c-date">{html.escape(_fmt_dt(r.get("first_seen","")))}{badge}</td>'
            f'<td class="c-co">{star}{html.escape(r["company"])}</td>'
            f'<td><span class="src src-{r["source"]}">{SOURCE_LABELS.get(r["source"], r["source"])}</span></td>'
            f'<td class="c-title"><a href="{html.escape(r["url"])}" target="_blank" rel="noopener">{html.escape(r["title"])}</a>'
            f'{summary_html}'
            f'<div class="detail">{html.escape(r.get("detail",""))} · {html.escape(r.get("date",""))}</div></td></tr>')

    # sidebar
    sidebar_items = []
    for i, subj in enumerate(subjects):
        rp = report_pages.get(subj["id"], {})
        active = " active" if i == 0 else ""
        sidebar_items.append(
            f'<div class="sb-item{active}" data-sid="{subj["id"]}">'
            f'<div class="sb-name">{html.escape(subj["name"])}</div>'
            f'<div class="sb-desc">{html.escape(subj["description"])}</div>'
            f'<div class="sb-stats">{rp.get("total", 0)} 条 · ★{rp.get("priority", 0)}</div></div>')

    btns = ('<div class="action-bar"><button id="btn-preview" class="btn">📋 预览摘要</button>'
            '<button id="btn-download" class="btn btn-outline">📥 下载日报</button>'
            '<button id="btn-roadmap" class="btn btn-outline">📅 路线图</button>'
            '<span id="active-subj-label" class="active-subj-label"></span></div>')

    health = _build_health_panel()
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    total_all = len(db)
    recent_all = sum(1 for r in db if r.get("first_seen", "") >= cutoff.isoformat()[:10])

    page = _TEMPLATE.format(
        title=html.escape(site_cfg["title"]),
        total=total_all, recent=recent_all, nsubj=len(subjects),
        generated=html.escape(generated), highlight_days=highlight_days,
        health_panel=health,
        sidebar_items="\n".join(sidebar_items),
        action_bar=btns,
        rows="".join(rows_html) or '<tr><td colspan="4" class="empty">基线建立中——竞品一旦发布新的临床数据或监管进展，会自动出现在这里。</td></tr>',
        js_subjects=js_subjects,
        report_pages_json=json.dumps({k: v for k, v in report_pages.items()}, ensure_ascii=False),
        first_subj_id=subjects[0]["id"] if subjects else "",
    )
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)

    with open(os.path.join(out_dir, "report.css"), "w", encoding="utf-8") as f:
        f.write(_REPORT_CSS)

    return os.path.join(out_dir, "index.html")


_REPORT_CSS = """body{font-family:-apple-system,"Microsoft YaHei",sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#232323;background:#f7f8fa}
.report h2{color:#1f3b57;border-bottom:2px solid #1f3b57;padding-bottom:8px}
.report-meta{color:#6e6e6e;font-size:13px;margin-bottom:8px}
.report-company{margin:20px 0;background:#fff;border-radius:8px;padding:16px;border:1px solid #e2e6ea}
.report-company h3{color:#1f3b57;margin-top:0;font-size:15px}
.report-item{margin:8px 0;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:13.5px}
.report-item:last-child{border-bottom:none}
.report-item a{color:#1a1a1a;text-decoration:none}.report-item a:hover{color:#c98a2c}
.report-date{color:#6e6e6e;font-size:11px;margin-left:10px}
.report-summary{color:#555;font-size:12px;margin:4px 0 0 0;line-height:1.5}
.src{font-size:10px;border-radius:3px;padding:1px 6px;color:#fff;margin-right:6px}
.src-clinicaltrials{background:#3e7cb1}.src-sec{background:#1f3b57}.src-pubmed{background:#6a7f4f}.src-web,.src-rss{background:#c98a2c}
"""

_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#f7f8fa;--card:#fff;--navy:#1f3b57;--gold:#c98a2c;--gray:#6e6e6e;--border:#e2e6ea;--red:#b0453a;--blue:#3e7cb1;--sidebar:260px}}
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,"Microsoft YaHei",Segoe UI,sans-serif;background:var(--bg);color:#232323;display:flex;min-height:100vh}}
#sidebar{{width:var(--sidebar);background:var(--navy);color:#fff;padding:20px 0;overflow-y:auto;flex-shrink:0;position:fixed;top:0;left:0;bottom:0;z-index:10}}
.sb-logo{{padding:0 18px 18px;border-bottom:1px solid rgba(255,255,255,.15);margin-bottom:12px}}
.sb-logo h2{{font-size:16px;margin:0;font-weight:700}}.sb-logo p{{font-size:11px;opacity:.7;margin:4px 0 0}}
.sb-item{{padding:12px 18px;cursor:pointer;border-left:3px solid transparent;margin:2px 0;transition:.15s}}
.sb-item:hover,.sb-item.active{{background:rgba(255,255,255,.1);border-left-color:var(--gold)}}
.sb-item.active .sb-name{{color:var(--gold)}}
.sb-name{{font-size:13.5px;font-weight:600}}.sb-desc{{font-size:11px;opacity:.7;margin-top:2px}}
.sb-stats{{font-size:10.5px;opacity:.6;margin-top:4px}}
.sb-add{{padding:16px 18px;font-size:11px;opacity:.4;border-top:1px solid rgba(255,255,255,.1);margin-top:12px}}
#main{{margin-left:var(--sidebar);flex:1;min-width:0}}
header{{background:var(--navy);color:#fff;padding:16px 28px;display:flex;justify-content:space-between;align-items:center}}
header h1{{margin:0;font-size:16px}}.header-right{{font-size:12px;opacity:.8}}
.stats{{display:flex;gap:10px;padding:14px 28px;flex-wrap:wrap}}
.stat{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 16px;min-width:100px}}
.stat .n{{font-size:20px;font-weight:700;color:var(--navy)}}.stat .l{{font-size:11px;color:var(--gray);margin-top:2px}}
.action-bar{{display:flex;gap:10px;padding:8px 28px 14px;align-items:center;flex-wrap:wrap}}
.btn{{padding:8px 18px;border-radius:6px;font-size:13px;cursor:pointer;border:none;background:var(--navy);color:#fff;font-weight:600}}
.btn:hover{{opacity:.9}}.btn-outline{{background:transparent;border:1.5px solid var(--navy);color:var(--navy)}}
.active-subj-label{{font-size:12.5px;color:var(--gray);margin-left:auto}}
.controls{{padding:0 28px 8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
#q{{flex:1;min-width:200px;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px}}
.toggle{{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--navy);cursor:pointer;user-select:none}}
.toggle input{{cursor:pointer}}
table{{width:calc(100% - 56px);margin:0 28px 30px;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden}}
th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);font-size:13px;vertical-align:top}}
th{{background:#eef1f5;color:var(--navy);font-size:12px;position:sticky;top:0}}
.c-date{{white-space:nowrap;color:var(--gray);font-size:11.5px}}.c-co{{white-space:nowrap;font-weight:600;color:var(--navy);font-size:12.5px}}
.star{{color:var(--gold)}}
.c-title a{{color:#1a1a1a;text-decoration:none;font-size:13px}}.c-title a:hover{{color:var(--gold);text-decoration:underline}}
.detail{{color:var(--gray);font-size:11px;margin-top:3px}}
.item-summary{{color:#555;font-size:11.5px;line-height:1.5;margin-top:4px;padding-left:8px;border-left:2px solid var(--blue)}}
.badge{{background:var(--gold);color:#fff;font-size:9.5px;border-radius:3px;padding:1px 4px;margin-left:4px}}
.src{{font-size:10.5px;border-radius:3px;padding:1px 6px;color:#fff;white-space:nowrap}}
.src-clinicaltrials{{background:var(--blue)}}.src-sec{{background:var(--navy)}}.src-pubmed{{background:#6a7f4f}}.src-web,.src-rss{{background:var(--gold)}}
.empty{{text-align:center;color:var(--gray);padding:30px}}
.health{{margin:12px 28px 0;border-radius:8px;padding:12px 16px;font-size:12.5px;border:1px solid var(--border)}}
.health-ok{{background:#eaf6ee;border-color:#bfe3c9}}.health-warn{{background:#fbeeea;border-color:#f0c4b4}}
.health-badge{{font-weight:700;font-size:13px;color:var(--navy);margin-bottom:3px}}.health-warn .health-badge{{color:var(--red)}}
.health-text{{color:#3a3a3a;line-height:1.6}}.health-err{{color:var(--red);font-weight:600}}
.health-history{{margin-top:6px}}.health-history summary{{cursor:pointer;color:var(--blue);font-size:12px}}
table.mini{{width:100%;margin-top:6px;border-collapse:collapse;font-size:11.5px}}
table.mini th,table.mini td{{padding:5px 8px;border-bottom:1px solid var(--border);text-align:left}}
table.mini th{{background:#f2f4f7;color:var(--navy)}}.health-err-cell{{color:var(--red);font-weight:700}}
.modal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);z-index:100;justify-content:center;align-items:flex-start;padding-top:60px}}
.modal.show{{display:flex}}.modal-content{{background:#fff;border-radius:10px;max-width:800px;width:90%;max-height:80vh;overflow-y:auto;padding:24px;box-shadow:0 8px 30px rgba(0,0,0,.15)}}
.modal-close{{float:right;font-size:20px;cursor:pointer;color:var(--gray);border:none;background:none}}
@media(max-width:768px){{#sidebar{{width:200px}}#main{{margin-left:200px}}header{{flex-direction:column;gap:6px}}}}
/* Roadmap Gantt */
.rm-gantt{{overflow-x:auto;overflow-y:visible}}
.rm-table{{border-collapse:collapse;font-size:12px;width:100%;min-width:700px}}
.rm-table th,.rm-table td{{border:1px solid var(--border);padding:8px 6px;vertical-align:top}}
.rm-table th{{background:var(--navy);color:#fff;font-size:11px;text-align:center;white-space:nowrap;min-width:80px}}
.rm-co{{font-weight:700;color:var(--navy);white-space:nowrap;font-size:12px;background:#f8f9fb;position:sticky;left:0;z-index:1;min-width:130px}}
.rm-ev{{position:relative;padding:4px 5px!important;min-height:60px}}
.rm-ev-block{{border-radius:6px;padding:5px 7px;margin:2px 0;font-size:11px;line-height:1.4;cursor:default}}
.rm-ev-block:hover{{filter:brightness(.92)}}
.rm-ev-title{{font-weight:600}}
.rm-ev-prod{{font-size:10px;opacity:.8;margin-top:1px}}
.rm-ev-note{{font-size:9.5px;opacity:.65;margin-top:1px;font-style:italic}}
.rm-cat-临床数据{{background:#d6e9f8;border-left:3px solid var(--blue);color:#1a3a5c}}
.rm-cat-监管进展{{background:#fce4e4;border-left:3px solid var(--red);color:#5c1a1a}}
.rm-cat-学术会议{{background:#d4edda;border-left:3px solid #2d7a3f;color:#1a3a1a}}
.rm-cat-商业化{{background:#fef3cd;border-left:3px solid var(--gold);color:#5c4a1a}}
.rm-conf{{font-size:9px;padding:0 4px;border-radius:2px;margin-left:3px;font-weight:600}}
.rm-cf-预计{{background:#fef3cd;color:#856404}}.rm-cf-确定{{background:#d4edda;color:#155724}}
.rm-cf-可能{{background:#e8e8e8;color:#555}}.rm-cf-乐观预计{{background:#cce5ff;color:#004085}}
.rm-legend{{display:flex;gap:14px;margin-bottom:12px;font-size:11px;flex-wrap:wrap}}
.rm-legend span{{display:flex;align-items:center;gap:4px}}
.rm-dot{{width:10px;height:10px;border-radius:2px;display:inline-block}}
</style></head><body>
<div id="sidebar"><div class="sb-logo"><h2>竞品监控</h2><p>{generated}</p></div>
{sidebar_items}
<div class="sb-add">+ 后续可添加更多监控主体</div></div>
<div id="main">
<header><h1>{title}</h1><div class="header-right">最近 {highlight_days} 天 NEW 标记</div></header>
{health_panel}
<div class="stats"><div class="stat"><div class="n">{total}</div><div class="l">累计条目</div></div>
<div class="stat"><div class="n">{recent}</div><div class="l">近 {highlight_days} 天新增</div></div>
<div class="stat"><div class="n">{nsubj}</div><div class="l">监控主体</div></div></div>
{action_bar}
<div class="controls"><input id="q" placeholder="搜索公司 / 标题 / 关键词...">
<label class="toggle"><input type="checkbox" id="onlyStar"> ★ 只看重点</label></div>
<div class="chips" id="chips"></div>
<table id="tbl"><thead><tr><th>首次发现</th><th>公司</th><th>类型</th><th>标题</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<div class="modal" id="summary-modal"><div class="modal-content">
<button class="modal-close" onclick="closeModal()">✕</button>
<div id="modal-body">加载中...</div></div></div>
<div class="modal" id="roadmap-modal"><div class="modal-content" style="max-width:1100px">
<button class="modal-close" onclick="closeRoadmap()">✕</button>
<h2 id="roadmap-title" style="margin:0 0 4px;font-size:17px">竞争路线图</h2>
<div style="font-size:11px;color:var(--gray);margin-bottom:12px">横轴 = 时间 · 纵轴 = 公司 · 色块 = 关键里程碑</div>
<div id="roadmap-body">加载中...</div></div></div>
<script>
{js_subjects}
var REPORTS = {report_pages_json};
var FIRST_SID = "{first_subj_id}";
var q=document.getElementById('q'),tb=document.querySelector('#tbl tbody'),activeSid=FIRST_SID,onlyStar=document.getElementById('onlyStar');
document.querySelectorAll('.sb-item').forEach(function(el){{
el.addEventListener('click',function(){{
document.querySelector('.sb-item.active').classList.remove('active');
el.classList.add('active');
activeSid = el.getAttribute('data-sid');
document.getElementById('active-subj-label').textContent = '当前主体: ' + (SUBJECTS.find(function(s){{return s.id===activeSid}})||{{name:''}}).name;
apply();
}});}});
if(SUBJECTS.length>0){{
document.getElementById('active-subj-label').textContent = '当前主体: ' + SUBJECTS[0].name;
}}
var filter='all';
function apply(){{
var kw=q.value.trim().toLowerCase();
var coSet=null;
var subjData=SUBJECTS.find(function(s){{return s.id===activeSid}});
if(subjData&&subjData.companies)coSet=new Set(subjData.companies);
Array.prototype.forEach.call(tb.rows,function(r){{
if(r.cells.length<4)return;
var okCo=!coSet||coSet.has(r.getAttribute('data-co'));
var okSrc=filter==='all'||r.getAttribute('data-src')===filter;
var okKw=!kw||r.textContent.toLowerCase().indexOf(kw)>=0;
var okStar=!onlyStar.checked||r.getAttribute('data-tier')==='priority';
r.style.display=(okCo&&okSrc&&okKw&&okStar)?'':'none';
}});
updateChips();
}}
function updateChips(){{
var chipsDiv=document.getElementById('chips');
var srcs=new Set();
Array.prototype.forEach.call(tb.rows,function(r){{
if(r.style.display!=='none'&&r.cells.length>=4)srcs.add(r.getAttribute('data-src'));
}});
var labels={{clinicaltrials:'临床试验',sec:'SEC申报',pubmed:'论文',web:'新闻',rss:'新闻'}};
chipsDiv.innerHTML='<button class="chip'+(filter==='all'?' active':'')+'" data-f="all">全部</button>';
srcs.forEach(function(s){{
chipsDiv.innerHTML+='<button class="chip'+(filter===s?' active':'')+'" data-f="'+s+'">'+(labels[s]||s)+'</button>';
}});
chipsDiv.querySelectorAll('.chip').forEach(function(b){{
b.addEventListener('click',function(){{
chipsDiv.querySelector('.chip.active').classList.remove('active');
b.classList.add('active');filter=b.getAttribute('data-f');apply();
}});}});
}}
q.addEventListener('input',apply);onlyStar.addEventListener('change',apply);apply();
document.getElementById('btn-preview').addEventListener('click',function(){{
var rp=REPORTS[activeSid];if(!rp){{alert('暂无该主体的报告');return;}}
fetch(rp.html_url).then(function(r){{return r.text()}}).then(function(html){{
var body=html.match(/<body[^>]*>([\\s\\S]*)<\\/body>/i);
document.getElementById('modal-body').innerHTML=body?body[1]:html;
document.getElementById('summary-modal').classList.add('show');
}}).catch(function(){{alert('加载报告失败');}});
}});
document.getElementById('btn-download').addEventListener('click',function(){{
var rp=REPORTS[activeSid];if(!rp){{alert('暂无该主体的报告');return;}}
window.open(rp.md_url,'_blank');
}});
// ── Roadmap Gantt ──
var ROADMAP=[];
fetch('roadmap.json').then(function(r){{return r.json()}}).then(function(data){{ROADMAP=data;}}).catch(function(){{}});
var COLS=['2026-Q3','2026-Q4','2027-H1','2027-H2','2028'];
function _colIdx(d){{
var y=parseInt(d.substring(0,4)),m=d.substring(5);
if(y===2026){{
  if(m==='07'||m==='08'||m==='09'||m==='Q3')return 0;
  if(m==='Q4'||m==='10'||m==='11'||m==='12')return 1;
}}
if(y===2027){{
  if(m==='Q1'||m==='H1'||m==='01'||m==='02'||m==='03')return 2;
  if(m==='Q2'||m==='H2'||m==='04'||m==='05'||m==='06'||m==='07'||m==='08'||m==='09'||m==='10'||m==='11'||m==='12')return 3;
}}
if(y>=2028)return 4;
return -1;
}}
function buildTimeline(sid){{
var subj=SUBJECTS.find(function(s){{return s.id===sid}});
if(!subj){{document.getElementById('roadmap-body').innerHTML='<p style="color:var(--gray)">请先选择监控主体</p>';return;}}
var cos=new Set(subj.companies);
var items=ROADMAP.filter(function(r){{return cos.has(r.company);}});
if(!items.length){{document.getElementById('roadmap-body').innerHTML='<p style="color:var(--gray)">该主体暂无路线图数据，请手动在 config.py ROADMAP 中添加关键时间节点。</p>';return;}}
// Group by company, only priority companies
var byCo={{}},coOrder=[];
items.forEach(function(it){{
if(!byCo[it.company]){{byCo[it.company]=Array(COLS.length).fill(null);coOrder.push(it.company);}}
var ci=_colIdx(it.date);if(ci<0)return;
var cell=byCo[it.company][ci];if(!cell)cell=[];
cell.push(it);byCo[it.company][ci]=cell;
}});
// Sort: Lyell first, then others
coOrder.sort(function(a,b){{return a.indexOf('Lyell')>=0?-1:b.indexOf('Lyell')>=0?1:0;}});
var catCls={{'临床数据':'rm-cat-临床数据','监管进展':'rm-cat-监管进展',
  '学术会议':'rm-cat-学术会议','商业化':'rm-cat-商业化'}};
var html='<div class="rm-legend">';
for(var k in catCls)html+='<span><span class="rm-dot '+catCls[k]+'"></span> '+k+'</span>';
html+='</div><div class="rm-gantt"><table class="rm-table"><thead><tr><th>公司</th>';
COLS.forEach(function(c){{html+='<th>'+c+'</th>';}});
html+='</tr></thead><tbody>';
coOrder.forEach(function(co){{
var row=byCo[co];
var isLyell=co.indexOf('Lyell')>=0;
html+='<tr><td class="rm-co" style="'+(isLyell?'background:#e8f0fe;':'')+'">'+(isLyell?'★ ':'')+co+'</td>';
for(var i=0;i<COLS.length;i++){{
  var cell=row[i];
  if(!cell||!cell.length){{html+='<td class="rm-ev"></td>';continue;}}
  html+='<td class="rm-ev">';
  cell.forEach(function(it){{
    var cls=catCls[it.category]||'rm-cat-临床数据';
    html+='<div class="rm-ev-block '+cls+'">';
    html+='<div class="rm-ev-title">'+it.event+'<span class="rm-conf rm-cf-'+it.confidence.replace(/[^\\u4e00-\\u9fa5]/g,'')+'">'+it.confidence+'</span></div>';
    if(it.product)html+='<div class="rm-ev-prod">🔬 '+it.product+'</div>';
    if(it.note)html+='<div class="rm-ev-note">'+it.note+'</div>';
    html+='</div>';
  }});
  html+='</td>';
}}
html+='</tr>';
}});
html+='</tbody></table></div>';
document.getElementById('roadmap-body').innerHTML=html;
document.getElementById('roadmap-title').textContent=subj.name+' 竞品路线图';
}}
document.getElementById('btn-roadmap').addEventListener('click',function(){{
buildTimeline(activeSid);
document.getElementById('roadmap-modal').classList.add('show');
}});
function closeRoadmap(){{document.getElementById('roadmap-modal').classList.remove('show');}}
document.getElementById('roadmap-modal').addEventListener('click',function(e){{if(e.target===this)closeRoadmap();}});
function closeModal(){{document.getElementById('summary-modal').classList.remove('show');}}
document.getElementById('summary-modal').addEventListener('click',function(e){{if(e.target===this)closeModal();}});
</script></body></html>"""
