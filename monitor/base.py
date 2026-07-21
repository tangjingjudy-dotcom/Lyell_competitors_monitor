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
