# Lyell 及下一代 CAR-T 竞品动态监控

对报告中所有公司做长期自动监控：抓取多个可靠信息源 → 计算“上次运行以来的新增” → **里程碑过滤（只留新临床数据/上市前进展/重大事件）** → 更新一个可分享的静态看板 →（可选）在有新消息时发送邮件摘要。

**在线看板（每天在此查看）**：https://tangjingjudy-dotcom.github.io/Lyell_competitors_monitor/
**更新频率**：每天北京时间约 09:00 由 GitHub Actions 自动运行并部署，无需手动操作。

## 只保留“关键里程碑”（里程碑过滤器）

为避免刷屏，抓到的新增条目会先经过 `config.py` 中 `SETTINGS["milestone_filter"]` 过滤，只保留真正重要的进展：

- **ClinicalTrials.gov**：试验状态/分期变化本身即高信号 → 全部保留（如 招募中→已完成、1期→2期、新登记试验）。
- **SEC EDGAR**：只保留“重大事件/年报”类表单（8-K / 6-K / 20-F / 10-K 等），丢弃 Form 4（高管持股）、季报、S-8 等例行文件。
- **PubMed / 新闻 / RSS**：标题命中里程碑关键词（phase、ORR/CR/PFS、topline、FDA/EMA/NMPA、BLA/IND/MAA、approval、获批、认定、收购、授权……）才保留。

关键词与表单清单均可在 `config.py` 中增删、放宽或收紧。

## 如何判断“真的没有新进展” vs. “爬虫坏了”

如果一两周看板都没有新增，别只靠“猜”，有三层由弱到强的检查方式：

1. **看板顶部的“系统运行状态”条**（最方便，日常只看这个就够）。每次运行都会写一条健康记录，看板顶部会显示：

   - ✅ **系统运行正常**（绿色）：说明当天成功跑完，只是各信息源确实没有命中里程碑关键词——大概率是真的没有新进展。
   - ⚠️ **上次运行存在信息源故障**（橙色）：说明某个数据源（如 SEC/PubMed/官网）本轮请求失败，"0 条新增"可能是假的，需要留意（不过只要不是连续多天同一个源报错，通常是对方网站临时抽风，下次会自动恢复，无需处理）。
   - ⚠️ **距上次运行已超过 36 小时**：说明 GitHub Actions 可能没有按时触发，需要去 Actions 页检查。

   点开条目下方“查看最近 N 次运行趋势”，能看到每次运行“扫描了几家公司 / 抓到多少原始信息 / 过滤掉多少噪音 / 保留多少新增 / 故障次数”。如果“抓取原始信息”这一列突然从平时的几十条掉到 0，即使“新增里程碑”是 0，也大概率是爬虫出了问题而不是行业没进展。

2. **GitHub 仓库 Actions 页**（`Actions` 标签）：每天应有一条新的运行记录，绿色勾表示成功。如果连续出现红色叉，说明代码报错崩了（点进去能看具体报错），而不是"没有新闻"。

3. **仓库里的 `data/run_log.json`**：如果想用代码/脚本自动巡检（而不是人工每天看网页），可以直接读这个文件的最后一条记录做校验，字段含义：`timestamp`(运行时间)、`companies`(扫描公司数)、`sources.<源>.error`(该源故障次数)、`sources.<源>.raw`(该源本轮抓到的原始条数)。

> 简单经验规则：**"新增里程碑=0" 是正常现象，但 "原始抓取条数=0" 或 "故障次数>0" 才是要警惕的信号**——前者说明系统在正常工作但行业确实平静，后者说明系统本身可能出了问题。

## 架构

```
run.py                  主运行器（抓取 → 差异 → 站点 → 邮件）
config.py               公司清单 + 各公司信息源钩子 + 全局设置
monitor/
  base.py               数据模型 / HTTP / JSON存储 / 差异引擎
  sources/
    clinicaltrials.py   ClinicalTrials.gov v2 API（按申办方）
    sec_edgar.py        SEC EDGAR submissions API（ticker→CIK）
    pubmed.py           PubMed E-utilities（按关键词）
    webwatch.py         通用 RSS / 新闻页链接差异检测
  deliver/
    site.py             生成单文件静态看板 index.html
    email_digest.py     SMTP 邮件摘要（仅在有新增且未超发送频率时）
data/                   状态与输出（首次运行后自动生成）
  state/                每个信息源的“已见 uid”
  items.json            全量条目库（站点数据源）
  run_log.json           最近30次运行的健康记录（供“系统运行状态”面板使用）
  site/index.html       生成的看板（可托管分享）
```

**核心设计：抓取与交付解耦。** 抓取只产出「全量条目库 + 本轮新增」；看板和邮件都只是它的消费者。所以“网站”和“邮件”可以同时拥有，互不影响。

## 交付方式对比（回答“邮件还是网站”）

| | 网站（推荐主用） | 邮件（可选叠加） |
|---|---|---|
| 分享 | 一个链接分享给任意多人 | 仅收件人列表 |
| 触发 | 每次抓取自动刷新，随时打开查看 | 仅在**有新增时**触发，可设最小间隔防打扰 |
| 适用 | 团队共享、随时回看全量 | 你/少数人要“被推送提醒” |

建议：**网站为主**（托管到 GitHub Pages / Netlify / S3，永远最新、可分享），**邮件为辅**（`config.py` 里 `email.enabled=True` 打开，`min_hours_between_emails` 控制频率，0 表示有新消息即发）。

## 安装

```bash
cd lyell_monitor
pip install -r requirements.txt
```

## 配置

编辑 `config.py`：
1. `SETTINGS["user_agent"]`：改成带你邮箱的字符串（SEC 要求）。
2. 邮件：`SETTINGS["email"]` 里填 SMTP 账号、收件人、发送间隔（默认关闭）。
3. 公司源钩子：已按报告预填；可增删 `rss` / `news_pages` / `pubmed` 等。

## 运行

```bash
python run.py                       # 抓取一次（首次运行=静默建立基线，不发邮件）
python run.py --site-url https://你的看板地址   # 邮件中附看板链接
python run.py --no-email            # 只更新站点，不发邮件
python run.py --only LYEL           # 只跑某家（调试）
```

**首次“静默建立基线”**：第一次运行会把当前已存在的全部存量条目一次性记为“已见”但**不显示**在看板上，避免上百条历史信息刷屏。此后看板**只累积新出现的里程碑**（顶部以 NEW 标记、并统计近 14 天新增）。因此看板刚上线时可能接近空白属正常现象，会随竞品发布新动态逐日累积。

> 若要重置基线（例如清掉旧的未过滤快照，重新建立干净基线）：删除仓库中的 `data/` 目录后再运行一次即可。

## 定时执行

**方式 A：本机 cron（每天 9:00）**
```cron
0 9 * * * cd /Users/judy/Desktop/lyell/lyell_monitor && /usr/bin/python3 run.py >> data/cron.log 2>&1
```

**方式 B：GitHub Actions + Pages（推荐，免服务器、云端常驻、公开可分享）**

工作流已内置：`.github/workflows/monitor.yml`（每天北京时间约 09:00 自动跑，也可手动触发）。它会：抓取 → 里程碑过滤 → 生成看板 → 把 `data/` 状态快照提交回仓库（保留“已见”基线）→ 部署到 GitHub Pages。**日常无需手动点击 Run workflow**，仅在想立刻刷新时才用。

> ⚠️ **务必把 `lyell_monitor/` 作为独立仓库单独推送，不要把上级目录 `/Desktop/lyell` 整个传上去** —— 那里有竞品分析报告的 docx/pptx，公开仓库会导致机密外泄。本目录只含爬虫代码与公开新闻链接，可安全公开。

一次性设置步骤：
```bash
cd lyell_monitor
git init && git add . && git commit -m "init competitor monitor"
# 在 GitHub 新建一个仓库后：
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```
然后在仓库 **Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**；首次可在 **Actions** 页点 “Run workflow” 手动跑一次。看板地址即：`https://<你的用户名>.github.io/<仓库名>/`

> 如果日后要开邮件推送，把账号密码放 **仓库 Settings → Secrets**（不要写进 `config.py`），再改工作流去掉 `--no-email`。

## 信息源可靠性说明

- **最稳（结构化 API）**：ClinicalTrials.gov、SEC EDGAR、PubMed —— 直接解析官方 JSON。
- **较稳（RSS）**：有订阅源的公司优先在 `rss` 里配。
- **尽力而为（HTML 抓取）**：`news_pages` 走“页面链接集合差异”，页面改版可能需微调；私有公司（ICT、艺妙神州、A2 Bio 等）通常只能靠这个 + ClinicalTrials.gov。
- 港股（CARsgen/Akeso）建议辅以 HKEXnews、澳股（Chimeric）辅以 ASX 公告页（可加入 `news_pages`）。
```
