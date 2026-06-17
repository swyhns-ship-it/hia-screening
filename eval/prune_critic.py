# -*- coding: utf-8 -*-
"""② 改向 · 确定性剪枝 critic(纯规则,零 API,可复现)。
信号:CSDH 门控 / 枢纽-题号一致性 / 模板支持度(该 (hub,题,方向) 被多少政策验证过) /
链长 / 强度 / 同 (hub,题,方向) 去重。

评测:拿已付费的 Claude 判例(cc_exp_base)当答案,离线算剪枝 critic 的:
  - 剪枝后精确率(留下的里 Claude 认 keep/fix 的占比)= 新引擎精确率
  - 召回(Claude 认 keep/fix 的里被留下的占比)
全程零新 API 调用。扫几组阈值看权衡。
"""
import collections
import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import determinants as D                       # noqa: E402
from cluster_templates import primary_hub      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "eval", "templates_validated.json")
OUT_BASE = os.path.join(ROOT, "eval", "out_exp_base")     # base 引擎候选
CC_BASE = os.path.join(ROOT, "eval", "cc_exp_base")       # Claude 判例(答案)

# 模板支持度:(hub, q, direction) → 被多少政策验证过(文件缺失时为空,不影响导入)
_SUPPORT = {}
try:
    for t in json.load(open(TEMPLATES, encoding="utf-8")):
        _SUPPORT[(t["hub"], t["outcome_q"], t["direction"])] = t["n_policies"]
except (FileNotFoundError, ValueError):
    pass


def critic_keep(pathways, params):
    """对一份政策的路径列表判 keep,返回 set(保留的 index)。
    数据驱动:最强信号是 strength=推测(91%该删)与长链(>=5,62%该删)。"""
    LONG = params.get("long_chain", 5)
    drop_spec = params.get("drop_spec", True)       # 删 strength=推测
    drop_long = params.get("drop_long", True)       # 删长链(强度非强)
    drop_bad_outcome = params.get("drop_bad_outcome", False)  # 删题号越界(已修 bug)
    keep = set()
    for i, p in enumerate(pathways):
        chain, q = p.get("chain", []), p.get("outcome_q")
        if not chain or not q:
            continue
        strength = p.get("strength", "")
        if drop_spec and strength == "推测":
            continue
        if drop_long and len(chain) >= LONG and strength != "强":
            continue
        if drop_bad_outcome:
            hub = primary_hub(chain, q)
            if hub and f"Q{q}" not in D.outcomes_of(hub):   # 修:Q前缀比较
                continue
        keep.add(i)
    return keep


def evaluate(params):
    tp = fp = fn = 0          # tp=critic留且Claude keep; fp=critic留但Claude drop; fn=critic删但Claude keep
    base_real = base_total = 0
    docs = 0
    for cf in glob.glob(os.path.join(CC_BASE, "*.json")):
        if os.path.basename(cf).startswith("_"):
            continue
        name = os.path.basename(cf)
        hf = os.path.join(OUT_BASE, name)
        if not os.path.exists(hf):
            continue
        try:
            cd = json.load(open(cf, encoding="utf-8"))
            hd = json.load(open(hf, encoding="utf-8"))
        except Exception:
            continue
        if cd.get("error") or hd.get("error"):
            continue
        paths = hd.get("res", {}).get("pathways", [])
        verds = {v.get("id"): v.get("judgment")
                 for v in (cd.get("audit", {}).get("pathways") or [])}
        # Claude 真值:keep/fix=应留,drop=应删;无判定的跳过
        idx_truth = {}
        for j, p in enumerate(paths):
            jd = verds.get(p.get("id"))
            if jd in ("keep", "fix"):
                idx_truth[j] = True
            elif jd == "drop":
                idx_truth[j] = False
        if not idx_truth:
            continue
        docs += 1
        kept = critic_keep(paths, params)
        for j, real in idx_truth.items():
            base_total += 1
            if real:
                base_real += 1
            in_kept = j in kept
            if in_kept and real:
                tp += 1
            elif in_kept and not real:
                fp += 1
            elif (not in_kept) and real:
                fn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0       # 剪枝后精确率
    rec = tp / (tp + fn) if (tp + fn) else 0.0        # 真路径保留率
    base_prec = base_real / base_total if base_total else 0.0
    return {"docs": docs, "base_prec": base_prec, "prune_prec": prec, "recall": rec,
            "kept": tp + fp, "dropped_real": fn}


def main():
    print("基线(不剪)精确率 = Claude 认 keep/fix 占全部候选的比例\n")
    variants = [
        ("仅删推测", {"drop_spec": True, "drop_long": False}),
        ("仅删长链>=5(非强)", {"drop_spec": False, "drop_long": True, "long_chain": 5}),
        ("删推测+长链>=5", {"drop_spec": True, "drop_long": True, "long_chain": 5}),
        ("删推测+长链>=5+题号越界", {"drop_spec": True, "drop_long": True, "long_chain": 5,
                                "drop_bad_outcome": True}),
        ("删推测+长链>=6", {"drop_spec": True, "drop_long": True, "long_chain": 6}),
    ]
    print("%-26s %9s %7s %8s" % ("规则", "剪后精确率", "召回", "(基线)"))
    for name, params in variants:
        r = evaluate(params)
        print("%-26s   %.3f    %.3f   (%.3f)"
              % (name, r["prune_prec"], r["recall"], r["base_prec"]))
    print("\n注:精确率↑、召回别掉太多 = 剪枝有效。docs=%d,候选总=%d" % (r["docs"], r["kept"] + r["dropped_real"]))


if __name__ == "__main__":
    main()
