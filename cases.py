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

# 来源:单人初筛工作台 / 专家组协同
SOURCE_SINGLE = "单人初筛"
SOURCE_PANEL = "专家协同"
# 状态流转:协同案例 评审中→已定稿;单人案例直接 已定稿;两者均可 归档 / 作废
STATUSES = ("评审中", "已定稿", "已归档", "作废")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def new_id():
    return secrets.token_hex(4)          # 8 位十六进制,作案例码


def new_pwd():
    return secrets.token_hex(3)          # 6 位口令(经办可改)


def _path(cid):
    return os.path.join(CASES_DIR, f"{cid}.json")


def _store_doc(case, doc_bytes, doc_filename):
    if doc_bytes and doc_filename:
        ext = os.path.splitext(doc_filename)[1] or ".bin"
        stored = case["id"] + ext
        with open(os.path.join(CASES_DIR, stored), "wb") as f:
            f.write(doc_bytes)
        case["doc_file"] = stored


def create_case(name, res, docinfo, n_experts=3, creator="", pwd=None,
                doc_bytes=None, doc_filename="", source=SOURCE_PANEL):
    os.makedirs(CASES_DIR, exist_ok=True)
    cid = new_id()
    case = {
        "id": cid, "name": name or "评估对象", "created": _now(), "creator": creator,
        "source": source,
        "status": "评审中", "expert_pwd": pwd or new_pwd(), "n_experts": int(n_experts),
        "res": res, "docinfo": docinfo,
        "doc_name": doc_filename or "", "doc_file": None,   # 政策原文(供专家查阅下载)
        "reviews": [], "consensus": None,
    }
    _store_doc(case, doc_bytes, doc_filename)
    save_case(case)
    return case


def save_single_case(name, res, docinfo, items, level, opinion, creator="经办",
                     doc_bytes=None, doc_filename="", adopted_ids=None):
    """单人初筛工作台一键存入台账:直接以「已定稿」入库,判定/结论存入 consensus,
    统一供台账重新导出。items: [{"q","answer","note"}, ...10];adopted_ids: 当时采纳的影响路径 id。"""
    os.makedirs(CASES_DIR, exist_ok=True)
    cid = new_id()
    case = {
        "id": cid, "name": name or "评估对象", "created": _now(), "creator": creator,
        "source": SOURCE_SINGLE,
        "status": "已定稿", "expert_pwd": "", "n_experts": 0,
        "res": res, "docinfo": docinfo,
        "adopted_ids": list(adopted_ids) if adopted_ids is not None else None,
        "doc_name": doc_filename or "", "doc_file": None,
        "reviews": [],
        "consensus": {"items": items, "level": level, "opinion": opinion,
                      "by": creator, "ts": _now()},
    }
    _store_doc(case, doc_bytes, doc_filename)
    save_case(case)
    return case


def adopted_pathways(case):
    """台账重新导出时,取该案例当时采纳的影响路径。
    单人案例用 adopted_ids;协同/旧案例回落「非假设待证」默认。"""
    paths = (case.get("res") or {}).get("pathways", [])
    ids = case.get("adopted_ids")
    if ids is not None:
        idset = set(ids)
        return [p for p in paths if p.get("id") in idset]
    return [p for p in paths if p.get("status") != "假设待证"]


def doc_path(case):
    """案例原始政策文档的本地路径;无则 None。"""
    f = (case or {}).get("doc_file")
    p = os.path.join(CASES_DIR, f) if f else None
    return p if (p and os.path.exists(p)) else None


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


def set_status(cid, status):
    """台账状态流转(已定稿/已归档/作废/恢复)。恢复时:协同未定稿→评审中,否则→已定稿。"""
    case = load_case(cid)
    if not case:
        return None
    if status == "恢复":
        if case.get("source") == SOURCE_PANEL and not case.get("consensus"):
            status = "评审中"
        else:
            status = "已定稿"
    if status in STATUSES:
        case["status"] = status
        save_case(case)
    return case


def set_reference(cid, val):
    """把案例发布为「参考案例」(范例)或取消。供案例参考页只读展示。"""
    case = load_case(cid)
    if not case:
        return None
    case["reference"] = bool(val)
    save_case(case)
    return case


def list_reference():
    """已发布为参考案例的项目(按时间倒序)。"""
    return [c for c in list_cases() if c.get("reference")]


def delete_case(cid):
    """彻底删除一个案例(json + 政策原文文件)。返回是否删除成功。"""
    case = load_case(cid)
    if not case:
        return False
    df = case.get("doc_file")
    if df:
        dp = os.path.join(CASES_DIR, df)
        if os.path.exists(dp):
            try:
                os.remove(dp)
            except OSError:
                pass
    p = _path(cid)
    if os.path.exists(p):
        os.remove(p)
    return True


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
