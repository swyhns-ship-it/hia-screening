# -*- coding: utf-8 -*-
"""首段蒸馏 · 构建【验证后】模板库:join 引擎候选(out_harvest)与 Claude 审计(crosscheck),
只保留 keep + fix(应用修正)+ missing(补回)的路径 → 按 (主枢纽,题,方向) 聚类成模板。
对比 cluster_templates 的【未验证】候选,虚配(如 DIET·Q2 农村公路链)应被剪掉。

产物:eval/templates_validated.json + 控制台 top 模板。
"""
import collections
import glob
import io
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
HARVEST = os.path.join(ROOT, "eval", "out_harvest")
CROSS = os.path.join(ROOT, "eval", "crosscheck")
OUT = os.path.join(ROOT, "eval", "templates_validated.json")


def validated_pathways(name):
    """返回该政策经 Claude 验证后的路径列表 [{chain,outcome_q,direction,strength,src}]。"""
    hf = os.path.join(HARVEST, name + ".json")
    cf = os.path.join(CROSS, name + ".json")
    if not (os.path.exists(hf) and os.path.exists(cf)):
        return []
    try:
        hd = json.load(open(hf, encoding="utf-8"))
        cd = json.load(open(cf, encoding="utf-8"))
    except Exception:
        return []
    orig = {p.get("id"): p for p in hd.get("res", {}).get("pathways", [])}
    aud = cd.get("audit", {}) or {}
    verds = {v.get("id"): v for v in (aud.get("pathways") or [])}
    out = []
    for pid, p in orig.items():
        v = verds.get(pid)
        if not v:
            continue
        j = v.get("judgment")
        if j == "keep":
            out.append({"chain": p.get("chain", []), "outcome_q": p.get("outcome_q"),
                        "direction": p.get("direction", ""), "strength": p.get("strength", ""),
                        "src": "keep"})
        elif j == "fix":
            fx = v.get("fix") or {}
            out.append({"chain": fx.get("chain") or p.get("chain", []),
                        "outcome_q": fx.get("outcome_q") or p.get("outcome_q"),
                        "direction": fx.get("direction") or p.get("direction", ""),
                        "strength": fx.get("strength") or p.get("strength", ""),
                        "src": "fix"})
        # drop → 丢弃
    for m in (aud.get("missing") or []):        # 补回 Claude 发现的漏报
        out.append({"chain": m.get("chain", []), "outcome_q": m.get("outcome_q"),
                    "direction": m.get("direction", ""), "strength": "中", "src": "missing"})
    return out


def main():
    names = [os.path.splitext(os.path.basename(f))[0]
             for f in glob.glob(os.path.join(CROSS, "*.json"))
             if not os.path.basename(f).startswith("_")]
    clusters = collections.defaultdict(lambda: {"policies": set(), "depts": set(),
                                                "actions": [], "chains": [], "src": collections.Counter()})
    n_val = n_gated = 0
    for name in names:
        dept = name.split("_")[0]
        for p in validated_pathways(name):
            chain, q = p["chain"], p["outcome_q"]
            if not chain or not q:
                continue
            n_val += 1
            hub = primary_hub(chain, q)
            if not hub:
                n_gated += 1
                continue
            key = (hub, q, p["direction"])
            c = clusters[key]
            c["policies"].add(name)
            c["depts"].add(dept)
            c["actions"].append(chain[0])
            c["chains"].append(" → ".join(chain))
            c["src"][p["src"]] += 1
    out = []
    for (hub, q, direction), c in clusters.items():
        af = collections.Counter(c["actions"])
        out.append({
            "template_id": "T_%s_Q%s_%s" % (hub, q, "B" if direction == "效益" else "R"),
            "hub": hub, "hub_name": D.hub(hub)["name"] if D.hub(hub) else hub,
            "outcome_q": q, "direction": direction,
            "n_policies": len(c["policies"]), "n_depts": len(c["depts"]),
            "src": dict(c["src"]),
            "action_examples": [a for a, _ in af.most_common(6)],
            "chain_examples": c["chains"][:3],
        })
    out.sort(key=lambda x: (-x["n_policies"], -x["n_depts"]))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("验证后路径 %d(%d 条未落触发枢纽丢弃)→ 验证模板 %d 个 → %s\n"
          % (n_val, n_gated, len(out), OUT))
    print("=== 验证后 Top 25 模板(按命中政策数)===")
    print("%-24s %3s %3s  %s" % ("模板", "策", "部", "措施样本"))
    for t in out[:25]:
        print("%-24s %3d %3d  %s" % (
            "%s·Q%d·%s" % (t["hub"], t["outcome_q"], t["direction"]),
            t["n_policies"], t["n_depts"], "/".join(t["action_examples"][:3])[:44]))


if __name__ == "__main__":
    main()
