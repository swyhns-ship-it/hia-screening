# -*- coding: utf-8 -*-
"""多跑量化 flash 方差:对给定政策跑 N 遍,看危害数分布 + 哪些危害签名稳定复现。"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import hia_screen as hs   # noqa: E402
import funnel             # noqa: E402

N = int(os.environ.get("N", "3"))
PICKS = ["石化化工", "节能降碳改造", "社区卫生服务"]


def get_key():
    import tomllib
    return (tomllib.load(open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb"))
            .get("deepseek_api_key", "") or "").strip()


def sig(chain):
    # 用前2节点+末节点做粗签名(容忍措辞微变,识"同一危害")
    nodes = [c for x in chain for c in str(x).replace("→", "\n").split("\n")]
    nodes = ["".join(n.split())[:8] for n in nodes if n.strip()]
    return (tuple(nodes[:2]), nodes[-1] if nodes else "")


def main():
    key = get_key()
    rows = json.load(open(os.path.join(ROOT, "eval", "_funnel_sample.json"), encoding="utf-8"))
    for kw in PICKS:
        r = next(x for x in rows if kw in x["key"])
        text, info = hs.extract_text(os.path.basename(r["path"]), open(r["path"], "rb").read())
        counts, sigcount = [], collections.Counter()
        for run in range(N):
            res = funnel.run_funnel(text, key, model="deepseek-v4-flash")
            ps = res.get("pathways") or []
            counts.append(len(ps))
            for p in ps:
                sigcount[sig(p["chain"])] += 1
        print("\n=== %s  N=%d ===" % (kw, N), flush=True)
        print("  危害数每跑:", counts, flush=True)
        stable = [(s, c) for s, c in sigcount.items() if c == N]
        flick = [(s, c) for s, c in sigcount.items() if c < N]
        print("  稳定复现(全 %d 跑都有)%d 类:" % (N, len(stable)), flush=True)
        for s, c in stable:
            print("     ·", "→".join(s[0]) + "…→" + s[1], flush=True)
        print("  闪烁(部分跑出现)%d 类" % len(flick), flush=True)


if __name__ == "__main__":
    main()
