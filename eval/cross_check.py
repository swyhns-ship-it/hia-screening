# -*- coding: utf-8 -*-
"""DeepSeek ⇄ Claude 交叉检验引擎(离线优化飞轮的脊柱)。

流程:读 DeepSeek 引擎输出(run_eval 产的 out/*.json)→ 对每份政策让 Claude 当审计员
逐路径判定(保留/修正/删除 + 漏报)→ 算一致/分歧 → 出【分歧队列】供人工只抽检关键分歧。
一致的自动采纳,分歧的进队列。产物即"路径级黄金集"的雏形 + 错误类型分布。

定位:**离线**用(开发/优化期)。生产线上只有 DeepSeek,Claude 不在运行时。

用法:
  # 1) 在 secrets.toml 配 anthropic_api_key(本仓库公开,严禁入库;已 gitignore),或设环境变量
  #    ANTHROPIC_API_KEY。DeepSeek key 同 run_eval。
  # 2) 先有 DeepSeek 输出:EVAL_OUT 指向 run_eval 的 out 目录(默认 eval/out)
  EVAL_WORKERS=4 PYTHONIOENCODING=utf-8 python eval/cross_check.py
  # 产物:eval/crosscheck/<政策>.json(逐路径审计)+ eval/crosscheck/_disagreements.md(分歧队列)
  #       + eval/crosscheck/_summary.md(一致率/错误类型分布)

环境变量:
  EVAL_OUT      DeepSeek 输出目录(默认 eval/out)
  CROSS_OUT     审计产物目录(默认 eval/crosscheck)
  POLICY_DIR    政策原文目录(默认 E:/projects/test2;审计需原文判"是否锚定")
  CROSS_MODEL   Claude 审计模型(默认 claude-sonnet-4-6;定稿可换 claude-opus-4-8)
  EVAL_WORKERS  并发(默认 1)
"""
import concurrent.futures as cf
import glob
import json
import os
import re
import sys
import threading

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hia_screen as hs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR = os.path.join(ROOT, os.environ.get("EVAL_OUT", os.path.join("eval", "out")))
CROSS_OUT = os.path.join(ROOT, os.environ.get("CROSS_OUT", os.path.join("eval", "crosscheck")))
POLICY_DIR = os.environ.get("POLICY_DIR", r"E:\projects\test2")
CROSS_MODEL = os.environ.get("CROSS_MODEL", "claude-sonnet-4-6")
CROSS_BACKEND = os.environ.get("CROSS_BACKEND", "anthropic")   # anthropic | deepseek
WORKERS = max(1, int(os.environ.get("EVAL_WORKERS", "1")))
_lock = threading.Lock()

ERROR_TYPES = [
    "hallucination_not_anchored",   # 幻觉/未锚定原文
    "over_expansion_false_positive",  # 过度展开(纯程序/经济政策硬造)
    "wrong_evidence_card",          # 证据卡贴错/跨题号误配
    "wrong_direction",              # 方向错(效益/危害)
    "wrong_strength",               # 强度过/欠
    "wrong_outcome",                # 落错健康方面(题号)
    "duplicate",                    # 与其它路径重复
    "self_contradiction",           # 自相矛盾
    "broken_mechanism",             # 因果链断裂/不成立
    "other",
]

SYS_AUDIT = """你是健康影响评估(HIA)初筛的资深审计专家,负责审一台 AI 引擎给出的政策**不利健康影响
(危害)路径**。HIA 初筛只筛**危害**(不利影响),不评效益。你的判定用于校正引擎,务必严格、可复核。

审计铁律:
- **只保留"显著或非显而易见"的高价值危害**;**任何工程都有的、可标准缓解的常规建设期影响
  (一般施工扬尘/施工噪声/常规运营尾气)→ drop**(低价值,非 HIA 重点),除非规模大/难缓解/
  有特定毒害/明显冲击脆弱群体。高价值=① 显著新危害 ② 削减健康保护因素 ③ 扩大健康不公平 ④ 非显而易见的间接危害。
- **有据可查 > 召回**:危害路径必须锚定政策原文的实体措施;凭空推测、原文找不到对应措施的 → drop。
- **绝不放过"硬造的危害"**:为凑数把好处反说成坏处、或多跳推测拼出的危害,一律 drop(这是本轮重点)。
- **假阳性比漏报更糟**:纯程序/财税/金融/价格/数据/统计/认定/人事/表彰类、以及纯效益/民生政策,
  本就**无危害可言 → 应为空**,不应硬造不利影响。
- 一条好的危害路径要件:① 首环节锚定原文实体措施;② 机制成立(确会**损害**某健康决定因素,
  含"削减保护因素""扩大健康不公平");③ 落对题号;④ 方向必为**危害(风险)**;⑤ 强度与证据匹配;
  ⑥ 不与其它路径重复、不自相矛盾。
- 效益路径若出现(direction 非风险)→ 一律 drop(本工具不评效益)。
- **措施维度**:HIA 落点是控制措施。审每条危害时一并看:① mitigation 判断对不对(政策原文确实
  "未提及/不足/已含"该危害的控制措施吗?);② measures 建议是否对口、可操作。若危害其实政策已
  充分控制(mitigation 实为"已含")却被标成缺口 → 可 fix 或降级;measures 空泛/不对口 → fix。

逐条给判定:keep(确为真实危害) / fix(题号/强度/链条小错,给修正) / drop(应删:硬造危害/幻觉/过度展开/重复/实为效益)。
再补 missing:引擎**漏掉的、原文明显支持的不利影响**(没有就空数组;同样只补危害,不补效益)。
再给 policy_verdict:这份政策整体该不该有危害路径——A(确有潜在不利影响)/ B(无,纯效益/程序/经济)/ X(边界)。

只输出 JSON,不要任何解释文字,结构:
{
 "policy_verdict": "A|B|X",
 "verdict_reason": "一句话:该政策为何应有/不应有健康路径",
 "pathways": [
   {"id":"P1","judgment":"keep|fix|drop","error_type":"上述枚举之一或留空",
    "reason":"一句中文依据",
    "fix":{"chain":[...],"direction":"效益|危害","outcome_q":1-10,"strength":"强|中|弱|推测"}}
 ],
 "missing": [
   {"chain":["..."],"outcome_q":1-10,"direction":"效益|危害","reason":"原文哪条措施支持"}
 ]
}
其中 fix 仅在 judgment=fix 时给;keep/drop 时 fix 省略或留空。"""


def get_deepseek_key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    try:
        import tomllib
        with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
            return (tomllib.load(f).get("deepseek_api_key", "") or "").strip()
    except Exception:
        return ""


def get_anthropic_key():
    k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if k:
        return k
    try:
        import tomllib
        with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
            return (tomllib.load(f).get("anthropic_api_key", "") or "").strip()
    except Exception:
        return ""


def _norm(s):
    return re.sub(r"[\s，。、；:：()()【】\[\]\"'`→-]+", "", str(s or "")).lower()


def pathway_key(p):
    """跨次/跨模型对齐用:题号 + 首环节 + 末环节 归一化。"""
    chain = p.get("chain") or []
    return (p.get("outcome_q"), _norm(chain[0]) if chain else "",
            _norm(chain[-1]) if chain else "")


def _find_policy_file(name):
    """name 可能带或不带扩展名;在 POLICY_DIR 定位原文。"""
    cand = os.path.join(POLICY_DIR, name)
    if os.path.exists(cand):
        return cand
    stem = os.path.splitext(name)[0]
    for ext in (".pdf", ".docx"):
        p = os.path.join(POLICY_DIR, stem + ext)
        if os.path.exists(p):
            return p
    hit = glob.glob(os.path.join(POLICY_DIR, glob.escape(stem) + ".*"))
    return hit[0] if hit else None


def _policy_text(name):
    f = _find_policy_file(name)
    if not f:
        return ""
    try:
        with open(f, "rb") as fp:
            text, info = hs.extract_text(os.path.basename(f), fp.read())
        return "" if info.get("error") else (text or "")
    except Exception:
        return ""


def build_audit_user(name, text, res):
    q = hs.QUESTIONS
    lines = ["【政策标题】" + os.path.splitext(name)[0],
             "\n【政策原文(节选)】\n" + (text or "(原文缺失,仅凭下方信息审)")[:5000],
             "\n【引擎研判小结】" + str(res.get("summary", "")),
             "\n【引擎抽取的行动】"]
    for a in res.get("actions", []):
        lines.append(f"- {a.get('id')}: {a.get('action','')[:160]}")
    lines.append("\n【引擎给出的候选路径(逐条判定)】")
    ps = res.get("pathways", [])
    if not ps:
        lines.append("(引擎给了 0 条路径)")
    for p in ps:
        oq = p.get("outcome_q")
        qtext = q[oq - 1] if isinstance(oq, int) and 1 <= oq <= len(q) else "?"
        has_card = "有证据卡" if p.get("cards") else "无卡"
        lines.append(
            f"- {p.get('id')} [题{oq}:{qtext}] 方向={p.get('direction')} "
            f"强度={p.get('strength')} {has_card}\n"
            f"    链条:{' → '.join(p.get('chain', []))}\n"
            f"    引擎依据:{p.get('evidence','')[:160]}")
    lines.append("\n请按系统指令输出 JSON 审计结果。")
    return "\n".join(lines)


def _extract_json(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(s[i:j + 1])
        except Exception:
            return {}
    return {}


def audit_one(name, res, akey, client):
    text = _policy_text(name)
    user = build_audit_user(name, text, res)
    if CROSS_BACKEND == "deepseek":               # DeepSeek 审核:用更强的 v4-pro 审 v4-flash 的输出
        audit = hs._chat_json(SYS_AUDIT, user, akey, max_tokens=8000, temps=(0.0, 0.4),
                              model=CROSS_MODEL)
        return audit, bool(text)
    msg = client.messages.create(
        model=CROSS_MODEL, max_tokens=8000,     # 路径多+漏报的审计响应长,3000 会截断
        system=SYS_AUDIT,
        messages=[{"role": "user", "content": user}])
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    audit = _extract_json(raw)
    if not audit and msg.stop_reason == "max_tokens":
        # 仍截断(极端长)→ 再加倍重试一次
        msg = client.messages.create(
            model=CROSS_MODEL, max_tokens=16000, system=SYS_AUDIT,
            messages=[{"role": "user", "content": user}])
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        audit = _extract_json(raw)
    return audit, bool(text)


def summarize(name, res, audit):
    ds = res.get("pathways", [])
    verds = {p.get("id"): p for p in (audit.get("pathways") or [])}
    keep = [p for p in ds if (verds.get(p.get("id"), {}).get("judgment") == "keep")]
    fix = [p for p in ds if (verds.get(p.get("id"), {}).get("judgment") == "fix")]
    drop = [p for p in ds if (verds.get(p.get("id"), {}).get("judgment") == "drop")]
    missing = audit.get("missing") or []
    errs = {}
    for v in (audit.get("pathways") or []):
        if v.get("judgment") in ("fix", "drop") and v.get("error_type"):
            errs[v["error_type"]] = errs.get(v["error_type"], 0) + 1
    n_cand = len(ds)
    n_judged = len(keep) + len(fix) + len(drop)    # 拿到判定的候选数(<n_cand=审计漏判)
    n_gold = len(keep) + len(fix) + len(missing)   # 修正后认为"该有"的
    precision = len(keep) / n_cand if n_cand else (1.0 if not missing else 0.0)
    precision_soft = (len(keep) + len(fix)) / n_cand if n_cand else precision
    recall = (len(keep) + len(fix)) / n_gold if n_gold else 1.0
    return {
        "name": name,
        "policy_verdict": audit.get("policy_verdict"),
        "verdict_reason": audit.get("verdict_reason", ""),
        "n_candidate": n_cand, "n_judged": n_judged, "n_keep": len(keep),
        "n_fix": len(fix), "n_drop": len(drop), "n_missing": len(missing),
        "precision": round(precision, 3), "precision_soft": round(precision_soft, 3),
        "recall": round(recall, 3), "incomplete": n_judged < n_cand,
        "errors_by_type": errs,
        "audit": audit,
    }


def main():
    if CROSS_BACKEND == "deepseek":
        akey = get_deepseek_key()
        if not akey:
            sys.exit("缺 DEEPSEEK_API_KEY")
        client = None
    else:
        akey = get_anthropic_key()
        if not akey:
            sys.exit("缺 Anthropic key:请在 .streamlit/secrets.toml 配 anthropic_api_key,"
                     "或设环境变量 ANTHROPIC_API_KEY(本仓库公开,严禁把 key 写入任何入库文件)。")
        import anthropic
        client = anthropic.Anthropic(api_key=akey)
    os.makedirs(CROSS_OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(IN_DIR, "*.json")))
    files = [f for f in files if not os.path.basename(f).startswith("_")]
    if not files:
        sys.exit(f"没找到 DeepSeek 输出 @ {IN_DIR}。先跑 run_eval。")
    def _cc_done(f):
        p = os.path.join(CROSS_OUT, os.path.basename(f))
        if not os.path.exists(p):
            return False
        try:
            return not json.load(open(p, encoding="utf-8")).get("error")  # 错误行→重审
        except Exception:
            return False
    todo = [f for f in files if not _cc_done(f)]
    print(f"交叉检验:总 {len(files)} 份,待审 {len(todo)} 份;模型 {CROSS_MODEL};"
          f"并发 {WORKERS}\n原文目录 {POLICY_DIR} → 产物 {CROSS_OUT}")
    done = [0]

    def work(f):
        name_json = os.path.basename(f)
        try:
            d = json.load(open(f, encoding="utf-8"))
            res = d.get("res", {}) or {}
            name = d.get("name") or os.path.splitext(name_json)[0]
            if d.get("error"):
                row = {"name": name, "skip": "DeepSeek解析失败", "audit": {}}
            else:
                audit, had_text = audit_one(name, res, akey, client)
                row = summarize(name, res, audit)
                row["had_text"] = had_text
        except Exception as ex:                          # noqa: BLE001
            row = {"name": name_json, "error": str(ex)[:160], "audit": {}}
        with _lock:
            json.dump(row, open(os.path.join(CROSS_OUT, name_json), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            done[0] += 1
            tag = (row.get("skip") or row.get("error")
                   or f"P准{row.get('precision')} 召{row.get('recall')} "
                      f"删{row.get('n_drop')} 漏{row.get('n_missing')}")
            print(f"[{done[0]}/{len(todo)}] {row.get('name','')[:40]}  {tag}")

    if WORKERS <= 1:
        for f in todo:
            work(f)
    else:
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
            list(ex.map(work, todo))
    build_reports(files)
    print("完成。分歧队列 → " + os.path.join(CROSS_OUT, "_disagreements.md"))


def build_reports(files):
    rows = []
    for f in files:
        p = os.path.join(CROSS_OUT, os.path.basename(f))
        if os.path.exists(p):
            try:
                rows.append(json.load(open(p, encoding="utf-8")))
            except Exception:
                pass
    scored = [r for r in rows if "precision" in r]
    # —— 汇总 ——
    S = ["# 交叉检验汇总\n", f"审计 {len(scored)} 份(有评分)。\n"]
    if scored:
        import statistics as st
        S.append("| 指标 | 值 |\n|---|---|")
        S.append(f"| 平均路径精确率(keep/候选) | {st.mean(r['precision'] for r in scored):.3f} |")
        S.append(f"| 平均路径召回率 | {st.mean(r['recall'] for r in scored):.3f} |")
        S.append(f"| 总候选路径 | {sum(r['n_candidate'] for r in scored)} |")
        S.append(f"| 应删(drop) | {sum(r['n_drop'] for r in scored)} |")
        S.append(f"| 应修(fix) | {sum(r['n_fix'] for r in scored)} |")
        S.append(f"| 漏报(missing) | {sum(r['n_missing'] for r in scored)} |")
        errs = {}
        for r in scored:
            for k, v in (r.get("errors_by_type") or {}).items():
                errs[k] = errs.get(k, 0) + v
        S.append("\n## 错误类型分布\n| 类型 | 次数 |\n|---|---|")
        for k, v in sorted(errs.items(), key=lambda x: -x[1]):
            S.append(f"| {k} | {v} |")
    open(os.path.join(CROSS_OUT, "_summary.md"), "w", encoding="utf-8").write("\n".join(S) + "\n")
    # —— 分歧队列(只列 fix/drop/missing/整体判定异常,供人工抽检)——
    D = ["# 分歧队列(人工只看这里)\n",
         "按严重度:整体假阳/假阴 > drop > missing > fix。每条给引擎原判 + Claude 意见。\n"]
    for r in scored:
        name = r["name"][:60]
        items = []
        pv = r.get("policy_verdict")
        if pv == "B" and r["n_candidate"] >= 2:
            items.append(f"  ⚠整体疑假阳:Claude判B但引擎出{r['n_candidate']}条 — {r.get('verdict_reason','')}")
        if pv == "A" and r["n_candidate"] == 0:
            items.append(f"  ⚠整体疑假阴:Claude判A但引擎0条 — {r.get('verdict_reason','')}")
        for v in (r.get("audit", {}).get("pathways") or []):
            if v.get("judgment") == "drop":
                items.append(f"  ✖drop {v.get('id')} [{v.get('error_type','')}] {v.get('reason','')}")
            elif v.get("judgment") == "fix":
                items.append(f"  ✎fix {v.get('id')} [{v.get('error_type','')}] {v.get('reason','')}")
        for m in (r.get("audit", {}).get("missing") or []):
            items.append(f"  ＋漏 [题{m.get('outcome_q')}] {' → '.join(m.get('chain', []))} — {m.get('reason','')}")
        if items:
            D.append(f"\n### {name}\n" + "\n".join(items))
    open(os.path.join(CROSS_OUT, "_disagreements.md"), "w", encoding="utf-8").write("\n".join(D) + "\n")


if __name__ == "__main__":
    main()
