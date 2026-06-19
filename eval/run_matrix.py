# -*- coding: utf-8 -*-
"""矩阵骨架(S1+S2+S2.5)并发跑测。每份存 out_matrix*/<key>.json:interventions + cells。
用法:[SAMPLE=… OUT_DIR=… WORKERS=…] python eval/run_matrix.py"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import hia_screen as hs   # noqa: E402
import matrix             # noqa: E402

SAMPLE = os.environ.get("SAMPLE", os.path.join(ROOT, "eval", "_funnel_sample.json"))
OUT_DIR = os.environ.get("OUT_DIR", os.path.join(ROOT, "eval", "out_matrix"))
WORKERS = int(os.environ.get("WORKERS", "12"))
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
        res = matrix.run_matrix(text, key, model=MODEL)
        dt = time.time() - t0
        json.dump({"meta": r, "res": res}, open(os.path.join(OUT_DIR, safe(r["key"]) + ".json"),
                  "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        ivs = res.get("interventions") or []
        cells = res.get("cells") or []
        killed = res.get("killed") or []
        items = res.get("items") or []
        yes = [it["q"] for it in items if it["answer"] == "是"]
        with _lock:
            print("[%2d/%d] %-24s 干预%2d 存活%2d 杀%2d | 初筛'是'%d题:%s %.0fs"
                  % (i, total, title, len(ivs), len(cells), len(killed),
                     len(yes), yes, dt), flush=True)
    except Exception as e:
        with _lock:
            print("[%2d/%d] ✗ %s : %r" % (i, total, title, e), flush=True)


def main():
    key = get_key()
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = json.load(open(SAMPLE, encoding="utf-8"))
    total = len(rows)
    print("== 矩阵骨架跑测 %d 份 workers=%d model=%s ==" % (total, WORKERS, MODEL), flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(one, r, key, i, total) for i, r in enumerate(rows, 1)]
        for _ in as_completed(futs):
            pass
    print("== 完成 ==", flush=True)


if __name__ == "__main__":
    main()
