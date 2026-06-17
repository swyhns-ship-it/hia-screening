# -*- coding: utf-8 -*-
"""① 抽出 Claude删/DeepSeek留 的 272 条分歧,做成紧凑裁定数据(带政策原文片段 + 模式聚类)。
产物:eval/adjudication_272.jsonl(每行一条,字段紧凑,供 Opus 逐条预判 + 人工复核)。
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hia_screen as hs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "eval", "cc_exp_base")
DS = os.path.join(ROOT, "eval", "cc_ds_base")
OB = os.path.join(ROOT, "eval", "out_exp_base")
POLICY_DIR = r"E:\projects\test2"
OUT = os.path.join(ROOT, "eval", "adjudication_272.jsonl")

_txt_cache = {}


def policy_text(name):
    if name in _txt_cache:
        return _txt_cache[name]
    stem = os.path.splitext(name)[0]
    hit = glob.glob(os.path.join(POLICY_DIR, glob.escape(stem) + ".*"))
    t = ""
    if hit:
        try:
            with open(hit[0], "rb") as f:
                t, info = hs.extract_text(os.path.basename(hit[0]), f.read())
            t = "" if info.get("error") else t
        except Exception:
            t = ""
    _txt_cache[name] = t
    return t


def excerpt(text, keys, width=180):
    norm = re.sub(r"\s+", "", text or "")
    for k in keys:
        k2 = re.sub(r"\s+", "", str(k or ""))[:14]
        if len(k2) < 6:
            continue
        i = norm.find(k2)
        if i >= 0:
            return "…" + norm[max(0, i - 30):i + width] + "…"
    return ""


def pattern_of(err, reason):
    s = (err or "") + (reason or "")
    if "重复" in s or "重叠" in s or "冗余" in s:
        return "1_重复"
    if "幻觉" in s or "反向" in s or "原文无" in s or "找不到" in s or "锚定" in s:
        return "2_锚定/幻觉"
    if "题号" in s or "落点" in s or "落脚" in s:
        return "3_题号落点"
    if "过度展开" in s or "机制不成立" in s or "链条过长" in s or "推测" in s or "间接" in s:
        return "4_过度伸展"
    return "5_其它"


def audit_map(d):
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
        out[os.path.basename(f)] = {v.get("id"): v
                                    for v in (r.get("audit", {}).get("pathways") or [])}
    return out


def main():
    g, s = audit_map(GOLD), audit_map(DS)
    recs = []
    for name in sorted(set(g) & set(s)):
        hf = os.path.join(OB, name)
        if not os.path.exists(hf):
            continue
        try:
            hd = json.load(open(hf, encoding="utf-8"))
        except Exception:
            continue
        res = hd.get("res", {})
        paths = {p.get("id"): p for p in res.get("pathways", [])}
        actions = {a.get("id"): a.get("action", "") for a in res.get("actions", [])}
        for pid, gv in g[name].items():
            sv = s[name].get(pid)
            if not sv:
                continue
            if gv.get("judgment") == "drop" and sv.get("judgment") in ("keep", "fix"):
                p = paths.get(pid, {})
                act = actions.get(p.get("action_id"), "")
                ex = excerpt(policy_text(name), [p.get("evidence", ""), act,
                             (p.get("chain") or [""])[0]])
                recs.append({
                    "pol": os.path.splitext(name)[0][:48],
                    "chain": " → ".join(p.get("chain", [])),
                    "q": p.get("outcome_q"), "str": p.get("strength"),
                    "dir": p.get("direction"),
                    "action": act[:60],
                    "claude_err": gv.get("error_type", ""),
                    "claude_reason": (gv.get("reason", "") or "")[:160],
                    "ds_reason": (sv.get("reason", "") or "")[:160],
                    "excerpt": ex[:220],
                    "pattern": pattern_of(gv.get("error_type"), gv.get("reason")),
                })
    recs.sort(key=lambda r: (r["pattern"], r["pol"]))
    for i, r in enumerate(recs, 1):
        r["idx"] = i
    with open(OUT, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    import collections
    pat = collections.Counter(r["pattern"] for r in recs)
    miss_ex = sum(1 for r in recs if not r["excerpt"])
    print("抽出 %d 条 → %s" % (len(recs), OUT))
    print("按模式:", dict(sorted(pat.items())))
    print("原文片段未定位:", miss_ex)


if __name__ == "__main__":
    main()
