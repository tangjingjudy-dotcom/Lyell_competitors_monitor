# -*- coding: utf-8 -*-
"""PubMed E-utilities：按关键词监控最新发表论文。"""
from ..base import Item

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def fetch(http, company, retmax=15):
    terms = company.get("pubmed") or []
    items = []
    for term in terms:
        try:
            sr = http.get_json(ESEARCH, params={
                "db": "pubmed", "term": term, "retmode": "json",
                "sort": "date", "retmax": retmax,
            })
            ids = sr.get("esearchresult", {}).get("idlist", [])
            if not ids:
                continue
            summ = http.get_json(ESUMMARY, params={
                "db": "pubmed", "id": ",".join(ids), "retmode": "json",
            })
        except Exception as e:  # noqa: BLE001
            print(f"  [pubmed] {company['name']} '{term}' 失败: {e}")
            continue

        result = summ.get("result", {})
        for pmid in result.get("uids", []):
            rec = result.get(pmid, {})
            title = rec.get("title", "").strip() or f"PMID {pmid}"
            date = rec.get("pubdate", "") or rec.get("epubdate", "")
            journal = rec.get("fulljournalname", "") or rec.get("source", "")
            items.append(Item(
                company=company["name"], category=company["category"], source="pubmed",
                title=title, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                date=date, detail=f"检索词: {term}" + (f" · {journal}" if journal else ""),
                uid=f"pm-{pmid}",
            ))
    return items
