# -*- coding: utf-8 -*-
"""② 实验对比:base(无模板) vs tmpl(注入模板)在留出集上的审计结果。
按政策配对,分 A(正样本,看精确/召回)/ B(负样本,看假阳)汇总。
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
HELDOUT = json.load(open(os.path.join(ROOT, "eval", "dataset_heldout.json"), encoding="utf-8"))
CC_BASE = os.path.join(ROOT, "eval", "cc_exp_base")
CC_TMPL = os.path.join(ROOT, "eval", "cc_exp_tmpl")


def load(d):
    rows = {}
    for f in glob.glob(os.path.join(d, "*.json")):
        if os.path.basename(f).startswith("_"):
            continue
        try:
            r = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if "precision" in r:
            rows[r["name"]] = r
    return rows


def label_of(name):
    stem = os.path.splitext(name)[0]
    if stem in HELDOUT:
        return HELDOUT[stem]["label"]
    return HELDOUT.get(name, {}).get("label")


def agg(rows, names, fields):
    out = {}
    for fld in fields:
        vals = [rows[n][fld] for n in names if n in rows]
        out[fld] = sum(vals) / len(vals) if vals else 0.0
    return out


def main():
    b, t = load(CC_BASE), load(CC_TMPL)
    paired = sorted(set(b) & set(t))
    A = [n for n in paired if label_of(n) == "A"]
    B = [n for n in paired if label_of(n) == "B"]
    print("配对审计 %d 份(A %d / B %d);base=无模板, tmpl=注入模板\n" % (len(paired), len(A), len(B)))

    print("=== 正样本 A(应有路径;精确率↑/召回↑/漏报↓ 为好)===")
    print("%-14s %8s %8s %7s" % ("指标", "base", "tmpl", "Δ"))
    for fld, name in [("precision", "路径精确率"), ("precision_soft", "精确率(含fix)"),
                      ("recall", "召回率"), ("n_candidate", "候选/份"),
                      ("n_keep", "keep/份"), ("n_drop", "drop/份"), ("n_missing", "漏报/份")]:
        ab, at = agg(b, A, [fld])[fld], agg(t, A, [fld])[fld]
        print("%-14s %8.3f %8.3f %+7.3f" % (name, ab, at, at - ab))

    print("\n=== 负样本 B(应≈0;候选↓/keep↓/假阳率↓ 为好)===")
    print("%-14s %8s %8s %7s" % ("指标", "base", "tmpl", "Δ"))
    for fld, name in [("n_candidate", "候选/份"), ("n_keep", "keep/份")]:
        ab, at = agg(b, B, [fld])[fld], agg(t, B, [fld])[fld]
        print("%-14s %8.3f %8.3f %+7.3f" % (name, ab, at, at - ab))
    # 假阳率:B 份里审计后仍 ≥2 条 keep 的占比
    def fp_rate(rows):
        bad = sum(1 for n in B if n in rows and rows[n]["n_keep"] >= 2)
        return 100 * bad / max(1, len([n for n in B if n in rows]))
    print("%-14s %7.0f%% %7.0f%%  %+.0f%%" % ("假阳率(keep≥2)", fp_rate(b), fp_rate(t), fp_rate(t) - fp_rate(b)))

    # policy_verdict 翻转(B 被 Claude 判 A=该有却 base 漏 等)略
    print("\n注:tmpl 若 精确率↑且 B 假阳不升 → 模板有净增益,值得接生产。")


if __name__ == "__main__":
    main()
