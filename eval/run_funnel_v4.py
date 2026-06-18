# -*- coding: utf-8 -*-
"""漏斗 v5 并发跑测(R2 杀准 / R3 召回桶不走 R2)。

对 _funnel_sample.json 全样本并发跑(线程池;_chat_json 走 requests,I/O 释放 GIL → 真并发)。
每份存 out_funnel_v4/<key>.json,含:res.pathways(R2 确认集,已富化)+ res.recovered(R3 召回桶,
未经 R2,待 R4)。打印紧凑汇总:确认N / 召回M / 干预条款 / 候选 / 轮。
用法:python eval/run_funnel_v4.py   (WORKERS 环境变量调并发,默认 8)
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import hia_screen as hs   # noqa: E402
import funnel             # noqa: E402

SAMPLE = os.path.join(ROOT, "eval", "_funnel_sample.json")
OUT_DIR = os.path.join(ROOT, "eval", "out_funnel_v4")
WORKERS = int(os.environ.get("WORKERS", "8"))
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
_lock = threading.Lock()


def get_key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    import tomllib
    with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
        return (tomllib.load(f).get("deepseek_api_key", "") or "").strip()


def safe(key):
    import re
    return re.sub(r"[^\w一-鿿]+", "_", key)[:120]


def one(r, key, i, total):
    title = r["key"].split("_", 2)[-1][:24]
    try:
        text, info = hs.extract_text(os.path.basename(r["path"]), open(r["path"], "rb").read())
        if info.get("error"):
            with _lock:
                print("[%2d/%d] ⚠抽取失败 %s" % (i, total, title), flush=True)
            return
        t0 = time.time()
        res = funnel.run_funnel(text, key, model=MODEL)
        dt = time.time() - t0
        json.dump({"meta": r, "res": res}, open(os.path.join(OUT_DIR, safe(r["key"]) + ".json"),
                  "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        ps = res.get("pathways") or []
        via_r4 = sum(1 for p in ps if p.get("via") == "R3/R4")
        premerge = sum(p.get("n_merged", 1) for p in ps)
        with _lock:
            print("[%2d/%d] %-24s 干预=%-5s 确认%2d(合并前%d·R4补%d) 桶%d (候选%d 轮%d) %.0fs"
                  % (i, total, title, res.get("intervention"), len(ps), premerge, via_r4,
                     res.get("n_recovered", 0),
                     res.get("n_candidates", 0), res.get("n_rounds", 0), dt), flush=True)
    except Exception as e:
        with _lock:
            print("[%2d/%d] ✗ %s : %r" % (i, total, title, e), flush=True)


def main():
    key = get_key()
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = json.load(open(SAMPLE, encoding="utf-8"))
    total = len(rows)
    print("== 漏斗 v5 并发跑测 %d 份  workers=%d model=%s ==" % (total, WORKERS, MODEL), flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(one, r, key, i, total) for i, r in enumerate(rows, 1)]
        for _ in as_completed(futs):
            pass
    print("== 完成 ==", flush=True)


if __name__ == "__main__":
    main()
