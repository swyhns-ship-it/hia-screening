# -*- coding: utf-8 -*-
"""针对性回归:只重跑关键样本,验证修复。不动 eval/out 全量。"""
import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hia_screen as hs  # noqa: E402

DIR = r"E:\projects\test"
import tomllib
KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
if not KEY:
    with open(".streamlit/secrets.toml", "rb") as f:
        KEY = tomllib.load(f).get("deepseek_api_key", "")

# (关键词, 期望)  期望:'+'=应出路径(原假阴) / '0'=应0或极少(原假阳) / '~'=应保持有路径(正样本不回归)
TARGETS = [
    ("绿色低碳先进技术示范", "+"),   # fallback正样本:技术示范=实体,应保留
    ("非化石能源电力消费核算", "+"), # fallback边界正样本
    ("第一批高质量户外运动目的地建设地区名单", "+"),  # fallback正样本:体育锻炼
    ("国家级零碳园区建设名单第一批", "+"),  # fallback正样本:名单类
]

print("回归 %d 份\n" % len(TARGETS))
for kw, exp in TARGETS:
    g = glob.glob(os.path.join(DIR, "*" + kw + "*.pdf"))
    if not g:
        print("× 未找到", kw); continue
    name = os.path.basename(g[0])
    data = open(g[0], "rb").read()
    text, info = hs.extract_text(name, data)
    if info.get("error"):
        print("× 解析失败", kw); continue
    res = hs.analyze(text, KEY, project_name=os.path.splitext(name)[0])
    ps = res["pathways"]
    n_card = sum(1 for p in ps if p.get("cards"))
    n_spec = sum(1 for p in ps if p.get("strength") == "推测")
    # 列出挂卡的国标来源,检查误配
    badwater = any("18918" in s for p in ps for c in (p.get("cards") or []) for s in c["sources"])
    print("[期望%s] %-22s 行动%2d 路径%2d (挂卡%d 推测%d)%s"
          % (exp, kw[:22], len(res["actions"]), len(ps), n_card, n_spec,
             "  ⚠仍挂污水卡" if badwater else ""))
    for p in ps[:3]:
        ch = p.get("chain", [])
        print("     [%s] %s → %s" % (p.get("strength"), (ch[0] if ch else "?")[:16],
                                     (ch[-1] if ch else "?")[:20]))
