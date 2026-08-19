# -*- coding: utf-8 -*-
"""
监控目标配置：Lyell 及所有竞品公司的信息源钩子。

每个公司可配置的监控钩子（全部可选，按需填写）：
  - sec_ticker : 美股代码（用于 SEC EDGAR 申报监控，自动映射到 CIK）
  - rss        : RSS/Atom 订阅地址列表（最稳，优先使用）
  - news_pages : 需要监控的新闻/IR 页面 URL 列表（无 RSS 时，做"链接集合差异"检测）

分类 category 仅用于站点分组展示。
"""
import os

# 邮件凭据从环境变量/GitHub Secrets 读取（不要把密码写进代码提交到公开仓库）
_SMTP_USER = os.environ.get("MONITOR_SMTP_USER", "")
_SMTP_PASS = os.environ.get("MONITOR_SMTP_PASS", "")
_MAIL_TO = os.environ.get("MONITOR_MAIL_TO", _SMTP_USER)


# —— 全局设置 ——
SETTINGS = {
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "request_timeout": 25,
    "request_delay_sec": 0.8,
    "sec_recent_count": 30,
    "email": {
        "enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_tls": True,
        "username": "",
        "password": "",
        "from_addr": "",
        "to_addrs": [],
        "min_hours_between_emails": 0,
        "subject_prefix": "[Lyell竞品监控·重点]"
    },
    "site": {
        "title": "竞品动态监控",
        "output_dir": "data/site",
        "recent_days_highlight": 7,
        "items_max_age_days": 7
    },
    "milestone_filter": {
        "enabled": True,
        "meaningful_sec_forms": [
            "10-K",
            "10-K/A",
            "10-Q",
            "10-Q/A",
            "20-F",
            "20-F/A",
            "40-F",
            "40-F/A"
        ],
        "keywords": [
            "phase 1",
            "phase 2",
            "phase 3",
            "phase i",
            "phase ii",
            "phase iii",
            "1期",
            "2期",
            "3期",
            "一期",
            "二期",
            "三期",
            "临床数据",
            "临床结果",
            "topline",
            "readout",
            "interim",
            "data",
            "results",
            "efficacy",
            "response rate",
            "orr",
            "complete response",
            " cr ",
            "pfs",
            "overall survival",
            " os ",
            "duration of response",
            "中期",
            "数据",
            "疗效",
            "缓解率",
            "完全缓解",
            "生存期",
            "随访",
            "pivotal",
            "registrational",
            "关键性",
            "注册",
            "first patient",
            "首例",
            "dosed",
            "给药",
            "cohort",
            "队列",
            "trial",
            "study",
            "试验",
            "enrollment",
            "入组",
            "ash",
            "asco",
            "eha",
            "aacr",
            "esmo",
            "会议",
            "abstract",
            "presentation",
            "摘要",
            "poster",
            "oral",
            "fda",
            "ema",
            "nmpa",
            "mhra",
            "pmda",
            "bla",
            "nda",
            "maa",
            "ind",
            "biologics license",
            "approval",
            "approved",
            "clearance",
            "authoris",
            "authoriz",
            "获批",
            "批准",
            "上市许可",
            "递交",
            "提交",
            "受理",
            "breakthrough",
            "fast track",
            "rmat",
            "orphan",
            "priority review",
            "accelerated",
            "pdufa",
            "complete response letter",
            "crl",
            "designation",
            "认定",
            "突破性",
            "孤儿药",
            "优先审评",
            "clinical hold",
            "临床暂停",
            "terminated",
            "discontinu",
            "终止",
            "暂停",
            "acquire",
            "acquisition",
            "merger",
            "收购",
            "并购",
            "license",
            "licensing",
            "授权",
            "合作",
            "partnership",
            "collaboration",
            "deal",
            "milestone",
            "里程碑"
        ]
    },
    "tiers": {
        "priority": {
            "label": "重点监控",
            "run_every_days": 1,
            "relaxed_filter": True,
            "email": True
        },
        "standard": {
            "label": "常规监控",
            "run_every_days": 7,
            "relaxed_filter": False,
            "email": False
        }
    }
}


# —— 监控主体（左侧栏导航） ——
# 每个主体定义一个 id + 名称 + 描述 + 关联公司列表（自身+竞品）。
# 看板左侧栏按此顺序排列，点击后在右侧显示该主体及其竞品的最新情报。
# 添加新主体：只需在下表中新增一条记录，并将其 company 及竞品加入 COMPANIES。
MONITORING_SUBJECTS = [
    {
        "id": "lyell",
        "name": "Lyell Immunopharma",
        "description": "下一代CAR-T（ronde-cel + LYL273）",
        "companies": [
            "Lyell Immunopharma",
            "Gilead (含Arcellx/Kite)",
            "Miltenyi Biomedicine (zamto-cel)",
            "Merck KGaA (M9140)",
            "北京艺妙神州 (Immunochina)",
            "Legend Biotech",
            "CARsgen (科济药业)",
        ]
    },
    {
        "id": "parabilis",
        "name": "Parabilis Medicines",
        "description": "Helicon 肽 / β-catenin（zolucatetide）",
        "companies": [
            "Parabilis Medicines",
            "Sapience Therapeutics",
            "Immunome",
        ]
    }
]


# —— 公司信息源配置 ——
COMPANIES = [
    {
        "name": "Lyell Immunopharma",
        "category": "监控主体",
        "tier": "priority",
        "subject_id": "lyell",
        "subject_name": "Lyell 下一代CAR-T",
        "sec_ticker": "LYEL",
        "rss": [
            "https://ir.lyell.com/rss/news-releases.xml",
        ],
    },
    {
        "name": "Gilead (含Arcellx/Kite)",
        "category": "在位者/下一代CAR-T",
        "tier": "priority",
        "subject_id": "lyell",
        "subject_name": "Lyell 下一代CAR-T",
        "sec_ticker": "GILD",
        "news_pages": [
            "https://www.gilead.com/news/news-details",
        ],
        "product_keywords": [
            "kite-363",
            "kite-753",
        ],
    },
    {
        "name": "Miltenyi Biomedicine (zamto-cel)",
        "category": "CD19-CD20双靶点CAR-T",
        "tier": "priority",
        "subject_id": "lyell",
        "subject_name": "Lyell 下一代CAR-T",
        "news_pages": [
            "https://www.miltenyibiomedicine.com/news-events/press-releases/",
        ],
        "product_keywords": [
            "zamto-cel",
            "zamtocabtagene autoleucel",
        ],
    },
    {
        "name": "Merck KGaA (M9140)",
        "category": "CEACAM5 ADC",
        "tier": "priority",
        "subject_id": "lyell",
        "subject_name": "Lyell 下一代CAR-T",
        "sec_ticker": "MKKGY",
        "news_pages": [
            "https://www.merckgroup.com/en/news.html",
        ],
        "product_keywords": [
            "M9140",
        ],
    },
    {
        "name": "北京艺妙神州 (Immunochina)",
        "category": "实体瘤CAR-T (GUCY2C)",
        "tier": "priority",
        "subject_id": "lyell",
        "subject_name": "Lyell 下一代CAR-T",
        "news_pages": [
            "http://www.immunochina.com/Home/news/news.html",
        ],
        "product_keywords": [
            "IM96",
        ],
    },
    {
        "name": "Legend Biotech",
        "category": "体内CAR-T (in vivo)",
        "tier": "priority",
        "subject_id": "lyell",
        "subject_name": "Lyell 下一代CAR-T",
        "sec_ticker": "LEGN",
        "news_pages": [
            "https://investors.legendbiotech.com/news-releases",
        ],
        "product_keywords": [
            "LB2501",
        ],
    },
    {
        "name": "CARsgen (科济药业)",
        "category": "同种异体CD19-CD20双靶点",
        "tier": "priority",
        "subject_id": "lyell",
        "subject_name": "Lyell 下一代CAR-T",
        "news_pages": [
            "https://www.carsgen.com/en/news/",
        ],
        "product_keywords": [
            "CT1190B",
        ],
    },
    {
        "name": "Parabilis Medicines",
        "category": "监控主体",
        "tier": "priority",
        "subject_id": "parabilis",
        "sec_ticker": "PBLS",
        "news_pages": [
            "https://investors.parabilismed.com/news-events/news-releases",
        ],
    },
    {
        "name": "Sapience Therapeutics",
        "category": "竞品",
        "tier": "priority",
        "subject_id": "parabilis",
        "news_pages": [
            "https://sapiencetherapeutics.com/news-events/press-releases/",
        ],
        "product_keywords": [
            "ST316",
        ],
    },
    {
        "name": "Immunome",
        "category": "竞品",
        "tier": "priority",
        "subject_id": "parabilis",
        "sec_ticker": "IMNM",
        "news_pages": [
            "https://investors.immunome.com/news-releases/",
        ],
        "product_keywords": [
            "varegacestat",
            "AL102",
        ],
    },
]

ROADMAP = [
    # ────── ronde-cel 产品线 ──────
    {
        "company": "Lyell Immunopharma",
        "product_line": "ronde-cel",
        "date": "2026-Q4",
        "event": "PiNACLE Ph2更新数据",
        "category": "临床数据",
        "product": "ronde-cel",
        "confidence": "预计",
        "note": ""
    },
    {
        "company": "Lyell Immunopharma",
        "product_line": "ronde-cel",
        "date": "2026-Q4",
        "event": "H2H Ph3更新数据",
        "category": "临床数据",
        "product": "ronde-cel",
        "confidence": "预计",
        "note": "vs Yescarta/Breyanzi; 业界首个头对头CAR-T试验"
    },
    {
        "company": "Lyell Immunopharma",
        "product_line": "ronde-cel",
        "date": "2027-H1",
        "event": "PiNACLE关键读出",
        "category": "临床数据",
        "product": "ronde-cel",
        "confidence": "预计",
        "note": "支撑加速批准路径"
    },
    {
        "company": "Miltenyi Biomedicine (zamto-cel)",
        "product_line": "ronde-cel",
        "date": "2027-H1",
        "event": "EMA审评决定",
        "category": "监管进展",
        "product": "zamto-cel",
        "confidence": "预计",
        "note": "若获批, 将成为ronde-cel上市前已存在的同赛道竞品"
    },
    {
        "company": "Gilead (含Arcellx/Kite)",
        "product_line": "ronde-cel",
        "date": "2027-H2",
        "event": "Ph3中期读出",
        "category": "临床数据",
        "product": "KITE-753",
        "confidence": "可能",
        "note": "若数据积极, Kite在位者优势直接威胁ronde-cel"
    },
    {
        "company": "Lyell Immunopharma",
        "product_line": "ronde-cel",
        "date": "2027-H2",
        "event": "BLA提交",
        "category": "监管进展",
        "product": "ronde-cel",
        "confidence": "乐观预计",
        "note": "最早上市时间窗口"
    },
    # ────── LYL273 产品线 ──────
    {
        "company": "北京艺妙神州 (Immunochina)",
        "product_line": "LYL273",
        "date": "2026-Q3",
        "event": "IM96 Ph1数据更新",
        "category": "临床数据",
        "product": "IM96",
        "confidence": "预计",
        "note": "GUCY2C CAR-T; JCO已发表爬坡; 同靶点唯一竞品"
    },
    {
        "company": "Lyell Immunopharma",
        "product_line": "LYL273",
        "date": "2026-Q4",
        "event": "Ph1 DL3剂量数据",
        "category": "临床数据",
        "product": "LYL273",
        "confidence": "预计",
        "note": ""
    },
    {
        "company": "Lyell Immunopharma",
        "product_line": "LYL273",
        "date": "2027-H1",
        "event": "关键试验启动",
        "category": "临床数据",
        "product": "LYL273",
        "confidence": "预计",
        "note": ""
    },
    {
        "company": "Merck KGaA (M9140)",
        "product_line": "LYL273",
        "date": "2028-H2",
        "event": "Ph3关键读出",
        "category": "临床数据",
        "product": "M9140",
        "confidence": "可能",
        "note": "CEACAM5 ADC; 若积极, 可能在LYL273之前获批mCRC"
    }
]

# ──────────────────────────── Sheets 集成 ────────────────────────────
import json as _json

_HERE2 = os.path.dirname(os.path.abspath(__file__))
_ENV_FILE2 = os.path.join(_HERE2, "env.json")
_CSV_URL = os.environ.get("GOOGLE_SHEETS_CSV_URL", "").strip()
if not _CSV_URL and os.path.isfile(_ENV_FILE2):
    with open(_ENV_FILE2, "r", encoding="utf-8") as _f:
        _CSV_URL = _json.load(_f).get("GOOGLE_SHEETS_CSV_URL", "").strip()
if _CSV_URL:
    try:
        import sys as _sys
        _sys.path.insert(0, _HERE2)
        from sheets_loader import fetch_csv as _fetch, parse_csv as _parse
        _fallback = list(COMPANIES)
        _csv_text = _fetch()
        if _csv_text:
            _companies = _parse(_csv_text)
            if _companies:
                _have = {c["name"] for c in _companies}
                for _c in _fallback:
                    if _c["name"] not in _have:
                        _companies.append(_c)
                COMPANIES = _companies
                print(f"[config] 已从 Google Sheets 加载 {len(COMPANIES)} 家公司")
    except Exception as _e:
        print(f"[config] Google Sheets 加载失败，使用本地 fallback ({len(COMPANIES)} 家): {_e}")

