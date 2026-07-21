# -*- coding: utf-8 -*-
"""ClinicalTrials.gov v2 API：按申办方拉取最新试验，追踪状态/更新日期变化。"""
from ..base import Item

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ",".join([
    "NCTId", "BriefTitle", "OverallStatus", "Phase",
    "LastUpdatePostDate", "StudyFirstPostDate",
])


def fetch(http, company, page_size=30, stats=None):
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
    for study in data.get("studies", []):
        ps = study.get("protocolSection", {})
        ident = ps.get("identificationModule", {})
        status = ps.get("statusModule", {})
        design = ps.get("designModule", {})
        nct = ident.get("nctId", "")
        if not nct:
            continue
        title = ident.get("briefTitle", nct)
        overall = status.get("overallStatus", "")
        phase = ",".join(design.get("phases", []) or [])
        updated = (status.get("lastUpdatePostDateStruct", {}) or {}).get("date", "")
        # uid 含状态+更新日期 → 状态或更新变化时视为“新条目”，可被推送
        detail = f"状态: {overall}" + (f" · 分期: {phase}" if phase else "") + (f" · 更新: {updated}" if updated else "")
        items.append(Item(
            company=company["name"], category=company["category"], source="clinicaltrials",
            title=title, url=f"https://clinicaltrials.gov/study/{nct}",
            date=updated, detail=detail,
            uid=f"ct-{nct}-{overall}-{updated}"[:64],
        ))
    if stats:
        stats.record("clinicaltrials", ok=True, count=len(items))
    return items
