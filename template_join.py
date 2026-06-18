# -*- coding: utf-8 -*-
"""运行时模板 ID-join —— 危害路径 → 决定因素枢纽 → 验证版危害模板,挂【同类政策参考做法】。

架构定位(见会话架构讨论):
  ID-join 做【分类/连接】、向量检索做【相似度排序】,二者不同层。本场景目标空间是
  封闭本体(CSDH 39 枢纽),且工具卖点是"有据可查/可审计",故 **符号优先**:
    一条危害路径的 chain 必然穿过暴露环节(决定因素枢纽)→ resolve_all(chain) 落到枢纽 ID
    → 按 (hub, outcome_q) 精确 join `eval/templates_harm.json` 的验证版模板
    → 把该枢纽下经 pro 审核的代表性【参考措施】+ 措施缺口分布挂到 p["template_ref"]。
  全程**确定性、零 API、可复现**,改一处别名表全局生效(可审计)。

★参考 vs 定制(本工具措施逻辑,见会话):
  · p["measures"]   = 引擎结合**本政策背景**现场生成的建议措施(定制),始终生成,口吻随 mitigation;
  · p["template_ref"] = 历史**同类政策**的通用做法(参考 checklist),来源透明,**不冒充定制、不覆盖 measures**。
  · p["mitigation"] = 政策原文已有措施的判断(已含/不足/未提及),驱动"是/否"判定(增量措施不改判定)。

为什么接在【展开之后】而非 hint_builder(展开之前):
  实测 resolve 在"措施文本(actions)"上仅 ~16% 命中(措施不含暴露别名),
  在"整条 chain"上 ~83%+ 命中(暴露环节都在链里)。故 post-gen 回填,不做 pre-gen 注入。

向量检索作为后续【兜底】:仅当留出集实测 resolve→None 占比显著、或同枢纽内措施过多需
  语义排序时再引入(template_retrieval.py 重指到本文件即可),现阶段不需要。
"""
import ast
import json
import os

import determinants as D

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_PATH = os.path.join(ROOT, "eval", "templates_harm.json")

_TEMPLATES = None       # list[dict]
_BY_HUB_Q = None        # (hub, q) -> template(最佳)
_BY_HUB = None          # hub -> [templates]


def _clean_measure(m):
    """measure_examples 偶被 pro 审产物存成 list-repr 字符串 "['..','..']" → join 成一行。"""
    s = str(m or "").strip()
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        try:
            parts = ast.literal_eval(s)
            if isinstance(parts, (list, tuple)):
                return "；".join(str(x).strip() for x in parts if str(x).strip())
        except Exception:
            pass
    return s


def _load():
    global _TEMPLATES, _BY_HUB_Q, _BY_HUB
    if _TEMPLATES is not None:
        return
    try:
        with open(TEMPLATES_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []
    _TEMPLATES, _BY_HUB_Q, _BY_HUB = data, {}, {}
    for t in data:
        if t.get("direction") != "风险":        # 运行时只用危害模板
            continue
        hub, q = t.get("hub"), t.get("outcome_q")
        _BY_HUB.setdefault(hub, []).append(t)
        # 同 (hub,q) 若多条,留命中政策最多的(更稳、更可复用)
        cur = _BY_HUB_Q.get((hub, q))
        if cur is None or t.get("n_policies", 0) > cur.get("n_policies", 0):
            _BY_HUB_Q[(hub, q)] = t


def match_template(chain, outcome_q):
    """一条危害路径 chain → 危害模板:**仅按 (hub, outcome_q) 精确 join**,落不到则 None。

    刻意不做"同 hub 兜底":实测兜底命中的 17.5% 全是 outcome_q 不同的跨题匹配
    (把别题的措施贴过来,样例全错),违反"精准 > 召回 / 贴错比没有更糟"铁律。
    宁可这条路径"措施待补",也不贴一个错题的模板。覆盖缺口走【补 determinants 别名表】这条
    可审计的符号路修,或后续向量兜底——不靠降精度的兜底凑数。"""
    _load()
    hubs = D.resolve_all(chain or [])
    if not hubs:
        return None
    try:
        q = int(outcome_q)
    except Exception:
        return None
    for h in hubs:
        t = _BY_HUB_Q.get((h, q))
        if t:
            return t
    return None


def enrich_path(p, n_examples=3):
    """对一条危害路径做 ID-join,挂上**同类政策参考做法**(原地改并返回 p):
      · p["template_ref"]:命中的验证模板引用——hub/命中政策数/措施缺口分布/代表性参考措施。

    ★只作【参考 checklist】,**不覆盖 p["measures"]**:measures 是引擎结合本政策背景现场生成的
    "建议措施"(定制),template_ref 是历史同类政策的"通用做法"(参考)。两者并列、来源透明,
    模板不冒充定制方案。未命中模板则保持原样(不臆造)。"""
    if p.get("direction") != "风险":
        return p
    t = match_template(p.get("chain") or [], p.get("outcome_q"))
    if not t:
        return p
    examples = [_clean_measure(m) for m in (t.get("measure_examples") or [])]
    examples = [m for m in examples if m][:max(1, n_examples)]
    p["template_ref"] = {
        "template_id": t.get("template_id"),
        "hub": t.get("hub"),
        "hub_name": t.get("hub_name"),
        "n_policies": t.get("n_policies"),       # 同类政策数(可复用度)
        "mitigation_dist": t.get("mitigation_dist") or {},   # 同类政策的措施缺口分布(监管洞察)
        "measure_examples": examples,            # 代表性通用做法(供参考,非定制)
    }
    return p


def enrich(pathways):
    """批量:对一组危害路径逐条 ID-join 回填。返回同一列表(原地改)。"""
    for p in pathways or []:
        enrich_path(p)
    return pathways


def coverage(pathways):
    """诊断用:返回 (命中模板数, 风险路径总数)。"""
    risk = [p for p in (pathways or []) if p.get("direction") == "风险"]
    hit = sum(1 for p in risk
              if match_template(p.get("chain") or [], p.get("outcome_q")))
    return hit, len(risk)
