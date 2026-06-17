# -*- coding: utf-8 -*-
"""DeepSeek 审计 vs Claude 审计(金标准)对照:逐路径比 keep/drop 判定。
关键问题:DeepSeek 自审能不能抓住 Claude 抓的"垃圾"(drop)?(自我护短检验)
"""
import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "eval", "cc_exp_base")     # Claude 金标准
DS = os.path.join(ROOT, "eval", "cc_ds_base")        # DeepSeek 审计


def verds(d):
    out = {}
    for f in glob.glob(os.path.join(d, "*.json")):
        if os.path.basename(f).startswith("_"):
            continue
        try:
            r = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if r.get("error"):
            continue
        m = {v.get("id"): v.get("judgment")
             for v in (r.get("audit", {}).get("pathways") or [])}
        out[os.path.basename(f)] = m
    return out


def real(j):
    return j in ("keep", "fix")


def main():
    g, s = verds(GOLD), verds(DS)
    docs = sorted(set(g) & set(s))
    # 混淆:(claude_real, ds_real)
    n = collections.Counter()
    both = 0
    for name in docs:
        gm, sm = g[name], s[name]
        for pid, gj in gm.items():
            sj = sm.get(pid)
            if gj not in ("keep", "fix", "drop") or sj not in ("keep", "fix", "drop"):
                continue
            both += 1
            n[(real(gj), real(sj))] += 1
    cr_sr = n[(True, True)]    # Claude真 & DS留
    cr_sj = n[(True, False)]   # Claude真 & DS删(误删真路径)
    cj_sr = n[(False, True)]   # Claude垃圾 & DS留(护短漏删)
    cj_sj = n[(False, False)]  # Claude垃圾 & DS删(正确抓垃圾)
    tot = both
    agree = (cr_sr + cj_sj) / tot if tot else 0
    drop_recall = cj_sj / (cj_sj + cj_sr) if (cj_sj + cj_sr) else 0   # 垃圾抓回率
    keep_recall = cr_sr / (cr_sr + cr_sj) if (cr_sr + cr_sj) else 0   # 真路径保留率
    ds_prune_prec = cr_sr / (cr_sr + cj_sr) if (cr_sr + cj_sr) else 0  # DS当剪枝器的精确率
    base_prec = (cr_sr + cr_sj) / tot if tot else 0
    print("配对 %d 份,逐路径比 %d 条(两边都有判定)\n" % (len(docs), tot))
    print("混淆矩阵(行=Claude 金标准,列=DeepSeek):")
    print("              DS留      DS删")
    print("Claude真     %5d    %5d" % (cr_sr, cr_sj))
    print("Claude垃圾   %5d    %5d" % (cj_sr, cj_sj))
    print("\n总体一致率        %.3f" % agree)
    print("★垃圾抓回率(drop) %.3f   ← Claude判drop的,DS也drop的比例(自我护短就低)" % drop_recall)
    print("真路径保留率       %.3f" % keep_recall)
    print("\nDeepSeek 当剪枝器:精确率 %.3f(基线 %.3f)" % (ds_prune_prec, base_prec))
    print("对比:确定性'删推测'剪枝精确率 0.746、召回 0.971(零API)")


if __name__ == "__main__":
    import collections
    main()
