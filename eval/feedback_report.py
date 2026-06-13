# -*- coding: utf-8 -*-
"""专家反馈回流报告 —— 把累积的专家反馈汇总成可指导知识库/提示词改进的清单。

读 feedback/feedback_log.jsonl,输出:
- 按问题类型计数(机制不成立/来源错配/强度不当…)
- 被标"来源错配"最多的来源(→ 该修这些卡的 keys/同义词/停用词,或剔除)
- 被否决/质疑的路径机制(→ 提示词或路径生成问题)
运行:  python eval/feedback_report.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import feedback as fbk  # noqa: E402


def main():
    s = fbk.summarize()
    L = ["# 专家反馈回流报告\n",
         f"- 反馈条目:**{s['total']}**　其中标记了问题:**{s['with_flag']}**\n",
         "## 按问题类型"]
    if s["by_flag"]:
        for k, v in s["by_flag"].items():
            L.append(f"- {k}:{v}")
    else:
        L.append("-(暂无标记)")
    L.append("\n## 被标「来源错配」最多的来源(优先修 keys/同义词/停用词,或剔除该卡)")
    if s["mismatched_cards"]:
        for k, v in s["mismatched_cards"].items():
            L.append(f"- [{v} 次] {k}")
    else:
        L.append("-(暂无)")
    L.append(f"\n## 被否决 / 质疑的路径({len(s['rejected'])} 条,提示词或路径生成可能的问题)")
    for r in s["rejected"][:50]:
        chain = " → ".join(r.get("chain") or [])
        tag = f"〔{r['flag']}〕" if r.get("flag") else "〔排除〕"
        L.append(f"- Q{r.get('q')} {tag} {chain}" + (f"  备注:{r['note']}" if r.get("note") else ""))
    report = "\n".join(L) + "\n"

    out = os.path.join(fbk.FB_DIR, "feedback_report.md")
    os.makedirs(fbk.FB_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print("→ 已写出", os.path.relpath(out, os.path.dirname(os.path.dirname(out))))


if __name__ == "__main__":
    main()
