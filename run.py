# -*- coding: utf-8 -*-
"""
主运行器：抓取所有信息源 → 计算新增 → 更新条目库 → 生成站点 →（可选）发送邮件。

用法：
  python run.py                 # 正常运行一次
  python run.py --site-url URL  # 在邮件中附上看板链接
  python run.py --no-email      # 本次不发邮件（只更新站点）
  python run.py --only LYEL     # 只跑名称包含该关键词的公司（调试用）
"""
import argparse
import sys

from config import COMPANIES, SETTINGS
from monitor.base import Http, StateStore, diff_new, merge_into_items_db, is_milestone, load_json, save_json, META_FILE, now_iso
from monitor.sources import clinicaltrials, sec_edgar, pubmed, webwatch
from monitor.deliver import site, email_digest


def run(args):
    http = Http(SETTINGS["user_agent"], SETTINGS["request_timeout"], SETTINGS["request_delay_sec"])
    store = StateStore()

    meta = load_json(META_FILE, {})
    first_run = not meta.get("initialized")
    if first_run:
        print("== 首次运行：建立基线，本次不发送邮件 ==")

    companies = COMPANIES
    if args.only:
        companies = [c for c in COMPANIES if args.only.lower() in c["name"].lower()]

    mfilter = SETTINGS.get("milestone_filter", {})
    all_new = []
    filtered_total = 0
    for c in companies:
        print(f"[{c['name']}]")
        collected = []

        ct_items = clinicaltrials.fetch(http, c, SETTINGS["clinicaltrials_page_size"])
        collected.append((f"{c['name']}:ct", ct_items))

        sec_items = sec_edgar.fetch(http, c, SETTINGS["sec_recent_count"])
        collected.append((f"{c['name']}:sec", sec_items))

        pm_items = pubmed.fetch(http, c, SETTINGS["pubmed_retmax"])
        collected.append((f"{c['name']}:pubmed", pm_items))

        rss_items = webwatch.fetch_rss(http, c)
        collected.append((f"{c['name']}:rss", rss_items))

        web_items = webwatch.fetch_web(http, c)
        collected.append((f"{c['name']}:web", web_items))

        for source_id, items in collected:
            new_items = diff_new(store, source_id, items)
            if not new_items:
                continue
            kept = [it for it in new_items if is_milestone(it, mfilter)]
            filtered_total += len(new_items) - len(kept)
            if kept:
                print(f"    + {len(kept)} 条里程碑新增 <- {source_id.split(':')[-1]}"
                      + (f"（已过滤{len(new_items) - len(kept)}条噪音）" if len(kept) != len(new_items) else ""))
                all_new.extend(kept)

    if first_run:
        # 首次运行只建立“已见”基线：把当前存量条目全部记为已知，但【不写入展示库】，
        # 避免上百条历史条目一次性刷屏。此后仅【新出现】的里程碑条目才会进入看板。
        meta["initialized"] = True
        meta["first_run_at"] = now_iso()
        save_json(META_FILE, meta)
        out_path = site.generate(SETTINGS)
        print(f"\n站点已生成: {out_path}")
        print(f"基线建立完成：已将当前 {len(all_new)} 条存量里程碑记为‘已见’（不展示）；"
              f"后续运行仅呈现新增。")
        return

    merge_into_items_db(all_new)
    out_path = site.generate(SETTINGS)
    print(f"\n站点已生成: {out_path}")
    print(f"本轮里程碑新增合计: {len(all_new)} 条（已过滤例行噪音 {filtered_total} 条）")

    if not args.no_email:
        ok, info = email_digest.send_digest(SETTINGS["email"], all_new, args.site_url)
        print(f"邮件: {'已发送' if ok else '未发送'} ({info})")


def main():
    p = argparse.ArgumentParser(description="Lyell 竞品动态监控")
    p.add_argument("--site-url", default=None, help="看板公开访问地址（写入邮件）")
    p.add_argument("--no-email", action="store_true", help="本次不发送邮件")
    p.add_argument("--only", default=None, help="仅运行名称包含该关键词的公司")
    args = p.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
