# -*- coding: utf-8 -*-
"""R0 重构(逐条摘录干预条款)对照测:关键 8 份,看漏报捞回 / 假阳 gate / 不打乱。"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import hia_screen as hs   # noqa: E402
import funnel             # noqa: E402

OUT = os.path.join(ROOT, "eval", "out_funnel_v4")
os.makedirs(OUT, exist_ok=True)

# (key前缀关键词, v3里的问题)
PICKS = [
    ("石化化工", "v3=R0漏报→期望 true+危害"),
    ("矿山隐蔽致灾", "v3=R0假阳→期望 gate(空)"),
    ("海上风电", "v3=R0假阳+6假→期望 gate(空)"),
    ("消防安全标志", "v3=R0漏报(放松防护边界)→看摘出啥"),
    ("节能降碳改造", "v3=correct true 16/16→应仍 true·真危害保住"),
    ("国债期货", "v3=correct false→应仍 gate"),
    ("综合运输春运", "v3=correct false→应仍 gate"),
    ("社区卫生服务", "v3=true 1/9 硬造→R2狠杀后应只剩真危害"),
    ("互助性养老", "v3=4/16 硬造→R2狠杀:硬造↓真危害保住"),
]


def get_key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    import tomllib
    with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
        return (tomllib.load(f).get("deepseek_api_key", "") or "").strip()


def main():
    key = get_key()
    rows = json.load(open(os.path.join(ROOT, "eval", "_funnel_sample.json"), encoding="utf-8"))
    for kw, note in PICKS:
        r = next((x for x in rows if kw in x["key"]), None)
        if not r:
            print("?? 未找到", kw, flush=True)
            continue
        title = r["key"].split("_", 2)[-1][:30]
        data = open(r["path"], "rb").read()
        text, info = hs.extract_text(os.path.basename(r["path"]), data)
        if info.get("error"):
            print("⚠ %s 抽取失败" % title, flush=True)
            continue
        t0 = time.time()
        res = funnel.run_funnel(text, key, model="deepseek-v4-flash")
        dt = time.time() - t0
        json.dump({"meta": r, "res": res}, open(os.path.join(OUT, kw + ".json"), "w",
                  encoding="utf-8"), ensure_ascii=False, indent=2)
        ivs = res.get("interventions") or []
        print("\n=== %s  [%s] ===" % (title, note), flush=True)
        print("  干预条款抽取 %d 条 | intervention=%s | 危害%d | 候选%d 轮%d | %.0fs"
              % (len(ivs), res.get("intervention"), len(res.get("pathways") or []),
                 res.get("n_candidates", 0), res.get("n_rounds", 0), dt), flush=True)
        for iv in ivs[:6]:
            print("    · 〔%s〕%s" % (iv.get("change", "")[:30],
                                   (iv.get("quote", "") or "")[:50]), flush=True)
        for p in (res.get("pathways") or []):
            print("    P q%d %s %s | %s" % (p["outcome_q"], p["strength"],
                  p["mitigation"], " → ".join(p["chain"])), flush=True)


if __name__ == "__main__":
    main()
