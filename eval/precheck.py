# -*- coding: utf-8 -*-
"""抽取层预检:对目录内全部 PDF 跑 extract_text,不调 API。
报告 页数/字符数/截断/疑似乱码(CID)/疑似扫描/抽取错误。"""
import glob
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hia_screen as hs  # noqa: E402

DIR = sys.argv[1] if len(sys.argv) > 1 else r"E:\projects\test"
files = sorted(glob.glob(os.path.join(DIR, "*.pdf")) + glob.glob(os.path.join(DIR, "*.docx")))
print(f"预检 {len(files)} 份 @ {DIR}\n")
print(f"{'状态':<6}{'页':>4}{'字符':>7}{'MB':>6}  文件")
bad = []
for f in files:
    name = os.path.basename(f)
    mb = os.path.getsize(f) / 1e6
    try:
        with open(f, "rb") as fp:
            data = fp.read()
        text, info = hs.extract_text(name, data)
    except Exception as ex:  # noqa: BLE001
        print(f"{'崩':<6}{'-':>4}{'-':>7}{mb:6.1f}  {name}  [{ex}]")
        bad.append((name, "extract异常", str(ex)))
        continue
    if info.get("error"):
        print(f"{'错':<6}{'-':>4}{'-':>7}{mb:6.1f}  {name}  [{info['error']}]")
        bad.append((name, "解析失败", info["error"]))
        continue
    n = len(text or "")
    pages = info.get("pages", "?")
    # 乱码/扫描启发:字符数极少 vs 页数 → 疑扫描;CID 标记 → 乱码
    cid = "(cid:" in (text or "")
    per_page = n / pages if isinstance(pages, int) and pages else n
    flag = "OK"
    if cid:
        flag = "乱码"
    elif isinstance(pages, int) and pages >= 2 and per_page < 80:
        flag = "疑扫描"
    elif n < 200:
        flag = "极短"
    trunc = "✂" if info.get("truncated") else " "
    print(f"{flag:<6}{pages:>4}{n:>7}{mb:6.1f} {trunc} {name}")
    if flag != "OK":
        bad.append((name, flag, f"{n}字/{pages}页"))

print(f"\n=== 异常 {len(bad)} 份 ===")
for n, k, d in bad:
    print(f"  [{k}] {n}  {d}")
