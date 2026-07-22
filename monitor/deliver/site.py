# -*- coding: utf-8 -*-
"""静态站点生成：把全量条目库渲染成单文件 HTML（可直接托管分享）。"""
import html
import json
import os
from datetime import datetime, timezone, timedelta

from ..base import ITEMS_DB, RUN_LOG, load_json

SOURCE_LABELS = {
    "clinicaltrials": "临床试验",
    "sec": "SEC申报",
    "pubmed": "论文",
    "web": "新闻",
}
HEALTH_SOURCE_LABELS = {
    "clinicaltrials": "ClinicalTrials.gov",
    "sec": "SEC EDGAR",
    "sec_ticker_map": "SEC代码映射表",
    "pubmed": "PubMed",
    "rss": "RSS订阅",
    "web": "官网新闻页",
}
# 每日定时任务的容忍窗口：超过这个时长没有新的运行记录，视为“可能已停止”
STALE_HOURS = 36


def _fmt_dt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso or ""


def _build_health_panel():
    """基于 run_log.json 生成“系统运行状态”面板：用于区分“真的没进展”与“爬虫故障”。"""
    log = load_json(RUN_LOG, [])
    if not log:
        return (
            '<div class="health health-warn">'
            '<div class="health-badge">⚠️ 未检测到运行记录</div>'
            '<div class="health-text">还没有找到 run_log.json —— 说明爬虫从未成功运行过一次，或状态文件未随代码一起提交。请检查 GitHub Actions 的运行日志。</div>'
            '</div>'
        )

    last = log[-1]
    now = datetime.now(timezone.utc)
    try:
        last_dt = datetime.fromisoformat(last["timestamp"])
    except (ValueError, TypeError, KeyError):
        last_dt = None

    stale = last_dt is None or (now - last_dt).total_seconds() > STALE_HOURS * 3600
    src = last.get("sources", {})
    error_items = [(HEALTH_SOURCE_LABELS.get(k, k), v["error"]) for k, v in src.items() if v.get("error", 0) > 0]
    # sec_ticker_map 是一次性全局映射表（约1万+条），不计入“逐条信息”的抓取总量，否则会淹没其他源
    raw_total = sum(v.get("raw", 0) for k, v in src.items() if k != "sec_ticker_map")

    if stale:
        badge, cls = "⚠️ 距上次运行已超过 {}小时".format(STALE_HOURS), "health-warn"
    elif error_items:
        badge, cls = "⚠️ 上次运行存在信息源故障", "health-warn"
    else:
        badge, cls = "✅ 系统运行正常", "health-ok"

    last_str = _fmt_dt(last.get("timestamp", ""))
    parts = [f'上次运行：<b>{html.escape(last_str)}</b>（耗时{last.get("duration_sec","?")}秒）']
    parts.append(f'扫描 <b>{last.get("companies","?")}</b> 家公司，抓取原始信息 <b>{raw_total}</b> 条')
    parts.append(f'过滤噪音 <b>{last.get("filtered_noise",0)}</b> 条，保留里程碑新增 <b>{last.get("kept_new",0)}</b> 条')
    if error_items:
        err_text = "、".join(f"{name}×{n}" for name, n in error_items)
        parts.append(f'<span class="health-err">故障源：{html.escape(err_text)}</span>')
    if last.get("first_run"):
        parts.append("（本次为首次运行 / 静默建立基线）")

    # 最近若干次运行趋势
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
            '</tr>'
        )
    history_table = (
        '<details class="health-history"><summary>查看最近 {} 次运行趋势 ▾</summary>'
        '<table class="mini"><thead><tr><th>时间</th><th>公司数</th><th>原始抓取</th>'
        '<th>过滤噪音</th><th>保留新增</th><th>故障次数</th></tr></thead>'
        '<tbody>{}</tbody></table></details>'
    ).format(len(rows), "".join(rows))

    return (
        f'<div class="health {cls}">'
        f'<div class="health-badge">{badge}</div>'
        f'<div class="health-text">{" · ".join(parts)}</div>'
        f'{history_table}'
        f'</div>'
    )


def generate(settings):
    site_cfg = settings["site"]
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           site_cfg["output_dir"])
    os.makedirs(out_dir, exist_ok=True)

    db = load_json(ITEMS_DB, [])
    db.sort(key=lambda r: r.get("first_seen", ""), reverse=True)

    highlight_days = site_cfg.get("recent_days_highlight", 14)
    cutoff = datetime.now(timezone.utc) - timedelta(days=highlight_days)

    categories = sorted({r["category"] for r in db})
    recent_count = 0
    priority_count = 0
    rows_html = []
    for r in db:
        try:
            is_new = datetime.fromisoformat(r.get("first_seen", "")) >= cutoff
        except (ValueError, TypeError):
            is_new = False
        if is_new:
            recent_count += 1
        is_priority = r.get("tier") == "priority"
        if is_priority:
            priority_count += 1
        badge = '<span class="badge">NEW</span>' if is_new else ""
        star = '<span class="star" title="重点监控对象">★</span> ' if is_priority else ""
        rows_html.append(
            f'<tr data-cat="{html.escape(r["category"])}" data-src="{r["source"]}" data-tier="{r.get("tier","standard")}">'
            f'<td class="c-date">{html.escape(_fmt_dt(r.get("first_seen","")))}{badge}</td>'
            f'<td class="c-co">{star}{html.escape(r["company"])}</td>'
            f'<td><span class="src src-{r["source"]}">{SOURCE_LABELS.get(r["source"], r["source"])}</span></td>'
            f'<td class="c-title"><a href="{html.escape(r["url"])}" target="_blank" rel="noopener">{html.escape(r["title"])}</a>'
            f'<div class="detail">{html.escape(r.get("detail",""))} · {html.escape(r.get("date",""))}</div></td>'
            f'</tr>'
        )

    cat_buttons = '<button class="chip active" data-f="all">全部</button>' + "".join(
        f'<button class="chip" data-f="{html.escape(c)}">{html.escape(c)}</button>' for c in categories
    )
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    health_panel = _build_health_panel()

    page = _TEMPLATE.format(
        title=html.escape(site_cfg["title"]),
        total=len(db),
        recent=recent_count,
        priority=priority_count,
        ncat=len(categories),
        generated=html.escape(generated),
        highlight_days=highlight_days,
        health_panel=health_panel,
        cat_buttons=cat_buttons,
        rows="".join(rows_html) or '<tr><td colspan="4" class="empty">基线已建立，正在监控中——竞品一旦发布新的临床数据或监管进展，会自动出现在这里。</td></tr>',
    )
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)

    with open(os.path.join(out_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    return out_path


_TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#f7f8fa;--card:#fff;--navy:#1f3b57;--gold:#c98a2c;--gray:#6e6e6e;--border:#e2e6ea;--red:#b0453a;--blue:#3e7cb1}}
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,"Microsoft YaHei",Segoe UI,sans-serif;background:var(--bg);color:#232323}}
header{{background:var(--navy);color:#fff;padding:22px 28px}}
header h1{{margin:0;font-size:20px}}header .sub{{opacity:.8;font-size:13px;margin-top:5px}}
.stats{{display:flex;gap:14px;padding:18px 28px;flex-wrap:wrap}}
.stat{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 18px;min-width:120px}}
.stat .n{{font-size:24px;font-weight:700;color:var(--navy)}}.stat .l{{font-size:12px;color:var(--gray);margin-top:2px}}
.controls{{padding:0 28px 12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
#q{{flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--border);border-radius:8px;font-size:14px}}
.chips{{padding:0 28px 14px;display:flex;gap:8px;flex-wrap:wrap}}
.chip{{border:1px solid var(--border);background:var(--card);border-radius:20px;padding:5px 13px;font-size:12.5px;cursor:pointer}}
.chip.active{{background:var(--navy);color:#fff;border-color:var(--navy)}}
table{{width:calc(100% - 56px);margin:0 28px 40px;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
th,td{{text-align:left;padding:11px 14px;border-bottom:1px solid var(--border);font-size:13.5px;vertical-align:top}}
th{{background:#eef1f5;color:var(--navy);font-size:12.5px;position:sticky;top:0}}
.c-date{{white-space:nowrap;color:var(--gray);font-size:12px}}.c-co{{white-space:nowrap;font-weight:600;color:var(--navy)}}
.star{{color:var(--gold)}}
.toggle{{display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--navy);cursor:pointer;user-select:none;white-space:nowrap}}
.toggle input{{cursor:pointer}}
.c-title a{{color:#1a1a1a;text-decoration:none}}.c-title a:hover{{color:var(--gold);text-decoration:underline}}
.detail{{color:var(--gray);font-size:11.5px;margin-top:3px}}
.badge{{background:var(--gold);color:#fff;font-size:10px;border-radius:4px;padding:1px 5px;margin-left:6px}}
.src{{font-size:11px;border-radius:4px;padding:2px 7px;color:#fff;white-space:nowrap}}
.src-clinicaltrials{{background:var(--blue)}}.src-sec{{background:var(--navy)}}.src-pubmed{{background:#6a7f4f}}.src-web{{background:var(--gold)}}
.empty{{text-align:center;color:var(--gray);padding:30px}}
.health{{margin:18px 28px 0;border-radius:10px;padding:14px 18px;font-size:13px;border:1px solid var(--border)}}
.health-ok{{background:#eaf6ee;border-color:#bfe3c9}}
.health-warn{{background:#fbeeea;border-color:#f0c4b4}}
.health-badge{{font-weight:700;font-size:14px;color:var(--navy);margin-bottom:4px}}
.health-warn .health-badge{{color:var(--red)}}
.health-text{{color:#3a3a3a;line-height:1.7}}
.health-err{{color:var(--red);font-weight:600}}
.health-history{{margin-top:8px}}
.health-history summary{{cursor:pointer;color:var(--blue);font-size:12.5px}}
table.mini{{width:100%;margin-top:8px;border-collapse:collapse;font-size:12px}}
table.mini th,table.mini td{{padding:6px 10px;border-bottom:1px solid var(--border);text-align:left}}
table.mini th{{background:#f2f4f7;color:var(--navy)}}
.health-err-cell{{color:var(--red);font-weight:700}}
</style></head><body>
<header><h1>{title}</h1><div class="sub">最近 {highlight_days} 天新增以 NEW 标记 · 生成时间 {generated}</div></header>
{health_panel}
<div class="stats">
  <div class="stat"><div class="n">{total}</div><div class="l">累计条目</div></div>
  <div class="stat"><div class="n">{recent}</div><div class="l">近 {highlight_days} 天新增</div></div>
  <div class="stat"><div class="n">★ {priority}</div><div class="l">重点对象条目</div></div>
  <div class="stat"><div class="n">{ncat}</div><div class="l">监控分类</div></div>
</div>
<div class="controls"><input id="q" placeholder="搜索公司 / 标题 / 关键词...">
  <label class="toggle"><input type="checkbox" id="onlyStar"> ★ 只看重点监控对象</label>
</div>
<div class="chips">{cat_buttons}</div>
<table id="tbl"><thead><tr><th>首次发现</th><th>公司</th><th>类型</th><th>标题</th></tr></thead>
<tbody>{rows}</tbody></table>
<script>
var q=document.getElementById('q'),tb=document.querySelector('#tbl tbody'),filter='all',onlyStar=document.getElementById('onlyStar');
function apply(){{
  var kw=q.value.trim().toLowerCase();
  Array.prototype.forEach.call(tb.rows,function(r){{
    if(r.cells.length<4){{return;}}
    var okCat=filter==='all'||r.getAttribute('data-cat')===filter;
    var okKw=!kw||r.innerText.toLowerCase().indexOf(kw)>=0;
    var okStar=!onlyStar.checked||r.getAttribute('data-tier')==='priority';
    r.style.display=(okCat&&okKw&&okStar)?'':'none';
  }});
}}
q.addEventListener('input',apply);
onlyStar.addEventListener('change',apply);
Array.prototype.forEach.call(document.querySelectorAll('.chip'),function(b){{
  b.addEventListener('click',function(){{
    document.querySelector('.chip.active').classList.remove('active');
    b.classList.add('active');filter=b.getAttribute('data-f');apply();
  }});
}});
</script></body></html>"""
