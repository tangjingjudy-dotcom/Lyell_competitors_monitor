# -*- coding: utf-8 -*-
"""静态站点生成 v2：左侧栏（监控主体） + 右侧面板（情报列表 + 摘要/报告）。

数据流：
  items.json   → 所有情报条目
  summaries.json → {uid: 摘要文本}
  subjects.json → 监控主体配置（config.py 的 MONITORING_SUBJECTS）
  每个主体生成 report_{id}.html / report_{id}.md
"""
import html
import json
import os
from datetime import datetime, timezone, timedelta

from ..base import ITEMS_DB, RUN_LOG, load_json

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


def _fmt_dt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso or ""


def _build_health_panel():
    log = load_json(RUN_LOG, [])
    if not log:
        return (
            '<div class="health health-warn">'
            '<div class="health-badge">⚠️ 未检测到运行记录</div>'
            '<div class="health-text">爬虫从未成功运行，请检查 GitHub Actions。</div>'
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
    raw_total = sum(v.get("raw", 0) for k, v in src.items() if k != "sec_ticker_map")
    if stale:
        badge, cls = f"⚠️ 距上次运行已超过{STALE_HOURS}小时", "health-warn"
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


def generate(settings, subjects=None):
    site_cfg = settings["site"]
    out_dir = os.path.join(ROOT, site_cfg["output_dir"])
    os.makedirs(out_dir, exist_ok=True)
    highlight_days = site_cfg.get("recent_days_highlight", 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=highlight_days)

    # —— 读取配置 ——
    if subjects is None:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", os.path.join(ROOT, "config.py"))
            cfg_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfg_mod)
            subjects = getattr(cfg_mod, "MONITORING_SUBJECTS", [])
        except Exception:
            subjects = []

    # —— 读取数据 ——
    db = load_json(ITEMS_DB, [])
    db.sort(key=lambda r: r.get("first_seen", ""), reverse=True)

    summaries = load_json(os.path.join(ROOT, "data", "summaries.json"), {})

    # —— 生成 subjects.json ——
    with open(os.path.join(out_dir, "subjects.json"), "w", encoding="utf-8") as f:
        json.dump(subjects, f, ensure_ascii=False, indent=2)

    # —— 生成 subjects_data.js（供前端 JS 读取）——
    js_subjects = "var SUBJECTS = " + json.dumps(subjects, ensure_ascii=False) + ";"

    # —— 按主体生成报告页 ——
    report_pages = {}
    for subj in subjects:
        sid = subj["id"]
        subj_companies = set(subj.get("companies", []))
        subj_items = [r for r in db if r.get("company") in subj_companies]

        # 构建报告 HTML
        now = datetime.now(timezone.utc).astimezone()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M %Z")
        total = len(subj_items)
        prio = sum(1 for r in subj_items if r.get("tier") == "priority")

        # 按公司分组
        by_co = {}
        for r in subj_items:
            co = r.get("company", "")
            by_co.setdefault(co, []).append(r)

        md_lines = [
            f"# {subj['name']} 竞品监控日报",
            "",
            f"**生成时间**: {date_str} {time_str}",
            f"**监控条目**: {total} 条 · {len(by_co)} 家公司",
            "",
            "---",
            "",
        ]
        rpt_html_parts = [
            f'<div class="report">',
            f'<h2>{html.escape(subj["name"])} 竞品监控日报</h2>',
            f'<div class="report-meta">生成时间: {date_str} {time_str} · {total} 条 · {len(by_co)} 家公司</div>',
            f'<hr>',
        ]

        for co, co_items in sorted(by_co.items(), key=lambda x: (not any(it.get("tier") == "priority" for it in x[1]), x[0])):
            star = "★ " if any(it.get("tier") == "priority" for it in co_items) else ""
            md_lines.append(f"## {star}{co}  ({len(co_items)} 条)")
            md_lines.append("")
            rpt_html_parts.append(f'<div class="report-company">')
            rpt_html_parts.append(f'<h3>{"★ " if star else ""}{html.escape(co)} ({len(co_items)} 条)</h3>')

            for it in co_items:
                src_label = SOURCE_LABELS.get(it.get("source", ""), it.get("source", ""))
                summary = summaries.get(it.get("uid", ""), "")
                date_disp = it.get("date", "")

                md_lines.append(f"- **[{src_label}]** [{it['title']}]({it['url']})")
                if date_disp:
                    md_lines.append(f"  _{date_disp}_")
                if summary:
                    md_lines.append(f"  > {summary}")
                md_lines.append("")

                rpt_html_parts.append(
                    f'<div class="report-item">'
                    f'<span class="src src-{it["source"]}">{html.escape(src_label)}</span> '
                    f'<a href="{html.escape(it["url"])}" target="_blank">{html.escape(it["title"])}</a>'
                )
                if date_disp:
                    rpt_html_parts.append(f'<span class="report-date">{html.escape(date_disp)}</span>')
                if summary:
                    rpt_html_parts.append(f'<p class="report-summary">{html.escape(summary)}</p>')
                rpt_html_parts.append(f'</div>')
            rpt_html_parts.append('</div>')
        rpt_html_parts.append('</div>')

        report_html = "\n".join(rpt_html_parts)
        report_md = "\n".join(md_lines)

        # 写入文件
        html_path = os.path.join(out_dir, f"report_{sid}.html")
        md_path = os.path.join(out_dir, f"report_{sid}.md")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                    f'<title>{html.escape(subj["name"])} 监控日报</title>'
                    f'<link rel="stylesheet" href="report.css">'
                    f'</head><body>{report_html}</body></html>')
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_md)

        report_pages[sid] = {
            "id": sid, "name": subj["name"], "description": subj["description"],
            "total": total, "priority": prio, "companies": len(by_co),
            "html_url": f"report_{sid}.html",
            "md_url": f"report_{sid}.md",
        }

    # —— 构建条目表格行（每行带 data-co 属性，用于按主体筛选）——
    rows_html = []
    for r in db:
        try:
            is_new = datetime.fromisoformat(r.get("first_seen", "")) >= cutoff
        except (ValueError, TypeError):
            is_new = False
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
            f'<div class="detail">{html.escape(r.get("detail",""))} · {html.escape(r.get("date",""))}</div></td>'
            f'</tr>'
        )

    # —— 左侧栏 HTML ——
    sidebar_items = []
    for i, subj in enumerate(subjects):
        rp = report_pages.get(subj["id"], {})
        active = " active" if i == 0 else ""
        sidebar_items.append(
            f'<div class="sb-item{active}" data-sid="{subj["id"]}">'
            f'<div class="sb-name">{html.escape(subj["name"])}</div>'
            f'<div class="sb-desc">{html.escape(subj["description"])}</div>'
            f'<div class="sb-stats">{rp.get("total", 0)} 条 · ★{rp.get("priority", 0)}</div>'
            f'</div>'
        )

    # —— 按钮区（按主体动态）——
    btns_html = (
        '<div class="action-bar">'
        '<button id="btn-preview" class="btn">📋 预览摘要</button>'
        '<button id="btn-download" class="btn btn-outline">📥 下载日报</button>'
        '<span id="active-subj-label" class="active-subj-label"></span>'
        '</div>'
    )

    health_panel = _build_health_panel()
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")

    total_all = len(db)
    recent_all = sum(1 for r in db if r.get("first_seen", "") >= cutoff.isoformat()[:10])

    page = _TEMPLATE.format(
        title=html.escape(site_cfg["title"]),
        total=total_all,
        recent=recent_all,
        nsubj=len(subjects),
        generated=html.escape(generated),
        highlight_days=highlight_days,
        health_panel=health_panel,
        sidebar_items="\n".join(sidebar_items),
        action_bar=btns_html,
        rows="".join(rows_html) or '<tr><td colspan="4" class="empty">基线已建立，正在监控中——竞品一旦发布新的临床数据或监管进展，会自动出现在这里。</td></tr>',
        js_subjects=js_subjects,
        report_pages_json=json.dumps({k: v for k, v in report_pages.items()}, ensure_ascii=False),
        first_subj_id=subjects[0]["id"] if subjects else "",
    )

    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)

    # 同时生成 report.css
    css = _REPORT_CSS
    with open(os.path.join(out_dir, "report.css"), "w", encoding="utf-8") as f:
        f.write(css)

    return out_path


_REPORT_CSS = """
body{font-family:-apple-system,"Microsoft YaHei",sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#232323;background:#f7f8fa}
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
/* ====== SIDEBAR ====== */
#sidebar{{width:var(--sidebar);background:var(--navy);color:#fff;padding:20px 0;overflow-y:auto;flex-shrink:0;position:fixed;top:0;left:0;bottom:0;z-index:10}}
.sb-logo{{padding:0 18px 18px;border-bottom:1px solid rgba(255,255,255,.15);margin-bottom:12px}}
.sb-logo h2{{font-size:16px;margin:0;font-weight:700}}.sb-logo p{{font-size:11px;opacity:.7;margin:4px 0 0}}
.sb-item{{padding:12px 18px;cursor:pointer;border-left:3px solid transparent;margin:2px 0;transition:.15s}}
.sb-item:hover,.sb-item.active{{background:rgba(255,255,255,.1);border-left-color:var(--gold)}}
.sb-item.active .sb-name{{color:var(--gold)}}
.sb-name{{font-size:13.5px;font-weight:600}}
.sb-desc{{font-size:11px;opacity:.7;margin-top:2px}}
.sb-stats{{font-size:10.5px;opacity:.6;margin-top:4px}}
.sb-add{{padding:16px 18px;font-size:11px;opacity:.4;border-top:1px solid rgba(255,255,255,.1);margin-top:12px}}
/* ====== MAIN ====== */
#main{{margin-left:var(--sidebar);flex:1;min-width:0}}
header{{background:var(--navy);color:#fff;padding:16px 28px;display:flex;justify-content:space-between;align-items:center}}
header h1{{margin:0;font-size:16px}}.header-right{{font-size:12px;opacity:.8}}
.stats{{display:flex;gap:10px;padding:14px 28px;flex-wrap:wrap}}
.stat{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 16px;min-width:100px}}
.stat .n{{font-size:20px;font-weight:700;color:var(--navy)}}.stat .l{{font-size:11px;color:var(--gray);margin-top:2px}}
/* ====== ACTION BAR ====== */
.action-bar{{display:flex;gap:10px;padding:8px 28px 14px;align-items:center;flex-wrap:wrap}}
.btn{{padding:8px 18px;border-radius:6px;font-size:13px;cursor:pointer;border:none;background:var(--navy);color:#fff;font-weight:600;transition:.15s}}
.btn:hover{{opacity:.9}}.btn-outline{{background:transparent;border:1.5px solid var(--navy);color:var(--navy)}}
.active-subj-label{{font-size:12.5px;color:var(--gray);margin-left:auto}}
.controls{{padding:0 28px 8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
#q{{flex:1;min-width:200px;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px}}
.chips{{padding:0 28px 8px;display:flex;gap:6px;flex-wrap:wrap}}
.chip{{border:1px solid var(--border);background:var(--card);border-radius:16px;padding:4px 11px;font-size:11.5px;cursor:pointer}}
.chip.active{{background:var(--navy);color:#fff;border-color:var(--navy)}}
/* ====== TABLE ====== */
table{{width:calc(100% - 56px);margin:0 28px 30px;border-collapse:collapse;background:var(--card);border:1px solid var(--border);border-radius:8px;overflow:hidden}}
th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);font-size:13px;vertical-align:top}}
th{{background:#eef1f5;color:var(--navy);font-size:12px;position:sticky;top:0}}
.c-date{{white-space:nowrap;color:var(--gray);font-size:11.5px}}.c-co{{white-space:nowrap;font-weight:600;color:var(--navy);font-size:12.5px}}
.star{{color:var(--gold)}}
.toggle{{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--navy);cursor:pointer;user-select:none;white-space:nowrap}}
.toggle input{{cursor:pointer}}
.c-title a{{color:#1a1a1a;text-decoration:none;font-size:13px}}.c-title a:hover{{color:var(--gold);text-decoration:underline}}
.detail{{color:var(--gray);font-size:11px;margin-top:3px}}
.item-summary{{color:#555;font-size:11.5px;line-height:1.5;margin-top:4px;padding-left:8px;border-left:2px solid var(--blue)}}
.badge{{background:var(--gold);color:#fff;font-size:9.5px;border-radius:3px;padding:1px 4px;margin-left:4px}}
.src{{font-size:10.5px;border-radius:3px;padding:1px 6px;color:#fff;white-space:nowrap}}
.src-clinicaltrials{{background:var(--blue)}}.src-sec{{background:var(--navy)}}.src-pubmed{{background:#6a7f4f}}.src-web,.src-rss{{background:var(--gold)}}
.empty{{text-align:center;color:var(--gray);padding:30px}}
.health{{margin:12px 28px 0;border-radius:8px;padding:12px 16px;font-size:12.5px;border:1px solid var(--border)}}
.health-ok{{background:#eaf6ee;border-color:#bfe3c9}}
.health-warn{{background:#fbeeea;border-color:#f0c4b4}}
.health-badge{{font-weight:700;font-size:13px;color:var(--navy);margin-bottom:3px}}
.health-warn .health-badge{{color:var(--red)}}
.health-text{{color:#3a3a3a;line-height:1.6}}
.health-err{{color:var(--red);font-weight:600}}
.health-history{{margin-top:6px}}
.health-history summary{{cursor:pointer;color:var(--blue);font-size:12px}}
table.mini{{width:100%;margin-top:6px;border-collapse:collapse;font-size:11.5px}}
table.mini th,table.mini td{{padding:5px 8px;border-bottom:1px solid var(--border);text-align:left}}
table.mini th{{background:#f2f4f7;color:var(--navy)}}
.health-err-cell{{color:var(--red);font-weight:700}}
/* ====== MODAL ====== */
.modal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);z-index:100;justify-content:center;align-items:flex-start;padding-top:60px}}
.modal.show{{display:flex}}
.modal-content{{background:#fff;border-radius:10px;max-width:800px;width:90%;max-height:80vh;overflow-y:auto;padding:24px;box-shadow:0 8px 30px rgba(0,0,0,.15)}}
.modal-close{{float:right;font-size:20px;cursor:pointer;color:var(--gray);border:none;background:none}}
/* mobile */
@media(max-width:768px){{#sidebar{{width:200px}}#main{{margin-left:200px}}header{{flex-direction:column;gap:6px}}}}
</style></head><body>
<div id="sidebar">
  <div class="sb-logo">
    <h2>竞品监控</h2>
    <p>{generated}</p>
  </div>
  {sidebar_items}
  <div class="sb-add">+ 后续可添加更多<br>监控主体</div>
</div>
<div id="main">
<header><h1>{title}</h1><div class="header-right">最近 {highlight_days} 天 NEW 标记</div></header>
{health_panel}
<div class="stats">
  <div class="stat"><div class="n">{total}</div><div class="l">累计条目</div></div>
  <div class="stat"><div class="n">{recent}</div><div class="l">近 {highlight_days} 天新增</div></div>
  <div class="stat"><div class="n">{nsubj}</div><div class="l">监控主体</div></div>
</div>
{action_bar}
<div class="controls"><input id="q" placeholder="搜索公司 / 标题 / 关键词...">
  <label class="toggle"><input type="checkbox" id="onlyStar"> ★ 只看重点</label>
</div>
<div class="chips" id="chips"></div>
<table id="tbl"><thead><tr><th>首次发现</th><th>公司</th><th>类型</th><th>标题</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<div class="modal" id="summary-modal">
  <div class="modal-content">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div id="modal-body">加载中...</div>
  </div>
</div>
<script>
{js_subjects}
var REPORTS = {report_pages_json};
var FIRST_SID = "{first_subj_id}";
var q=document.getElementById('q'),tb=document.querySelector('#tbl tbody'),filter='all',activeSid=FIRST_SID,onlyStar=document.getElementById('onlyStar');

// ====== 左侧栏点击 ======
document.querySelectorAll('.sb-item').forEach(function(el){{
  el.addEventListener('click',function(){{
    document.querySelector('.sb-item.active').classList.remove('active');
    el.classList.add('active');
    activeSid = el.getAttribute('data-sid');
    document.getElementById('active-subj-label').textContent = '当前主体: ' + SUBJECTS.find(function(s){{return s.id===activeSid}}).name;
    apply();
  }});
}});

// 初始化：第一个主体
if(SUBJECTS.length>0){{
  document.getElementById('active-subj-label').textContent = '当前主体: ' + SUBJECTS[0].name;
}}

// ====== 过滤逻辑 ======
function apply(){{
  var kw=q.value.trim().toLowerCase();
  var coSet = null;
  var subjData = SUBJECTS.find(function(s){{return s.id===activeSid}});
  if(subjData && subjData.companies){{
    coSet = new Set(subjData.companies);
  }}
  Array.prototype.forEach.call(tb.rows,function(r){{
    if(r.cells.length<4){{return;}}
    var okCo = !coSet || coSet.has(r.getAttribute('data-co'));
    var okSrc = filter==='all'||r.getAttribute('data-src')===filter;
    var okKw = !kw||r.textContent.toLowerCase().indexOf(kw)>=0;
    var okStar = !onlyStar.checked||r.getAttribute('data-tier')==='priority';
    r.style.display=(okCo&&okSrc&&okKw&&okStar)?'':'none';
  }});
  // 更新 chips
  updateChips();
}}

// ====== Chips（类型筛选，基于当前活跃主体可见条目动态生成）=====
function updateChips(){{
  var chipsDiv = document.getElementById('chips');
  var srcs = new Set();
  Array.prototype.forEach.call(tb.rows,function(r){{
    if(r.style.display!=='none' && r.cells.length>=4){{
      srcs.add(r.getAttribute('data-src'));
    }}
  }});
  chipsDiv.innerHTML = '<button class="chip' + (filter==='all'?' active':'') + '" data-f="all">全部</button>';
  srcs.forEach(function(s){{
    chipsDiv.innerHTML += '<button class="chip' + (filter===s?' active':'') + '" data-f="' + s + '">' +
      ({{clinicaltrials:'临床试验',sec:'SEC申报',pubmed:'论文',web:'新闻',rss:'新闻'}}[s]||s) + '</button>';
  }});
  // 重新绑定事件
  chipsDiv.querySelectorAll('.chip').forEach(function(b){{
    b.addEventListener('click',function(){{
      chipsDiv.querySelector('.chip.active').classList.remove('active');
      b.classList.add('active');
      filter = b.getAttribute('data-f');
      apply();
    }});
  }});
}}

q.addEventListener('input',apply);
onlyStar.addEventListener('change',apply);
apply();

// ====== 按钮：预览摘要 / 下载日报 ======
document.getElementById('btn-preview').addEventListener('click',function(){{
  var rp = REPORTS[activeSid];
  if(!rp){{alert('暂无该主体的报告');return;}}
  fetch(rp.html_url).then(function(r){{return r.text()}}).then(function(html){{
    var body = html.match(/<body[^>]*>([\\s\\S]*)<\\/body>/i);
    document.getElementById('modal-body').innerHTML = body ? body[1] : html;
    document.getElementById('summary-modal').classList.add('show');
  }}).catch(function(){{alert('加载报告失败');}});
}});
document.getElementById('btn-download').addEventListener('click',function(){{
  var rp = REPORTS[activeSid];
  if(!rp){{alert('暂无该主体的报告');return;}}
  window.open(rp.md_url, '_blank');
}});
function closeModal(){{document.getElementById('summary-modal').classList.remove('show');}}
document.getElementById('summary-modal').addEventListener('click',function(e){{if(e.target===this)closeModal();}});
</script></body></html>"""
