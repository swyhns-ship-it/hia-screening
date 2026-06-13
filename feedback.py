# -*- coding: utf-8 -*-
"""专家反馈引擎 —— 记录/读取/汇总专家对 AI 路径与证据匹配的复核反馈。

定位:形成"专家在用 → 标出问题 → 回流改进知识库/提示词"的闭环,每条反馈留痕可审计。
存储:追加写 feedback/feedback_log.jsonl(每行一条 JSON)。文件级、无数据库依赖。
注:云端(如 Streamlit/容器)文件系统通常临时,长期留存需接外部存储或定期导出。

被 views/app 调用:record_many(entries) / load() / summarize()。
"""
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
FB_DIR = os.path.join(ROOT, "feedback")
FB_LOG = os.path.join(FB_DIR, "feedback_log.jsonl")

# 专家可标记的问题类型(与界面下拉一致)
FLAGS = ["机制不成立", "与文档不符", "来源错配", "强度不当", "缺权威来源", "其他"]


def record_many(entries):
    """批量追加反馈条目(list[dict])。自动补 ts 时间戳。返回写入条数。"""
    if not entries:
        return 0
    os.makedirs(FB_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n = 0
    with open(FB_LOG, "a", encoding="utf-8") as f:
        for e in entries:
            if not isinstance(e, dict):
                continue
            e = {"ts": ts, **e}
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            n += 1
    return n


def load():
    """读取全部反馈条目(list[dict]);无文件返回 []。"""
    if not os.path.exists(FB_LOG):
        return []
    out = []
    with open(FB_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def summarize(entries=None):
    """汇总反馈,供回流改进:按问题类型计数、被标错配最多的来源、被否决最多的路径机制。"""
    rows = entries if entries is not None else load()
    by_flag, by_card, rejected = {}, {}, []
    n_total = len(rows)
    n_with_flag = 0
    for r in rows:
        flag = (r.get("flag") or "").strip()
        if flag:
            n_with_flag += 1
            by_flag[flag] = by_flag.get(flag, 0) + 1
        # 被标"来源错配"的来源,累计(供修 keys/同义词/停用词)
        if flag == "来源错配":
            for s in (r.get("cards") or []):
                key = s.split(". http")[0]
                by_card[key] = by_card.get(key, 0) + 1
        # 被专家排除(adopted=False)或标"机制不成立/与文档不符"的路径
        if r.get("adopted") is False or flag in ("机制不成立", "与文档不符"):
            rejected.append({"q": r.get("outcome_q"), "chain": r.get("chain"),
                             "flag": flag, "note": r.get("note", "")})
    return {
        "total": n_total, "with_flag": n_with_flag,
        "by_flag": dict(sorted(by_flag.items(), key=lambda x: -x[1])),
        "mismatched_cards": dict(sorted(by_card.items(), key=lambda x: -x[1])),
        "rejected": rejected,
    }


if __name__ == "__main__":
    s = summarize()
    print(f"反馈条目:{s['total']},含标记:{s['with_flag']}")
    print("按问题类型:", s["by_flag"])
    print("被标错配最多的来源:", s["mismatched_cards"])
    print(f"被否决/质疑路径:{len(s['rejected'])} 条")
