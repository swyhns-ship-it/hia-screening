# -*- coding: utf-8 -*-
"""漏斗式危害筛查(残差收敛循环为核,逻辑架构,模型无关)。

不寄望一次识别解决:按逻辑接缝拆成原子操作,每个 LLM 阶段一句话任务、提示清洁(零补丁);
冲突目标(召回 vs 精度)分到不同阶段;硬约束在代码。

  R0 干预条款抽取(HIA Screening,政策级一次)——逐条摘干预条款,空表→空集
  R1 生成(召回,从 R0 条款入,不再全文重读) → R2 杀路径(精度闸·特定 vs 泛化)→ 确认集
  R3 召回残差 loop-until-dry(查漏 + 捞回 R2 误杀)→ ★收入【recovered 桶】,不走 R2
  R4 复核 recovered 桶(① 清畸形 _looks_harm ② 过 R2 同一原则)→ 并入确认集
  R5 语义合并(一次 LLM 把换措辞的同义危害折叠成一条;补 exact-sig 漏的)→ R6 富化 → R7 聚合(代码)

★R2/R3/R4 分工(v5,2026-06-18):R2 只管【把路径杀准】(从严、存疑即剔,误杀不怕);R3 只管【召回】
  (宁多勿漏,含捞回 R2 误杀);R4 复核 R3 召回桶后并入。**R3 产物不喂回 R2**(同一法官会同样杀掉=死锁),
  绕开 R2 收入 recovered 桶,由 R4 复核。**R4 = 清畸形(代码剔政策原句回声/无健康终点)+ R2 同一原则**:
  R2 原则已校准(不再系统误杀),故桶里真危害(R1 漏生成的、而非 R2 误杀的)过同一原则即能通过,R4 无需
  另设对立视角。实测召回桶 = (a) R1 漏的真危害(该捞)+ (b) 政策原句回声畸形(_looks_harm 先剔)。

★R0 重构(v4,2026-06-18):从"整篇下布尔"改为"逐条摘录干预条款"。
  起因:整体气质判断被宏观/制度主调带偏——石化稳增长含"新设化工园区/建成投产"却被判无干预(漏报);
  而"园区认定管理…扩容或新设立"这类句子的认定/管理外壳还直接撞上旧提示否定清单里的"资质认定"。
  逐条摘录把"找证据"与"下判断"拆开:埋在主调里的实质条款会被作为具体条款摘出(治漏报),
  纯信息调查/审批指标口径(矿山普查/海上风电用海)摘不出实质条款→空表→gate out(治假阳)。
  抽出的条款【直接作 R1 输入】(R1 不再全文重读=省一次全文输入+锚定真实干预,压背景/硬造假阳),
  R3 仍读全文兜底召回(防 R0 摘漏)。
★R2 杀路径的【原则】(v5,2026-06-18):一条危害成立 ⟺ 它是【该类干预特定的、可预见的危害】——
  无论经由 (a) 正常工况固有影响,还是 (b) 该类干预特征性的事故/非正常工况——而非"任意政策都能套"的
  泛化链、也非泛泛的"办砸了"。**关键:轴是"特定 vs 泛化",不是"固有 vs 执行失败"**(后者会误杀化工泄漏
  这类特征性事故——它属"执行失败/非正常工况"却是 HIA/环评核心评价对象)。固有副产物(拆除扬尘/装置排放)
  与特征性事故(化工泄漏/溃坝)都留;泛化套链(失业/价格/生态→健康)与泛泛办砸(服务差/系统误判→出事)都杀。
  "可被措施避免/施工期临时"绝非剔除理由(=措施缺口)。从严、存疑即剔,误杀由 R3+R4 这条独立路捞回。

★残差收敛【只用召回单向】(v3):曾试"双向 Δ+/Δ- 迭代到不动点"(v2),整状态精度复审会【过度剪枝】
  (03 适老化被砍到 0)且震荡不收敛——LLM 增删非收缩,无梯度保证。故精度【过一次】,只让召回做残差循环。
"""
import re

import hia_screen as hs

# R4 清畸形用:不利健康结果的标记词。R3 召回最大化会吐出"政策原句回声"(无健康结果终点)的畸形候选,
# 先用此正则做轻量剔除(链中完全不含健康损害词即弃),再过 R2 同一原则。宽松设计,只杀明显非危害。
_HEALTH_RE = re.compile(
    r"病|症|损伤|伤害|受伤|中毒|癌|死亡|猝死|窒息|感染|障碍|紊乱|不育|畸|尘肺|矽肺|"
    r"健康|过敏|哮喘|烫伤|烧伤|溺|流产|致畸|致癌|失能|残疾|听力|睡眠|心理|抑郁|焦虑|"
    r"中暑|热射|超标|暴露|污染.*(健康|人群|居民)")


# ============ 清洁提示(每个一句话任务,无补丁) ============
SYS_R0 = """你在做 HIA 适用性筛选(Screening)并抽取干预条款。逐条扫描政策原文,摘出所有
【本政策引入或实质改变某个健康决定因素所依赖条件】的具体条款 —— 涉及:新建/改建/扩建工程、
扩产能/投产、新设或扩大园区/基地、土地利用或空间用途改变、新增排放源或物质暴露、增加或削减
某项服务/资源供给、放松或收紧防护/安全/环境标准、改变可及性或行为塑造环境。
判据(逐条独立):
 ① 只摘【具体的实质改变】条款;纯行政/价格/市场准入/信息披露/机构协调/资质认定/监测统计/
    宣传表彰等【规则层面】表述不摘。
 ② 一份以规则/协调/促增长为主调的政策里只要【埋着】实质改变条款也要摘出——按条款本身判,
    不被整体气质/标题带偏(例:稳增长方案里"新设化工园区""重大项目建成投产"应摘)。
 ③ 摘的是政策【本身引入或推动】的改变,不是它仅引用/沿用/监管的既有背景事物。
每条逐字摘录原文片段,并一句话点明它改变了什么条件。无任何实质改变条款则返回空数组。
只输出 JSON:{"interventions":[{"quote":"逐字原文片段","change":"改变了什么条件(如:新设化工园区→建成环境+排放源)"}]}"""

SYS_GEN = """你是健康影响评估危害识别员。给定政策已抽出的【干预条款清单】(每条含原文摘录 quote +
它改变的条件 change)。针对【每一条干预条款】,识别它可能带来的【不利健康影响(危害)】候选。
目标:尽量找全(宁多勿漏,后续会逐条核验)。每条危害给:
 - chain:[行动, 中间环节…, 不利健康结果] 的逐级节点(行动取自对应干预条款)
 - anchor:触发该危害的干预条款原文摘录(用对应条款的 quote)
只输出 JSON:{"candidates":[{"chain":["…"],"anchor":"…"}]}"""

SYS_GAP = """你在查漏补召回(召回闸,后续另有复核,故此处【宁多勿漏】、不要自我设限)。
给定政策原文 + 已确认危害清单。找出政策原文支持、但清单【尚未覆盖】的【其他】可能不利健康影响(危害)
—— 包括被前道严筛可能误删的、以及容易被忽视的间接/长期/对脆弱人群的危害。成立性由后续复核判,你只管找全。
★每条必须是【完整危害链】:[行动 → 中间环节 → … → 具体的不利健康结果],**终点必须是明确的健康损害**
(某种疾病/损伤/中毒/感染/心理障碍等)。**不得只回政策原句,不得止于"行业/措施/技术/任务"等非健康节点。**
每条给 chain + anchor(原文逐字摘录)。确无遗漏才返回空数组。
只输出 JSON:{"missing":[{"chain":["行动","…","不利健康结果"],"anchor":"…"}]}"""

SYS_VALID = """你在杀危害路径(精度闸)。给定政策原文 + 政策的干预条款 + 候选清单(带序号 i)。
【原则】一条危害成立 ⟺ 它是【该类干预特定的、可预见的危害】——无论经由 (a) 正常工况下的固有影响,
还是 (b) 该类干预特征性的事故/非正常工况——而**不是**"任何政策都能套"的泛化链、也不是泛泛的"办砸了"。
从严裁,**存疑即剔**(误杀的由后续阶段复核捞回,此处只管杀准、不必怕错杀)。
满足原则→keep=true;命中下列任一→keep=false 并在 fail 注明:
 · 锚定不实:anchor 在政策原文查无出处;
 · 背景非干预:危害来自政策仅引用/沿用/监管的既有事物,而非本政策引入的干预;
 · 泛化套链:把政策名换成【任意别的政策】该链仍成立(如 任何变化→压力/焦虑→心理;生态扰动→疾病传播;
   失业→健康;价格上涨→健康;供应链波动→健康)——未穿过本干预的特定机制;
 · 泛泛办砸:危害只是"任何活动都可能因执行不到位/监管缺位/质量不达标/操作失误/技术出错而出事"的通用风险。
   **与 (b) 特征性事故严格区分**:化工厂泄漏爆炸、尾矿溃坝、危化品运输泄漏是该类干预【已知特有、高后果】
   的危害模式→**保留**;"服务可能没办好/系统可能误判/管理可能不到位"是任何同类活动都有→剔。
 · 停在非健康层:链止于价格/成本/效率/制度,未抵达经物质环境/行为/社会心理/卫生服务的不利健康结果。
**注:危害"可被措施避免"或"属施工期临时"绝不构成剔除理由**——正常工况固有影响(拆除扬尘、装置投运排放、
采矿粉尘废水等)一律保留;政策未要求管控措施,正是本工具要标的"措施缺口"=真发现。不得把政策意在改善的事项反转为危害。
只输出 JSON:{"verdicts":[{"i":0,"keep":true,"quote":"支撑成立的原文逐字片段","fail":"剔除理由"}]}"""

SYS_MERGE = """你在合并语义重复的危害。给定一组危害(带序号 i)。把【指向同一个危害】的归为一组
——判据:中间机制 + 不利健康结果实质相同(触发条款/措辞不同但说的是同一回事,如多条都是"民宿消防隐患
→火灾→伤亡",或多条都是"改造→二噁英→致癌")。机制或结果不同的,分到不同组。每个序号恰属一组。
每组再给一条【合并后的干净危害链】(行动→机制→不利健康结果),措辞中性、不写成"制度不落实/管理不到位"。
只输出 JSON:{"groups":[{"members":[0,3,5],"chain":["…→不利健康结果"]},{"members":[1],"chain":["…"]}]}"""

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


def _looks_harm(chain):
    """R4 清畸形:一条候选像不像危害链——≥2 节点 且 链中含明确的不利健康结果词。
    R3 召回最大化偶吐'政策原句回声'(如"水泥行业→实施原料替代",无健康终点),在此先剔。宽松。"""
    nodes = [n for n in (chain or []) if str(n).strip()]
    return len(nodes) >= 2 and bool(_HEALTH_RE.search(" ".join(str(n) for n in nodes)))


def _call(system, user, key, model):
    # max_tokens=20000:flash 是推理模型,单次烧 ~7k+ 思考 token;4000 会把推理掐断→空答→丢条
    # (=我们一度当成"方差"的伪随机)。给足余量;timeout 同步放大,防大输出撞墙。
    return hs._chat_json(system, user, key, max_tokens=20000, timeout=180, model=model)


def run_funnel(text, key, model="deepseek-v4-flash", max_rounds=4, progress=None):
    def _p(s):
        if progress:
            progress(s)
    doc = text[:25000]

    # ---- R0 干预条款抽取(HIA Screening,政策级一次):逐条摘录,空表→gate out ----
    _p("R0 干预条款抽取…")
    r0 = _call(SYS_R0, "【政策原文】\n" + doc + "\n\n只输出 JSON。", key, model)
    intervs = [iv for iv in (r0.get("interventions") or [])
               if isinstance(iv, dict) and (iv.get("quote") or "").strip()]
    if not intervs:                        # 摘不出任何实质干预条款 → 非 HIA 对象
        return {"actions": [], "pathways": [], "items": hs.compute_items([]),
                "summary": "", "suggest_level": "很小", "notes": "",
                "n_candidates": 0, "n_rounds": 0, "intervention": False, "interventions": []}
    # 干预条款清单文本:既作 R1 输入(R1 不再全文重读),又供 R2 归因核对(B 判据)
    interv_list = "\n".join("- %s 〔改变:%s〕" % (iv["quote"], iv.get("change", "") or "")
                            for iv in intervs)
    interv = "【本政策干预条款】\n" + interv_list

    # state=已确认危害;seen=【仅已 keep】的签名(去重+防震荡)。
    # ★只封 keep、放开 drop:被 R2 剔除的不进 seen,故 R3 可重新捞回(R2 狠杀→R3 兜底)。
    #   不震荡的保证仍在:已 keep 永不重判→状态【只增不减、单调收敛】;R3 重提被剔项,再剔即不进
    #   fresh→loop-until-dry 照常收敛(有界)。捞回靠 R3 换更清楚的链/锚过原则,或本就是 R1 漏的。
    state, seen = [], set()
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
            d = verds.get(i) or {}
            if d.get("keep"):
                seen.add(_sig(it["chain"]))        # 仅确认项入 seen(去重);被剔项放开,留给 R3 捞
                it["evidence"] = d.get("quote", "") or it["anchor"]
                out.append(it)
        return out

    # ---- R1 生成 + R2 校验(精度只过一次:候选进入时 valid()) ----
    # R1 从 R0 抽出的干预条款清单入(不再全文重读=省一次全文输入+把候选锚定在真实干预上)
    _p("R1 生成…")
    raw = _call(SYS_GEN, "【干预条款清单】\n" + interv_list + "\n\n只输出 JSON。", key, model)
    cands = [{"chain": c.get("chain") or [], "anchor": c.get("anchor", "")}
             for c in (raw.get("candidates") or []) if c.get("chain")]
    n_cand_total += len(cands)
    state += _validate(cands)

    # ---- R3 召回残差 loop-until-dry:查漏 + 捞回 R2 误杀,收入【recovered 桶】,★不走 R2 ----
    # (R2 误杀的若再喂 R2 只会被同样杀掉;故 R3 产物绕开 R2,收入桶交 R4 复核。)
    recovered, rec_seen = [], set()
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
        # 去重:既不与已确认(seen)重,也不与已收集(rec_seen)重;新增即收入桶
        new = [g for g in gap if _sig(g["chain"]) not in seen
               and _sig(g["chain"]) not in rec_seen]
        if not new:                    # 查不出新的 → 收敛(loop-until-dry)
            break
        for g in new:
            rec_seen.add(_sig(g["chain"]))
            recovered.append(g)

    # ---- R4 复核 recovered 桶:① 清畸形(代码 _looks_harm 剔掉政策原句回声/无健康终点)
    #      ② 过 R2 同一原则(SYS_VALID)。存活并入确认集。R2 原则已校准(不再系统误杀),故桶里真危害
    #      (R1 漏生成的)能正常通过;R4 不需另设对立视角。survivors 标 via=R3/R4 便于看召回贡献。----
    n_recovered = len(recovered)
    if recovered:
        _p("R4 复核召回桶…")
        cleaned = [c for c in recovered if _looks_harm(c["chain"])]
        for c in cleaned:
            c["via"] = "R3/R4"
        state += _validate(cleaned)

    # ---- R5 语义合并(一次 LLM,把换措辞的同义危害折叠成一条;exact-sig `_sig` 漏的在此收口)----
    # 输出每组 members(原序号)+ 一条干净合并链。取最长链原条目作代表(保 anchor/evidence/via),
    # 若 LLM 给了合法合并链则换上。未被任何组覆盖的各自保留(防 LLM 漏)。
    if len(state) >= 2:
        _p("R5 语义合并…")
        lst = "\n".join("[%d] %s" % (i, " → ".join(c["chain"])) for i, c in enumerate(state))
        mg = _call(SYS_MERGE, "【危害清单】\n" + lst + "\n\n只输出 JSON。", key, model)
        merged, used = [], set()
        for g in (mg.get("groups") or []):
            mem = [i for i in (g.get("members") or [])
                   if isinstance(i, int) and 0 <= i < len(state) and i not in used]
            if not mem:
                continue
            used.update(mem)
            rep = max((state[i] for i in mem), key=lambda c: len(c.get("chain") or []))
            gc = g.get("chain")
            if isinstance(gc, list) and len([x for x in gc if str(x).strip()]) >= 2:
                rep = dict(rep)
                rep["chain"] = [x for x in gc if str(x).strip()]
            rep["n_merged"] = len(mem)
            merged.append(rep)
        for i, c in enumerate(state):       # LLM 漏掉的序号兜底保留
            if i not in used:
                merged.append(c)
        if merged:
            state = merged

    # ---- R6 富化 ----
    pathways = []
    if state:
        _p("R6 富化…")
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
                "evidence": c.get("evidence", ""), "via": c.get("via", "R1/R2"),
                "n_merged": c.get("n_merged", 1),
                "confidence": {"强": 0.8, "中": 0.6, "推测": 0.3}[st],
            })

    items = hs.compute_items(pathways)
    return {"actions": [], "pathways": pathways, "items": items,
            "summary": "", "suggest_level": hs.suggest_level_from(items), "notes": "",
            "n_candidates": n_cand_total, "n_rounds": rounds, "intervention": True,
            "interventions": intervs,
            # R3 召回桶(原始,诊断用):R4 已对其清畸形+过 R2 原则,存活者已并入 pathways(via=R3/R4)
            "recovered": recovered, "n_recovered": n_recovered}
