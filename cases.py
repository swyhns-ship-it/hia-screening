# -*- coding: utf-8 -*-
"""专家组协同初筛 · 案例存储引擎(文件级,无数据库)。

一个评估对象 = 一个案例(cases/<id>.json),含 AI 初筛草案 + 各专家独立评审 + 组长定稿。
经办创建案例 → 生成"案例码 + 口令"分发给专家 → 专家凭链接/口令独立评 → 汇总共识 → 组长定稿导出。

被 app_nicegui.py 的 /panel、/review/<id> 页面调用。
注:云端文件系统通常临时,长期留存需接外部存储或定期备份 cases/。
"""
import json
import os
import secrets
from collections import Counter
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(ROOT, "cases")
ANSWERS = ("是", "不知道", "否")
ANSWER_LABEL = {"是": "需要关注", "不知道": "尚不确定", "否": "暂未发现"}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def new_id():
    return secrets.token_hex(4)          # 8 位十六进制,作案例码


def new_pwd():
    return secrets.token_hex(3)          # 6 位口令(经办可改)


def _path(cid):
    return os.path.join(CASES_DIR, f"{cid}.json")


def create_case(name, res, docinfo, n_experts=3, creator="", pwd=None):
    os.makedirs(CASES_DIR, exist_ok=True)
    cid = new_id()
    case = {
        "id": cid, "name": name or "评估对象", "created": _now(), "creator": creator,
        "status": "评审中", "expert_pwd": pwd or new_pwd(), "n_experts": int(n_experts),
        "res": res, "docinfo": docinfo,
        "reviews": [], "consensus": None,
    }
    save_case(case)
    return case


def save_case(case):
    os.makedirs(CASES_DIR, exist_ok=True)
    with open(_path(case["id"]), "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)


def load_case(cid):
    p = _path(cid)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_cases():
    if not os.path.isdir(CASES_DIR):
        return []
    out = []
    for fn in os.listdir(CASES_DIR):
        if fn.endswith(".json"):
            c = load_case(fn[:-5])
            if c:
                out.append(c)
    out.sort(key=lambda c: c.get("created", ""), reverse=True)
    return out


def add_review(cid, review):
    """追加/更新一位专家的评审。review: {expert, answers{str(q):ans}, notes{str(q):note},
    level, opinion}。同名专家重复提交则覆盖其上一次。"""
    case = load_case(cid)
    if not case:
        return None
    review = {"ts": _now(), **review}
    name = (review.get("expert") or "").strip()
    case["reviews"] = [r for r in case["reviews"]
                       if (r.get("expert") or "").strip() != name or not name]
    case["reviews"].append(review)
    save_case(case)
    return case


def finalize(cid, items, level, opinion, by=""):
    case = load_case(cid)
    if not case:
        return None
    case["consensus"] = {"items": items, "level": level, "opinion": opinion,
                         "by": by, "ts": _now()}
    case["status"] = "已定稿"
    save_case(case)
    return case


def consensus_view(case):
    """逐题汇总各专家判定:分布计数、多数意见、是否分歧。返回 {q: {...}}。"""
    reviews = case.get("reviews", [])
    out = {}
    for q in range(1, 11):
        votes = [r.get("answers", {}).get(str(q)) for r in reviews]
        votes = [v for v in votes if v in ANSWERS]
        cnt = Counter(votes)
        majority = cnt.most_common(1)[0][0] if cnt else None
        out[q] = {"counts": dict(cnt), "n": len(votes),
                  "majority": majority, "divergent": len(cnt) > 1}
    return out


if __name__ == "__main__":
    cs = list_cases()
    print(f"案例数:{len(cs)}")
    for c in cs:
        print(f"  {c['id']} {c['name']} [{c['status']}] 专家提交 {len(c['reviews'])}/{c['n_experts']}")
