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

# —— 全局设置 ——
SETTINGS = {
    # SEC 要求 User-Agent 带真实联系方式（否则会被限流）
    "user_agent": "LyellCompetitorMonitor/1.0 (contact: tangjingjudy@gmail.com)",
    "request_timeout": 25,
    "request_delay_sec": 0.8,          # 每次请求之间的礼貌间隔
    "clinicaltrials_page_size": 30,    # 每家公司拉取的最新临床试验数量
    "sec_recent_count": 30,            # 每家公司检查的最新申报数量
    "pubmed_retmax": 15,               # 每个关键词拉取的最新论文数量

    # —— 邮件推送（可选）——
    "email": {
        "enabled": False,              # 设为 True 才会发邮件
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_tls": True,
        "username": "your-email@example.com",
        "password": "your-app-password",   # 建议用应用专用密码 / 环境变量
        "from_addr": "your-email@example.com",
        "to_addrs": ["your-email@example.com"],  # 可填多个收件人
        "min_hours_between_emails": 12,    # 两封邮件的最小间隔（防打扰）；0=有新消息即发
        "subject_prefix": "[Lyell竞品监控]",
    },

    # —— 站点输出 ——
    "site": {
        "title": "Lyell 及下一代 CAR-T 竞品动态监控",
        "output_dir": "data/site",     # 生成的静态站点目录（可托管到 GitHub Pages / Netlify / S3）
        "recent_days_highlight": 14,    # 首页高亮“近 N 天”新增
    },
}


COMPANIES = [
    # ————————————————————————————— 监控主体 —————————————————————————————
    {
        "name": "Lyell Immunopharma",
        "category": "监控主体",
        "ct_sponsor": "Lyell Immunopharma",
        "sec_ticker": "LYEL",
        "rss": [],
        "news_pages": ["https://ir.lyell.com/news-events/news-releases"],
        "pubmed": ["Lyell Immunopharma", "rondecabtagene", "ronde-cel"],
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
     "ct_sponsor": "Kite, A Gilead Company", "sec_ticker": "GILD",
     "news_pages": ["https://www.gilead.com/news/news-details"]},
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

    # ————————————————— 四、已上市大型药企（在位者）—————————————————
    {"name": "Bristol Myers Squibb", "category": "在位者大药企",
     "ct_sponsor": "Bristol-Myers Squibb", "sec_ticker": "BMY",
     "news_pages": ["https://news.bms.com/news/corporate-financial.aspx"]},
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
     "ct_sponsor": "Miltenyi Biomedicine",
     "news_pages": ["https://www.miltenyibiomedicine.com/news-events/press-releases"],
     "pubmed": ["zamtocabtagene", "zamto-cel"]},
    {"name": "CARsgen Therapeutics (科济药业)", "category": "Ronde-cel竞品(LBCL)",
     "ct_sponsor": "CARsgen Therapeutics",
     "news_pages": ["https://www.carsgen.com/en/media/news/"],
     "pubmed": ["CARsgen satricabtagene", "satri-cel CT041"]},

    # ————————————————— 六、LYL273（mCRC）具体竞品 —————————————————
    {"name": "Innovative Cellular Therapeutics (ICT)", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Innovative Cellular Therapeutics",
     "news_pages": ["https://www.ictbio.com/news/"],
     "pubmed": ["GCC19CART", "GCC CAR-T colorectal"]},
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
     "ct_sponsor": "Merck KGaA, Darmstadt, Germany",
     "news_pages": ["https://www.merckgroup.com/en/news.html"],
     "pubmed": ["precemtabart tocentecan", "M9140 CEACAM5"]},
    {"name": "Sanofi", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Sanofi", "sec_ticker": "SNY",
     "pubmed": ["tusamitamab CEACAM5"]},

    # ————————————————— 七、10-K 列示的其他潜在竞争对手 —————————————————
    {"name": "AstraZeneca (含EsoBiotec)", "category": "10-K潜在竞品",
     "ct_sponsor": "AstraZeneca", "sec_ticker": "AZN",
     "pubmed": ["in vivo CAR-T ENaBL"]},
    {"name": "Agenus", "category": "10-K潜在竞品",
     "ct_sponsor": "Agenus", "sec_ticker": "AGEN"},
    {"name": "Summit Therapeutics", "category": "10-K潜在竞品",
     "ct_sponsor": "Summit Therapeutics", "sec_ticker": "SMMT"},
]
