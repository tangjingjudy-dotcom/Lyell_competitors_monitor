# -*- coding: utf-8 -*-
"""ClinicalTrials.gov v2 API：按申办方拉取最新试验，追踪状态/更新日期变化。"""
from datetime import datetime, timezone
from ..base import Item

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ",".join([
    "NCTId", "BriefTitle", "OverallStatus", "Phase",
    "LastUpdatePostDate", "StudyFirstPostDate",
])


def fetch(http, company, page_size=30, max_age_days=None, stats=None):
    """
    max_age_days: None=全保留, int=只保留最近N天内更新过的试验
    """
    sponsor = company.get("ct_sponsor")
    if not sponsor:
        return []
    params = {
        "query.spons": sponsor,
        "pageSize": page_size,
        "sort": "LastUpdatePostDate:desc",
        "fields": FIELDS,
    }
    try:
        data = http.get_json(API, params=params)
    except Exception as e:  # noqa: BLE001
        print(f"  [clinicaltrials] {company['name']} 失败: {e}")
        if stats:
            stats.record("clinicaltrials", ok=False)
        return []

    items = []
    ct_kw = company.get("ct_keywords", None)  # None=全部保留（Lyell等小biotech），list=按关键词过滤
    filtered_out = 0
    for study in data.get("studies", []):
        ps = study.get("protocolSection", {})
        ident = ps.get("identificationModule", {})
        status = ps.get("statusModule", {})
        design = ps.get("designModule", {})
        conds = ps.get("conditionsModule", {})
        nct = ident.get("nctId", "")
        if not nct:
            continue
        title = ident.get("briefTitle", nct)
        updated = (status.get("lastUpdatePostDateStruct", {}) or {}).get("date", "")

        # 临床试验关键词过滤：只保留与我们关注的CAR-T/适应症相关的试验
        if ct_kw is not None:
            if not any(kw.lower() in title.lower() for kw in ct_kw):
                filtered_out += 1
                continue
        # 时间窗口过滤：只保留最近 N 天内更新过的试验
        if max_age_days is not None:
            try:
                td = (datetime.now(timezone.utc) -
                      datetime.strptime(updated, "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
                if td > max_age_days:
                    filtered_out += 1
                    continue
            except (ValueError, TypeError):
                pass
        overall = status.get("overallStatus", "")
        phase = ",".join(design.get("phases", []) or [])
        # uid 含状态+更新日期 → 状态或更新变化时视为“新条目”，可被推送
        detail = f"状态: {overall}" + (f" · 分期: {phase}" if phase else "") + (f" · 更新: {updated}" if updated else "")
        items.append(Item(
            company=company["name"], category=company["category"], source="clinicaltrials",
            title=title, url=f"https://clinicaltrials.gov/study/{nct}",
            date=updated, detail=detail,
            uid=f"ct-{nct}-{overall}-{updated}"[:64],
        ))
    if filtered_out:
        print(f"  [ct filter] {company['name']}: {len(items) + filtered_out}条抓取, {len(items)}条保留（过滤{filtered_out}条）")
    if stats:
        stats.record("clinicaltrials", ok=True, count=len(items))
    return items
