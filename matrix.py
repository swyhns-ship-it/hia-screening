# -*- coding: utf-8 -*-
"""HIA 引擎 v6:「干预 × 决定因素」影响矩阵(推倒线性漏斗,见 docs/HIA引擎重构方案_影响矩阵.md)。

交付物 = 矩阵格子(干预 × 决定因素),每格答全 5 问:有无危害 / 路径 / 有无措施 / 建议措施 / 参考标准。
脊椎 = determinants.py 的枢纽:危害问法清单(S2)+ outcomes(题号)+ triggering(泛化门)。

管线(3 次 LLM + 代码聚合):
  S1   干预抽取(LLM,不 gate,分类整合成高层级干预)
  S2   危害筛查矩阵(LLM:每条干预 × 37 枢纽危害问法 → (干预,因素,why);含"宁多勿漏"查全,已吸收原 S2.5)
  S3+S4 合并(LLM 一次:逐格补完整路径 + 选题号 + 复核 keep,精度从严杀泛化/间接/臆测)
  S7   聚合 10 题(代码,复用 hs.compute_items)
  --- 后续:S5 措施判定(政策有无措施)、S6 建议措施+参考标准(改提示词需用户同意)---

不重 =(干预,因素)主键(代码);不漏因素 = 固定清单逐列;不泛化 = 只问触发性枢纽 + S4 杀间接/泛化。
"""
import re

import determinants as D
import hia_screen as hs

# ============ 脊椎:37 触发性枢纽的【危害问法】(方向已校正:暴露类"增加/加剧",好东西类"减少/削弱")
#   引擎专属措辞,determinants.py 不改。INCOME/EDU(结构性·非触发)不在内 → 泛化套链从源头挡。
HARM_Q = {
    # 〔物质环境 20〕
    "AIR": "加剧大气污染(PM/NOx/SO₂/VOCs)",
    "NOISE": "增加噪声/振动",
    "WATER": "污染水体、损害饮用水安全",
    "SOIL": "造成土壤/重金属污染",
    "CHEM": "增加危险化学品暴露",
    "WASTE": "增加固废/危废暴露",
    "WORK_ENV": "增加职业危害/工伤暴露",
    "INDOOR_AIR": "加剧室内空气污染",
    "ODOR": "产生恶臭/异味",
    "VECTOR": "增加病媒孳生(蚊蝇鼠)",
    "RADIATION": "增加电离/非电离辐射暴露",
    "HEAT": "加剧高温/热暴露",
    "CLIMATE": "增加碳排放/气候风险",
    "HOUSING": "恶化居住条件(潮湿/霉菌/结构隐患)",
    "CROWDING": "加剧居住拥挤/人群聚集",
    "SANITATION": "恶化环境卫生/污水处理",
    "FOOD": "损害食品安全/食物供给",
    "ROAD": "增加道路交通事故/伤害",
    "BUILT_SAFETY": "增加建筑/消防/跌倒等安全隐患",
    "GREEN": "减少绿地/开放空间可达",
    # 〔行为 4〕
    "TOBACCO": "增加烟草暴露",
    "ALCOHOL": "增加有害饮酒",
    "DIET": "恶化膳食营养(高盐高糖/营养不足)",
    "PA": "减少体力活动机会",
    # 〔社会心理 6〕
    "STRESS": "加剧心理社会应激",
    "JOB_STRAIN": "加剧工作压力/就业不安全",
    "FINANCIAL_STRESS": "加剧财务压力/降低可负担性",
    "SOCIAL_SUPPORT": "削弱社会支持、加剧社会排斥隔离",
    "CONTROL": "削弱掌控感/自主性",
    "VIOLENCE": "增加暴力/暴力威胁",
    # 〔卫生系统 7〕
    "ACCESS": "降低卫生服务可及性",
    "QUALITY": "降低服务质量/回应性",
    "HEALTH_INVEST": "削减卫生健康投入保障",
    "INSURANCE": "削弱医保、增加灾难性支出",
    "EQUITY": "扩大健康不公平",
    "REGIONAL": "加剧区域资源配置失衡",
    "EMERGENCY": "削弱突发公共卫生应对",
}

_BY_ID = {h["id"]: h for h in D.HUBS}
# 触发性枢纽 = 在 HARM_Q 里且 determinants 未标 triggering=False
HUB_IDS = [h["id"] for h in D.HUBS
           if h.get("triggering") is not False and h["id"] in HARM_Q]


def hub_name(hid):
    return (_BY_ID.get(hid) or {}).get("name", hid)


def hub_outcomes(hid):
    return (_BY_ID.get(hid) or {}).get("outcomes", []) or []


def _checklist():
    """按 CSDH 层分组的危害问法清单文本(喂 S2)。"""
    layers = ["物质环境", "行为生物", "社会心理", "卫生系统"]
    out = []
    for lay in layers:
        items = [f"{hid} {HARM_Q[hid]}?" for hid in HUB_IDS
                 if (_BY_ID[hid].get("layer") == lay)]
        if items:
            out.append(f"〔{lay}〕" + " · ".join(items))
    return "\n".join(out)


# ============ 清洁提示(每段一句话任务) ============
SYS_S1 = """你在做 HIA 干预抽取(供逐条筛健康危害)。通读政策,列出它【引入或实质改变】的干预——
要【分类整合、不要逐句罗列】:同一类实质行动的多条表述【合并成一条干预】,给提炼(gist)+ 支撑原文
(quotes,可多条)。目标是【少而全】的高层级干预清单(通常 ≤ 15 条)。
 · 穿透外壳:政策即便以"规划/指引/管理办法/方案/意见"的形式出现,只要它针对某项实质活动(建设/改造/
   开发/产业等),就把【那项实质活动本身】作为干预抽出,不因形式是规则文件而跳过其指向的实质活动。
 · 干预的范围:凡【引入或实质改变】物理建设、产能生产、园区基地、资源开发(采矿取水用地)、排放处置、
   服务或资源供给的增减、防护标准的松紧、某项管制的放开或收紧、交通消费等行为塑造条件者,均属之。
 · 只抽政策真实写到或明确指向的;绝不臆造。**不判"有没有害"——只列全做了什么。**
只输出 JSON:{"interventions":[{"id":"I1","gist":"一句话提炼","quotes":["原文片段","…"]}]}"""

SYS_S2 = """你在做 HIA 危害筛查。给定政策的【干预清单】+【健康决定因素危害清单】。
对【每一条干预】,逐项对照危害清单判断该项危害是否成立(逐条干预、逐项危害都过一遍,宁多勿漏)。判据(两条都满足才命中):
 · 方向:本干预使该项危害【增加】;若它【减少/防治/控制】该危害,或与之无关 → 否。
 · 直接性:危害须由本干预【自身的物理/实质内容】直接引起——它建设、生产、排放、占用、暴露,或放松某
   防护标准;施工期或正常运行期的固有影响都算直接(不因"临时"而排除)。反之,危害若仅源于政策【笼统地
   刺激了更多活动/消费/人流】这一间接渠道(任何刺激性政策都会有的弥漫副产物),→ 否。
命中给 hub_id + 一句【落到本干预具体内容上】的理由;一条干预可命中多项,也可一项都不命中(无害则不输出)。
【健康决定因素危害清单(逐项问)】
%s
只输出 JSON:{"cells":[{"intervention_id":"I1","hub_id":"AIR","why":"…"}]}""" % _checklist()

SYS_S34 = """你在为危害格子补全路径并复核是否成立(精度从严)。给定若干格子,每格含:干预、决定因素、为何有害、初筛题候选。
对每格:
① 写完整因果路径 chain:[干预 → (中间环节…) → 决定因素 → 具体不利健康结果],终点须是明确健康损害;路径节点 ≤ %d;
② 从初筛题候选里选最贴的一个 outcome_q;
③ 判 keep——仅当它是【本干预直接、特定、实质】的危害才 keep=true。从严裁,以下一律 keep=false:
   · 泛化/间接:危害是政策【刺激、鼓励或诱导某活动、消费、产业发展】所衍生的下游后果(政策本身并未直接
     建设/生产/排放/暴露),或是【任何同类政策都会有】的通用属性;
   · 臆测实现:危害依赖本干预【未必经历】的实现假设(该干预可不经该有害物理过程而达成);
   · 微弱不实:暴露微弱、弥漫、可忽略,无实质健康意义;
   · 锚定不实:chain 不由该干预支持。
   (注:政策直接建设/运营/拆除/放松防护的固有暴露,即便属施工期或短期,仍属直接且实质 → 保留。)
只输出 JSON:{"results":[{"i":0,"chain":["…","…不利健康结果"],"outcome_q":6,"keep":true,"reason":"删则写原因"}]}"""


def _call(system, user, key, model):
    # flash 是推理模型,单调用烧 ~7k 思考 token;20000 留足余量防截断(见漏斗第六段实锤)
    return hs._chat_json(system, user, key, max_tokens=20000, timeout=180, model=model)


def _cell(intervention_id, hid, why):
    return {"intervention_id": intervention_id, "hub_id": hid, "hub_name": hub_name(hid),
            "why": why or "", "outcome_candidates": hub_outcomes(hid)}


def aggregate(cells):
    """S7:存活危害格子 → 初筛表 10 题判定(纯代码,复用 hs.compute_items)。
    ★暂注:strength(S3 未评)默认'中'、mitigation(S5 未建)默认'未提及' → 现阶段
    "是" = 该题有存活危害(=可能有不利影响,正是 10 题本意);措施缺口那层待 S5 接上。"""
    paths = [{"outcome_q": c["outcome_q"], "direction": "风险", "strength": "中",
              "status": "文档支持", "mitigation": "未提及", "confidence": 0.6,
              "chain": c.get("chain") or [c.get("why", "")], "measures": ""}
             for c in (cells or []) if c.get("outcome_q")]
    return hs.compute_items(paths)


def run_matrix(text, key, model="deepseek-v4-flash", max_path=4, progress=None):
    """3 次 LLM:S1 抽取 → S2 矩阵(含宁多勿漏查全)→ S3+S4 合并(补路径+复核)→ S7 代码聚合 10 题。
    返回 {interventions, cells(存活), killed(S4 删的), items(10 题判定)}。"""
    def _p(s):
        if progress:
            progress(s)
    doc = text[:25000]

    # ---- S1 干预抽取(不 gate) ----
    _p("S1 干预抽取…")
    r = _call(SYS_S1, "【政策原文】\n" + doc + "\n\n只输出 JSON。", key, model)
    def _quotes(iv):
        qs = iv.get("quotes")
        if isinstance(qs, str):
            qs = [qs]
        qs = [str(q).strip() for q in (qs or []) if str(q).strip()]
        if not qs and (iv.get("quote") or "").strip():    # 兼容旧 quote 字段
            qs = [iv["quote"].strip()]
        return qs

    intervs = []
    for i, iv in enumerate(r.get("interventions") or [], 1):
        gist = (iv.get("gist") or "").strip()
        qs = _quotes(iv)
        if gist or qs:
            intervs.append({"id": "I%d" % i, "gist": gist or qs[0][:40], "quotes": qs})
    if not intervs:
        return {"interventions": [], "cells": []}
    iv_by_id = {x["id"]: x for x in intervs}
    iv_list = "\n".join("%s〔%s〕%s" % (x["id"], x["gist"], " / ".join(x["quotes"])[:120])
                        for x in intervs)

    # ---- S2 危害筛查矩阵 ----
    _p("S2 危害筛查矩阵…")
    valid_pairs = set()        # (干预id, hub) 去重主键
    cells = []

    def _add(iid, hid, why):
        if iid in iv_by_id and hid in HARM_Q and (iid, hid) not in valid_pairs:
            valid_pairs.add((iid, hid))
            cells.append(_cell(iid, hid, why))

    # S2 含"宁多勿漏"查全(已吸收原 S2.5,省一次调用)
    r = _call(SYS_S2, "【干预清单】\n" + iv_list + "\n\n只输出 JSON。", key, model)
    for c in (r.get("cells") or []):
        _add(c.get("intervention_id"), c.get("hub_id"), c.get("why"))

    if not cells:
        return {"interventions": intervs, "cells": [], "killed": [], "items": aggregate([])}

    # ---- S3+S4 合并(一次调用:逐格补路径 + 选题号 + 判 keep,精度从严) ----
    _p("S3+S4 补路径+复核…")
    lst = "\n".join("[%d] 干预〔%s〕| 因素:%s | 为何:%s | 题候选:%s"
                    % (i, iv_by_id[c["intervention_id"]]["gist"][:30], c["hub_name"],
                       c["why"][:46], "/".join(c["outcome_candidates"]))
                    for i, c in enumerate(cells))
    r = _call(SYS_S34, "【危害格子】\n" + lst + "\n\n路径节点 ≤ %d。只输出 JSON。" % max_path, key, model)
    rm = {d.get("i"): d for d in (r.get("results") or [])}
    kept, killed = [], []
    for i, c in enumerate(cells):
        d = rm.get(i) or {}
        c["chain"] = [str(x).strip() for x in (d.get("chain") or []) if str(x).strip()]
        cand = [int(x[1:]) for x in c["outcome_candidates"] if str(x).startswith("Q")]
        try:
            q = int(d.get("outcome_q"))
        except Exception:
            q = None
        c["outcome_q"] = q if q in cand else (cand[0] if cand else None)
        if d.get("keep"):
            kept.append(c)
        else:
            c["_reason"] = d.get("reason", "")
            killed.append(c)

    # ---- S7 聚合 10 题(代码) ----
    _p("S7 聚合…")
    items = aggregate(kept)
    return {"interventions": intervs, "cells": kept, "killed": killed, "items": items}
