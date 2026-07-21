# -*- coding: utf-8 -*-
"""核心：数据模型、HTTP 请求、JSON 存储与状态差异引擎。"""
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
STATE_DIR = os.path.join(DATA_DIR, "state")
ITEMS_DB = os.path.join(DATA_DIR, "items.json")
META_FILE = os.path.join(DATA_DIR, "meta.json")
RUN_LOG = os.path.join(DATA_DIR, "run_log.json")
RUN_LOG_KEEP = 30  # 保留最近 N 次运行记录，供“系统健康检查”使用


@dataclass
class Item:
    """一条被监控到的信息（临床试验/申报/新闻/论文）。"""
    company: str
    category: str
    source: str            # clinicaltrials | sec | pubmed | web
    title: str
    url: str
    date: str = ""         # ISO 日期字符串（尽量填）
    detail: str = ""       # 补充说明（状态、表单类型等）
    uid: str = field(default="")

    def __post_init__(self):
        if not self.uid:
            raw = f"{self.source}|{self.company}|{self.url}|{self.title}"
            self.uid = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self):
        return asdict(self)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs():
    for d in (DATA_DIR, STATE_DIR):
        os.makedirs(d, exist_ok=True)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, obj):
    _ensure_dirs()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Http:
    """带 User-Agent、超时与礼貌间隔的简单 HTTP 客户端。"""

    def __init__(self, user_agent, timeout=25, delay=0.8):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.timeout = timeout
        self.delay = delay

    def get(self, url, headers=None, params=None):
        time.sleep(self.delay)
        r = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r

    def get_json(self, url, headers=None, params=None):
        return self.get(url, headers=headers, params=params).json()


class StateStore:
    """按 source_id 记录已见过的 uid，用于计算“本次新增”。"""

    def __init__(self):
        _ensure_dirs()

    def _path(self, source_id):
        safe = source_id.replace("/", "_").replace(":", "_")
        return os.path.join(STATE_DIR, f"{safe}.json")

    def seen_uids(self, source_id):
        return set(load_json(self._path(source_id), []))

    def update_seen(self, source_id, uids):
        merged = self.seen_uids(source_id) | set(uids)
        save_json(self._path(source_id), sorted(merged))


def diff_new(store, source_id, items):
    """返回该 source 相对上次运行的新增 Item 列表，并更新状态。"""
    seen = store.seen_uids(source_id)
    new_items = [it for it in items if it.uid not in seen]
    store.update_seen(source_id, [it.uid for it in items])
    return new_items


def is_milestone(item, cfg):
    """判断一条 Item 是否属于“关键里程碑”（新临床数据/上市前进展/重大公司事件）。

    规则（可在 config.py 的 SETTINGS['milestone_filter'] 调整）：
      - clinicaltrials : 试验状态/分期变化本身即高信号，默认整体保留
      - sec            : 仅保留“重大事件/年报”类表单（8-K/6-K/20-F/10-K 等）
      - pubmed/web     : 标题或补充说明命中里程碑关键词才保留
    """
    if not cfg or not cfg.get("enabled", True):
        return True

    if item.source == "clinicaltrials":
        return cfg.get("always_keep_clinicaltrials", True)

    if item.source == "sec":
        forms = cfg.get("meaningful_sec_forms") or []
        blob = f"{item.detail} {item.title}"
        return any(f.lower() in blob.lower() for f in forms)

    # pubmed / web / rss → 关键词匹配
    text = f"{item.title} {item.detail}".lower()
    return any(kw.lower() in text for kw in (cfg.get("keywords") or []))


class RunStats:
    """记录本次运行中每类信息源的“成功/失败次数”与“原始抓取条数”。

    目的：区分“真的没有新进展”与“爬虫本身出故障”——
    例如某源本轮 error 次数骤增、或 raw 条数骤降为 0，即为故障信号，
    即便本次“新增里程碑”仍是 0 也不代表系统正常。
    """

    def __init__(self):
        self.sources = {}

    def record(self, name, ok, count=0):
        s = self.sources.setdefault(name, {"ok": 0, "error": 0, "raw": 0})
        if ok:
            s["ok"] += 1
            s["raw"] += count
        else:
            s["error"] += 1

    def summary(self):
        return self.sources


def append_run_log(entry, keep=RUN_LOG_KEEP):
    """把一次运行的健康摘要追加进滚动日志（供站点渲染“系统运行状态”）。"""
    log = load_json(RUN_LOG, [])
    log.append(entry)
    log = log[-keep:]
    save_json(RUN_LOG, log)
    return log


def merge_into_items_db(new_items):
    """把新增条目并入全量条目库（供站点渲染），带首次发现时间。"""
    db = load_json(ITEMS_DB, [])
    known = {row["uid"] for row in db}
    stamp = now_iso()
    for it in new_items:
        if it.uid in known:
            continue
        row = it.to_dict()
        row["first_seen"] = stamp
        db.append(row)
        known.add(it.uid)
    save_json(ITEMS_DB, db)
    return db
