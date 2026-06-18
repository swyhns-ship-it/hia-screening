# -*- coding: utf-8 -*-
"""首段蒸馏 · 聚类器:读引擎候选路径(run_eval 产物)→ 映射决定因素枢纽 + 过 CSDH 门控
→ 按 (主枢纽, 结果题, 方向) 聚类出【涌现的因果模板】。

这是把"措施(无限)→ 枢纽(有限)"坍缩成有限格子的一步:措施虽千变万化,一旦投影到
(哪个枢纽 + 哪个结果),就落进有限的格子;格子内复现的措施措辞 = 模板的触发样本。

输入:EVAL_OUT 指向的引擎输出目录(默认 eval/out_harvest)。
产物:
  eval/templates_candidates.json  候选模板(未经 Claude 审计;后续 cross_check 验证)
  控制台:按覆盖度(命中政策数)排序的 top 模板
注:此版为【未验证】候选——它只统计 DeepSeek 怎么连;Claude 审计(cross_check)再validate/纠正。
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import determinants as D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR = os.path.join(ROOT, os.environ.get("EVAL_OUT", os.path.join("eval", "out_harvest")))
OUT = os.path.join(ROOT, "eval", "templates_candidates.json")


def primary_hub(chain, outcome_q):
    """该路径的'目的地'触发型枢纽:在链中出现、且其 outcomes 含本题号的触发枢纽,取最靠后者;
    退而求其次取最后一个触发枢纽。返回 hub_id 或 None(未落到触发枢纽=被 CSDH 门控挡)。"""
    trig = [(i, h) for i, node in enumerate(chain)
            for h in [D.resolve(node)] if h and D.is_triggering(h)]
    if not trig:
        return None
    qs = "Q%s" % outcome_q
    matched = [(i, h) for i, h in trig if qs in D.outcomes_of(h)]
    pool = matched or trig
    return pool[-1][1]          # 取链中最靠后的(最接近健康结果端的决定因素)


def main():
    files = [f for f in glob.glob(os.path.join(IN_DIR, "*.json"))
             if not os.path.basename(f).startswith("_")]
    if not files:
        sys.exit("没找到引擎输出 @ " + IN_DIR + "(先跑 run_eval,EVAL_OUT 指此目录)")
    clusters = collections.defaultdict(lambda: {"instances": [], "policies": set(),
                                                "depts": set(), "actions": [], "chains": [],
                                                "mitigations": collections.Counter(), "measures": []})
    n_path = n_gated = 0
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if d.get("error"):
            continue
        name = os.path.splitext(os.path.basename(f))[0]
        dept = name.split("_")[0]
        for p in d.get("res", {}).get("pathways", []):
            chain = p.get("chain") or []
            q = p.get("outcome_q")
            if not chain or not q:
                continue
            n_path += 1
            hub = primary_hub(chain, q)
            if not hub:                        # CSDH 门控:没落到触发型枢纽 → 丢
                n_gated += 1
                continue
            direction = p.get("direction", "")
            key = (hub, q, direction)
            c = clusters[key]
            c["instances"].append(name)
            c["policies"].add(name)
            c["depts"].add(dept)
            c["actions"].append(chain[0])
            c["chains"].append(" → ".join(chain))
            mit = (p.get("mitigation") or "").strip()
            if mit:
                c["mitigations"][mit] += 1
            mea = (p.get("measures") or "").strip()
            if mea:
                c["measures"].append(mea)

    # 整理成候选模板,按覆盖政策数排序
    out = []
    for (hub, q, direction), c in clusters.items():
        action_freq = collections.Counter(c["actions"])
        measure_freq = collections.Counter(c["measures"])
        out.append({
            "template_id": "T_%s_Q%s_%s" % (hub, q, "B" if direction == "效益" else "R"),
            "hub": hub, "hub_name": D.hub(hub)["name"] if D.hub(hub) else hub,
            "outcome_q": q, "direction": direction,
            "n_instances": len(c["instances"]), "n_policies": len(c["policies"]),
            "n_depts": len(c["depts"]),
            "mitigation_dist": dict(c["mitigations"]),
            "measure_examples": [m for m, _ in measure_freq.most_common(5)],
            "action_examples": [a for a, _ in action_freq.most_common(6)],
            "chain_examples": c["chains"][:3],
        })
    out.sort(key=lambda x: (-x["n_policies"], -x["n_instances"]))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("引擎输出 %d 份 | 路径 %d(其中 %d 条未落触发枢纽被CSDH门控丢弃)" %
          (len(files), n_path, n_gated))
    print("涌现候选模板 %d 个 → %s\n" % (len(out), OUT))
    print("=== Top 25 候选模板(按命中政策数)===")
    print("%-26s %3s %3s %3s  %s" % ("模板(枢纽·题·方向)", "策", "例", "部", "措施样本"))
    for t in out[:25]:
        print("%-26s %3d %3d %3d  %s" % (
            "%s·Q%d·%s" % (t["hub"], t["outcome_q"], t["direction"]),
            t["n_policies"], t["n_instances"], t["n_depts"],
            "/".join(t["action_examples"][:3])[:46]))


if __name__ == "__main__":
    main()
