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
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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
        "recent_days_highlight": 7,     # 面板上"NEW"标记
        "items_max_age_days": 7,        # 面板只保留最近 N 天的条目，超时自动清理
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
        "rss": ["https://ir.lyell.com/rss/news-releases.xml"],
        "pubmed": ["Lyell Immunopharma", "rondecabtagene", "ronde-cel", "LYL314", "LYL273", "LYL119"],
    },

    # ————————————————————— 一、异体/现货型 CAR-T —————————————————————
    {"name": "Allogene Therapeutics", "category": "异体/现货型CAR-T",
     "ct_sponsor": "Allogene Therapeutics", "sec_ticker": "ALLO",
     "rss": ["https://ir.allogene.com/rss/news-releases.xml"], "pubmed": ["Allogene cema-cel"],
     "product_keywords": ["allogene", "cema-cel", "allo-501", "allo-715"],
     "ct_keywords": ["allogene", "cema-cel", "allo-501", "allo-715", "car-t", "car t", "chimeric antigen"]},
    {"name": "Caribou Biosciences", "category": "异体/现货型CAR-T",
     "ct_sponsor": "Caribou Biosciences", "sec_ticker": "CRBU",
     "rss": ["https://news.google.com/rss/search?q=%22Caribou+Biosciences%22+car-t&hl=en-US&gl=US&ceid=US:en"],
     "pubmed": ["Caribou CB-010 vispa-cel"],
     "product_keywords": ["caribou", "cb-010", "cb-011", "vispa-cel"],
     "ct_keywords": ["caribou", "cb-010", "cb-011", "vispa-cel", "car-t", "car t", "chimeric antigen"]},
    {"name": "CRISPR Therapeutics", "category": "异体/现货型CAR-T",
     "ct_sponsor": "CRISPR Therapeutics", "sec_ticker": "CRSP",
     "news_pages": ["https://www.crisprtx.com/about-us/press-releases-and-presentations"],
     "product_keywords": ["crispr", "ctx110", "ctx112", "ctx130", "casgevy"],
     "ct_keywords": ["crispr", "ctx110", "ctx112", "ctx130", "casgevy", "car-t", "car t", "chimeric antigen"]},
    {"name": "Century Therapeutics", "category": "异体/现货型CAR-T",
     "ct_sponsor": "Century Therapeutics", "sec_ticker": "IPSC",
     "rss": ["https://news.google.com/rss/search?q=%22Century+Therapeutics%22+car-t&hl=en-US&gl=US&ceid=US:en"],
     "product_keywords": ["century", "cnty-101", "cnty-102"],
     "ct_keywords": ["century", "cnty-101", "cnty-102", "car-t", "car t", "chimeric antigen"]},

    # ——————————————— 二、自体下一代基因/表观增强型 CAR-T ———————————————
    {"name": "Autolus Therapeutics", "category": "自体下一代CAR-T",
     "ct_sponsor": "Autolus", "sec_ticker": "AUTL",
     "rss": ["https://news.google.com/rss/search?q=%22Autolus+Therapeutics%22+car-t&hl=en-US&gl=US&ceid=US:en"],
     "product_keywords": ["autolus", "obe-cel", "obecabtagene", "auto1"],
     "ct_keywords": ["autolus", "obe-cel", "obecabtagene", "auto1", "car-t", "car t", "chimeric antigen"]},
    {"name": "Arsenal Biosciences", "category": "自体下一代CAR-T",
     "ct_sponsor": "Arsenal Biosciences",
     "news_pages": ["https://www.arsenalbio.com/news/"],
     "product_keywords": ["arsenal", "ab-1015"],
     "ct_keywords": ["arsenal", "ab-1015", "car-t", "car t", "chimeric antigen"]},
    # Arcellx 已被 Gilead 收购 → 跟踪 Gilead
    {"name": "Gilead (含Arcellx/Kite)", "category": "自体下一代CAR-T / 在位者",
     "diversified": True,           # 多元化大集团，网页新闻走关键词过滤
     "ct_sponsor": "Kite, A Gilead Company", "sec_ticker": "GILD",
     "news_pages": ["https://www.gilead.com/news/news-details"],
     # 只保留 CAR-T/细胞治疗 相关试验（过滤HIV/HCV/肝病等大量无关管线）
     "ct_keywords": ["yescarta", "axicabtagene", "axi-cel", "tecartus", "brexucabtagene",
                     "kite-363", "kite-753", "duocore", "car-t", "car t",
                     "chimeric antigen", "lymphoma", "dlbcl", "follicular",
                     "leukemia", "all", "b-cell", "mantle cell"],
     "product_keywords": ["yescarta", "axi-cel", "tecartus", "brexu-cel", "anito-cel", "kite-363", "arcellx"]},
    # Poseida 已被 Roche 收购 → 跟踪 Roche
    {"name": "Roche (含Poseida/Genentech)", "category": "自体下一代CAR-T / 在位者",
     "ct_sponsor": "Hoffmann-La Roche",
     "news_pages": ["https://www.roche.com/media/releases"],
     # 只保留 CAR-T/血液肿瘤/Poseida管线 相关试验（过滤罗氏数百条实体瘤/眼科/神经管线）
     "ct_keywords": ["glofitamab", "columvi", "polivy", "mosunetuzumab", "lunsumio",
                     "poseida", "p-bcma", "p-muc1c", "car-t", "car t",
                     "chimeric antigen", "lymphoma", "dlbcl", "follicular",
                     "leukemia", "b-cell", "cibisatamab", "ceacam5"],
     "product_keywords": ["columvi", "glofitamab", "lunsumio", "mosunetuzumab", "polivy", "poseida"]},

    # ————————————————— 三、实体瘤 CAR-T / TCR-T 专精 —————————————————
    {"name": "A2 Biotherapeutics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "A2 Biotherapeutics",
     "news_pages": ["https://www.a2bio.com/news/"],
     "product_keywords": ["a2b530", "a2b694", "tmod"],
     "ct_keywords": ["a2b530", "a2b694", "tmod", "car-t", "car t", "chimeric antigen"]},
    {"name": "Affini-T Therapeutics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Affini-T Therapeutics",
     "news_pages": ["https://www.affini-t.com/news"],
     "product_keywords": ["affini-t", "afnt-111", "afnt-211"],
     "ct_keywords": ["affini-t", "afnt-111", "afnt-211", "car-t", "car t", "chimeric antigen"]},
    {"name": "Immatics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Immatics", "sec_ticker": "IMTX",
     "rss": ["https://investors.immatics.com/rss/news-releases.xml"],
     "product_keywords": ["immatics", "ima401", "ima402", "ima203", "actengine"],
     "ct_keywords": ["immatics", "ima401", "ima402", "ima203", "actengine", "car-t", "car t", "chimeric antigen"]},
    {"name": "Immunocore", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Immunocore", "sec_ticker": "IMCR",
     "news_pages": ["https://www.immunocore.com/investors/news/press-releases"],
     "product_keywords": ["immunocore", "kimmtrak", "tebentafusp", "imc-f106c"],
     "ct_keywords": ["immunocore", "kimmtrak", "tebentafusp", "imc-f106c", "car-t", "car t", "chimeric antigen"]},
    {"name": "Adaptimmune Therapeutics", "category": "实体瘤CAR-T/TCR-T",
     "ct_sponsor": "Adaptimmune",
     "pubmed": ["afami-cel Tecelra", "Adaptimmune TCR"],
     "product_keywords": ["adaptimmune", "afami-cel", "tecelra", "lete-cel"],
     "ct_keywords": ["adaptimmune", "afami-cel", "tecelra", "lete-cel", "car-t", "car t", "chimeric antigen"]},

    # ————————————————— 失败/并购/转向案例（低优先级，仅跟踪残余资产/授权动向）—————————————————
    {"name": "Precision Biosciences", "category": "失败/转向案例",
     "ct_sponsor": "Precision Biosciences", "sec_ticker": "DTIL",
     "product_keywords": ["pbcar0191", "azer-cel", "azercabtagene"],
     "ct_keywords": ["pbcar0191", "azer-cel", "azercabtagene", "car-t", "car t", "chimeric antigen"]},
    {"name": "Sana Biotechnology", "category": "失败/转向案例",
     "ct_sponsor": "Sana Biotechnology", "sec_ticker": "SANA",
     "product_keywords": ["sana", "sc291", "sc262"],
     "ct_keywords": ["sana", "sc291", "sc262", "car-t", "car t", "chimeric antigen"]},

    # ————————————————— 四、已上市大型药企（在位者）—————————————————
    {"name": "Bristol Myers Squibb", "category": "在位者大药企",
     "diversified": True,           # 多元化大集团，网页新闻走关键词过滤
     "ct_sponsor": "Bristol-Myers Squibb", "sec_ticker": "BMY",
     "rss": ["https://news.google.com/rss/search?q=%22Bristol+Myers+Squibb%22+car-t+cell+therapy&hl=en-US&gl=US&ceid=US:en"],
     # 只保留 CAR-T/细胞治疗/血液肿瘤 相关试验（过滤Opdivo/Eliquis/Pomalyst等大量无关管线）
     "ct_keywords": ["breyanzi", "lisocabtagene", "liso-cel", "abecma", "idecabtagene",
                     "ide-cel", "arlo-cel", "car-t", "car t", "chimeric antigen",
                     "lymphoma", "dlbcl", "follicular", "myeloma", "gprc5d",
                     "b-cell", "mantle cell", "leukemia"],
     "product_keywords": ["breyanzi", "liso-cel", "abecma", "ide-cel", "arlo-cel"]},
    {"name": "Johnson & Johnson", "category": "在位者大药企",
     "ct_sponsor": "Janssen Research & Development, LLC", "sec_ticker": "JNJ",
     # 只保留 CAR-T/骨髓瘤/淋巴瘤 相关试验（过滤Janssen数百条实体瘤/免疫/神经管线）
     "ct_keywords": ["carvykti", "cilta-cel", "jnj-4496", "jnj-90014496", "c-car039",
                     "lb2501", "lb1908", "car-t", "car t", "chimeric antigen",
                     "lymphoma", "dlbcl", "myeloma", "b-cell", "bcma", "gprc5d",
                     "claudin", "gastric"],
     "product_keywords": ["carvykti", "cilta-cel", "ciltacabtagene", "c-car039"]},
    {"name": "Legend Biotech", "category": "在位者大药企",
     "ct_sponsor": "Legend Biotech", "sec_ticker": "LEGN",
     "rss": ["https://investors.legendbiotech.com/rss/news-releases.xml"],
     "product_keywords": ["legend", "carvykti", "cilta-cel", "lcar-b38m"],
     "ct_keywords": ["legend", "carvykti", "cilta-cel", "lcar-b38m", "car-t", "car t", "chimeric antigen"]},
    {"name": "Novartis", "category": "在位者大药企",
     "ct_sponsor": "Novartis", "sec_ticker": "NVS",
     # 只保留 CAR-T/血液肿瘤 相关试验（过滤Novartis大量实体瘤/心血管/免疫管线）
     "ct_keywords": ["kymriah", "tisa-cel", "tisagenlecleucel", "t-charge",
                     "ytb323", "car-t", "car t", "chimeric antigen",
                     "lymphoma", "dlbcl", "b-cell"],
     "product_keywords": ["kymriah", "tisa-cel", "tisagenlecleucel", "t-charge"]},

    # ————————————————— 五、Ronde-cel（LBCL）具体竞品 —————————————————
    {"name": "AbbVie / Genmab (epcoritamab)", "category": "Ronde-cel竞品(LBCL)",
     "ct_sponsor": "Genmab", "sec_ticker": "GMAB",
     "rss": ["https://ir.genmab.com/rss/news-releases.xml"],
     # Genmab = epcoritamab 申办方，但 Genmab 也有其他抗体管线（实体瘤等）需过滤
     "ct_keywords": ["epcoritamab", "epkinly", "tepkinly", "car-t", "car t",
                     "lymphoma", "dlbcl", "follicular", "b-cell", "diffuse"],
     "product_keywords": ["epcoritamab", "epkinly", "tepkinly", "genmab"]},
    {"name": "ADC Therapeutics", "category": "Ronde-cel竞品(LBCL)",
     "ct_sponsor": "ADC Therapeutics", "sec_ticker": "ADCT",
     "news_pages": ["https://ir.adctherapeutics.com/news-releases"],
     "product_keywords": ["zynlonta", "loncastuximab", "adct-301", "adct-602"],
     "ct_keywords": ["zynlonta", "loncastuximab", "adct-301", "adct-602", "car-t", "car t", "chimeric antigen"]},
    {"name": "Incyte", "category": "Ronde-cel竞品(LBCL)",
     "ct_sponsor": "Incyte Corporation", "sec_ticker": "INCY",
     # Incyte 管线很广（JAK抑制剂等），只保留 CD19/淋巴瘤 相关
     "ct_keywords": ["monjuvi", "tafasitamab", "car-t", "car t",
                     "lymphoma", "dlbcl", "b-cell", "diffuse"],
     "product_keywords": ["monjuvi", "tafasitamab"]},
    {"name": "Miltenyi Biomedicine (zamto-cel)", "category": "Ronde-cel竞品(LBCL)",
     "tier": "priority",            # CD19/CD20双靶点最成熟竞品，已进入随机对照3期(DALY 2-EU, vs化疗)；ronde-cel最需要跟踪的直接竞争对手
     "ct_sponsor": "Miltenyi Biomedicine",
     "news_pages": ["https://www.miltenyibiomedicine.com/news-events/press-releases"],
     "pubmed": ["zamtocabtagene", "zamto-cel", "MB-CART2019.1"],
     "ct_keywords": ["zamto", "mb-cart", "car-t", "car t", "lymphoma", "dlbcl",
                     "cd19", "cd20", "b-cell"],
     "product_keywords": ["zamto-cel", "zamtocabtagene", "mb-cart2019"]},
    {"name": "CARsgen Therapeutics (科济药业)", "category": "Ronde-cel竞品(LBCL)",
     "tier": "priority",            # satri-cel：同为 CD19/CD20 双靶点 LBCL 直接竞品
     "ct_sponsor": "CARsgen Therapeutics",
     "rss": ["https://news.google.com/rss/search?q=CARsgen+Therapeutics+car-t&hl=en-US&gl=US&ceid=US:en"],
     "pubmed": ["CARsgen satricabtagene", "satri-cel CT041"],
     "ct_keywords": ["satri", "ct041", "ct1190", "carsgen", "car-t", "car t",
                     "lymphoma", "dlbcl", "cd19", "cd20", "cldn18", "gpc3",
                     "claudin", "gastric", "hepatocellular", "b-cell"],
     "product_keywords": ["satri-cel", "ct041", "ct1190", "carsgen"]},

    # ————————————————— 六、LYL273（mCRC）具体竞品 —————————————————
    {"name": "Innovative Cellular Therapeutics (ICT)", "category": "LYL273竞品(mCRC)",
     "tier": "priority",            # GCC19CART：GUCY2C 靶点 mCRC 进度最快的直接竞品
     "ct_sponsor": "Innovative Cellular Therapeutics",
     "news_pages": ["https://www.ictbio.com/news/"],
     "pubmed": ["GCC19CART", "GCC CAR-T colorectal"],
     "ct_keywords": ["gcc19cart", "gcc", "gucy2c", "car-t", "car t",
                     "coupledcar", "colorectal", "mcrc", "crc"],
     "product_keywords": ["gcc19cart", "gcc", "gucy2c", "coupledcar"]},
    {"name": "北京艺妙神州 (Immunochina)", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Beijing Immunochina Medical",
     "news_pages": ["http://www.immunochina.com/en/index.php/home/news/news_1.html"],
     "pubmed": ["IM96 CAR-T colorectal", "GUCY2C CAR-T"],
     "product_keywords": ["im96", "immunochina", "gucy2c"],
     "ct_keywords": ["im96", "immunochina", "gucy2c", "car-t", "car t", "chimeric antigen"]},
    {"name": "Chimeric Therapeutics", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Chimeric Therapeutics",
     "news_pages": ["https://www.chimerictherapeutics.com/investor"],
     "pubmed": ["CHM-2101 CDH17"],
     "product_keywords": ["chm-2101", "cdh17"],
     "ct_keywords": ["chm-2101", "cdh17", "car-t", "car t", "chimeric antigen"]},
    {"name": "Carina Biotech", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Carina Biotech",
     "news_pages": ["https://www.carinabiotech.com/news/"],
     "pubmed": ["CNA3103 LGR5 CAR-T"],
     "product_keywords": ["cna3103", "lgr5"],
     "ct_keywords": ["cna3103", "lgr5", "car-t", "car t", "chimeric antigen"]},
    {"name": "Merck KGaA (M9140)", "category": "LYL273竞品(mCRC)",
     "tier": "priority",            # M9140 CEACAM5 ADC：mCRC 跨模态关键威胁
     "diversified": True,           # 多元化大集团：网页新闻混杂大量无关业务，重点档下仍对网页做关键词过滤（临床/论文精确检索不受影响）
     "ct_sponsor": "Merck KGaA, Darmstadt, Germany",
     "rss": ["https://news.google.com/rss/search?q=%22Merck+KGaA%22+ADC+cancer+colorectal&hl=en-US&gl=US&ceid=US:en"],
     "pubmed": ["precemtabart tocentecan", "M9140 CEACAM5"],
     # 只保留 CEACAM5 ADC / 结直肠癌 相关试验（过滤电子/生命科学等大量无关管线）
     "ct_keywords": ["precemtabart", "m9140", "ceacam5", "tocentecan"],
     "product_keywords": ["precemtabart", "m9140", "ceacam5", "tocentecan"]},
    # （注：不包含 "adc"/"antibody-drug"/"colorectal"/"crc" 等泛用词——
    #  Merck KGaA 有数十条其他 ADC 管线与多条 CRC 药物，广义词会导致大量误命中）
    {"name": "Sanofi", "category": "LYL273竞品(mCRC)",
     "ct_sponsor": "Sanofi", "sec_ticker": "SNY",
     "pubmed": ["tusamitamab CEACAM5"],
     # 只保留 CEACAM5 / mCRC 相关（过滤Sanofi大量胰岛素/疫苗/特药管线）
     "ct_keywords": ["tusamitamab", "ceacam5", "car-t", "car t"],
     "product_keywords": ["tusamitamab", "ceacam5"]},
    {"name": "Pfizer", "category": "LYL273竞品(mCRC) / 10-K列示",
     "ct_sponsor": "Pfizer", "sec_ticker": "PFE",
     "pubmed": ["tusamitamab CEACAM5"],
     # 只保留 CEACAM5 / CAR-T 相关（过滤Pfizer大量心血管/疫苗/特药管线）
     "ct_keywords": ["tusamitamab", "ceacam5", "car-t", "car t"],
     "product_keywords": ["tusamitamab", "ceacam5"]},
    # ————————————————— 七、10-K 列示的其他潜在竞争对手 —————————————————
    {"name": "AstraZeneca (含EsoBiotec)", "category": "10-K潜在竞品",
     "ct_sponsor": "AstraZeneca", "sec_ticker": "AZN",
     "pubmed": ["in vivo CAR-T ENaBL"],
     # 只保留体内CAR-T/EsoBiotec/血液肿瘤 相关（过滤AZ数百条实体瘤/呼吸/心血管管线）
     "ct_keywords": ["enabl", "eso", "in vivo", "car-t", "car t",
                     "chimeric antigen", "lymphoma", "dlbcl",
                     "leukemia", "b-cell", "myeloma"],
     "product_keywords": ["enabl", "esobiotec", "in vivo car-t"]},
    {"name": "Agenus", "category": "10-K潜在竞品",
     "ct_sponsor": "Agenus", "sec_ticker": "AGEN",
     "product_keywords": ["agenus", "balstilimab", "botensilimab"],
     "ct_keywords": ["agenus", "balstilimab", "botensilimab", "car-t", "car t", "chimeric antigen"]},
    {"name": "Akeso（康方生物）", "category": "10-K潜在竞品",
     "ct_sponsor": "Akeso",
     "news_pages": ["https://www.akesobio.com/en/media/akeso-news/"],
     "pubmed": ["Akeso ivonescimab"],
     # 康方主业双抗（PD-1×VEGF等），暂无CAR-T或LBCL/mCRC管线；
     # 设极窄过滤器——仅当未来进入本赛道时才触发
     "ct_keywords": ["car-t", "car t", "chimeric antigen",
                     "lymphoma", "dlbcl", "colorectal", "mcrc"],
     "product_keywords": ["akeso", "ivonescimab", "ak104", "ak112"]},
    {"name": "Summit Therapeutics", "category": "10-K潜在竞品",
     "ct_sponsor": "Summit Therapeutics", "sec_ticker": "SMMT",
     "product_keywords": ["summit", "ivonescimab", "smt112"],
     "ct_keywords": ["summit", "ivonescimab", "smt112", "car-t", "car t", "chimeric antigen"]},
]
