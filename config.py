# -*- coding: utf-8 -*-
"""
监控目标配置：Lyell 及所有竞品公司的信息源钩子。

每个公司可配置的监控钩子（全部可选，按需填写）：
  - ct_sponsor : ClinicalTrials.gov 的 Sponsor 名称（用于按申办方检索临床试验）
  - sec_ticker : 美股代码（用于 SEC EDGAR 申报监控，自动映射到 CIK）
  - rss        : RSS/Atom 订阅地址列表（最稳，优先使用）
  - news_pages : 需要监控的新闻/IR 页面 URL 列表（无 RSS 时，做“链接集合差异”检测）
  - pubmed     : PubMed 检索关键词列表（监控新发表论文）

分类 category 仅用于站点分组展示。
"""
import os

# 邮件凭据从环境变量/GitHub Secrets 读取（不要把密码写进代码提交到公开仓库）
_SMTP_USER = os.environ.get("MONITOR_SMTP_USER", "")
_SMTP_PASS = os.environ.get("MONITOR_SMTP_PASS", "")
_MAIL_TO = os.environ.get("MONITOR_MAIL_TO", _SMTP_USER)

# —— 全局设置 ——
SETTINGS = {
    # SEC 要求 User-Agent 带真实联系方式（否则会被限流）
    "user_agent": "LyellCompetitorMonitor/1.0 (contact: tangjingjudy@gmail.com)",
    "request_timeout": 25,
    "request_delay_sec": 0.8,          # 每次请求之间的礼貌间隔
    "clinicaltrials_page_size": 30,    # 每家公司拉取的最新临床试验数量
    "clinicaltrials_max_age_days": 14, # 只保留最近 N 天内更新过的试验（过滤陈旧回溯）
    "sec_recent_count": 30,            # 每家公司检查的最新申报数量
    "pubmed_retmax": 15,               # 每个关键词拉取的最新论文数量

    # —— 邮件推送（可选，仅推送“重点监控对象”的新增）——
    # 凭据齐全（配置了 SMTP 用户名+密码）即自动开启；否则自动跳过发送。
    # 本地测试可 export MONITOR_SMTP_USER / MONITOR_SMTP_PASS / MONITOR_MAIL_TO；
    # 云端到 仓库 Settings → Secrets 里配同名 Secret 即可，切勿把密码写进本文件。
    "email": {
        "enabled": bool(_SMTP_USER and _SMTP_PASS),
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_tls": True,
        "username": _SMTP_USER,
        "password": _SMTP_PASS,            # Gmail 需用「应用专用密码」，非登录密码
        "from_addr": _SMTP_USER,
        "to_addrs": [a.strip() for a in _MAIL_TO.split(",") if a.strip()],  # 逗号分隔可多收件人
        "min_hours_between_emails": 0,     # 重点对象一有新消息即发；>0 可设最小间隔防打扰
        "subject_prefix": "[Lyell竞品监控·重点]",
    },

    # —— 站点输出 ——
    "site": {
        "title": "Lyell 及下一代 CAR-T 竞品动态监控",
        "output_dir": "data/site",     # 生成的静态站点目录（可托管到 GitHub Pages / Netlify / S3）
        "recent_days_highlight": 14,    # 首页高亮“近 N 天”新增
    },

    # —— 里程碑过滤（核心）——
    # 目的：只保留“新临床数据 / 上市前进展 / 重大公司事件”，过滤例行噪音。
    "milestone_filter": {
        "enabled": True,
        # ClinicalTrials.gov 的试验状态/分期变化本身即高信号，默认整体保留
        "always_keep_clinicaltrials": True,
        # SEC 只保留“重大事件/年报”类表单，丢弃 Form 4(高管持股)、季报、S-8 等例行文件
        "meaningful_sec_forms": [
            "8-K", "8-K/A", "6-K", "6-K/A", "20-F", "20-F/A", "10-K", "10-K/A", "F-1", "424B4",
        ],
        # PubMed / 新闻 / RSS：标题或摘要命中以下任一关键词才保留
        "keywords": [
            # —— 临床数据 ——
            "phase 1", "phase 2", "phase 3", "phase i", "phase ii", "phase iii",
            "1期", "2期", "3期", "一期", "二期", "三期", "临床数据", "临床结果",
            "topline", "readout", "interim", "data", "results", "efficacy", "response rate",
            "orr", "complete response", " cr ", "pfs", "overall survival", " os ", "duration of response",
            "中期", "数据", "疗效", "缓解率", "完全缓解", "生存期", "随访",
            "pivotal", "registrational", "关键性", "注册", "first patient", "首例", "dosed", "给药",
            "cohort", "队列", "trial", "study", "试验", "enrollment", "入组",
            # —— 会议 ——
            "ash", "asco", "eha", "aacr", "esmo", "会议", "abstract", "presentation", "摘要", "poster", "oral",
            # —— 监管/上市前进展 ——
            "fda", "ema", "nmpa", "mhra", "pmda", "bla", "nda", "maa", "ind", "biologics license",
            "approval", "approved", "clearance", "authoris", "authoriz", "获批", "批准", "上市许可", "递交", "提交", "受理",
            "breakthrough", "fast track", "rmat", "orphan", "priority review", "accelerated",
            "pdufa", "complete response letter", "crl", "designation", "认定", "突破性", "孤儿药", "优先审评",
            "clinical hold", "临床暂停", "terminated", "discontinu", "终止", "暂停",
            # —— 重大公司事件 ——
            "acquire", "acquisition", "merger", "收购", "并购", "license", "licensing", "授权", "合作",
            "partnership", "collaboration", "deal", "milestone", "里程碑",
        ],
    },

    # —— 分级监控（权重）——
    # 给公司分“重点/常规”两档：重点对象抓取更频繁、过滤更宽松、并纳入每日邮件；
    # 常规对象降低频率、维持严格里程碑过滤，以压制噪音。
    # 在 COMPANIES 中给某公司加 "tier": "priority" 即升为重点；不写则默认为 "standard"。
    "tiers": {
        "priority": {
            "label": "重点监控",
            "run_every_days": 1,     # 每天扫描
            "relaxed_filter": True,  # 放宽：新论文/新闻即保留（临床、申报本就保留）
            "email": True,           # 纳入每日邮件推送
        },
        "standard": {
            "label": "常规监控",
            "run_every_days": 3,     # 每 3 天扫描一次（降频降噪）
            "relaxed_filter": False, # 维持严格里程碑关键词过滤
            "email": False,          # 不进邮件，只在看板可查
        },
    },
}


COMPANIES = [
    # ————————————————————————————— 监控主体 —————————————————————————————
    {
        "name": "Lyell Immunopharma",
        "category": "监控主体",
        "tier": "priority",            # 监控主体：最高优先级
        "ct_sponsor": "Lyell Immunopharma",
        "sec_ticker": "LYEL",
        "rss": [],
        "news_pages": ["https://ir.lyell.com/news-events/news-releases"],
        "pubmed": ["Lyell Immunopharma", "rondecabtagene", "ronde-cel", "LYL314", "LYL273", "LYL119"],
    },

    # ————————————————————— 一、异体/现货型 CAR-T —————————————————————
    {"name": "Allogene Therapeutics", "category": "异体/现货型CAR-T",
     "ct_sponsor": "Allogene Therapeutics", "sec_ticker": "ALLO",
     "news_pages": ["https://ir.allogene.com/news-releases"], "pubmed": ["Allogene cema-cel"]},
    {"name": "Caribou Biosciences", "category": "异体/现货型CAR-T",
     "ct_sponsor": "Caribou Biosciences", "sec_ticker": "CRBU",
     "news_pages": ["https://ir.cariboubio.com/news-releases"], "pubmed": ["Caribou CB-010 vispa-cel"]},
    {"name": "CRISPR Therapeutics", "category": "异体/现货型CAR-T",
     "ct_sponsor": "CRISPR Therapeutics", "sec_ticker": "CRSP",
     "news_pages": ["https://www.crisprtx.com/about-us/press-releases-and-presentations"]},
    {"name": "Century Therapeutics", "category": "异体/现货型CAR-T",
     "ct_sponsor": "Century Therapeutics", "sec_ticker": "IPSC",
     "news_pages": ["https://ir.centurytx.com/news-releases"]},

    # ——————————————— 二、自体下一代基因/表观增强型 CAR-T ———————————————
    {"name": "Autolus Therapeutics", "category": "自体下一代CAR-T",
     "ct_sponsor": "Autolus", "sec_ticker": "AUTL",
     "news_pages": ["https://www.autolus.com/media/press-releases/"]},
    {"name": "Arsenal Biosciences", "category": "自体下一代CAR-T",
     "ct_sponsor": "Arsenal Biosciences",
     "news_pages": ["https://www.arsenalbio.com/news/"]},
    # Arcellx 已被 Gilead 收购 → 跟踪 Gilead
    {"name": "Gilead (含Arcellx/Kite)", "category": "自体下一代CAR-T / 在位者",
     "tier": "priority",            # Yescarta(axi-cel) 是 PiNACLE-H2H 头对头对照之一；PiNACLE-H2H 结果直接决定 ronde-cel 市场前景
     "diversified": True,           # 多元化大集团，网页新闻走关键词过滤
     "ct_sponsor": "Kite, A Gilead Company", "sec_ticker": "GILD",
     "news_pages": ["https://www.gilead.com/news/news-details"],
     # 只保留 CAR-T/细胞治疗 相关试验（过滤HIV/HCV/肝病等大量无关管线）
     "ct_keywords": ["yescarta", "axicabtagene", "axi-cel", "tecartus", "brexucabtagene",
                     "kite-363", "kite-753", "duocore", "car-t", "car t",
                     "chimeric antigen", "lymphoma", "dlbcl", "follicular",
                     "leukemia", "all", "b-cell", "mantle cell"]},
    # Poseida 已被 Roche 收购 → 跟踪 Roche
    {"name": "Roche (含Poseida/Genentech)", "category": "自体下一代CAR-T / 在位者",
     "ct_sponsor": "Hoffmann-La Roche",
     "news_pages": ["https://www.roche.com/media/releases"]},

    # ————————————————— 三、实体瘤 CAR-T / TCR-T 专精 —————————————————
    {"name": "A2 Biotherapeutics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "A2 Biotherapeutics",
     "news_pages": ["https://www.a2bio.com/news/"]},
    {"name": "Affini-T Therapeutics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Affini-T Therapeutics",
     "news_pages": ["https://www.affini-t.com/news"]},
    {"name": "Immatics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Immatics", "sec_ticker": "IMTX",
     "news_pages": ["https://investors.immatics.com/news-releases"]},
    {"name": "Immunocore", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Immunocore", "sec_ticker": "IMCR",
     "news_pages": ["https://ir.immunocore.com/news-releases"]},
    {"name": "Adaptimmune Therapeutics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Adaptimmune",
     "pubmed": ["afami-cel Tecelra", "Adaptimmune TCR"]},

    # ————————————————— 失败/并购/转向案例（低优先级，仅跟踪残余资产/授权动向）—————————————————
    {"name": "Atara Biotherapeutics", "category": "失败/退出案例",
     "ct_sponsor": "Atara Biotherapeutics", "sec_ticker": "ATRA",
     "pubmed": ["tabelecleucel Ebvallo"]},
    {"name": "Precision Biosciences", "category": "失败/转向案例",
     "ct_sponsor": "Precision Biosciences", "sec_ticker": "DTIL"},
    {"name": "Sana Biotechnology", "category": "失败/转向案例",
     "ct_sponsor": "Sana Biotechnology", "sec_ticker": "SANA"},

    # ————————————————— 四、已上市大型药企（在位者）—————————————————
    {"name": "Bristol Myers Squibb", "category": "在位者大药企",
     "tier": "priority",            # Breyanzi(liso-cel) 是 PiNACLE-H2H 头对头对照之一；ronde-cel上市后面临的直接竞争
     "diversified": True,           # 多元化大集团，网页新闻走关键词过滤
     "ct_sponsor": "Bristol-Myers Squibb", "sec_ticker": "BMY",
     "news_pages": ["https://news.bms.com/news/corporate-financial.aspx"],
     # 只保留 CAR-T/细胞治疗/血液肿瘤 相关试验（过滤Opdivo/Eliquis/Pomalyst等大量无关管线）
     "ct_keywords": ["breyanzi", "lisocabtagene", "liso-cel", "abecma", "idecabtagene",
                     "ide-cel", "arlo-cel", "car-t", "car t", "chimeric antigen",
                     "lymphoma", "dlbcl", "follicular", "myeloma", "gprc5d",
                     "b-cell", "mantle cell", "leukemia"]},
    {"name": "Johnson & Johnson", "category": "在位者大药企",
     "ct_sponsor": "Janssen Research & Development, LLC", "sec_ticker": "JNJ"},
    {"name": "Legend Biotech", "category": "在位者大药企",
     "ct_sponsor": "Legend Biotech", "sec_ticker": "LEGN",
     "news_pages": ["https://investors.legendbiotech.com/news-releases"]},
    {"name": "Novartis", "category": "在位者大药企",
     "ct_sponsor": "Novartis", "sec_ticker": "NVS"},

    # ————————————————— 五、Ronde-cel（LBCL）具体竞品 —————————————————
    {"name": "AbbVie / Genmab (epcoritamab)", "category": "Ronde-cel竞品(LBCL)",
     "ct_sponsor": "Genmab", "sec_ticker": "GMAB",
     "news_pages": ["https://ir.genmab.com/news-releases"]},
    {"name": "ADC Therapeutics", "category": "Ronde-cel竞品(LBCL)",
     "ct_sponsor": "ADC Therapeutics", "sec_ticker": "ADCT",
     "news_pages": ["https://ir.adctherapeutics.com/news-releases"]},
    {"name": "Incyte", "category": "Ronde-cel竞品(LBCL)",
     "ct_sponsor": "Incyte Corporation", "sec_ticker": "INCY"},
    {"name": "Miltenyi Biomedicine (zamto-cel)", "category": "Ronde-cel竞品(LBCL)",
     "tier": "priority",            # CD19/CD20双靶点最成熟竞品，已进入随机对照3期(DALY 2-EU, vs化疗)；ronde-cel最需要跟踪的直接竞争对手
     "ct_sponsor": "Miltenyi Biomedicine",
     "news_pages": ["https://www.miltenyibiomedicine.com/news-events/press-releases"],
     "pubmed": ["zamtocabtagene", "zamto-cel", "MB-CART2019.1"],
     "ct_keywords": ["zamto", "mb-cart", "car-t", "car t", "lymphoma", "dlbcl",
                     "cd19", "cd20", "b-cell"]},
    {"name": "CARsgen Therapeutics (科济药业)", "category": "Ronde-cel竞品(LBCL)",
     "tier": "priority",            # satri-cel：同为 CD19/CD20 双靶点 LBCL 直接竞品
     "ct_sponsor": "CARsgen Therapeutics",
     "news_pages": ["https://www.carsgen.com/en/media/news/"],
     "pubmed": ["CARsgen satricabtagene", "satri-cel CT041"],
     "ct_keywords": ["satri", "ct041", "ct1190", "carsgen", "car-t", "car t",
                     "lymphoma", "dlbcl", "cd19", "cd20", "cldn18", "gpc3",
                     "claudin", "gastric", "hepatocellular", "b-cell"]},

    # ————————————————— 六、LYL273（mCRC）具体竞品 —————————————————
    {"name": "Innovative Cellular Therapeutics (ICT)", "category": "LYL273竞品(mCRC)",
     "tier": "priority",            # GCC19CART：GUCY2C 靶点 mCRC 进度最快的直接竞品
     "ct_sponsor": "Innovative Cellular Therapeutics",
     "news_pages": ["https://www.ictbio.com/news/"],
     "pubmed": ["GCC19CART", "GCC CAR-T colorectal"],
     "ct_keywords": ["gcc19cart", "gcc", "gucy2c", "car-t", "car t",
                     "coupledcar", "colorectal", "mcrc", "crc"]},
    {"name": "北京艺妙神州 (Immunochina)", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Beijing Immunochina Medical",
     "news_pages": ["http://www.immunochina.com/en/index.php/home/news/news_1.html"],
     "pubmed": ["IM96 CAR-T colorectal", "GUCY2C CAR-T"]},
    {"name": "Chimeric Therapeutics", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Chimeric Therapeutics",
     "news_pages": ["https://www.chimerictherapeutics.com/investor"],
     "pubmed": ["CHM-2101 CDH17"]},
    {"name": "Carina Biotech", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Carina Biotech",
     "news_pages": ["https://www.carinabiotech.com/news/"],
     "pubmed": ["CNA3103 LGR5 CAR-T"]},
    {"name": "Merck KGaA (M9140)", "category": "LYL273竞品(mCRC)",
     "tier": "priority",            # M9140 CEACAM5 ADC：mCRC 跨模态关键威胁
     "diversified": True,           # 多元化大集团：网页新闻混杂大量无关业务，重点档下仍对网页做关键词过滤（临床/论文精确检索不受影响）
     "ct_sponsor": "Merck KGaA, Darmstadt, Germany",
     "news_pages": ["https://www.merckgroup.com/en/news.html"],
     "pubmed": ["precemtabart tocentecan", "M9140 CEACAM5"],
     # 只保留 CEACAM5 ADC / 结直肠癌 相关试验（过滤电子/生命科学等大量无关管线）
     "ct_keywords": ["precemtabart", "m9140", "ceacam5", "tocentecan"]},
    # （注：不包含 "adc"/"antibody-drug"/"colorectal"/"crc" 等泛用词——
    #  Merck KGaA 有数十条其他 ADC 管线与多条 CRC 药物，广义词会导致大量误命中）
    {"name": "Sanofi", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Sanofi", "sec_ticker": "SNY",
     "pubmed": ["tusamitamab CEACAM5"]},
    {"name": "Pfizer", "category": "LYL273竞品(mCRC) / 10-K列示",
     "ct_sponsor": "Pfizer", "sec_ticker": "PFE",
     "pubmed": ["tusamitamab CEACAM5"]},
    {"name": "Celyad Oncology", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Celyad Oncology",
     "pubmed": ["CYAD-101 NKG2D colorectal"]},

    # ————————————————— 七、10-K 列示的其他潜在竞争对手 —————————————————
    {"name": "AstraZeneca (含EsoBiotec)", "category": "10-K潜在竞品",
     "ct_sponsor": "AstraZeneca", "sec_ticker": "AZN",
     "pubmed": ["in vivo CAR-T ENaBL"]},
    {"name": "Agenus", "category": "10-K潜在竞品",
     "ct_sponsor": "Agenus", "sec_ticker": "AGEN"},
    {"name": "Akeso（康方生物）", "category": "10-K潜在竞品",
     "ct_sponsor": "Akeso",
     "news_pages": ["https://www.akesobio.com/en/media/akeso-news/"],
     "pubmed": ["Akeso ivonescimab"]},
    {"name": "Summit Therapeutics", "category": "10-K潜在竞品",
     "ct_sponsor": "Summit Therapeutics", "sec_ticker": "SMMT"},
]
