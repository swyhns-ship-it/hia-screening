# -*- coding: utf-8 -*-
"""回归评分 —— 读 eval/out/*.json(run_eval 产物),按金标准 labels 算混淆矩阵;
若存在基线则标出判定变化的样本。

用法:
  python eval/run_eval.py E:\\projects\\test     # ① 跑全量(烧 API),生成 out/
  python eval/score.py                            # ② 算分 + 与基线对比
  python eval/score.py --save-baseline            # ③ 满意后把当前结果固化为基线
基线文件:eval/baseline.json(随仓库,记录每份的 路径数+判定,供后续 diff)。"""
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labels as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "eval", "out")
BASELINE = os.path.join(ROOT, "eval", "baseline.json")


def load_results():
    rows = {}
    for p in sorted(glob.glob(os.path.join(OUT, "*.json"))):
        name = os.path.splitext(os.path.basename(p))[0]
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        res = d.get("res", {})
        n = len(res.get("pathways", []))
        if d.get("error") or "res" not in d:
            n = 0
        rows[name] = {"n_path": n, "label": L.expect(name)}
        rows[name]["verdict"] = L.verdict(rows[name]["label"], n)
    return rows


def main():
    save = "--save-baseline" in sys.argv
    rows = load_results()
    if not rows:
        sys.exit("eval/out 为空。先跑 python eval/run_eval.py <政策目录>。")

    # —— 混淆矩阵(只在 A/B 高置信样本上算率;X 边界、C 跳过单列)——
    A = [r for r in rows.values() if r["label"] == "A"]
    B = [r for r in rows.values() if r["label"] == "B"]
    X = [r for r in rows.values() if r["label"] == "X"]
    C = [r for r in rows.values() if r["label"] == "C"]
    fn = [(n, r) for n, r in rows.items() if r["verdict"] == "假阴"]
    fp = [(n, r) for n, r in rows.items() if r["verdict"] == "假阳"]
    a_ok = len(A) - len(fn)
    b_ok = len(B) - len(fp)

    print("=" * 56)
    print("HIA 引擎回归评分  (%d 份)" % len(rows))
    print("=" * 56)
    print("正样本 A:%2d  正确出路径 %2d  → 假阴 %d (%.0f%%)"
          % (len(A), a_ok, len(fn), 100 * len(fn) / max(1, len(A))))
    print("负样本 B:%2d  正确判≈0  %2d  → 假阳 %d (%.0f%%)"
          % (len(B), b_ok, len(fp), 100 * len(fp) / max(1, len(B))))
    print("边界 X:%2d(不计率,只监控)   抽取失败 C:%2d(跳过)" % (len(X), len(C)))
    acc = (a_ok + b_ok) / max(1, len(A) + len(B))
    print("A/B 综合准确率:%.1f%%" % (100 * acc))

    if fn:
        print("\n❌ 假阴性(A 正样本却 0 路径) %d:" % len(fn))
        for n, r in fn:
            print("   %s" % n[:54])
    if fp:
        print("\n❌ 假阳性(B 负样本却 ≥%d 路径) %d (按路径数降序):" % (L.FALSE_POS_MIN, len(fp)))
        for n, r in sorted(fp, key=lambda x: -x[1]["n_path"]):
            print("   路径%2d  %s" % (r["n_path"], n[:48]))

    # —— 与基线对比 ——
    if os.path.exists(BASELINE):
        base = json.load(open(BASELINE, encoding="utf-8"))
        changed = []
        for n, r in rows.items():
            b = base.get(n)
            if b and (b["verdict"] != r["verdict"] or b["n_path"] != r["n_path"]):
                changed.append((n, b, r))
        new_only = [n for n in rows if n not in base]
        gone = [n for n in base if n not in rows]
        print("\n" + "-" * 56)
        print("与基线对比(baseline.json):")
        if not changed and not new_only and not gone:
            print("  ✓ 无变化(与基线完全一致)")
        for n, b, r in changed:
            flag = ""
            if b["verdict"] not in ("假阴", "假阳") and r["verdict"] in ("假阴", "假阳"):
                flag = "  ⚠新增问题"
            elif b["verdict"] in ("假阴", "假阳") and r["verdict"] not in ("假阴", "假阳"):
                flag = "  ✅已修复"
            print("  %-46s 路径 %d→%d  [%s→%s]%s"
                  % (n[:46], b["n_path"], r["n_path"], b["verdict"], r["verdict"], flag))
        for n in new_only:
            print("  + 新样本 %s (路径%d,%s)" % (n[:44], rows[n]["n_path"], rows[n]["verdict"]))
        for n in gone:
            print("  - 基线有但本次缺 %s" % n[:42])
    else:
        print("\n(无基线。跑 python eval/score.py --save-baseline 固化当前为基线)")

    if save:
        snap = {n: {"n_path": r["n_path"], "verdict": r["verdict"], "label": r["label"]}
                for n, r in rows.items()}
        json.dump(snap, open(BASELINE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("\n✓ 已保存基线 → eval/baseline.json (%d 份)" % len(snap))


if __name__ == "__main__":
    main()
