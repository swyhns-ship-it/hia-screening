# -*- coding: utf-8 -*-
"""漏斗 v3 跑测 —— 对 _funnel_sample.json 逐份跑 funnel.run_funnel,存 out_funnel/。

断点续跑(已有有效 json 则跳过)、单份失败不中断、打印进度。
产物字段:meta(key/dept/label/stratum)+ funnel 全量返回(intervention/n_candidates/
n_rounds/pathways/items)+ 原文(text,供裁定时锚定核对,截 25k 与引擎一致)。

用法:python eval/run_funnel_eval.py   (密钥走 DEEPSEEK_API_KEY 或 .streamlit/secrets.toml)
"""
import json
import os
import re
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hia_screen as hs       # noqa: E402
import funnel                 # noqa: E402

SAMPLE = os.path.join(ROOT, "eval", "_funnel_sample.json")
OUT_DIR = os.path.join(ROOT, "eval", "out_funnel")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")


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


def safe(key):
    return re.sub(r"[^\w一-鿿]+", "_", key)[:120]


def done(path):
    if not os.path.exists(path):
        return False
    try:
        json.load(open(path, encoding="utf-8"))
        return True
    except Exception:
        return False


def main():
    key = get_key()
    if not key:
        sys.exit("未找到密钥:设 DEEPSEEK_API_KEY 或 .streamlit/secrets.toml 的 deepseek_api_key。")
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = json.load(open(SAMPLE, encoding="utf-8"))
    total = len(rows)
    print("== 漏斗 v3 跑测 %d 份  model=%s ==" % (total, MODEL), flush=True)

    for i, r in enumerate(rows, 1):
        outp = os.path.join(OUT_DIR, safe(r["key"]) + ".json")
        tag = "[%2d/%d] %-18s %s" % (i, total, r["stratum"], r["key"].split("_", 2)[-1][:30])
        if done(outp):
            print(tag + "  ✓已存,跳过", flush=True)
            continue
        try:
            with open(r["path"], "rb") as f:
                data = f.read()
            text, info = hs.extract_text(os.path.basename(r["path"]), data)
            if info.get("error"):
                rec = {"meta": r, "error": "抽取失败:" + info["error"]}
                json.dump(rec, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print(tag + "  ⚠抽取失败:" + info["error"], flush=True)
                continue
            t0 = time.time()
            res = funnel.run_funnel(text, key, model=MODEL)
            dt = time.time() - t0
            rec = {"meta": r, "info": {k: info.get(k) for k in ("kind", "pages", "truncated")},
                   "text": text[:25000], "res": res, "secs": round(dt, 1)}
            json.dump(rec, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            n = len(res.get("pathways") or [])
            print(tag + "  → 干预=%s 危害%d条 候选%d 轮%d %.0fs"
                  % (res.get("intervention"), n, res.get("n_candidates", 0),
                     res.get("n_rounds", 0), dt), flush=True)
        except Exception as e:
            print(tag + "  ✗异常:" + repr(e), flush=True)
            traceback.print_exc()

    print("== 完成 ==", flush=True)


if __name__ == "__main__":
    main()
