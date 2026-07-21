# -*- coding: utf-8 -*-
"""静态站点生成：把全量条目库渲染成单文件 HTML（可直接托管分享）。"""
import html
import json
import os
from datetime import datetime, timezone, timedelta

from ..base import ITEMS_DB, load_json

SOURCE_LABELS = {
    "clinicaltrials": "临床试验",
    "sec": "SEC申报",
    "pubmed": "论文",
    "web": "新闻",
}


def _fmt_dt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso or ""


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
    rows_html = []
    for r in db:
        try:
            is_new = datetime.fromisoformat(r.get("first_seen", "")) >= cutoff
        except (ValueError, TypeError):
            is_new = False
        if is_new:
            recent_count += 1
        badge = '<span class="badge">NEW</span>' if is_new else ""
        rows_html.append(
            f'<tr data-cat="{html.escape(r["category"])}" data-src="{r["source"]}">'
            f'<td class="c-date">{html.escape(_fmt_dt(r.get("first_seen","")))}{badge}</td>'
            f'<td class="c-co">{html.escape(r["company"])}</td>'
            f'<td><span class="src src-{r["source"]}">{SOURCE_LABELS.get(r["source"], r["source"])}</span></td>'
            f'<td class="c-title"><a href="{html.escape(r["url"])}" target="_blank" rel="noopener">{html.escape(r["title"])}</a>'
            f'<div class="detail">{html.escape(r.get("detail",""))} · {html.escape(r.get("date",""))}</div></td>'
            f'</tr>'
        )

    cat_buttons = '<button class="chip active" data-f="all">全部</button>' + "".join(
        f'<button class="chip" data-f="{html.escape(c)}">{html.escape(c)}</button>' for c in categories
    )
    generated = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")

    page = _TEMPLATE.format(
        title=html.escape(site_cfg["title"]),
        total=len(db),
        recent=recent_count,
        ncat=len(categories),
        generated=html.escape(generated),
        highlight_days=highlight_days,
        cat_buttons=cat_buttons,
        rows="".join(rows_html) or '<tr><td colspan="4" class="empty">暂无数据，请先运行一次抓取。</td></tr>',
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
.c-title a{{color:#1a1a1a;text-decoration:none}}.c-title a:hover{{color:var(--gold);text-decoration:underline}}
.detail{{color:var(--gray);font-size:11.5px;margin-top:3px}}
.badge{{background:var(--gold);color:#fff;font-size:10px;border-radius:4px;padding:1px 5px;margin-left:6px}}
.src{{font-size:11px;border-radius:4px;padding:2px 7px;color:#fff;white-space:nowrap}}
.src-clinicaltrials{{background:var(--blue)}}.src-sec{{background:var(--navy)}}.src-pubmed{{background:#6a7f4f}}.src-web{{background:var(--gold)}}
.empty{{text-align:center;color:var(--gray);padding:30px}}
</style></head><body>
<header><h1>{title}</h1><div class="sub">最近 {highlight_days} 天新增以 NEW 标记 · 生成时间 {generated}</div></header>
<div class="stats">
  <div class="stat"><div class="n">{total}</div><div class="l">累计条目</div></div>
  <div class="stat"><div class="n">{recent}</div><div class="l">近 {highlight_days} 天新增</div></div>
  <div class="stat"><div class="n">{ncat}</div><div class="l">监控分类</div></div>
</div>
<div class="controls"><input id="q" placeholder="搜索公司 / 标题 / 关键词..."></div>
<div class="chips">{cat_buttons}</div>
<table id="tbl"><thead><tr><th>首次发现</th><th>公司</th><th>类型</th><th>标题</th></tr></thead>
<tbody>{rows}</tbody></table>
<script>
var q=document.getElementById('q'),tb=document.querySelector('#tbl tbody'),filter='all';
function apply(){{
  var kw=q.value.trim().toLowerCase();
  Array.prototype.forEach.call(tb.rows,function(r){{
    if(r.cells.length<4){{return;}}
    var okCat=filter==='all'||r.getAttribute('data-cat')===filter;
    var okKw=!kw||r.innerText.toLowerCase().indexOf(kw)>=0;
    r.style.display=(okCat&&okKw)?'':'none';
  }});
}}
q.addEventListener('input',apply);
Array.prototype.forEach.call(document.querySelectorAll('.chip'),function(b){{
  b.addEventListener('click',function(){{
    document.querySelector('.chip.active').classList.remove('active');
    b.classList.add('active');filter=b.getAttribute('data-f');apply();
  }});
}});
</script></body></html>"""
