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
        "title": "Lyell 及下一代 CAR-T 竞品动态监控",
        "output_dir": "data/site",
        "recent_days_highlight": 7,
        "items_max_age_days": 7
    },
    "milestone_filter": {
        "enabled": True,
        "meaningful_sec_forms": [
            "8-K",
            "8-K/A",
            "6-K",
            "6-K/A",
            "20-F",
            "20-F/A",
            "10-K",
            "10-K/A",
            "F-1",
            "424B4"
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
            "Allogene Therapeutics",
            "Caribou Biosciences",
            "CRISPR Therapeutics",
            "Century Therapeutics",
            "Autolus Therapeutics",
            "Arsenal Biosciences",
            "Gilead (含Arcellx/Kite)",
            "Roche (含Poseida/Genentech)",
            "A2 Biotherapeutics",
            "Affini-T Therapeutics",
            "Immatics",
            "Immunocore",
            "Adaptimmune Therapeutics",
            "Precision Biosciences",
            "Sana Biotechnology",
            "Bristol Myers Squibb",
            "Johnson & Johnson",
            "Legend Biotech",
            "Novartis",
            "AbbVie / Genmab (epcoritamab)",
            "ADC Therapeutics",
            "Incyte",
            "Miltenyi Biomedicine (zamto-cel)",
            "CARsgen Therapeutics (科济药业)",
            "Innovative Cellular Therapeutics (ICT)",
            "北京艺妙神州 (Immunochina)",
            "Chimeric Therapeutics",
            "Carina Biotech",
            "Merck KGaA (M9140)",
            "Sanofi",
            "Pfizer",
            "AstraZeneca (含EsoBiotec)",
            "Agenus",
            "Akeso（康方生物）",
            "Summit Therapeutics"
        ]
    }
]

COMPANIES = [
    {
        "name": "Lyell Immunopharma",
        "category": "监控主体",
        "tier": "priority",
        "sec_ticker": "LYEL",
        "rss": [
            "https://ir.lyell.com/rss/news-releases.xml"
        ]
    },
    {
        "name": "Allogene Therapeutics",
        "category": "异体/现货型CAR-T",
        "sec_ticker": "ALLO",
        "rss": [
            "https://ir.allogene.com/rss/news-releases.xml"
        ],
        "product_keywords": [
            "cema-cel",
            "allo-501",
            "allo-715"
        ]
    },
    {
        "name": "Caribou Biosciences",
        "category": "异体/现货型CAR-T",
        "sec_ticker": "CRBU",
        "rss": [
            "https://news.google.com/rss/search?q=%22Caribou+Biosciences%22+car-t&hl=en-US&gl=US&ceid=US:en"
        ],
        "product_keywords": [
            "cb-010",
            "cb-011",
            "vispa-cel"
        ]
    },
    {
        "name": "CRISPR Therapeutics",
        "category": "异体/现货型CAR-T",
        "sec_ticker": "CRSP",
        "news_pages": [
            "https://www.crisprtx.com/about-us/press-releases-and-presentations"
        ],
        "product_keywords": [
            "ctx110",
            "ctx112",
            "ctx130",
            "casgevy"
        ]
    },
    {
        "name": "Century Therapeutics",
        "category": "异体/现货型CAR-T",
        "sec_ticker": "IPSC",
        "rss": [
            "https://news.google.com/rss/search?q=%22Century+Therapeutics%22+car-t&hl=en-US&gl=US&ceid=US:en"
        ],
        "product_keywords": [
            "cnty-101",
            "cnty-102"
        ]
    },
    {
        "name": "Autolus Therapeutics",
        "category": "自体下一代CAR-T",
        "sec_ticker": "AUTL",
        "rss": [
            "https://news.google.com/rss/search?q=%22Autolus+Therapeutics%22+car-t&hl=en-US&gl=US&ceid=US:en"
        ],
        "product_keywords": [
            "obe-cel",
            "obecabtagene",
            "auto1"
        ]
    },
    {
        "name": "Arsenal Biosciences",
        "category": "自体下一代CAR-T",
        "news_pages": [
            "https://www.arsenalbio.com/news/"
        ],
        "product_keywords": [
            "arsenal",
            "ab-1015"
        ]
    },
    {
        "name": "Gilead (含Arcellx/Kite)",
        "category": "自体下一代CAR-T / 在位者",
        "tier": "priority",
        "diversified": True,
        "sec_ticker": "GILD",
        "news_pages": [
            "https://www.gilead.com/news/news-details"
        ],
        "product_keywords": [
            "kite-363",
            "kite-753"
        ]
    },
    {
        "name": "Roche (含Poseida/Genentech)",
        "category": "自体下一代CAR-T / 在位者",
        "news_pages": [
            "https://www.roche.com/media/releases"
        ],
        "product_keywords": [
            "columvi",
            "glofitamab",
            "lunsumio",
            "mosunetuzumab",
            "polivy",
            "poseida"
        ]
    },
    {
        "name": "A2 Biotherapeutics",
        "category": "实体瘤CAR-T/TCR-T",
        "news_pages": [
            "https://www.a2bio.com/news/"
        ],
        "product_keywords": [
            "a2b530",
            "a2b694",
            "tmod"
        ]
    },
    {
        "name": "Affini-T Therapeutics",
        "category": "实体瘤CAR-T/TCR-T",
        "news_pages": [
            "https://www.affini-t.com/news"
        ],
        "product_keywords": [
            "afnt-111",
            "afnt-211"
        ]
    },
    {
        "name": "Immatics",
        "category": "实体瘤CAR-T/TCR-T",
        "sec_ticker": "IMTX",
        "rss": [
            "https://investors.immatics.com/rss/news-releases.xml"
        ],
        "product_keywords": [
            "ima401",
            "ima402",
            "ima203",
            "actengine"
        ]
    },
    {
        "name": "Immunocore",
        "category": "实体瘤CAR-T/TCR-T",
        "sec_ticker": "IMCR",
        "news_pages": [
            "https://www.immunocore.com/investors/news/press-releases"
        ],
        "product_keywords": [
            "kimmtrak",
            "tebentafusp",
            "imc-f106c"
        ]
    },
    {
        "name": "Adaptimmune Therapeutics",
        "category": "实体瘤CAR-T/TCR-T",
        "product_keywords": [
            "afami-cel",
            "tecelra",
            "lete-cel"
        ]
    },
    {
        "name": "Precision Biosciences",
        "category": "失败/转向案例",
        "sec_ticker": "DTIL",
        "product_keywords": [
            "pbcar0191",
            "azer-cel",
            "azercabtagene"
        ]
    },
    {
        "name": "Sana Biotechnology",
        "category": "失败/转向案例",
        "sec_ticker": "SANA",
        "product_keywords": [
            "sc291",
            "sc262"
        ]
    },
    {
        "name": "Bristol Myers Squibb",
        "category": "在位者大药企",
        "diversified": True,
        "sec_ticker": "BMY",
        "rss": [
            "https://news.google.com/rss/search?q=%22Bristol+Myers+Squibb%22+car-t+cell+therapy&hl=en-US&gl=US&ceid=US:en"
        ],
        "product_keywords": [
            "breyanzi",
            "liso-cel",
            "abecma",
            "ide-cel",
            "arlo-cel"
        ]
    },
    {
        "name": "Johnson & Johnson",
        "category": "在位者大药企",
        "sec_ticker": "JNJ",
        "product_keywords": [
            "carvykti",
            "cilta-cel",
            "ciltacabtagene",
            "c-car039"
        ]
    },
    {
        "name": "Legend Biotech",
        "category": "在位者大药企",
        "sec_ticker": "LEGN",
        "rss": [
            "https://investors.legendbiotech.com/rss/news-releases.xml"
        ],
        "product_keywords": [
            "carvykti",
            "cilta-cel",
            "lcar-b38m"
        ]
    },
    {
        "name": "Novartis",
        "category": "在位者大药企",
        "sec_ticker": "NVS",
        "product_keywords": [
            "kymriah",
            "tisa-cel",
            "tisagenlecleucel",
            "t-charge"
        ]
    },
    {
        "name": "AbbVie / Genmab (epcoritamab)",
        "category": "Ronde-cel竞品(LBCL)",
        "sec_ticker": "GMAB",
        "rss": [
            "https://ir.genmab.com/rss/news-releases.xml"
        ],
        "product_keywords": [
            "epcoritamab",
            "epkinly",
            "tepkinly",
            "genmab"
        ]
    },
    {
        "name": "ADC Therapeutics",
        "category": "Ronde-cel竞品(LBCL)",
        "sec_ticker": "ADCT",
        "news_pages": [
            "https://ir.adctherapeutics.com/news-releases"
        ],
        "product_keywords": [
            "zynlonta",
            "loncastuximab",
            "adct-301",
            "adct-602"
        ]
    },
    {
        "name": "Incyte",
        "category": "Ronde-cel竞品(LBCL)",
        "sec_ticker": "INCY",
        "product_keywords": [
            "monjuvi",
            "tafasitamab"
        ]
    },
    {
        "name": "Miltenyi Biomedicine (zamto-cel)",
        "category": "Ronde-cel竞品(LBCL)",
        "tier": "priority",
        "news_pages": [
            "https://www.miltenyibiomedicine.com/news-events/press-releases"
        ],
        "product_keywords": [
            "zamto-cel",
            "zamtocabtagene",
            "mb-cart2019"
        ]
    },
    {
        "name": "CARsgen Therapeutics (科济药业)",
        "category": "Ronde-cel竞品(LBCL)",
        "rss": [
            "https://news.google.com/rss/search?q=CARsgen+Therapeutics+car-t&hl=en-US&gl=US&ceid=US:en"
        ],
        "product_keywords": [
            "satri-cel",
            "ct041",
            "ct1190",
            "carsgen"
        ]
    },
    {
        "name": "Innovative Cellular Therapeutics (ICT)",
        "category": "LYL273竞品(mCRC)",
        "news_pages": [
            "https://www.ictbio.com/news/"
        ],
        "product_keywords": [
            "gcc19cart",
            "gcc",
            "gucy2c",
            "coupledcar"
        ]
    },
    {
        "name": "北京艺妙神州 (Immunochina)",
        "category": "LYL273竞品(mCRC)",
        "news_pages": [
            "http://www.immunochina.com/en/index.php/home/news/news_1.html"
        ],
        "product_keywords": [
            "im96",
            "gucy2c"
        ],
        "tier": "priority"
    },
    {
        "name": "Chimeric Therapeutics",
        "category": "LYL273竞品(mCRC)",
        "news_pages": [
            "https://www.chimerictherapeutics.com/investor"
        ],
        "product_keywords": [
            "chm-2101",
            "cdh17"
        ]
    },
    {
        "name": "Carina Biotech",
        "category": "LYL273竞品(mCRC)",
        "news_pages": [
            "https://www.carinabiotech.com/news/"
        ],
        "product_keywords": [
            "cna3103",
            "lgr5"
        ]
    },
    {
        "name": "Merck KGaA (M9140)",
        "category": "LYL273竞品(mCRC)",
        "tier": "priority",
        "diversified": True,
        "rss": [
            "https://news.google.com/rss/search?q=%22Merck+KGaA%22+ADC+cancer+colorectal&hl=en-US&gl=US&ceid=US:en"
        ],
        "product_keywords": [
            "precemtabart",
            "m9140",
            "ceacam5",
            "tocentecan"
        ]
    },
    {
        "name": "Sanofi",
        "category": "LYL273竞品(mCRC)",
        "sec_ticker": "SNY",
        "product_keywords": [
            "tusamitamab",
            "ceacam5"
        ]
    },
    {
        "name": "Pfizer",
        "category": "LYL273竞品(mCRC) / 10-K列示",
        "sec_ticker": "PFE",
        "product_keywords": [
            "tusamitamab",
            "ceacam5"
        ]
    },
    {
        "name": "AstraZeneca (含EsoBiotec)",
        "category": "10-K潜在竞品",
        "sec_ticker": "AZN",
        "product_keywords": [
            "enabl",
            "esobiotec",
            "in vivo car-t"
        ]
    },
    {
        "name": "Agenus",
        "category": "10-K潜在竞品",
        "sec_ticker": "AGEN",
        "product_keywords": [
            "balstilimab",
            "botensilimab"
        ]
    },
    {
        "name": "Akeso（康方生物）",
        "category": "10-K潜在竞品",
        "news_pages": [
            "https://www.akesobio.com/en/media/akeso-news/"
        ],
        "product_keywords": [
            "ivonescimab",
            "ak104",
            "ak112"
        ]
    },
    {
        "name": "Summit Therapeutics",
        "category": "10-K潜在竞品",
        "sec_ticker": "SMMT",
        "product_keywords": [
            "ivonescimab",
            "smt112"
        ]
    }
]
# ═══════════════════════════════════════════════════════
# 竞争路线图（Competitive Roadmap）
# ═══════════════════════════════════════════════════════
# 基于实际试验时间线手动维护。
# 重点对象（5家）：Lyell/ronde-cel+LYL273 / zamto-cel / KITE-753 / M9140 / IM96
# 每个条目：company(需匹配COMPANIES)、date(YYYY-MM / YYYY-QX / YYYY-HX)、
#           event、category(临床数据/监管进展/学术会议)、
#           product、confidence(确定/预计/可能/乐观预计)、note
# 看板"路线图"按钮展示为甘特图矩阵（公司×时间轴）。
ROADMAP = [
    {
        "company": "北京艺妙神州 (Immunochina)",
        "date": "2026-Q3",
        "event": "IM96 NCT06718738 数据更新",
        "category": "临床数据",
        "product": "IM96",
        "confidence": "预计",
        "note": "GUCY2C CAR-T；JCO 2024 已有 20 例爬坡 ORR 26.3%/DL3 40%；LYL273 同靶点唯一竞品"
    },
    {
        "company": "Lyell Immunopharma",
        "date": "2026-Q4",
        "event": "ronde-cel PiNACLE Phase 2 数据更新",
        "category": "临床数据",
        "product": "ronde-cel",
        "confidence": "预计",
        "note": ""
    },
    {
        "company": "Lyell Immunopharma",
        "date": "2026-Q4",
        "event": "LYL273 Phase 1 mCRC DL3剂量数据更新",
        "category": "临床数据",
        "product": "LYL273",
        "confidence": "预计",
        "note": ""
    },
    {
        "company": "Lyell Immunopharma",
        "date": "2026-Q4",
        "event": "PiNACLE-H2H 头对头试验3期进展公布",
        "category": "临床数据",
        "product": "ronde-cel",
        "confidence": "预计",
        "note": "vs Yescarta/Breyanzi；2025.2 已启动入组，业界首个头对头 CAR-T 试验"
    },
        {
        "company": "Lyell Immunopharma",
        "date": "2027-H1",
        "event": "LYL273关键性/注册性试验启动",
        "category": "临床数据",
        "product": "ronde-cel",
        "confidence": "预计",
        "note": ""
    },
    {
        "company": "Lyell Immunopharma",
        "date": "2027-H1",
        "event": "ronde-cel PiNACLE 关键性试验数据读出",
        "category": "临床数据",
        "product": "ronde-cel",
        "confidence": "预计",
        "note": "取决于 PiNACLE 数据是否支持加速批准路径"
    },
    {
        "company": "Miltenyi Biomedicine (zamto-cel)",
        "date": "2027-Q2",
        "event": "EMA 审评决定预期 (MAA)",
        "category": "监管进展",
        "product": "zamto-cel",
        "confidence": "预计",
        "note": "若获批，将成为 ronde-cel 上市前已存在的同赛道竞品"
    },
    {
        "company": "Gilead (含Arcellx/Kite)",
        "date": "2027-H2",
        "event": "KITE-753 vs axi-cel 随机对照中期/关键数据读出",
        "category": "临床数据",
        "product": "KITE-753",
        "confidence": "可能",
        "note": "若数据积极，Kite 将直接威胁 ronde-cel"
    },
    {
        "company": "Lyell Immunopharma",
        "date": "2027-H2",
        "event": "ronde-cel BLA 提交（加速批准路径）",
        "category": "监管进展",
        "product": "ronde-cel",
        "confidence": "乐观预计",
        "note": "最早上市时间窗口"
    },
    {
        "company": "Merck KGaA (M9140)",
        "date": "2028-H2",
        "event": "M9140 PROCEADE-CRC-03 3 期关键数据读出预期",
        "category": "临床数据",
        "product": "M9140",
        "confidence": "可能",
        "note": "若积极，ADC 可能在 LYL273 之前获批 mCRC 后线"
    }
]
