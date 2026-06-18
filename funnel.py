# -*- coding: utf-8 -*-
"""漏斗式危害筛查(残差收敛循环为核,逻辑架构,模型无关)。

不寄望一次识别解决:按逻辑接缝拆成原子操作,每个 LLM 阶段一句话任务、提示清洁(零补丁);
冲突目标(召回 vs 精度)分到不同阶段;硬约束在代码。

  R0 干预性筛选(HIA Screening,政策级一次)——无干预→空集
  R1 生成(召回) → R2 valid() 三判据(精度·过一次)
  R3 召回残差 loop-until-dry(残差核心·只此一向:查漏→valid()→并入,查不出新的即收敛)
  R4 去重(代码) → R5 富化(题号/措施缺口/建议措施/强度) → R6 聚合(代码)

R0 = HIA 的"对象必须是含干预的 proposed policy/program/project":判"有无干预"
     (引入或实质改变某健康决定因素所依赖的条件——含服务/资源/保护标准的增减,不只物理建设)。
valid() 三判据:A 原文锚定 / B 归因于本政策干预(非既有背景) / C 穿中间性决定因素。

★实验定稿(v3,2026-06-18):残差收敛【只用召回单向】。曾试"双向 Δ+/Δ- 迭代到不动点"(v2),
  整状态精度复审迭代会【过度剪枝】(03 适老化被砍到 0)且震荡不收敛——LLM 增删非收缩,不像
  ResNet 残差有梯度保证。故精度【过一次】(候选进入时 valid()),只让召回做残差循环。
"""
import hia_screen as hs


# ============ 清洁提示(每个一句话任务,无补丁) ============
SYS_R0 = """你在做 HIA 适用性筛选(Screening)。HIA 的对象是【含干预的提案】(proposed policy/
program/project)。判断本政策是否【引入或实质改变了某个健康决定因素所依赖的条件】——建成环境/
土地利用/排放/物质暴露/服务供给/资源配置/保护标准/可及性/行为塑造环境(注:撤销服务、削减投入、
放松防护标准等"非建设型"实质改变也算干预)。
仅调整行政、价格、市场准入、信息披露、机构协调、资质认定等【规则层面】而不改变上述实质条件的,
不构成干预。
只输出 JSON:{"intervention": true/false, "what": "若有,一句话:引入了什么实质改变"}"""

SYS_GEN = """你是健康影响评估危害识别员。阅读政策原文,列出其中可能的【不利健康影响(危害)】候选。
目标:尽量找全(宁多勿漏,后续会逐条核验)。每条给:
 - chain:[行动, 中间环节…, 不利健康结果] 的逐级节点
 - anchor:触发该危害的政策原文片段(逐字摘录)
只输出 JSON:{"candidates":[{"chain":["…"],"anchor":"…"}]}"""

SYS_GAP = """你在查漏。给定政策原文 + 已确认的危害清单。找出政策原文支持、但清单【尚未覆盖】的
【其他】不利健康影响(危害)。若没有遗漏,返回空数组。每条给 chain + anchor。
只输出 JSON:{"missing":[{"chain":["…"],"anchor":"…"}]}"""

SYS_VALID = """你在核验危害候选是否成立。给定政策原文 + 政策的干预内容 + 候选清单(带序号 i)。
对每条【独立】判断是否同时满足三条:
 A 原文锚定:anchor 在政策原文中确有出处;
 B 干预归因:该危害源于本政策【所引入的干预】,而非政策仅监管/引用/沿用的既有背景事物;
 C 健康机制:chain 经由某个中间性健康决定因素(物质环境/行为/社会心理/卫生服务)抵达不利健康
   结果,而非停留在价格/成本/效率/制度层面。
三条全满足→keep=true;否则→keep=false 并在 fail 注明缺的判据(A/B/C)。
只输出 JSON:{"verdicts":[{"i":0,"keep":true,"quote":"支撑A的原文逐字片段","fail":""}]}"""

SYS_ENRICH = """你在为已确认的危害补充判断。给定政策原文 + 危害清单(带序号 i)。对每条给:
 - outcome_q:落到下面哪个初筛问题(取 1–10)
 - mitigation:政策原文对该危害是否已有控制措施 —— 已含 / 不足 / 未提及
 - measures:结合本政策背景的建议措施(未提及=建议新增、不足=建议强化、已含=可进一步)
 - strength:机制确凿且证据广泛=强;一般合理=中;依赖较多假设=推测
【10 个初筛问题】
%s
只输出 JSON:{"items":[{"i":0,"outcome_q":3,"mitigation":"未提及","measures":"…","strength":"中"}]}""" \
    % "\n".join("%d. %s" % (i + 1, q) for i, q in enumerate(hs.QUESTIONS))


def _sig(chain):
    nodes = []
    for c in chain or []:
        for part in str(c).replace("→", "\n").split("\n"):
            p = "".join(part.split())
            if p:
                nodes.append(p)
    return tuple(nodes)


def _call(system, user, key, model):
    return hs._chat_json(system, user, key, max_tokens=4000, model=model)


def run_funnel(text, key, model="deepseek-v4-flash", max_rounds=4, progress=None):
    def _p(s):
        if progress:
            progress(s)
    doc = text[:25000]

    # ---- R0 干预性筛选(HIA Screening,政策级一次) ----
    _p("R0 干预性筛选…")
    r0 = _call(SYS_R0, "【政策原文】\n" + doc + "\n\n只输出 JSON。", key, model)
    if not r0.get("intervention"):
        return {"actions": [], "pathways": [], "items": hs.compute_items([]),
                "summary": "", "suggest_level": "很小", "notes": "",
                "n_candidates": 0, "n_rounds": 0, "intervention": False}
    interv = "【本政策干预】" + (r0.get("what", "") or "(已判定有干预)")

    state, seen = [], set()        # state=已确认危害;seen=处理过的签名(防震荡:剔除的不再捞回)
    n_cand_total = 0

    def _validate(items):
        items = [it for it in items if _sig(it["chain"]) not in seen]
        if not items:
            return []
        lst = "\n".join("[%d] %s | 原文锚:%s" % (i, " → ".join(it["chain"]), it["anchor"])
                        for i, it in enumerate(items))
        v = _call(SYS_VALID, "【政策原文】\n" + doc + "\n" + interv + "\n\n【候选】\n" + lst
                  + "\n\n只输出 JSON。", key, model)
        verds = {d.get("i"): d for d in (v.get("verdicts") or [])}
        out = []
        for i, it in enumerate(items):
            seen.add(_sig(it["chain"]))
            d = verds.get(i) or {}
            if d.get("keep"):
                it["evidence"] = d.get("quote", "") or it["anchor"]
                out.append(it)
        return out

    # ---- R1 生成 + R2 校验(精度只过一次:候选进入时 valid()) ----
    _p("R1 生成…")
    raw = _call(SYS_GEN, "【政策原文】\n" + doc + "\n\n只输出 JSON。", key, model)
    cands = [{"chain": c.get("chain") or [], "anchor": c.get("anchor", "")}
             for c in (raw.get("candidates") or []) if c.get("chain")]
    n_cand_total += len(cands)
    state += _validate(cands)

    # ---- R3 召回残差 loop-until-dry(残差核心,只此一向;不做双向 Δ-,避免过度剪枝) ----
    rounds = 0
    for rnd in range(max_rounds):
        rounds = rnd + 1
        _p("R3 查漏(第%d轮)…" % rounds)
        clist = "\n".join("- " + " → ".join(c["chain"]) for c in state) or "(暂无)"
        raw = _call(SYS_GAP, "【政策原文】\n" + doc + "\n\n【已确认危害】\n" + clist
                    + "\n\n只输出 JSON。", key, model)
        gap = [{"chain": c.get("chain") or [], "anchor": c.get("anchor", "")}
               for c in (raw.get("missing") or []) if c.get("chain")]
        n_cand_total += len(gap)
        fresh = _validate(gap)
        if not fresh:                  # 查不出新的有效危害 → 收敛(loop-until-dry)
            break
        state += fresh

    # ---- R5 富化 ----
    pathways = []
    if state:
        _p("R5 富化…")
        lst = "\n".join("[%d] %s" % (i, " → ".join(c["chain"])) for i, c in enumerate(state))
        e = _call(SYS_ENRICH, "【政策原文】\n" + doc + "\n\n【危害】\n" + lst + "\n\n只输出 JSON。",
                  key, model)
        em = {d.get("i"): d for d in (e.get("items") or [])}
        for i, c in enumerate(state):
            d = em.get(i) or {}
            try:
                q = int(d.get("outcome_q"))
            except Exception:
                continue
            if not (1 <= q <= len(hs.QUESTIONS)):
                continue
            st = d.get("strength") if d.get("strength") in hs.STRENGTHS else "推测"
            mit = d.get("mitigation") if d.get("mitigation") in ("已含", "不足", "未提及") else "未提及"
            pathways.append({
                "id": "P%d" % (len(pathways) + 1), "action_id": "A1",
                "chain": [n for x in c["chain"]
                          for n in [s.strip() for s in str(x).replace("→", "\n").split("\n")] if n],
                "outcome_q": q, "direction": "风险", "strength": st, "status": "文档支持",
                "mitigation": mit, "measures": d.get("measures", "") or "",
                "evidence": c.get("evidence", ""),
                "confidence": {"强": 0.8, "中": 0.6, "推测": 0.3}[st],
            })

    items = hs.compute_items(pathways)
    return {"actions": [], "pathways": pathways, "items": items,
            "summary": "", "suggest_level": hs.suggest_level_from(items), "notes": "",
            "n_candidates": n_cand_total, "n_rounds": rounds, "intervention": True}
