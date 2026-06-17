# -*- coding: utf-8 -*-
"""路径推断内测脚本 —— 批量跑分析,导出可逐条检验的报告(供人工/AI 复核与矫正)。

用法:
  1. 把待测政策文件(PDF / .docx)放进  eval/policies/
  2. 配好密钥:环境变量 DEEPSEEK_API_KEY,或 .streamlit/secrets.toml 的 deepseek_api_key
  3. 在仓库根目录运行:  python eval/run_eval.py
  4. 结果写到 eval/out/<文件名>.md(给人/AI 读)与 .json(结构化),逐条检验。

每条路径会标出:把握/依据状态、完整因果链、落到的健康方面、文件原句依据、健康端来源。
复核重点(见 eval/REVIEW_GUIDE.md):文档锚定?机制合理?强度是否过/欠?是否拿健康证据
冒充中间环节?有无重要遗漏或幻觉?
"""
import concurrent.futures as cf
import glob
import io
import json
import os
import sys
import threading

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hia_screen as hs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_DIR = os.path.join(ROOT, "eval", "policies")
# 输出目录可经 EVAL_OUT 覆盖(大集重建基线时用独立目录,不污染旧 out/)
OUT_DIR = os.path.join(ROOT, os.environ.get("EVAL_OUT", os.path.join("eval", "out")))
# 并发度:默认 1(串行,旧行为);大集设 EVAL_WORKERS=8 提速
WORKERS = max(1, int(os.environ.get("EVAL_WORKERS", "1")))
_print_lock = threading.Lock()


def get_key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    try:
        import tomllib
        with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
            return (tomllib.load(f).get("deepseek_api_key", "") or "").strip()
    except Exception:
        return ""


def run_one(path, key):
    name = os.path.basename(path)
    with open(path, "rb") as f:
        data = f.read()
    text, info = hs.extract_text(name, data)
    if info.get("error"):
        return {"name": name, "error": info["error"]}
    res = hs.analyze(text, key, project_name=os.path.splitext(name)[0])
    return {"name": name, "info": info, "res": res}


def to_md(r):
    if r.get("error"):
        return f"# {r['name']}\n\n解析失败:{r['error']}\n"
    res, info = r["res"], r["info"]
    L = [f"# 内测报告:{r['name']}",
         f"\n解析:{info.get('kind','')} {info.get('pages','')}页"
         + ("(已截断前4万字)" if info.get("truncated") else ""),
         f"\nAI 研判小结:{res.get('summary','')}",
         f"\nAI 建议程度:{res.get('suggest_level','')}　|　仍需核实:{res.get('notes','')}",
         "\n## 抽取的措施"]
    for a in res["actions"]:
        L.append(f"- **{a['id']}** {a['action']}"
                 + (f"　〔文件依据:{a['evidence']}〕" if a.get("evidence") else "　〔无文件原句〕"))
    L.append("\n## 因果路径(按健康方面分组,逐条检验)")
    for q in range(1, len(hs.QUESTIONS) + 1):
        ps = [p for p in res["pathways"] if p["outcome_q"] == q]
        if not ps:
            continue
        L.append(f"\n### 健康方面 {q} · {hs.SHORT_Q[q-1]} —— {len(ps)} 条")
        L.append(f"_(初筛表问题:{hs.QUESTIONS[q-1]})_")
        for p in ps:
            L.append(f"\n- **[{p['strength']}/{p['status']}/{p['direction']}]** "
                     + " → ".join(p["chain"]))
            if p.get("population"):
                L.append(f"  - 人群:{p['population']}")
            if p.get("evidence"):
                L.append(f"  - 文件/机制依据:{p['evidence']}")
            cards = p.get("cards") or []
            if cards:
                for c in cards:
                    L.append(f"  - 健康端来源[{c.get('tier','?')}·"
                             f"{'待补强' if c.get('status')=='todo' else '已核实'}]:"
                             + "；".join(c["sources"]))
            else:
                L.append("  - 健康端来源:⚠ 无(机制推断,证据待补)")
            L.append("  - 🔎 检验:文档锚定[ ] 机制合理[ ] 强度恰当[ ] 无跨段冒充[ ] —— 备注:")
    return "\n".join(L)


def _done(base):
    """已有有效 json 产物则跳过(断点续跑)。"""
    p = os.path.join(OUT_DIR, base + ".json")
    if not os.path.exists(p):
        return False
    try:
        json.load(open(p, encoding="utf-8"))
        return True
    except Exception:
        return False


def _process(f, key, i, total):
    base = os.path.splitext(os.path.basename(f))[0]
    if _done(base):
        with _print_lock:
            print(f"[{i}/{total}] 跳过(已有) {base[:46]}")
        return None
    try:
        r = run_one(f, key)
    except Exception as ex:                               # noqa: BLE001
        with _print_lock:
            print(f"[{i}/{total}] 失败 {base[:40]}: {ex}")
        return None
    with open(os.path.join(OUT_DIR, base + ".json"), "w", encoding="utf-8") as fp:
        json.dump(r, fp, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, base + ".md"), "w", encoding="utf-8") as fp:
        fp.write(to_md(r))
    np = 0 if r.get("error") else len(r["res"]["pathways"])
    with _print_lock:
        print(f"[{i}/{total}] {'解析失败' if r.get('error') else f'路径{np}'}  {base[:42]}")
    return None


def _build_summary(files):
    summary = ["# 批量内测汇总\n",
               "| 政策 | 措施数 | 路径数 | 健康端有据 | 证据待补 | 待补占比 |",
               "|---|---|---|---|---|---|"]
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        p = os.path.join(OUT_DIR, base + ".json")
        if not os.path.exists(p):
            continue
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if r.get("error"):
            continue
        ps = r["res"]["pathways"]
        n_src = sum(1 for p_ in ps if p_.get("cards"))
        n_gap = len(ps) - n_src
        ratio = f"{(n_gap/len(ps)*100):.0f}%" if ps else "—"
        summary.append(f"| {base} | {len(r['res']['actions'])} | {len(ps)} | "
                       f"{n_src} | {n_gap} | {ratio} |")
    with open(os.path.join(OUT_DIR, "_SUMMARY.md"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(summary) + "\n")


def main():
    key = get_key()
    if not key:
        sys.exit("未找到密钥:请设 DEEPSEEK_API_KEY 或在 .streamlit/secrets.toml 配 deepseek_api_key。")
    pol_dir = os.path.join(ROOT, sys.argv[1]) if len(sys.argv) > 1 else POLICY_DIR
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(pol_dir, "*.pdf"))
                   + glob.glob(os.path.join(pol_dir, "*.docx")))
    if not files:
        sys.exit(f"没找到待测文件。请把政策 PDF/.docx 放进 {pol_dir}")
    # 可选 manifest:只跑清单里的文件(json:{name:...} 或 [name,...];name=无扩展名)
    mani = os.environ.get("EVAL_MANIFEST", "").strip()
    if mani:
        m = json.load(open(os.path.join(ROOT, mani) if not os.path.isabs(mani) else mani,
                            encoding="utf-8"))
        want = set(m.keys() if isinstance(m, dict) else m)
        files = [f for f in files if os.path.splitext(os.path.basename(f))[0] in want]
        print(f"[manifest] {mani} → 只跑 {len(files)} 份")
    total = len(files)
    todo = sum(0 if _done(os.path.splitext(os.path.basename(f))[0]) else 1 for f in files)
    print(f"待测 {total} 份(目录:{pol_dir});待跑 {todo} 份;并发 {WORKERS};输出 {OUT_DIR}")
    if WORKERS <= 1:
        for i, f in enumerate(files, 1):
            _process(f, key, i, total)
    else:
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(_process, f, key, i, total)
                    for i, f in enumerate(files, 1)]
            for _ in cf.as_completed(futs):
                pass
    _build_summary(files)
    print(f"完成。汇总见 {os.path.join(OUT_DIR, '_SUMMARY.md')};逐条报告 {OUT_DIR}/*.md。")


if __name__ == "__main__":
    main()
