# Lyell 及下一代 CAR-T 竞品动态监控

对报告中所有公司做长期自动监控：抓取多个可靠信息源 → 计算“上次运行以来的新增” → 更新一个可分享的静态看板 →（可选）在有新消息时发送邮件摘要。

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
python run.py                       # 抓取一次（首次运行=建立基线，不发邮件）
python run.py --site-url https://你的看板地址   # 邮件中附看板链接
python run.py --no-email            # 只更新站点，不发邮件
python run.py --only LYEL           # 只跑某家（调试）
```

首次运行会把当前所有条目记为“基线”（不推送），之后每次只推送**新出现**的内容。

## 定时执行

**方式 A：本机 cron（每天 9:00）**
```cron
0 9 * * * cd /Users/judy/Desktop/lyell/lyell_monitor && /usr/bin/python3 run.py >> data/cron.log 2>&1
```

**方式 B：GitHub Actions + Pages（推荐，免服务器、云端常驻、公开可分享）**

工作流已内置：`.github/workflows/monitor.yml`（每天北京时间 09:00 自动跑，也可手动触发）。它会：抓取 → 生成看板 → 把 `data/` 状态快照提交回仓库（保留“已见”基线）→ 部署到 GitHub Pages。

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
