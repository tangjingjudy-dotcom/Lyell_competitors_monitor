# -*- coding: utf-8 -*-
"""
主运行器：抓取所有信息源 → 计算新增 → 更新条目库 → 生成站点 →（可选）发送邮件。

用法：
  python run.py                 # 正常运行一次
  python run.py --site-url URL  # 在邮件中附上看板链接
  python run.py --no-email      # 本次不发邮件（只更新站点）
  python run.py --only LYEL     # 只跑名称包含该关键词的公司（调试用）
  python run.py --no-summary    # 跳过摘要生成（日常高频运行推荐）
"""
import argparse
import re
import sys
import time
from datetime import date

from config import COMPANIES, SETTINGS, MONITORING_SUBJECTS
from monitor.base import (
    Http, StateStore, RunStats, diff_new, merge_into_items_db, is_milestone,
    append_run_log, load_json, save_json, META_FILE, now_iso,
)
from monitor.sources import clinicaltrials, sec_edgar, pubmed, webwatch
from monitor.deliver import site, email_digest
from monitor.summarizer import summarize_items, _load_cache, _save_cache


def _due_today(tier_cfg):
    """按 tier 的 run_every_days 判断今天是否轮到扫描（每天=1 恒为真）。"""
    n = max(1, int(tier_cfg.get("run_every_days", 1)))
    if n == 1:
        return True
    return date.today().toordinal() % n == 0


def run(args):
    run_started = time.time()
    http = Http(SETTINGS["user_agent"], SETTINGS["request_timeout"], SETTINGS["request_delay_sec"])
    store = StateStore()
    stats = RunStats()

    meta = load_json(META_FILE, {})
    first_run = not meta.get("initialized")
    if first_run:
        print("== 首次运行：建立基线，本次不发送邮件 ==")

    tiers_cfg = SETTINGS.get("tiers", {})
    pool = COMPANIES
    if args.only:
        pool = [c for c in COMPANIES if args.only.lower() in c["name"].lower()]

    # 按 tier 频率决定今天扫描哪些公司；首次运行或 --all 时全量扫描
    force_all = args.all or first_run
    companies, skipped_cadence = [], 0
    for c in pool:
        tcfg = tiers_cfg.get(c.get("tier", "standard"), {})
        if force_all or _due_today(tcfg):
            companies.append(c)
        else:
            skipped_cadence += 1
    if skipped_cadence:
        print(f"（按频率跳过 {skipped_cadence} 家常规对象，今日只扫描 {len(companies)} 家）")

    mfilter = SETTINGS.get("milestone_filter", {})
    all_new = []
    filtered_total = 0
    for c in companies:
        tier = c.get("tier", "standard")
        tcfg = tiers_cfg.get(tier, {})
        relaxed = tcfg.get("relaxed_filter", False)
        diversified = c.get("diversified", False)
        pk = c.get("product_keywords")  # 非 Lyell 公司必须命中此列表才保留（Lyell 无此字段）
        tag = "★重点" if tier == "priority" else ""
        print(f"[{c['name']}]{tag}")
        collected = []

        ct_items = clinicaltrials.fetch(http, c, SETTINGS["clinicaltrials_page_size"],
                                        max_age_days=SETTINGS["clinicaltrials_max_age_days"] if c.get("ct_keywords") else None,
                                        stats=stats)
        collected.append((f"{c['name']}:ct", ct_items))

        sec_items = sec_edgar.fetch(http, c, SETTINGS["sec_recent_count"], stats=stats)
        collected.append((f"{c['name']}:sec", sec_items))

        pm_items = pubmed.fetch(http, c, SETTINGS["pubmed_retmax"], stats=stats)
        collected.append((f"{c['name']}:pubmed", pm_items))

        rss_items = webwatch.fetch_rss(http, c, stats=stats)
        collected.append((f"{c['name']}:rss", rss_items))

        web_items = webwatch.fetch_web(http, c, stats=stats)
        collected.append((f"{c['name']}:web", web_items))

        for source_id, items in collected:
            for it in items:
                it.tier = tier
            new_items = diff_new(store, source_id, items)
            if not new_items:
                continue
            kept = [it for it in new_items if is_milestone(it, mfilter, relaxed=relaxed, diversified=diversified, product_keywords=pk)]
            filtered_total += len(new_items) - len(kept)
            if kept:
                print(f"    + {len(kept)} 条里程碑新增 <- {source_id.split(':')[-1]}"
                      + (f"（已过滤{len(new_items) - len(kept)}条噪音）" if len(kept) != len(new_items) else ""))
                all_new.extend(kept)

    priority_new = [it for it in all_new if getattr(it, "tier", "standard") == "priority"]

    # —— 记录本次运行的“健康摘要”（供看板判断“真的没进展”还是“爬虫故障”）——
    src_summary = stats.summary()
    error_sources = {name: s["error"] for name, s in src_summary.items() if s["error"] > 0}
    run_record = {
        "timestamp": now_iso(),
        "duration_sec": round(time.time() - run_started, 1),
        "companies": len(companies),
        "skipped_cadence": skipped_cadence,
        "first_run": first_run,
        "kept_new": len(all_new),
        "priority_new": len(priority_new),
        "filtered_noise": filtered_total,
        "sources": src_summary,
    }
    append_run_log(run_record)
    if error_sources:
        print(f"\n⚠️ 本轮存在信息源故障: {error_sources}（详见 run_log.json / 看板顶部“系统运行状态”）")

    if first_run:
        # 首次运行只建立“已见”基线：把当前存量条目全部记为已知，但【不写入展示库】，
        # 避免上百条历史条目一次性刷屏。此后仅【新出现】的里程碑条目才会进入看板。
        meta["initialized"] = True
        meta["first_run_at"] = now_iso()
        save_json(META_FILE, meta)
        out_path = site.generate(SETTINGS, subjects=MONITORING_SUBJECTS)
        print(f"\n站点已生成: {out_path}")
        print(f"基线建立完成：已将当前 {len(all_new)} 条存量里程碑记为‘已见’（不展示）；"
              f"后续运行仅呈现新增。")
        return

    merge_into_items_db(all_new)
    cleaned_ct = _clean_stale_ct_items(companies)
    if cleaned_ct:
        print(f"  已从 items.json 移除 {cleaned_ct} 条过期临床试验（当前 ct_keywords 规则下不再保留）")
    cleaned_age = _clean_expired_items()
    if cleaned_age:
        print(f"  已从 items.json 移除 {cleaned_age} 条超过{_get_site_max_age()}天的旧条目")

    # —— 摘要生成（周度：由 --no-summary 控制） ——
    if args.no_summary:
        print(f"  摘要生成: 已跳过（--no-summary）")
    else:
        try:
            if all_new:
                summarize_items(all_new, max_per_run=60)
            cache = _load_cache()
            all_db = load_json(ITEMS_DB, [])
            all_db.sort(key=lambda r: r.get("first_seen", ""), reverse=True)
            missing = [it for it in all_db if it.get("uid") not in cache]
            if missing:
                print(f"    补摘要: items.json 中 {len(missing)} 条无缓存，将逐步生成")
                from monitor.base import Item
                pending = []
                for d in missing[:40]:
                    try:
                        pending.append(Item(**{k: v for k, v in d.items()
                                               if k in ("company", "category", "source", "title",
                                                        "url", "date", "detail", "tier", "uid")}))
                    except Exception as ex:
                        print(f"    跳过条目（Item构造失败）: {d.get('title','')[:40]} - {ex}")
                if pending:
                    print(f"    将生成 {len(pending)} 条摘要...")
                    summarize_items(pending, max_per_run=40)
        except Exception as e:
            print(f"  摘要生成跳过: {e}")

    out_path = site.generate(SETTINGS, subjects=MONITORING_SUBJECTS)
    print(f"\n站点已生成: {out_path}")
    print(f"本轮里程碑新增合计: {len(all_new)} 条（其中重点对象 {len(priority_new)} 条；已过滤例行噪音 {filtered_total} 条）")

    if not args.no_email:
        # 邮件只推送“重点监控对象”的新增，避免常规对象刷屏
        ok, info = email_digest.send_digest(SETTINGS["email"], priority_new, args.site_url)
        print(f"邮件（仅重点对象 {len(priority_new)} 条）: {'已发送' if ok else '未发送'} ({info})")


def _clean_stale_ct_items(companies):
    """将 items.json 中已被当前 ct_keywords/时间窗口 规则过滤掉的条目删除。

    两次检查：
    1. 关键词：有 ct_keywords 的公司，标题不匹配 → 删除
    2. 时间窗口：有 ct_keywords 的公司，detail 中的更新时间超过 max_age → 删除

    不检查 source != "clinicaltrials" 的条目；不检查无 ct_keywords 的公司（如 Lyell）。
    """
    from monitor.base import ITEMS_DB, load_json, save_json
    from datetime import datetime, timezone

    ctk_map = {}
    for c in companies:
        kw = c.get("ct_keywords")
        if kw:
            ctk_map[c["name"]] = kw

    if not ctk_map:
        return 0

    max_age = SETTINGS.get("clinicaltrials_max_age_days", 14)
    now = datetime.now(timezone.utc)
    db = load_json(ITEMS_DB, [])
    keep = []
    removed = 0
    for row in db:
        if row.get("source") != "clinicaltrials":
            keep.append(row)
            continue
        kwlist = ctk_map.get(row.get("company", ""))
        if kwlist is None:
            keep.append(row)
            continue

        title = (row.get("title", "") or "").lower()
        if not any(kw.lower() in title for kw in kwlist):
            removed += 1
            continue

        # 时间窗口检查：从 detail 字段提取 更新: YYYY-MM-DD
        detail = row.get("detail", "") or ""
        import re
        m = re.search(r'更新:\s*(\d{4}-\d{2}-\d{2})', detail)
        if m:
            try:
                td = now - datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if td.days > max_age:
                    removed += 1
                    continue
            except (ValueError, TypeError):
                pass
        keep.append(row)

    if removed:
        save_json(ITEMS_DB, keep)
    return removed


def _get_site_max_age():
    """读取面板条目保留天数配置。"""
    return SETTINGS.get("site", {}).get("items_max_age_days", 7)


def _clean_expired_items():
    """移除 items.json 中 first_seen 早于保留天数的条目。

    目的：控制面板信息量，只展示最近 N 天的动态。
    - 邮件已确保每次只推"真正新增"，历史条目不会重复发
    - 面板通过此函数自动清理过期条目，保持可读性
    """
    from monitor.base import ITEMS_DB, load_json, save_json
    from datetime import datetime, timezone

    max_age = _get_site_max_age()
    now_utc = datetime.now(timezone.utc)
    db = load_json(ITEMS_DB, [])
    keep = []
    removed = 0
    for row in db:
        try:
            fs = datetime.fromisoformat(row.get("first_seen", ""))
            if (now_utc - fs).days > max_age:
                removed += 1
                continue
        except (ValueError, TypeError):
            pass
        keep.append(row)
    if removed:
        save_json(ITEMS_DB, keep)
    return removed


def main():
    p = argparse.ArgumentParser(description="Lyell 竞品动态监控")
    p.add_argument("--site-url", default=None, help="看板公开访问地址（写入邮件）")
    p.add_argument("--no-email", action="store_true", help="本次不发送邮件")
    p.add_argument("--only", default=None, help="仅运行名称包含该关键词的公司")
    p.add_argument("--all", action="store_true", help="强制全量扫描（忽略常规对象的降频，手动全扫时用）")
    p.add_argument("--no-summary", action="store_true", help="跳过 DeepSeek 摘要生成（日常运行推荐）")
    args = p.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
