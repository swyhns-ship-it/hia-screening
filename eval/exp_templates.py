# -*- coding: utf-8 -*-
"""② 模板接入引擎 · 留出集对比实验(离线,不碰线上)。
对留出集均衡子集,跑两版引擎:base(无模板提示)/ tmpl(注入模板提示),
各存成 run_eval 格式 → 之后用 cross_check 分别审计 → 比精确率/召回/假阳。

用法:
  HF_ENDPOINT=https://huggingface.co EVAL_WORKERS=8 python eval/exp_templates.py
产物:eval/out_exp_base/*.json  与  eval/out_exp_tmpl/*.json
再分别:EVAL_OUT=eval/out_exp_base CROSS_OUT=eval/cc_exp_base python eval/cross_check.py
        EVAL_OUT=eval/out_exp_tmpl CROSS_OUT=eval/cc_exp_tmpl python eval/cross_check.py
"""
import concurrent.futures as cf
import glob
import json
import os
import sys
import threading

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hia_screen as hs               # noqa: E402
import run_eval                       # noqa: E402  (复用 get_key)
from template_retrieval import TemplateRetriever  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELDOUT = os.path.join(ROOT, "eval", "dataset_heldout.json")
POLICY_DIR = os.environ.get("POLICY_DIR", r"E:\projects\test2")
OUT_BASE = os.path.join(ROOT, "eval", "out_exp_base")
OUT_TMPL = os.path.join(ROOT, "eval", "out_exp_tmpl")
WORKERS = max(1, int(os.environ.get("EVAL_WORKERS", "1")))
THRESH = float(os.environ.get("TMPL_THRESH", "0.6"))
A_PER_DEPT = int(os.environ.get("A_PER_DEPT", "4"))
B_PER_DEPT = int(os.environ.get("B_PER_DEPT", "2"))

_retr = None
_rlock = threading.Lock()
_print_lock = threading.Lock()


def _retriever():
    global _retr
    if _retr is None:
        _retr = TemplateRetriever()
    return _retr


def make_hint_builder():
    r = _retriever()

    def build(actions):
        seen, lines = set(), []
        for a in actions:
            act = a.get("action", "")
            if not act:
                continue
            with _rlock:                       # 串行编码,避开 torch 多线程隐患(短句很快)
                hits = r.search(act, k=2)
            for h in hits:
                if h["score"] < THRESH:
                    continue
                sig = (h["hub"], h["outcome_q"], h["direction"])
                if sig in seen:
                    continue
                seen.add(sig)
                lines.append("- 「%s」类行动 → %s → 题%d(%s)"
                             % (act[:16], h.get("hub_name") or h["hub"],
                                h["outcome_q"], h["direction"]))
        return "\n".join(lines[:8])            # 最多 8 条提示,防过载
    return build


def _find(name):
    for ext in (".pdf", ".docx"):
        p = os.path.join(POLICY_DIR, name + ext)
        if os.path.exists(p):
            return p
    hit = glob.glob(os.path.join(POLICY_DIR, glob.escape(name) + ".*"))
    return hit[0] if hit else None


def sample_heldout():
    ho = json.load(open(HELDOUT, encoding="utf-8"))
    bydept = {}
    for name in sorted(ho):
        bydept.setdefault(name.split("_")[0], []).append((name, ho[name]["label"]))
    picked = []
    for dept, items in bydept.items():
        na = nb = 0
        for name, lab in items:
            if lab == "A" and na < A_PER_DEPT:
                picked.append(name); na += 1
            elif lab == "B" and nb < B_PER_DEPT:
                picked.append(name); nb += 1
    return picked


def run_one(name, key, hint_builder, out_dir):
    base = name
    outp = os.path.join(out_dir, base + ".json")
    if os.path.exists(outp):
        return
    f = _find(name)
    if not f:
        return
    with open(f, "rb") as fp:
        data = fp.read()
    text, info = hs.extract_text(os.path.basename(f), data)
    if info.get("error"):
        r = {"name": os.path.basename(f), "error": info["error"]}
    else:
        res = hs.analyze(text, key, project_name=name, hint_builder=hint_builder)
        r = {"name": os.path.basename(f), "info": info, "res": res}
    json.dump(r, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    key = run_eval.get_key()
    if not key:
        sys.exit("缺 DEEPSEEK_API_KEY")
    os.makedirs(OUT_BASE, exist_ok=True)
    os.makedirs(OUT_TMPL, exist_ok=True)
    names = sample_heldout()
    hb = make_hint_builder()
    print("留出集子集 %d 份(A≤%d/B≤%d 每部门);阈值 %.2f;并发 %d"
          % (len(names), A_PER_DEPT, B_PER_DEPT, THRESH, WORKERS))
    tasks = [(n, None, OUT_BASE) for n in names] + [(n, hb, OUT_TMPL) for n in names]
    done = [0]

    def work(t):
        name, builder, out_dir = t
        try:
            run_one(name, key, builder, out_dir)
        except Exception as ex:                 # noqa: BLE001
            with _print_lock:
                print("失败", name[:34], str(ex)[:50])
        with _print_lock:
            done[0] += 1
            if done[0] % 20 == 0:
                print("[%d/%d]" % (done[0], len(tasks)))

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, tasks))
    nb = len(glob.glob(os.path.join(OUT_BASE, "*.json")))
    nt = len(glob.glob(os.path.join(OUT_TMPL, "*.json")))
    print("完成。base %d 份 → %s ; tmpl %d 份 → %s" % (nb, OUT_BASE, nt, OUT_TMPL))


if __name__ == "__main__":
    main()
