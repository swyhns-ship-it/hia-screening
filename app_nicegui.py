# -*- coding: utf-8 -*-
"""健康影响评估智能初筛系统 —— NiceGUI 原型(信息架构对比版)。

与 Streamlit 版同功能、复用同一套引擎(hia_screen)与证据库(hia_evidence),
但用更清爽的信息架构解决"信息量太大"的问题:
  · 顶部一条汇总(10 个健康方面的红/黄/绿一览)——先看全局;
  · 10 行可折叠列表,每行一个健康方面,标题带"系统初判"色块;
  · 展开后,每条影响压成"一行"(勾选 + 把握色块 + 影响链),
    「依据/详情」(影响人群、WHO 来源、机制)收进每条后面的小折叠,按需才看;
  · 每个方面底部:专家判定(需要关注/尚不确定/暂未发现)+ 备注。

运行:  python app_nicegui.py   (默认 http://localhost:8502)
密钥:  环境变量 DEEPSEEK_API_KEY 或 .streamlit/secrets.toml 的 deepseek_api_key,
       否则在页面顶部的输入框临时填入。
现有 Streamlit 版(app.py)不受影响,二者各自独立。
"""
import json
import difflib
import os
import re
import unicodedata
from datetime import date

from nicegui import ui, run, app

import hia_screen as hs
import hia_evidence  # noqa: F401 (annotate 在 analyze 内部用)
import feedback as fb_engine
import cases as case_store

# —— 部署配置(走环境变量,不放明文)——
APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()   # 经办台访问口令;未配则不拦(本地开发)
APP_PORT = int(os.environ.get("PORT", "8502"))
STORAGE_SECRET = os.environ.get("STORAGE_SECRET", "hia-screening-dev-secret")


def require_app_login():
    """经办台(/、/panel)访问口令门。配置 APP_PASSWORD 才启用;专家 /review 用案例口令,不受此限。
    返回 True 放行;否则渲染登录界面并返回 False(调用方应 return)。"""
    if not APP_PASSWORD:
        return True
    if app.storage.user.get("staff_authed"):
        return True
    _page_head()
    with ui.column().classes("w-full items-center").style("margin-top:3rem;gap:.6rem;"):
        ui.label("🔒 " + PLATFORM_NAME).style(
            f"color:{GREEN_DEEP};font-size:1.3rem;font-weight:700;")
        ui.label("本平台供卫健委工作人员使用,请输入访问口令。").classes("text-sm text-grey")

        def _try():
            if (pw.value or "") == APP_PASSWORD:
                app.storage.user["staff_authed"] = True
                ui.navigate.reload()
            else:
                ui.notify("口令不正确。", type="negative")
        pw = ui.input("访问口令", password=True).on("keydown.enter", _try).style("min-width:260px;")
        ui.button("进入", on_click=_try).props("color=primary")
    return False

GREEN = "#2E9E5B"
GREEN_DEEP = "#1B6B3A"
PLATFORM_NAME = "AI辅助健康影响评估"
ANSWERS = list(hs.ANSWERS)                      # ('是','不知道','否')
# 简短形(仅用于顶部汇总卡/单选,语境已明确)
ANSWER_LABEL = {"是": "需要关注", "不知道": "尚不确定", "否": "暂未发现"}
# 完整形(用于方面标题徽标,力求自解释、不缩略)
ANSWER_FULL = {"是": "该维度健康影响需重点关注",
               "不知道": "该维度健康影响尚不确定、建议进一步评估",
               "否": "暂未发现明显健康影响"}
ANSWER_COLOR = {"是": "#C62828", "不知道": "#B07A00", "否": "#1B6B3A"}
# 顶部统计卡配色(规范 token,大数字与左侧色条统一):需要关注=红/尚不确定=橙/暂未发现=绿
STAT_COLOR = {"是": "var(--hia-danger-600)", "不知道": "var(--hia-grade-600)",
              "否": "var(--hia-benefit-600)"}
# 机制证据强度(AI 对该条机制成立的把握),完整表述
STRENGTH_LABEL = {"强": "机制证据较充分", "中": "机制证据中等", "推测": "尚属机制推测"}
STRENGTH_COLOR = {"强": "#C62828", "中": "#E07B39", "推测": "#9AA0A6"}
# 风险/效益 = 负面/正面健康影响效应
DIR_FULL = {"风险": "🔴 负面健康影响(风险)", "效益": "🟢 正面健康影响(效益)"}
STATUS_LABEL = {"文档支持": "线索源自上传文件原文", "路径库/文献": "机制有文献/指南支持",
                "假设待证": "属推断假设、有待证实", "专家补充": "专家手动补充"}

# 导航标签配色(规范第 2 节,引用 :root token):未选中=细灰边+状态圆点,选中=填实底色+白字。
# 颜色语义:需要关注=红 / 暂未发现=绿(未选中圆点退灰) / 尚不确定=橙(程度量)。
TAB_DOT = {"是": "var(--hia-danger-400)", "不知道": "var(--hia-grade-600)",
           "否": "var(--hia-neutral-200)"}
TAB_ACTIVE_BG = {"是": "var(--hia-danger-600)", "不知道": "var(--hia-grade-600)",
                 "否": "var(--hia-benefit-600)"}
TAB_ACTIVE_SUB = {"是": "var(--hia-danger-200)", "不知道": "var(--hia-grade-50)",
                  "否": "var(--hia-benefit-100)"}


def _adopt_default(p):
    return p.get("status") != "假设待证"


def _get_key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    try:
        import tomllib
        with open(".streamlit/secrets.toml", "rb") as f:
            return (tomllib.load(f).get("deepseek_api_key", "") or "").strip()
    except Exception:
        return ""


def _wrap_label(text, per=13, cap=52):
    """mermaid 节点文字:转义 + 超长截断省略 + 每 per 字换行,避免显示不全/巨框。"""
    t = str(text).replace('"', "'").replace("\\", "/").strip()
    if len(t) > cap:
        t = t[:cap] + "…"
    return "<br/>".join(t[i:i + per] for i in range(0, len(t), per))


_Q_COLOR = {"是": ("#FBEBEB", "#C62828", "#b3261e"),
            "不知道": ("#FFF7E6", "#B07A00", "#8a6100"),
            "否": ("#EAF6EE", "#1B6B3A", "#1B6B3A")}


# 健康方面节点「关注度」配色(不用红,避免与负面健康影响混淆):需关注=琥珀/待定=黄/暂无=绿
_ATT_FILL = {"是": ("#FBE9D8", "#E07B39"), "不知道": ("#FFF7E6", "#B07A00"),
             "否": ("#EAF6EE", "#2E9E5B")}
# 健康结果端按效应方向着色:风险=红 / 效益=绿(这才是真正的好坏)
_DIR_FILL = {"风险": ("#FBEBEB", "#C62828"), "效益": ("#E9F6EE", "#1B6B3A")}


def build_mermaid(actions, pathways, ans=None, sel_q=None):
    """渲成 mermaid 连线树:政策原文「引文」→ 措施 → 环节 → 健康结果 → HIA 维度,节点间用箭头相连。
    末端 QO「健康方面」节点 id 固定 QO{q}(供点击跳转),按关注度着色(不用红);
    末环节「健康结果」节点按效应方向(风险红/效益绿)着色;sel_q 当前方面粗框。"""
    act_label = {a["id"]: a.get("action", "") for a in actions}
    act_ev = {a["id"]: (a.get("evidence") or "").strip() for a in actions}
    lines = ["flowchart LR"]
    ids, edges, q_used, result_dir = {}, [], [], {}

    def node(prefix, text):
        key = (prefix, text)
        if key not in ids:
            nid = prefix + str(abs(hash(text)) % 100000)
            ids[key] = nid
            lines.append(f'{nid}["{_wrap_label(text)}"]')
        return ids[key]

    def qnode(q):
        qid = f"QO{q}"
        if q not in q_used:
            q_used.append(q)
            lines.append(f'{qid}["{_wrap_label(f"Q{q} {hs.SHORT_Q[q-1]}")}"]')
        return qid

    for p in pathways:
        seq = []
        ev = act_ev.get(p["action_id"], "")
        if ev:                                   # 政策原文(加引号)
            seq.append(node("E", "「" + ev + "」"))
        else:                                    # 无原文则用措施名作起点
            seq.append(node("A", act_label.get(p["action_id"], p["action_id"])))
        raw_chain = p.get("chain") or []
        if isinstance(raw_chain, str):
            raw_chain = [raw_chain]
        parts = []
        for step in raw_chain:                   # chain 元素内部自带 → 的拆成独立节点
            for part in _ARROW_RE.split(str(step)):
                part = part.strip()
                if part:
                    parts.append(part)
        for i, part in enumerate(parts):
            nid = node("D", part)
            if i == len(parts) - 1:              # 末环节 = 健康结果,记其效应方向
                result_dir[nid] = p.get("direction", "效益")
        seq.append(qnode(p["outcome_q"]))
        for n1, n2 in zip(seq, seq[1:]):
            e = f"{n1} --> {n2}"
            if e not in edges:
                edges.append(e)

    out = lines + edges
    for nid, d in result_dir.items():            # 健康结果端着色(风险红/效益绿)
        fill, stroke = _DIR_FILL.get(d, _DIR_FILL["效益"])
        out.append(f"style {nid} fill:{fill},stroke:{stroke},color:#333")
    if ans is not None:                          # HIA 维度按关注度着色(琥珀/黄/绿,不用红)+ 当前粗框
        for q in q_used:
            a = ans.get(q, "否")
            fill, stroke = _ATT_FILL.get(a, _ATT_FILL["否"])
            w = 4 if sel_q == q else 2
            out.append(f"style QO{q} fill:{fill},stroke:{stroke},stroke-width:{w}px,color:#333")
    return "\n".join(out)


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def humanize_summary(text, actions):
    """把总体研判里 AI 引用的措施编号 A1/A2/… 替换成「措施N·原话」,便于政务用户看懂。"""
    amap = {a["id"]: (a.get("action") or "").strip() for a in (actions or [])}

    def _repl(m):
        aid = m.group(0)
        lbl = amap.get(aid)
        if not lbl:
            return aid
        short = lbl if len(lbl) <= 20 else lbl[:20] + "…"
        return f"措施{aid[1:]}「{short}」"
    return re.sub(r"A\d+", _repl, text or "")


_ARROW_RE = re.compile(r"\s*(?:→|—>|->|⟶|=>|⇒)\s*")


def _norm_cmp(s):
    """归一化用于相似度比较:去空白与常见标点/书名号,便于判断两段文字是否近乎一致。"""
    return re.sub(r"[\s，。、；：,.;:\"'“”‘’《》«»〈〉「」（）()\[\]【】·…—-]+", "", s or "")


def _path_flow_html(p, actions):
    """把一条影响路径渲成节点流 HTML:📄原文引用 → 行动/环节 → 健康结果(仅末节点按风险/效益着色)。
    注:chain 元素内部若自带 → 箭头,拆成独立节点,保证流程连贯。"""
    raw = p.get("chain") or []
    if isinstance(raw, str):                      # 防御:字符串别按"字"拆开
        raw = [raw]
    steps, _seen = [], set()
    for el in raw:
        for part in _ARROW_RE.split(str(el)):
            part = part.strip()
            if part and part not in _seen:         # 去重:链条绕回先前节点时不重复显示
                _seen.add(part)
                steps.append(part)
    nodes = []
    origin = _origin_quote(p, actions)
    # 去首环节重复:原文框已逐字摘录政策原文,若第一个中间环节与之近乎一字不差,
    # 说明把原文又抄了一遍——丢弃它,让第一个中间环节落到提炼后的机制节点(仍保留≥1 个中间环节)。
    if origin and len(steps) >= 2:
        o, s0 = _norm_cmp(origin), _norm_cmp(steps[0])
        if s0 and (s0 in o or o in s0 or
                   difflib.SequenceMatcher(None, o, s0).ratio() > 0.8):
            steps = steps[1:]
    if origin:
        nodes.append(f'<span class="hia-node origin" title="引自政策原文(逐字摘录)">'
                     f'📄 “{_esc(origin)}”</span>')
    risk = p.get("direction") == "风险"
    for i, step in enumerate(steps):
        last = (i == len(steps) - 1)
        cls = "hia-node"
        if last:                                   # 末端=健康结果:实色块(益绿/害红)。好坏靠底色+染色连接箭头,
            cls += " outcome-risk" if risk else " outcome-benefit"   # 框内不再加 ↑/↓——避免与"降低/增加"等动词打架
            nodes.append(f'<span class="{cls}">{_esc(step)}</span>')
        else:
            nodes.append(f'<span class="hia-node">{_esc(step)}</span>')
    # 普通箭头灰色;指向最终结果的那一支染成对应语义色(规范第 4 节)
    arrow = '<span class="hia-arrow">→</span>'
    end_arrow = ('<span class="hia-arrow hia-arrow--risk">→</span>' if risk
                 else '<span class="hia-arrow hia-arrow--benefit">→</span>')
    html = ""
    for i, nd in enumerate(nodes):
        if i > 0:
            html += end_arrow if i == len(nodes) - 1 else arrow
        html += nd
    return '<div class="hia-flow">' + html + '</div>'


def _origin_quote(p, actions):
    """这条影响在节点流里展示的「政策原文逐字摘录」(链条起点)。供路径渲染与溯源高亮共用。"""
    act_ev = {a["id"]: (a.get("evidence") or "").strip() for a in (actions or [])}
    return act_ev.get(p.get("action_id"), "") or (
        p.get("evidence", "") if p.get("status") == "文档支持" else "")


# —— 政策原文溯源高亮:把摘录在原文里精确/近似定位,强化"有据可查、可审计" ——
_QUOTE_NORM = {"«": "《", "»": "》", "〈": "《", "〉": "》",
               "“": '"', "”": '"', "‘": "'", "’": "'"}
_src_seq = [0]                                     # 高亮锚点 id 自增,避免多弹窗同 id 冲突


def _collapse_for_match(text):
    """丢弃空白 + 归一化书名号/引号(PDF 抽取常把《》→«»);返回(压缩串, 原文索引映射)。
    保持 1 字符↔1 字符,索引映射可把压缩串里的位置还原回原文位置。"""
    out, idx = [], []
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        c = _QUOTE_NORM.get(ch)
        if c is None:                              # 全角→半角(政府公文常用全角数字/标点:１５%→15%、:→:)
            nf = unicodedata.normalize("NFKC", ch)
            c = nf if len(nf) == 1 else ch         # 仅 1↔1 映射,保证索引可还原
        out.append(c)
        idx.append(i)
    return "".join(out), idx


def _locate_quote(text, quote):
    """在原文 text 里定位摘录 quote;返回 (start, end, mode) 原文区间,mode∈exact/approx;定位不到→None。"""
    if not text or not quote:
        return None
    cq, _ = _collapse_for_match(quote)
    ct, idx = _collapse_for_match(text)
    if not cq or not ct:
        return None
    pos = ct.find(cq)
    if pos != -1:
        return (idx[pos], idx[pos + len(cq) - 1] + 1, "exact")
    # 近似:PDF 抽取常把字符拆散/改字,致连续匹配断裂。以最长公共片段为锚点,
    # 按引文长度在原文里框出对应段落(让锚点与其在引文中的位置对齐),并标「近似·请核对」。
    m = difflib.SequenceMatcher(None, ct, cq, autojunk=False).find_longest_match(
        0, len(ct), 0, len(cq))
    if m.size >= max(6, int(len(cq) * 0.35)):     # 锚点够长才框,否则宁可判定不到(不臆造)
        start = max(0, m.a - m.b)
        end = min(len(ct), start + len(cq))
        return (idx[start], idx[end - 1] + 1, "approx")
    return None


def _case_doc_text(case):
    """从案例随附的政策原文文件重新抽取纯文本(供只读页溯源高亮)。无原文/抽取失败→空串。"""
    dp = case_store.doc_path(case)
    if not dp:
        return ""
    try:
        with open(dp, "rb") as f:
            data = f.read()
        text, info = hs.extract_text(case.get("doc_name") or os.path.basename(dp), data)
        return "" if info.get("error") else text
    except Exception:                                 # noqa: BLE001
        return ""


def _open_source_dialog(doc_text, quote):
    """弹窗展示政策原文并高亮该摘录:精确命中=蓝高亮+自动滚到位;近似命中给提示;定位不到给人工核对提示。"""
    span = _locate_quote(doc_text, quote)
    _src_seq[0] += 1
    mid = f"srchl{_src_seq[0]}"
    with ui.dialog() as dlg, ui.card().style("width:min(900px,95vw);max-width:95vw;gap:8px;"):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label("📄 政策原文溯源").style(
                f"color:{GREEN_DEEP};font-weight:500;font-size:1.05rem;")
            ui.button(icon="close", on_click=dlg.close).props("flat round dense")
        ui.html('<div style="font-size:12px;color:var(--hia-neutral-500);">'
                f'核对依据摘录:“{_esc(quote)}”</div>')
        if span is None:
            ui.html('<div style="font-size:12.5px;background:var(--hia-grade-50);'
                    'color:var(--hia-grade-800);border-radius:6px;padding:8px 11px;">'
                    '⚠ 未能在原文中精确定位该摘录(可能为概括或文档抽取差异),请人工核对下方原文。</div>')
            body = _esc(doc_text)
        else:
            s, e, mode = span
            if mode == "approx":
                ui.html('<div style="font-size:12.5px;background:var(--hia-source-50);'
                        'color:var(--hia-source-800);border-radius:6px;padding:8px 11px;">'
                        'ℹ 下方蓝色高亮为系统在原文中近似定位的对应段落,请核对。</div>')
            body = (_esc(doc_text[:s])
                    + f'<mark id="{mid}" style="background:var(--hia-source-50);'
                    'border-bottom:2px solid var(--hia-source-600);color:var(--hia-source-800);'
                    'font-weight:500;padding:0 1px;">' + _esc(doc_text[s:e]) + '</mark>'
                    + _esc(doc_text[e:]))
        ui.html(f'<div style="white-space:pre-wrap;font-size:13px;line-height:1.7;'
                f'max-height:64vh;overflow:auto;border:0.5px solid var(--hia-border);'
                f'border-radius:var(--hia-radius-md);padding:12px 14px;'
                f'color:var(--hia-neutral-700);">{body}</div>')
    dlg.open()
    if span is not None:
        ui.run_javascript(
            "setTimeout(function(){var el=document.getElementById('" + mid + "');"
            "if(el)el.scrollIntoView({block:'center'});},150)")


def _source_button(doc_text, p, actions):
    """若有原文与摘录,渲一个「在原文中定位」按钮(/screen 与只读评审/参考页共用)。"""
    quote = _origin_quote(p, actions)
    if not (doc_text and quote):
        return
    ui.button("🔎 在原文中定位这段依据",
              on_click=lambda: _open_source_dialog(doc_text, quote)).props(
        "dense flat color=primary size=sm").classes("q-mt-xs")


def chip(text, color):
    return (f'<span style="background:{color};color:#fff;border-radius:9px;'
            f'padding:2px 10px;font-size:.82rem;white-space:nowrap;">{text}</span>')


def soft_chip(text, color):
    return (f'<span style="color:{color};border:1px solid {color};border-radius:9px;'
            f'padding:1px 9px;font-size:.82rem;white-space:nowrap;">{text}</span>')


# —— 卡片状态徽章(规范第 3 节)三级视觉层级:影响方向 > 证据等级 > 证据状态 ——
def dir_badge(direction):
    """影响方向(最显眼):色块 + 箭头 + 13px/500。益=绿底绿字↑ / 害=红底红字↓。"""
    if direction == "风险":
        return ('<span style="display:inline-flex;align-items:center;gap:6px;'
                'padding:4px 12px;border-radius:6px;font-size:13px;font-weight:500;'
                'background:var(--hia-danger-50);color:var(--hia-danger-800);">'
                '<b style="font-weight:500;">↓</b>负面健康影响(风险)</span>')
    return ('<span style="display:inline-flex;align-items:center;gap:6px;'
            'padding:4px 12px;border-radius:6px;font-size:13px;font-weight:500;'
            'background:var(--hia-benefit-50);color:var(--hia-benefit-800);">'
            '<b style="font-weight:500;">↑</b>正面健康影响(效益)</span>')


GRADE_SHORT = {"强": "强", "中": "中", "推测": "弱"}   # 徽章用简写(规范第 3 节:证据等级 强/中/弱)


def grade_badge(strength):
    """证据等级(次之):小橙色块 + 12px。橙色只服务于"证据等级"这一程度量(规范第 0/3 节)。
    文案用简写"证据等级 强/中/弱";去掉原"强=红",红色让回给"害"。"""
    lvl = GRADE_SHORT.get(strength, strength)
    return ('<span style="display:inline-flex;align-items:center;'
            'padding:4px 10px;border-radius:6px;font-size:12px;font-weight:400;'
            'background:var(--hia-grade-50);color:var(--hia-grade-800);">'
            f'证据等级 {lvl}</span>')


def status_badge(prov_t):
    """证据状态(最弱):灰色次要文字 + info 图标,无底色无边框。"""
    return ('<span style="display:inline-flex;align-items:center;gap:5px;'
            'font-size:12px;font-weight:400;color:var(--hia-neutral-500);">'
            f'ⓘ {prov_t}</span>')


def badge_row(p, margin_bottom="12px"):
    """三枚状态徽章按 影响方向 → 证据等级 → 证据状态 排布,横向 8px 间距(规范第 3/5 节)。"""
    prov_t, _ = prov_of(p)
    inner = dir_badge(p["direction"]) + grade_badge(p["strength"]) + status_badge(prov_t)
    return (f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;'
            f'margin-bottom:{margin_bottom};">{inner}</div>')


def prov_of(p):
    """一条影响'健康端'的出处标签:(文本, 颜色)。仅看「因果轨」证据(WHO/文献,支撑→健康结果);
    国标属「基准轨」(暴露限值),不计入健康端因果依据。无因果证据→证据待补。"""
    causal = [c for c in (p.get("cards") or []) if c.get("kind", "因果") == "因果"]
    if not causal:
        return "⚠ 健康结局端证据待补(暂为机制推断)", "#B07A00"
    done = any(c.get("status") != "todo" for c in causal)
    return ("📚 健康结局端有权威依据" if done else "📚 健康结局端依据待补强",
            GREEN_DEEP if done else "#B07A00")


# —— 依据区块:统一的小标题锚点 + 已核实徽章 + 来源条目卡(规范第 3/5 节)——
_SRC_URL_RE = re.compile(r"(https?://\S+)")
# 形如「PM2.5 年均 25、日均 50」:污染物 + 年均值 + 日均值(污染物名含下标/小数)
_LIMIT_ITEM_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9.₀-₉²³．]*)\s*年均\s*([0-9.]+)[^日]*?日均\s*([0-9.]+)")
# 浓度单位(从 note 原文里自动识别,不写死;µ=U+00B5 / μ=U+03BC 都认,³ 或 3 都认)
_UNIT_RE = re.compile(r"[µμ]g/m[³3]|mg/m[³3]|mg/kg|mg/L|ng/m[³3]")


def _split_source(src):
    """把一条来源串拆成 (标题, URL)。来源串形如「标准名 标准号. 发布机构. https://…」。"""
    s = str(src).strip()
    m = _SRC_URL_RE.search(s)
    url = m.group(1).rstrip("。.，,；;)]") if m else ""
    title = (s[:m.start()] if m else s).strip().rstrip("。.，,；; ").strip()
    return title or s, url


def _verified_chip(text, kind="ok"):
    """统一的「已核实/认证」标记:与卡片顶部徽章同一视觉语言(实底软块·圆角6·12px·400)。"""
    bg, fg = (("var(--hia-grade-50)", "var(--hia-grade-800)") if kind == "warn"
              else ("var(--hia-benefit-50)", "var(--hia-benefit-800)"))
    return (f'<span style="display:inline-flex;align-items:center;padding:4px 10px;'
            f'border-radius:6px;font-size:12px;font-weight:400;'
            f'background:{bg};color:{fg};">{_esc(text)}</span>')


def _ev_header(icon, title, accent, sub, hero=False):
    """三类依据的区块小标题锚点:图标 + 标题(左侧色条),副说明小字。hero=核心(更大更醒目)。"""
    tag = ('<span style="font-size:11px;font-weight:400;color:#fff;'
           f'background:{accent};border-radius:4px;padding:1px 7px;margin-left:2px;">核心</span>'
           ) if hero else ""
    fs = "15px" if hero else "13px"
    return (
        f'<div style="margin-top:{"12px" if hero else "9px"};">'
        f'<div style="display:flex;align-items:center;gap:7px;font-size:{fs};font-weight:500;'
        f'color:{accent};border-left:3px solid {accent};padding-left:9px;line-height:1.3;">'
        f'<span>{icon}</span><span>{_esc(title)}</span>{tag}</div>'
        f'<div style="font-size:11.5px;font-weight:400;color:var(--hia-neutral-500);'
        f'padding-left:12px;margin-top:3px;line-height:1.45;">{sub}</div></div>')


def _limit_table_html(note):
    """密集数值要点(尤其国标 PM2.5/PM10/NO₂/SO₂ 年/日均限值)渲成小表:污染物/年均/日均。
    解析不出≥2 条则返回空串,由调用方退回纯文字。"""
    items = _LIMIT_ITEM_RE.findall(note or "")
    if len(items) < 2:
        return ""
    um = _UNIT_RE.search(note or "")              # 单位从原文自动取,识别不出则不标(不臆造)
    unit = (f'<span style="font-weight:400;font-size:10.5px;'
            f'color:var(--hia-neutral-500);">（{_esc(um.group(0))}）</span>') if um else ""
    bd = "border-top:1px solid var(--hia-border);"
    rows = "".join(
        f'<tr><td style="padding:3px 12px 3px 0;{bd}">{_esc(n)}</td>'
        f'<td style="padding:3px 12px;{bd}text-align:right;">{_esc(y)}</td>'
        f'<td style="padding:3px 0 3px 12px;{bd}text-align:right;">{_esc(d)}</td></tr>'
        for n, y, d in items)
    return (
        '<table style="border-collapse:collapse;font-size:12px;margin:4px 0 2px;'
        'color:var(--hia-neutral-700);">'
        '<thead><tr style="color:var(--hia-neutral-500);font-weight:500;">'
        '<th style="padding:0 12px 3px 0;text-align:left;font-weight:500;">污染物</th>'
        f'<th style="padding:0 12px 3px;text-align:right;font-weight:500;">年均{unit}</th>'
        f'<th style="padding:0 0 3px 12px;text-align:right;font-weight:500;">日均{unit}</th>'
        '</tr></thead><tbody>' + rows + '</tbody></table>')


def _render_source_card(c):
    """一条来源 = 一张缩进小卡:已核实徽章 + 加粗标题 +「查看原文 ↗」+ 要点(小字/小表)。"""
    verified = c.get("status") != "todo"
    chips = (_verified_chip(c.get("tier", "WHO 资料"), "ok")
             + _verified_chip("已核实" if verified else "待补强",
                              "ok" if verified else "warn"))
    body = ""
    for src in c.get("sources", []):
        title, url = _split_source(src)
        link = (f'<a href="{_esc(url)}" target="_blank" rel="noopener" '
                f'style="color:var(--hia-source-600);text-decoration:none;white-space:nowrap;'
                f'margin-left:8px;font-size:12px;">查看原文 ↗</a>') if url else ""
        body += (f'<div style="font-size:12.5px;font-weight:500;color:var(--hia-neutral-700);'
                 f'line-height:1.5;margin-top:2px;">{_esc(title)}{link}</div>')
    note_html = ""
    if c.get("note"):
        tbl = _limit_table_html(c["note"])
        if tbl:
            note_html = ('<div style="font-size:11.5px;color:var(--hia-neutral-500);'
                         'margin-top:4px;">要点(概括,以原文为准):</div>' + tbl)
        else:
            note_html = (f'<div style="font-size:11.5px;color:var(--hia-neutral-500);'
                         f'margin-top:4px;line-height:1.5;">要点(概括,以原文链接为准):'
                         f'{_esc(c["note"])}</div>')
    ui.html(
        f'<div style="border:0.5px solid var(--hia-border);border-radius:8px;'
        f'background:var(--hia-surface);padding:8px 11px;margin:6px 0 6px 12px;">'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;">{chips}</div>'
        f'{body}{note_html}</div>')


def render_evidence(cards, last_node="健康结果"):
    """两轨依据显示:📚 健康因果依据(WHO/文献,支撑→健康结果) + 📐 相关国家标准(暴露限值/管控基准)。"""
    causal = [c for c in (cards or []) if c.get("kind", "因果") == "因果"]
    bench = [c for c in (cards or []) if c.get("kind") == "基准"]
    if causal:
        ui.html(_ev_header(
            "📚", "健康因果依据", "var(--hia-benefit-600)",
            f'下列来源支撑本条<b style="font-weight:500;">最后一段「→ {_esc(last_node)}」的健康影响</b>;'
            '链条前段的政策/行为/暴露环节,请结合上传文件与本地情况判断。', hero=True))
        for c in causal:
            _render_source_card(c)
    else:
        ui.html(_ev_header(
            "📚", "健康因果依据", "var(--hia-benefit-600)",
            "这条的健康影响目前缺权威因果证据。", hero=True)
            + '<div style="font-size:12.5px;background:var(--hia-grade-50);'
              'border-left:3px solid var(--hia-grade-600);padding:6px 10px;border-radius:4px;'
              'margin:5px 0 2px 12px;color:var(--hia-grade-800);line-height:1.5;">'
              '⚠ <b style="font-weight:500;">健康端因果证据待补</b>:'
              '暂无 WHO/文献支撑这条的健康影响,需专家补证后再采纳。</div>')
    if bench:
        ui.html(_ev_header(
            "📐", "相关国家标准", "var(--hia-neutral-700)",
            '以下为本路径涉及暴露/环节的国家标准,<b style="font-weight:500;">非因果证据</b>,'
            '用作评估基准、达标判据与改善建议依据。'))
        for c in bench:
            _render_source_card(c)


@ui.page("/screen")
def screen():
    if not require_app_login():
        return
    ui.colors(primary=GREEN)
    ui.add_head_html('<meta name="robots" content="noindex,nofollow,noarchive">')
    ui.add_head_html(
        "<style>"
        + _TOKENS_CSS +
        "body{font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;}"
        ".hia-chain{line-height:1.5;}"
        + _FLOW_CSS +
        ".hia-path{border-radius:10px;transition:background .12s,box-shadow .12s,outline-color .12s;"
        "outline:2px solid transparent;outline-offset:-1px;}"
        ".hia-path:hover{background:#EEF9F2 !important;outline-color:#2E9E5B;"
        "box-shadow:0 6px 18px -6px rgba(46,158,91,.55);}"
        ".hia-path:hover .hia-arrow{color:#2E9E5B;}"
        ".cmap-h{background:#EAF7EF;color:#1B6B3A;font-weight:700;font-size:.8rem;"
        "padding:8px 10px;border-bottom:2px solid #CFE0D5;position:sticky;top:0;z-index:2;}"
        ".cmap-dim{background:#F2F8F4;color:#1B6B3A;font-weight:700;font-size:.84rem;"
        "padding:7px 10px;border-top:1px solid #DCEEE3;}"
        ".cmap-cell{padding:8px 10px;border-bottom:1px solid #F0F5F2;display:flex;"
        "align-items:center;flex-wrap:wrap;gap:5px;}"
        ".cmap-q{cursor:pointer;transition:background .12s;}"
        ".cmap-q:hover{background:#EEF9F2;}"
        ".vflow{display:flex;flex-direction:column;align-items:flex-start;gap:2px;}"
        ".varrow{color:#9AA0A6;font-size:.72rem;line-height:1.1;margin-left:9px;}"
        ".cflow{color:#9AA0A6;font-weight:700;margin-left:auto;padding-left:8px;}"
        "</style>")
    # 内容居中 + 限宽,避免全屏过宽难读
    ui.query(".nicegui-content").classes("mx-auto").style("max-width:1000px;")
    _top_nav("new")

    # —— 每会话状态(闭包持有)——
    st = {"file_bytes": None, "file_name": "", "res": None, "docinfo": None}
    adopt, ans, note, sysans = {}, {}, {}, {}   # pid->bool / q->str / q->str / q->str(系统初判)
    overridden = set()                           # 专家手动改过判定的方面(不再被勾选自动覆盖)
    fb = {}                                      # pid -> {"flag":问题类型, "note":备注}(专家反馈)
    sel = {"q": 1}                               # 当前选中的健康方面(选项卡 + 评估地图共用)
    mapdlg = {"d": None}                          # 评估地图弹窗引用(浮动按钮打开,点节点后关闭)

    def all_pathways():
        return list((st["res"] or {}).get("pathways", []))

    # ===== 顶部品牌条 =====
    with ui.row().classes("w-full items-center justify-between q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("新建健康影响评估 · 健康影响初筛(单人)").style(
                f"color:{GREEN};letter-spacing:2px;font-size:.85rem;font-weight:600;")
            ui.label("健康影响初筛").style(
                f"color:{GREEN_DEEP};font-size:1.7rem;font-weight:700;")
            ui.label("智能分析展开健康影响路径 · 对照《健康影响评估初筛表》· 专家核定").style(
                "color:#5a7a66;font-size:.85rem;")
        ui.link("需要多位专家?→ 专家组协同评估", "/panel").style(
            f"color:{GREEN_DEEP};font-weight:600;font-size:.9rem;").props("no-underline")

    # ===== 步骤指引(随分析进度高亮)=====
    @ui.refreshable
    def stepper():
        cur = 2 if st["res"] else 0
        steps = [("1", "上传文件"), ("2", "智能分析"), ("3", "逐方面核对"), ("4", "导出初筛表")]
        with ui.row().classes("w-full items-center justify-center q-mb-sm").style(
                "gap:0;flex-wrap:wrap;"):
            for i, (n, t) in enumerate(steps):
                active = i <= cur
                c = GREEN if active else "#C9D6CD"
                tc = GREEN_DEEP if active else "#9AA0A6"
                fw = "600" if active else "400"
                ui.html(f'<span style="display:inline-flex;align-items:center;gap:6px;margin:0 4px;">'
                        f'<span style="width:22px;height:22px;border-radius:50%;background:{c};'
                        f'color:#fff;display:inline-flex;align-items:center;justify-content:center;'
                        f'font-size:.78rem;font-weight:600;">{n}</span>'
                        f'<span style="color:{tc};font-size:.85rem;font-weight:{fw};">{t}</span></span>')
                if i < 3:
                    seg = GREEN if i < cur else "#E0E8E3"
                    ui.html(f'<span style="width:30px;height:2px;background:{seg};'
                            f'display:inline-block;margin:0 3px;"></span>')
    stepper()

    # ===== 使用说明(默认收起,不占首屏)=====
    with ui.expansion("使用说明(第一次使用可展开看这里)", value=False).classes(
            "w-full").style("border:1px solid #DCEEE3;border-radius:10px;"):
        ui.markdown(
            "**怎么用?三步:** ①上传要评估的政策/规划文件 → ②点「开始分析」,"
            "系统自动梳理可能的健康影响 → ③逐方面核对、下载初筛表。\n\n"
            "**看结果:** 先看顶部 10 个健康方面的红/黄/绿一览;想细看某一方面,点开那一行,"
            "里面是系统找到的影响(勾掉不认可的),「依据/详情」按需展开。\n\n"
            "⚠️ 本系统借助智能分析技术辅助梳理,**结论和签字以专家判断为准**,不替代专家。")

    # ===== 上传 + 分析(分析后自动收起,把版面让给结果)=====
    upload_exp = ui.expansion("上传文件并开始智能分析", value=True).classes(
        "w-full").style("border:1px solid #DCEEE3;border-radius:10px;")
    with upload_exp:
        ui.label("上传要评估的政策或规划文件(支持 PDF / Word;扫描成图片的 PDF 暂不支持)。").classes(
            "text-sm").style("color:#5a7a66;")

        async def on_upload(e):
            st["file_bytes"] = await e.file.read()
            st["file_name"] = e.file.name
            st["name"] = e.file.name.rsplit(".", 1)[0]
            ui.notify(f"已上传:{e.file.name}", type="positive")

        ui.upload(on_upload=on_upload, auto_upload=True, max_files=1).props(
            'accept=".pdf,.docx" flat bordered').classes("w-full")

        key_in = ui.input("分析服务密钥(API Key)", password=True,
                          value=_get_key(), placeholder="sk-...").classes("w-full q-mt-sm")

        async def do_analyze():
            if not st["file_bytes"]:
                ui.notify("请先上传文件。", type="warning")
                return
            key = (key_in.value or "").strip()
            if not key:
                ui.notify("请先填写分析服务密钥。", type="warning")
                return
            text, info = hs.extract_text(st["file_name"], st["file_bytes"])
            if info.get("error"):
                ui.notify(info["error"], type="negative")
                return
            st["text"] = text                         # 留作政策原文溯源高亮
            analyze_btn.disable()
            n = ui.notification("正在分析(约 30–60 秒,分三步梳理健康影响)…",
                                spinner=True, timeout=None)
            try:
                res = await run.io_bound(hs.analyze, text, key,
                                         project_name=st.get("name", ""))
            except Exception as ex:                       # noqa: BLE001
                n.dismiss(); analyze_btn.enable()
                ui.notify(f"分析失败:{ex}", type="negative")
                return
            n.dismiss(); analyze_btn.enable()
            st["res"], st["docinfo"] = res, info
            st["name"] = hs.guess_title(text, fallback=st.get("name", ""))  # 用正文标题自动填充评估对象名
            adopt.clear(); ans.clear(); note.clear(); sysans.clear()
            for p in res["pathways"]:
                adopt[p["id"]] = _adopt_default(p)
            for it in hs.compute_items([p for p in res["pathways"] if adopt[p["id"]]]):
                sysans[it["q"]] = it["answer"]
                ans[it["q"]] = it["answer"]
            overridden.clear()
            sel["q"] = next((q for q in range(1, 11) if sysans.get(q) == "是"), 1)
            tip = f"已解析{info['kind']}" + (f"·{info['pages']}页" if info["pages"] else "")
            ui.notify(f"✅ {tip};识别 {len(res['actions'])} 项措施、"
                      f"梳理 {len(res['pathways'])} 条影响。", type="positive")
            upload_exp.value = False          # 分析完成,收起上传区
            stepper.refresh()
            results.refresh()

        analyze_btn = ui.button("🔍 开始分析(约 30–60 秒)", on_click=do_analyze).props(
            "color=primary")
        ui.label("分析期间请不要关闭页面。").classes("text-xs text-grey")

    # ===== 结果区(分析后渲染)=====
    @ui.refreshable
    def summary():
        if not st["res"]:
            return
        cnt = {"是": 0, "不知道": 0, "否": 0}
        for q in range(1, 11):
            cnt[ans.get(q, "否")] += 1
        with ui.row().classes("w-full items-stretch gap-3"):
            for a in ANSWERS:
                with ui.card().classes("flex-grow items-center").style(
                        f"border-left:4px solid {STAT_COLOR[a]};padding:8px;"):
                    ui.label(str(cnt[a])).style(
                        f"font-size:1.5rem;font-weight:500;color:{STAT_COLOR[a]};")
                    ui.label(ANSWER_LABEL[a]).classes("text-xs text-grey")

    @ui.refreshable
    def graph():
        """评估地图:按 HIA 维度分组,每行一条横向因果路径(政策原文「引文」→ 措施 → 环节 → 健康结果)。
        确定性布局(不依赖图引擎自动排版),路径箭头清晰、不同政策都稳定。"""
        adopted = [p for p in all_pathways() if adopt.get(p["id"])]
        ui.html('按 HIA 维度分组,每行 = 一条因果路径:<b>📄政策原文 → 措施 → 环节 → 健康结果</b>'
                '(绿=效益 / 红=风险)。<b>点维度标题进入该维度评估</b>(并关闭本窗)。').classes(
            "text-xs").style("color:#5a7a66;")
        if not adopted:
            ui.label("(暂无已认可的影响,勾选后再打开。)").classes("text-xs text-grey")
            return
        acts = st["res"].get("actions") or []
        ATT = {"是": ("需关注", "#E07B39"), "不知道": ("待定", "#B07A00"), "否": ("暂无", "#6E8378")}
        with ui.element("div").style(
                "max-height:74vh;overflow:auto;width:100%;border:1px solid #DCEEE3;"
                "border-radius:10px;padding:4px 8px 12px;"):
            bydim = {}
            for p in adopted:
                bydim.setdefault(p["outcome_q"], []).append(p)
            for q in sorted(bydim):
                a = ans.get(q, sysans.get(q, "否"))
                tag, tcol = ATT.get(a, ATT["否"])
                hdr = ui.html(
                    f'<b style="color:{GREEN_DEEP};font-size:.95rem;">Q{q} {hs.SHORT_Q[q-1]}</b>'
                    f'<span style="color:{tcol};font-size:.8rem;margin-left:8px;">· {tag}</span>'
                    f'<span style="color:#9AA0A6;font-size:.76rem;margin-left:10px;">↗ 点此进入该维度评估</span>'
                ).classes("cmap-q").style(
                    f"display:block;padding:8px 10px;margin-top:10px;background:#F2F8F4;"
                    f"border-left:5px solid {tcol};border-radius:6px;")
                hdr.on("click", lambda q=q: (_select_q(q),
                                             mapdlg["d"] and mapdlg["d"].close()))
                for p in bydim[q]:
                    ui.html(_path_flow_html(p, acts)).classes("hia-path").style(
                        "display:block;padding:8px 10px 8px 18px;border-bottom:1px solid #F2F6F3;")

    def pathway_row(p, on_toggle):
        """一条影响 = 一行:勾选 + 把握色块 + 风险/益处 + 影响链;依据/详情按需展开。"""
        with ui.row().classes("items-start no-wrap w-full gap-2"):
            cb = ui.checkbox(value=adopt.get(p["id"], _adopt_default(p))).props("dense")

            def _toggle(e, pid=p["id"]):
                adopt[pid] = e.value
                on_toggle()
            cb.on_value_change(_toggle)
            # 状态徽章三级层级:影响方向 → 证据等级 → 证据状态(规范第 3 节),影响链在下一行
            ui.html(badge_row(p)
                    + _path_flow_html(p, (st["res"] or {}).get("actions", [])))
        cards = p.get("cards") or []
        with ui.expansion("依据 / 详情(点此展开)", icon="menu_book").props(
                "dense").classes("w-full q-mt-xs").style(
                "border:1px dashed #CFE0D5;border-radius:8px;background:#FAFEFB;"):
            if p.get("population"):
                ui.label("主要影响人群:" + p["population"]).classes("text-xs")
            ui.label("证据强度评估:" + STRENGTH_LABEL.get(p["strength"], p["strength"])
                     + "　|　依据来源:" + STATUS_LABEL.get(p["status"], p["status"])).classes("text-xs")
            # 文件原句依据(锚住链路起点):蓝=政策来源,与影响链起点同色
            if p.get("status") == "文档支持" and p.get("evidence"):
                ui.html(
                    _ev_header("📄", "文件原文依据", "var(--hia-source-600)",
                               "下面这段逐字引自上传的政策文件,对应因果链最前段。")
                    + f'<div style="font-size:12.5px;background:var(--hia-source-50);'
                      f'border-radius:6px;padding:7px 11px;margin:5px 0 2px 12px;'
                      f'color:var(--hia-source-800);line-height:1.55;">'
                      f'“{_esc(p["evidence"])}”</div>')
            # 溯源:在政策原文里精确定位这段摘录(可信/可审计)
            _source_button(st.get("text"), p, (st["res"] or {}).get("actions", []))
            # 两轨依据:健康因果(WHO/文献) + 相关国家标准(暴露限值/管控基准)
            render_evidence(cards, p["chain"][-1] if p.get("chain") else "健康结果")
            # —— 专家反馈(可选):标出这条的问题,用于改进系统 ——
            pid = p["id"]
            fb.setdefault(pid, {"flag": "", "note": ""})
            ui.separator()
            ui.html(
                '<div style="display:flex;align-items:center;gap:7px;font-size:13px;'
                'font-weight:500;color:var(--hia-danger-600);border-left:3px solid '
                'var(--hia-danger-400);padding-left:9px;margin-top:2px;">'
                '<span>🚩</span><span>专家反馈</span>'
                '<span style="font-size:11.5px;font-weight:400;color:var(--hia-neutral-500);">'
                '发现机制不成立 / 来源错配?标一下,直接用于改进系统</span></div>')
            with ui.row().classes("items-center gap-2 w-full no-wrap").style(
                    "padding-left:12px;margin-top:4px;"):
                flag_sel = ui.select(["", *fb_engine.FLAGS], value=fb[pid]["flag"]).props(
                    "dense options-dense").style("min-width:130px;font-size:.78rem;")
                flag_sel.on_value_change(lambda e, i=pid: fb[i].__setitem__("flag", e.value or ""))
                ni = ui.input(placeholder="问题说明(可选)").props("dense").classes("flex-grow")
                ni.on_value_change(lambda e, i=pid: fb[i].__setitem__("note", e.value or ""))

    def _select_q(q):
        sel["q"] = q
        tabstrip.refresh()
        panel.refresh()

    def _go(d):
        nq = sel["q"] + d
        if 1 <= nq <= 10:
            _select_q(nq)

    def _open_map():
        graph.refresh()
        if mapdlg["d"]:
            mapdlg["d"].open()

    # ===== 横向选项卡(吸顶,常驻可见)=====
    @ui.refreshable
    def tabstrip():
        allp = all_pathways()
        with ui.element("div").classes("w-full").style(
                "position:sticky;top:0;z-index:50;background:#fff;padding:6px 0;"
                "border-bottom:1px solid #EEF4F0;box-shadow:0 4px 8px -6px rgba(0,0,0,.12);"):
            with ui.row().classes("w-full gap-1").style("flex-wrap:wrap;align-items:stretch;"):
                for q in range(1, 11):
                    a = ans.get(q, sysans.get(q, "否"))
                    on = sel["q"] == q
                    n = sum(1 for p in allp if p["outcome_q"] == q)
                    status = ANSWER_LABEL[a]                     # 需要关注/尚不确定/暂未发现
                    sub = (f"{n} 条 · {status}") if n else ("无影响 · " + status)
                    if on:                                       # 选中态:填实底色 + 白字,无描边
                        cell = ui.element("div").classes("cursor-pointer").style(
                            f"flex:1 1 84px;min-width:84px;border:none;"
                            f"border-radius:var(--hia-radius-md);padding:6px 8px;text-align:center;"
                            f"display:flex;flex-direction:column;justify-content:center;"
                            f"background:{TAB_ACTIVE_BG[a]};box-shadow:0 2px 6px -2px rgba(0,0,0,.30);")
                        with cell:
                            ui.html(
                                f'<div style="font-size:13px;font-weight:500;color:#fff;'
                                f'line-height:1.25;">{q} {hs.SHORT_Q[q-1]}</div>'
                                f'<div style="font-size:11px;font-weight:400;'
                                f'color:{TAB_ACTIVE_SUB[a]};">{sub}</div>')
                    else:                                        # 未选中态:细灰边 + 状态圆点 + 编号标题(单行);副信息进 hover
                        cell = ui.element("div").classes("cursor-pointer").style(
                            f"flex:1 1 84px;min-width:84px;border:0.5px solid var(--hia-border);"
                            f"border-radius:var(--hia-radius-md);padding:6px 8px;"
                            f"background:var(--hia-surface);display:flex;align-items:center;gap:6px;")
                        cell.props(f'title="{sub}"')
                        with cell:
                            ui.html(
                                f'<span style="width:7px;height:7px;border-radius:50%;flex:none;'
                                f'background:{TAB_DOT[a]};"></span>'
                                f'<span style="font-size:13px;font-weight:500;'
                                f'color:var(--hia-neutral-700);line-height:1.25;">'
                                f'{q} {hs.SHORT_Q[q-1]}</span>')
                    cell.on("click", lambda q=q: _select_q(q))

    # ===== 选中方面的内容面板 =====
    @ui.refreshable
    def panel():
        allp = all_pathways()
        q = sel["q"]
        ps = [p for p in allp if p["outcome_q"] == q]
        a = ans.get(q, sysans.get(q, "否"))
        with ui.row().classes("items-center gap-3 w-full q-mt-sm"):
            ui.html(f'<span style="width:26px;height:26px;border-radius:50%;'
                    f'background:{ANSWER_COLOR[a]};color:#fff;display:inline-flex;'
                    f'align-items:center;justify-content:center;font-weight:700;">{q}</span>')
            ui.label(hs.SHORT_Q[q - 1]).style(
                f"color:{GREEN_DEEP};font-size:1.2rem;font-weight:700;")
            ui.html(chip("当前研判:" + ANSWER_FULL[a], ANSWER_COLOR[a]))
        ui.label("初筛表问题:" + hs.QUESTIONS[q - 1]).classes("text-sm").style(
            "color:#5a7a66;")

        @ui.refreshable
        def judge_row():
            a2 = ans.get(q, sysans.get(q, "否"))
            with ui.card().classes("w-full").style(
                    "background:#F6FBF8;border:1px solid #DCEEE3;"):
                with ui.row().classes("items-center gap-4 w-full"):
                    ui.label("您对本方面的判断:").classes("text-sm font-medium")
                    rad = ui.radio({x: ANSWER_LABEL[x] for x in ANSWERS},
                                   value=a2).props("inline")

                    def _setans(e, qq=q):
                        ans[qq] = e.value
                        overridden.add(qq)
                        tabstrip.refresh()
                        summary.refresh()
                    rad.on_value_change(_setans)

        def after_toggle(qq=q, pss=ps):
            sub = [p for p in pss if adopt.get(p["id"])]
            sysans[qq] = hs.compute_items(sub)[qq - 1]["answer"]
            if qq not in overridden:
                ans[qq] = sysans[qq]
            judge_row.refresh()
            tabstrip.refresh()
            summary.refresh()

        if ps:
            for p in ps:
                with ui.card().classes("w-full hia-path").style(
                        "border:1px solid #E8F1EB;border-radius:10px;"
                        "padding:12px 14px;margin-top:6px;"):
                    pathway_row(p, after_toggle)
        else:
            ui.label("系统未找到这一方面的影响,默认「暂未发现」。可在下方直接确认或改判。").classes(
                "text-sm").style("color:#9AA0A6;")

        judge_row()
        note_in = ui.input("说明 / 备注(可选)", value=note.get(q, "")).classes("w-full")
        note_in.on_value_change(lambda e, qq=q: note.__setitem__(qq, e.value))

        # 上一/下一方面,顺序走完 10 个
        with ui.row().classes("w-full items-center justify-between q-mt-sm"):
            ui.button("← 上一方面", on_click=lambda: _go(-1)).props(
                "flat dense" + (" disable" if q == 1 else ""))
            ui.label(f"{q} / 10").classes("text-xs text-grey")
            ui.button("下一方面 →", on_click=lambda: _go(1)).props(
                "flat dense" + (" disable" if q == 10 else ""))

    @ui.refreshable
    def results():
        if not st["res"]:
            return
        res = st["res"]

        if res.get("summary"):
            with ui.card().classes("w-full").style(
                    "background:#EAF4FF;border:1px solid #CFE3FB;"):
                ui.markdown("🧭 **总体研判(供参考):** "
                            + humanize_summary(res["summary"], res.get("actions")))

        ui.label("健康影响一览").classes("text-base font-medium q-mt-sm")
        summary()

        # ===== 评估地图:弹窗 + 右下角浮动按钮(判断时滚到任何位置都能打开)=====
        with ui.dialog() as map_dialog, ui.card().classes("q-pa-none").style(
                "max-width:97vw;width:1200px;border-radius:14px;overflow:hidden;"):
            with ui.row().classes("w-full items-center justify-between q-px-md q-py-sm").style(
                    f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);"
                    f"border-bottom:1px solid #DCEEE3;"):
                with ui.column().classes("gap-0"):
                    ui.label("🗺 健康影响评估因果机制路径").style(
                        f"color:{GREEN_DEEP};font-size:1.1rem;font-weight:700;")
                    ui.label("政策原文 → 影响路径 → 健康结果 → HIA 维度").classes(
                        "text-xs").style("color:#5a7a66;")
                ui.button(icon="close", on_click=map_dialog.close).props("flat round dense")
            with ui.column().classes("w-full q-pa-md gap-2"):
                graph()
        mapdlg["d"] = map_dialog
        # 规范第 6 节(方案 A):原全宽绿条持续遮挡内容(移动端尤甚)→ 收为右下角紧凑入口,
        # 点击即展开完整「因果机制路径」弹窗。不占据正文宽度,不再挡住下方按钮。
        with ui.page_sticky(position="bottom-right", x_offset=18, y_offset=18).style(
                "z-index:6000;"):
            ui.button("因果机制路径图", icon="account_tree", on_click=_open_map).props(
                "rounded color=primary").style(
                "box-shadow:0 6px 18px -4px rgba(46,158,91,.45);text-transform:none;")

        ui.label("逐方面核对、给出判断").classes("text-base font-medium q-mt-md")
        tabstrip()
        panel()

        # ===== 第 4 步:结论 + 下载 =====
        ui.label("第 4 步 · 得出结论并下载初筛表").classes("text-base font-medium q-mt-md")
        with ui.row().classes("items-center gap-3 w-full"):
            ui.label("总体影响程度:").classes("text-sm")
            # 不预选——关系到结论严肃性,由专家主动选择,避免不经意提交偏重判断;AI 初判仅作提示。
            level_radio = ui.radio(["很小", "轻度", "重大"], value=None).props("inline dense")
            ai_lv = res.get("suggest_level") if res.get("suggest_level") in (
                "很小", "轻度", "重大") else ""
            if ai_lv:
                ui.label(f"系统初判:{ai_lv}（仅供参考，请专家确认）").classes("text-xs").style(
                    "color:var(--hia-neutral-500);")
        with ui.row().classes("w-full items-center"):
            name_in = ui.input("评估对象名称(用于初筛表标题,可改)",
                               value=st.get("name", "")).classes("flex-grow")
        opinion_in = ui.textarea("评估专家组意见(可选)").classes("w-full")

        def do_download():
            if not level_radio.value:
                ui.notify("请先选择「总体影响程度」再导出初筛表。", type="warning")
                return
            header = {"name": name_in.value, "category": "政府发布/实施",
                      "dept": "", "submitter": "", "phone": "",
                      "screen_date": str(date.today()),
                      "method": "智能分析辅助 + 专家核定(健康影响路径展开)",
                      "related_dept": ""}
            items_out = [{"q": q, "answer": ans.get(q, sysans.get(q, "否")),
                          "note": note.get(q, "")} for q in range(1, 11)]
            adopted = [p for p in allp if adopt.get(p["id"])]
            buf = hs.build_screen_docx(header, items_out, adopted,
                                       level_radio.value, opinion_in.value)
            ui.download(buf.getvalue(),
                        f"健康影响评估初筛表_{name_in.value or '评估对象'}.docx")

        def do_save_ledger():
            if not level_radio.value:
                ui.notify("请先选择「总体影响程度」再存入项目管理。", type="warning")
                return
            items_out = [{"q": q, "answer": ans.get(q, sysans.get(q, "否")),
                          "note": note.get(q, "")} for q in range(1, 11)]
            adopted_ids = [p["id"] for p in allp if adopt.get(p["id"])]
            case = case_store.save_single_case(
                name_in.value or st.get("name", ""), st["res"], st["docinfo"],
                items_out, level_radio.value, opinion_in.value,
                doc_bytes=st.get("file_bytes"), doc_filename=st.get("file_name", ""),
                adopted_ids=adopted_ids)
            ui.notify(f"✅ 已存入项目管理系统(案例码 {case['id']});可在「项目管理」中查看、"
                      f"重新导出或归档。", type="positive", timeout=6000)

        with ui.row().classes("items-center gap-3 q-mt-sm"):
            ui.button("📄 下载《健康影响评估初筛表》(Word)", on_click=do_download).props(
                "color=primary")
            ui.button("🗂 存入项目管理", on_click=do_save_ledger).props("outline color=primary")
        ui.label("初筛表已填好 10 项判断、各项采纳的影响与依据、结论与签字栏。"
                 "系统仅辅助梳理,签字与最终结论以专家为准。"
                 "「存入项目管理」会把本次评估归档,便于日后查阅和重新导出。").classes(
            "text-xs text-grey")

        # ===== 第 5 步(可选):提交专家反馈,用于持续改进系统 =====
        ui.separator()
        ui.label("第 5 步 · 提交专家反馈(可选,帮助改进系统)").classes(
            "text-base font-medium q-mt-md")
        ui.label("您的采纳/排除与判定会直接用于改进系统的路径推断与证据库——欢迎花一分钟反馈。").style(
            "font-size:13px;font-weight:500;color:var(--hia-neutral-700);")
        ui.label("（您在各条影响处的标记将匿名留痕,不含个人信息。）").classes("text-xs text-grey")
        expert_in = ui.input("专家署名(可选)").classes("w-full")

        def do_feedback():
            entries = []
            for p in allp:
                pid = p["id"]
                f = fb.get(pid, {})
                flag, fnote = f.get("flag", ""), f.get("note", "")
                adopted = bool(adopt.get(pid, _adopt_default(p)))
                # 只记录"有信号"的:标了问题、或被排除的
                if not flag and adopted:
                    continue
                entries.append({
                    "project": name_in.value or st.get("name", ""),
                    "expert": expert_in.value or "",
                    "pathway_id": pid, "outcome_q": p["outcome_q"],
                    "chain": p["chain"], "strength": p["strength"], "status": p["status"],
                    "cards": [s for c in (p.get("cards") or []) for s in c["sources"]],
                    "adopted": adopted, "flag": flag, "note": fnote,
                })
            n = fb_engine.record_many(entries)
            if n:
                ui.notify(f"已保存 {n} 条专家反馈,感谢!将用于改进系统。", type="positive")
            else:
                ui.notify("未发现需记录的反馈(没有标记问题、也没有排除任何影响)。", type="info")

        ui.button("💾 保存专家反馈", on_click=do_feedback).props("outline color=primary")
        ui.label("提示:在上方任意影响的「依据/详情」里用 🚩 标记问题(机制不成立/来源错配等),"
                 "或排除不认可的影响,再点此保存。").classes("text-xs text-grey")

        # 底部留白:角落悬浮入口已不占正文宽度,仅留少量间距避免遮住末行按钮
        ui.element("div").style("height:40px;")

    results()


# ==================== 专家组协同初筛(独立板块)====================

# —— 设计 Token(规范第 1 节):颜色只承担 害=红 / 益=绿 / 政策来源=蓝 / 证据等级=橙 / 中性=灰 ——
# 全站统一注入(/screen 内联 head 与 _page_head 各注一次),后续导航标签/徽章/路径链均引用这些变量。
_TOKENS_CSS = (
    ":root{"
    "--hia-danger-50:#FCEBEB;--hia-danger-200:#F09595;--hia-danger-400:#E24B4A;"
    "--hia-danger-600:#A32D2D;--hia-danger-800:#791F1F;"
    "--hia-benefit-50:#EAF3DE;--hia-benefit-100:#C0DD97;--hia-benefit-400:#639922;"
    "--hia-benefit-600:#3B6D11;--hia-benefit-800:#27500A;--hia-benefit-900:#173404;"
    "--hia-source-50:#E6F1FB;--hia-source-600:#185FA5;--hia-source-800:#0C447C;"
    "--hia-grade-50:#FAEEDA;--hia-grade-600:#BA7517;--hia-grade-800:#854F0B;"
    "--hia-neutral-50:#F1EFE8;--hia-neutral-200:#B4B2A9;--hia-neutral-500:#5F5E5A;"
    "--hia-neutral-700:#444441;"
    "--hia-surface:#FFFFFF;--hia-surface-muted:#F7F6F2;"
    "--hia-border:rgba(0,0,0,0.12);--hia-border-strong:rgba(0,0,0,0.20);"
    "--hia-radius-md:8px;--hia-radius-lg:12px;"
    "}")


# 因果路径链样式(规范第 4 节):浅灰底容器 + 三段颜色编码
#   政策原文=蓝(.origin) / 中间环节=白底细灰边·中性字 / 最终结果=实色块(益绿/害红,13px·500)
#   普通箭头灰;指向最终结果的箭头染成对应语义色(.hia-arrow--benefit/--risk)。字重只用 400/500。
_FLOW_CSS = (
    ".hia-flow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;line-height:1.8;"
    "background:var(--hia-surface-muted);padding:14px;border-radius:var(--hia-radius-lg);}"
    ".hia-node{display:inline-flex;align-items:center;padding:8px 12px;"
    "border-radius:var(--hia-radius-md);font-size:12px;font-weight:400;"
    "background:#EFEDE6;border:none;"
    "color:var(--hia-neutral-500);}"
    ".hia-node.origin{background:var(--hia-source-50);border:none;"
    "color:var(--hia-source-800);max-width:340px;font-style:italic;}"
    ".hia-node.outcome-risk{background:var(--hia-danger-200);border:none;"
    "color:var(--hia-danger-800);font-size:13px;font-weight:500;}"
    ".hia-node.outcome-benefit{background:var(--hia-benefit-100);border:none;"
    "color:var(--hia-benefit-900);font-size:13px;font-weight:500;}"
    ".hia-arrow{color:var(--hia-neutral-200);font-weight:400;font-size:.95rem;}"
    ".hia-arrow--benefit{color:var(--hia-benefit-600);}"
    ".hia-arrow--risk{color:var(--hia-danger-400);}")


def _page_head():
    ui.query(".nicegui-content").classes("mx-auto").style("max-width:1000px;")
    ui.add_head_html('<meta name="robots" content="noindex,nofollow,noarchive">')
    ui.add_head_html("<style>" + _TOKENS_CSS +
                     "body{font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;}"
                     ".hia-chain{line-height:1.5;}" + _FLOW_CSS + "</style>")
    ui.colors(primary=GREEN)


# 全站统一顶部导航(平台名 + 三大板块);active ∈ {"new","ledger","reference"}
# 规范第 7 节:四项统一 14px + 间距,字重只用 400/500;「新建评估」NEW 标记缩为小角标(不喧宾夺主)。
_NAV_ITEMS = [("新建评估", "/new", "new", True),
              ("🩺 批量体检", "/batch", "batch", False),
              ("🗂 项目管理", "/ledger", "ledger", False),
              ("📚 案例参考", "/reference", "reference", False)]
_NEW_BADGE = ('<sup style="font-size:9px;font-weight:500;color:#fff;'
              'background:var(--hia-benefit-600);border-radius:6px;padding:0 4px;'
              'margin-left:3px;vertical-align:super;line-height:1;">NEW</sup>')


def _top_nav(active=""):
    with ui.row().classes("w-full items-center gap-5 q-py-xs").style(
            "border-bottom:1px solid var(--hia-border);margin-bottom:8px;flex-wrap:wrap;"):
        with ui.link(target="/").props("no-underline").style(
                "color:var(--hia-neutral-700);font-weight:500;font-size:14px;"):
            ui.html("← 返回首页")
        ui.element("div").style("flex:1;")
        for label, href, key, is_new in _NAV_ITEMS:
            on = (key == active)
            with ui.link(target=href).props("no-underline").style(
                    f"color:{GREEN_DEEP if on else 'var(--hia-neutral-500)'};"
                    f"font-weight:{'500' if on else '400'};font-size:14px;"
                    + ("border-bottom:2px solid " + GREEN + ";" if on else "")):
                ui.html(label + (_NEW_BADGE if is_new else ""))


def render_pathway_ro(p, actions=None, doc_text=None):
    """只读渲染一条影响(供专家评审/汇总页):徽标行 + 影响链(节点流) + 依据折叠。
    传入 doc_text(政策原文)则附「在原文中定位」溯源按钮。"""
    ui.html(badge_row(p) + _path_flow_html(p, actions or []))
    cards = p.get("cards") or []
    with ui.expansion("依据 / 详情", icon="menu_book").props("dense").classes(
            "w-full q-mt-xs").style("border:1px dashed #CFE0D5;border-radius:8px;background:#FAFEFB;"):
        if p.get("population"):
            ui.label("主要影响人群:" + p["population"]).classes("text-xs")
        if p.get("status") == "文档支持" and p.get("evidence"):
            ui.label("📄 文件原文依据:" + p["evidence"]).classes("text-xs")
        _source_button(doc_text, p, actions)
        render_evidence(cards, p["chain"][-1] if p.get("chain") else "健康结果")


def _copy_invite(case):
    """把「评审链接(自动带服务器地址)+ 口令」组成一条可直接粘贴的邀请,复制到剪贴板。"""
    invite = ("【健康影响评估 · 专家评审邀请】\n"
              f"评估对象:{case['name']}\n"
              f"评审链接:__ORIGIN__/review/{case['id']}\n"
              f"评审口令:{case['expert_pwd']}\n"
              "请打开链接、输入口令后独立完成评定。")
    ui.run_javascript("navigator.clipboard.writeText("
                      + json.dumps(invite) + ".replace('__ORIGIN__', window.location.origin))")
    ui.notify("已复制完整邀请(含链接+口令),可直接粘贴到微信/邮件。", type="positive")


def _created_case_card(case):
    with ui.card().classes("w-full").style("background:#F1F8F4;border:1px solid #CFE0D5;"):
        ui.label(f"✅ 案例已创建:{case['name']}").classes("font-medium")
        with ui.row().classes("items-center gap-4 flex-wrap"):
            ui.label(f"案例码:{case['id']}").style("font-family:monospace;font-size:.95rem;")
            ui.label(f"专家口令:{case['expert_pwd']}").style("font-family:monospace;font-size:.95rem;")
        ui.label("把「专家评审链接 + 口令」发给各位专家(微信/邮件均可):").classes("text-xs text-grey")
        ui.input("专家评审链接", value=f"/review/{case['id']}").props(
            "readonly dense").classes("w-full").style("font-family:monospace;")
        ui.button("📋 复制完整邀请(链接+口令)",
                  on_click=lambda c=case: _copy_invite(c)).props("color=primary")
        ui.label("提示:复制的链接会自动带上本服务器地址,口令也一并包含,直接粘贴发送即可。").classes(
            "text-xs text-grey")


@ui.page("/panel")
def panel():
    if not require_app_login():
        return
    _page_head()
    _top_nav("new")
    with ui.row().classes("w-full items-center justify-between q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("卫生健康主管部门工作人员 · 发起方").style(
                f"color:{GREEN};letter-spacing:1px;font-size:.85rem;font-weight:600;")
            ui.label("发起专家组协同评估 · 经办台").style(
                f"color:{GREEN_DEEP};font-size:1.5rem;font-weight:700;")
            ui.label("您在此:上传文档→AI 初筛→创建案例→把「评审链接+口令」发给专家→汇总共识→组长定稿。"
                     "专家无需账号,凭链接+口令即可评定。").style(
                "color:#5a7a66;font-size:.85rem;")
        ui.link("单人快速初筛 →", "/screen").props("no-underline").style(
            f"color:{GREEN_DEEP};font-weight:600;")

    new = {"bytes": None, "fname": "", "name": ""}

    # ===== 创建新案例 =====
    with ui.expansion("➕ 创建新案例(上传文档 + AI 初筛)", value=True, icon="add_box").classes(
            "w-full").style("border:1px solid #DCEEE3;border-radius:10px;"):
        async def on_up(e):
            new["bytes"] = await e.file.read()
            new["fname"] = e.file.name
            if not name_in.value:
                name_in.value = e.file.name.rsplit(".", 1)[0]
            ui.notify(f"已上传:{e.file.name}", type="positive")

        ui.upload(on_upload=on_up, auto_upload=True, max_files=1).props(
            'accept=".pdf,.docx" flat bordered').classes("w-full")
        with ui.row().classes("w-full items-center"):
            name_in = ui.input("评估对象名称").classes("flex-grow")
            n_exp = ui.number("专家人数", value=3, min=1, max=15, format="%d").classes("w-32")
        key_in = ui.input("分析服务密钥(API Key)", password=True, value=_get_key(),
                          placeholder="sk-...").classes("w-full")
        created_box = ui.column().classes("w-full")

        async def do_create():
            if not new["bytes"]:
                ui.notify("请先上传文档。", type="warning"); return
            key = (key_in.value or "").strip()
            if not key:
                ui.notify("请填写分析服务密钥。", type="warning"); return
            text, info = hs.extract_text(new["fname"], new["bytes"])
            if info.get("error"):
                ui.notify(info["error"], type="negative"); return
            create_btn.disable()
            n = ui.notification("AI 初筛中(约 30–60 秒)…", spinner=True, timeout=None)
            try:
                res = await run.io_bound(hs.analyze, text, key, project_name=name_in.value or "")
            except Exception as ex:                       # noqa: BLE001
                n.dismiss(); create_btn.enable(); ui.notify(f"分析失败:{ex}", type="negative"); return
            n.dismiss(); create_btn.enable()
            case = case_store.create_case(name_in.value or new["name"], res, info,
                                          n_experts=int(n_exp.value or 3),
                                          doc_bytes=new["bytes"], doc_filename=new["fname"])
            created_box.clear()
            with created_box:
                _created_case_card(case)
            cases_list.refresh()
            ui.notify("案例已创建,可在下方列表查看汇总。", type="positive")

        create_btn = ui.button("🔍 开始 AI 初筛并创建案例", on_click=do_create).props("color=primary")

    # ===== 案例列表 + 汇总/定稿 =====
    ui.label("案例列表").classes("text-base font-medium q-mt-md")

    @ui.refreshable
    def cases_list():
        cs = case_store.list_cases()
        if not cs:
            ui.label("(暂无案例。用上方「创建新案例」开始。)").classes("text-xs text-grey")
            return
        for c in cs:
            done = len(c.get("reviews", []))
            with ui.expansion().classes("w-full").style(
                    "border:1px solid #DCEEE3;border-radius:10px;margin-bottom:6px;") as exp:
                with exp.add_slot("header"):
                    with ui.row().classes("items-center gap-3 w-full"):
                        ui.label(f"{c['name']}").classes("text-sm font-medium")
                        st_color = "#1B6B3A" if c["status"] == "已定稿" else "#B07A00"
                        ui.html(chip(c["status"], st_color))
                        ui.label(f"专家提交 {done}/{c['n_experts']}　·　案例码 {c['id']}"
                                 f"　·　{c['created']}").classes("text-xs text-grey")
                _render_case_panel(c, cases_list)

    cases_list()


def _render_case_panel(c, refresher):
    """经办台里单个案例:评审链接 + 逐题共识/分歧 + 组长定稿 + 导出。"""
    cid = c["id"]
    ui.label(f"专家评审链接:/review/{cid}　|　口令:{c['expert_pwd']}").classes(
        "text-xs").style("font-family:monospace;color:#5a7a66;")
    dp = case_store.doc_path(c)
    if dp:
        ui.button("📄 政策原文(" + (c.get("doc_name") or "文件") + ")",
                  on_click=lambda d=dp, n=c.get("doc_name") or "policy": ui.download(d, n)).props(
            "flat dense color=primary")
    reviews = c.get("reviews", [])
    if not reviews:
        ui.label("尚无专家提交。把链接+口令发给专家即可。").classes("text-xs text-grey")
        return
    ui.label(f"已提交专家:" + "、".join(r.get("expert") or "(匿名)" for r in reviews)).classes(
        "text-xs text-grey")
    cv = case_store.consensus_view(c)
    res_items = {it["q"]: it for it in c["res"].get("items", [])}
    final = {}     # q -> 组长定稿答案(默认多数意见或系统初判)

    ui.label("逐题共识(各专家判定分布;🔶 标分歧)").classes("text-sm font-medium q-mt-sm")
    for q in range(1, 11):
        v = cv[q]
        dist = "　".join(f"{ANSWER_LABEL[a]}×{n}" for a, n in v["counts"].items()) or "(无人评)"
        default = v["majority"] or res_items.get(q, {}).get("answer", "否")
        with ui.row().classes("items-center gap-3 w-full"):
            tag = "🔶" if v["divergent"] else "　"
            ui.label(f"{tag} {q}. {hs.SHORT_Q[q-1]}").classes("text-sm").style("min-width:150px;")
            ui.label(dist).classes("text-xs text-grey").style("min-width:160px;")
            rad = ui.radio({a: ANSWER_LABEL[a] for a in case_store.ANSWERS},
                           value=default).props("inline dense")
            final[q] = default
            rad.on_value_change(lambda e, qq=q: final.__setitem__(qq, e.value))

    leader_in = ui.input("组长署名").classes("w-full")
    level_default = c["res"].get("suggest_level") if c["res"].get("suggest_level") in (
        "很小", "轻度", "重大") else "轻度"
    with ui.row().classes("items-center gap-3"):
        ui.label("总体影响程度:").classes("text-sm")
        level_rad = ui.radio(["很小", "轻度", "重大"], value=level_default).props("inline dense")
    op_in = ui.textarea("专家组共识意见").classes("w-full")

    def do_finalize_and_export():
        items_out = [{"q": q, "answer": final.get(q, "否"), "note": ""} for q in range(1, 11)]
        case_store.finalize(cid, items_out, level_rad.value, op_in.value, by=leader_in.value)
        adopted = [p for p in c["res"]["pathways"]
                   if p.get("status") != "假设待证"]
        header = {"name": c["name"], "category": "政府发布/实施", "dept": "", "submitter": "",
                  "phone": "", "screen_date": str(date.today()),
                  "method": "AI 辅助 + 专家组协同核定(共识)", "related_dept": ""}
        buf = hs.build_screen_docx(header, items_out, adopted, level_rad.value, op_in.value)
        ui.download(buf.getvalue(), f"健康影响评估初筛表_{c['name']}_专家组共识.docx")
        refresher.refresh()
        ui.notify("已定稿并导出共识初筛表。", type="positive")

    ui.button("✅ 组长定稿并导出共识初筛表", on_click=do_finalize_and_export).props("color=primary")


@ui.page("/review/{cid}")
def review(cid):
    _page_head()
    case = case_store.load_case(cid)
    if not case:
        ui.label("未找到该案例(案例码有误或已删除)。").classes("text-negative q-pa-lg")
        return

    with ui.row().classes("w-full items-center q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("受邀专家 · 独立评审").style(
                f"color:{GREEN};letter-spacing:1px;font-size:.85rem;font-weight:600;")
            ui.label("健康影响评估 · 专家评审").style(
                f"color:{GREEN_DEEP};font-size:1.4rem;font-weight:700;")
            ui.label(f"评估对象:{case['name']}　·　发起方已邀请您对其进行独立评定").style(
                "color:#5a7a66;font-size:.9rem;")

    gate = {"ok": False}
    body = ui.column().classes("w-full")

    def render_body():
        body.clear()
        with body:
            _render_review_form(case)

    def check_pwd():
        if (pwd_in.value or "").strip() == case["expert_pwd"]:
            gate["ok"] = True
            gate_box.clear()
            render_body()
        else:
            ui.notify("口令不正确,请向经办人员索取。", type="negative")

    gate_box = ui.column().classes("w-full")
    with gate_box:
        ui.label(f"您受邀对「{case['name']}」进行独立评审。").classes("q-mt-md text-sm")
        ui.label("请输入发起方(经办人员)随链接一同发来的评审口令:").classes("text-xs text-grey")
        pwd_in = ui.input("评审口令", password=True).on("keydown.enter", check_pwd)
        ui.button("进入评审", on_click=check_pwd).props("color=primary")


def _render_review_form(case):
    res = case["res"]
    allp = res.get("pathways", [])
    res_items = {it["q"]: it for it in res.get("items", [])}
    doc_text = _case_doc_text(case)               # 供专家在原文里核对每条依据
    ans, note = {}, {}

    # —— 给专家的任务说明(你只需做这三步)——
    with ui.card().classes("w-full q-mt-sm").style(
            "background:#F1F8F4;border:1px solid #CFE0D5;"):
        ui.label("您的任务(约 5–10 分钟)").classes("font-medium").style(
            f"color:{GREEN_DEEP};")
        ui.label("① 阅读政策原文 → ② 逐个健康方面核对 AI 梳理的影响、给出您的独立判断 → "
                 "③ 署名提交。您的判断将与其他专家汇总成共识,由组长定稿。").classes(
            "text-xs").style("color:#5a7a66;line-height:1.7;")

    # 政策原文(供专家先读原件,再核对 AI 草案)
    dp = case_store.doc_path(case)
    if dp:
        ui.button("📄 查看 / 下载政策原文(" + (case.get("doc_name") or "文件") + ")",
                  on_click=lambda: ui.download(dp, case.get("doc_name") or "policy")).props(
            "color=primary").classes("q-mt-sm")
        ui.label("建议先阅读政策原文,再逐条核对下方 AI 梳理的健康影响。").classes(
            "text-xs text-grey")
    else:
        ui.label("⚠ 本案例未随附政策原文(可能为旧案例);如需原件请联系经办人员。").classes(
            "text-xs").style("color:#B07A00;")

    if res.get("summary"):
        with ui.card().classes("w-full").style("background:#EAF4FF;border:1px solid #CFE3FB;"):
            ui.markdown("🧭 **AI 总体研判(供参考):** " + res["summary"])
    ui.label("请逐个健康方面核对 AI 梳理的影响,并给出您的独立判断。").classes("text-sm q-mt-sm")

    for q in range(1, 11):
        ps = [p for p in allp if p["outcome_q"] == q]
        sa = res_items.get(q, {}).get("answer", "否")
        ans[q] = sa
        with ui.expansion(value=(sa == "是")).classes("w-full").style(
                "border:1px solid #DCEEE3;border-radius:10px;margin-bottom:6px;") as exp:
            with exp.add_slot("header"):
                with ui.row().classes("items-center gap-3 w-full"):
                    ui.icon("expand_more").classes("text-grey")
                    ui.label(f"{q}. {hs.SHORT_Q[q-1]}").classes("text-sm font-medium").style(
                        "min-width:96px;")
                    ui.html(chip("AI 初判:" + ANSWER_LABEL[sa], ANSWER_COLOR[sa]))
                    ui.label(f"{len(ps)} 条影响" if ps else "无影响").classes("text-xs text-grey")
            ui.label("初筛表问题:" + hs.QUESTIONS[q - 1]).classes("text-xs text-grey")
            for p in ps:
                render_pathway_ro(p, res.get("actions", []), doc_text)
            if not ps:
                ui.label("AI 未找到这一方面的影响。").classes("text-xs text-grey")
            ui.separator()
            with ui.row().classes("items-center gap-3 w-full"):
                ui.label("您的判断:").classes("text-sm")
                rad = ui.radio({a: ANSWER_LABEL[a] for a in case_store.ANSWERS}, value=sa).props(
                    "inline dense")
                rad.on_value_change(lambda e, qq=q: ans.__setitem__(qq, e.value))
            ni = ui.input("说明 / 备注(可选)").classes("w-full")
            ni.on_value_change(lambda e, qq=q: note.__setitem__(qq, e.value))

    ui.separator()
    expert_in = ui.input("您的署名(必填)").classes("w-full")
    lv_default = res.get("suggest_level") if res.get("suggest_level") in (
        "很小", "轻度", "重大") else "轻度"
    with ui.row().classes("items-center gap-3"):
        ui.label("总体影响程度:").classes("text-sm")
        level_rad = ui.radio(["很小", "轻度", "重大"], value=lv_default).props("inline dense")
    op_in = ui.textarea("评审意见(可选)").classes("w-full")

    def submit():
        if not (expert_in.value or "").strip():
            ui.notify("请填写您的署名。", type="warning"); return
        case_store.add_review(case["id"], {
            "expert": expert_in.value.strip(),
            "answers": {str(q): ans.get(q, "否") for q in range(1, 11)},
            "notes": {str(q): note.get(q, "") for q in range(1, 11)},
            "level": level_rad.value, "opinion": op_in.value or "",
        })
        ui.notify("✅ 评审已提交,感谢!可关闭页面。", type="positive")

    ui.button("✅ 提交评审", on_click=submit).props("color=primary").classes("q-mt-sm")
    ui.label("提交后,经办/组长将在汇总台看到您的判断并形成专家组共识。").classes(
        "text-xs text-grey")


# ==================== 项目管理系统(既往评估项目统一管理)====================

STATUS_COLOR = {"评审中": "#B07A00", "已定稿": "#1B6B3A",
                "已归档": "#5a7a66", "作废": "#9AA0A6"}
SOURCE_COLOR = {case_store.SOURCE_SINGLE: "#2E6DB4", case_store.SOURCE_PANEL: GREEN_DEEP}


def _case_export_payload(c):
    """统一取一个案例的(items, level, opinion, 是否已定稿)用于重新导出。
    已定稿(单人/协同共识)用 consensus;否则回落 AI 初判草案。"""
    con = c.get("consensus")
    if con and con.get("items"):
        return con["items"], con.get("level") or "轻度", con.get("opinion") or "", True
    res = c.get("res") or {}
    items = res.get("items") or [{"q": q, "answer": "否", "note": ""} for q in range(1, 11)]
    return items, res.get("suggest_level") or "轻度", "", False


@ui.page("/ledger")
def ledger():
    if not require_app_login():
        return
    _page_head()
    _top_nav("ledger")
    with ui.row().classes("w-full items-center justify-between q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("项目管理 · 既往评估项目").style(
                f"color:{GREEN_DEEP};font-size:1.5rem;font-weight:700;")
            ui.label("单人初筛与专家协同的所有评估项目统一在此查阅、重新导出初筛表、归档、发布为参考案例").style(
                "color:#5a7a66;font-size:.85rem;")

    flt = {"q": "", "status": "全部", "source": "全部"}

    # ===== 筛选条 =====
    with ui.row().classes("w-full items-center gap-3 q-mt-sm"):
        q_in = ui.input("按名称搜索", placeholder="输入评估对象名称关键字").props(
            "dense clearable").classes("flex-grow")
        q_in.on_value_change(lambda e: (flt.__setitem__("q", (e.value or "").strip()),
                                        rows.refresh()))
        st_sel = ui.select(["全部", *case_store.STATUSES], value="全部", label="状态").props(
            "dense options-dense").style("min-width:120px;")
        st_sel.on_value_change(lambda e: (flt.__setitem__("status", e.value), rows.refresh()))
        src_sel = ui.select(["全部", case_store.SOURCE_SINGLE, case_store.SOURCE_PANEL],
                            value="全部", label="来源").props("dense options-dense").style(
            "min-width:120px;")
        src_sel.on_value_change(lambda e: (flt.__setitem__("source", e.value), rows.refresh()))

    stat_box = ui.row().classes("w-full gap-3 q-mt-xs")
    ui.separator().classes("q-mt-sm")

    def _match(c):
        if flt["q"] and flt["q"] not in (c.get("name") or ""):
            return False
        if flt["status"] != "全部" and c.get("status") != flt["status"]:
            return False
        if flt["source"] != "全部" and c.get("source", case_store.SOURCE_PANEL) != flt["source"]:
            return False
        return True

    @ui.refreshable
    def rows():
        allc = case_store.list_cases()
        # 顶部小统计(总数 + 按状态)
        stat_box.clear()
        with stat_box:
            ui.label(f"共 {len(allc)} 个项目").classes("text-xs text-grey")
            for sname in case_store.STATUSES:
                n = sum(1 for c in allc if c.get("status") == sname)
                if n:
                    ui.html(chip(f"{sname} {n}", STATUS_COLOR.get(sname, "#888")))
        cs = [c for c in allc if _match(c)]
        if not cs:
            ui.label("(没有符合条件的项目。)").classes("text-xs text-grey q-mt-md")
            return
        for c in cs:
            _ledger_row(c, rows)

    rows()


def _ledger_row(c, refresher):
    cid = c["id"]
    src = c.get("source", case_store.SOURCE_PANEL)
    status = c.get("status", "评审中")
    con = c.get("consensus") or {}
    level = con.get("level")
    with ui.expansion().classes("w-full").style(
            "border:1px solid #DCEEE3;border-radius:10px;margin-bottom:6px;") as exp:
        with exp.add_slot("header"):
            with ui.row().classes("items-center gap-3 w-full no-wrap"):
                ui.label(c.get("name") or "评估对象").classes("text-sm font-medium").style(
                    "min-width:160px;")
                ui.html(chip(src, SOURCE_COLOR.get(src, "#888")))
                ui.html(chip(status, STATUS_COLOR.get(status, "#888")))
                if c.get("reference"):
                    ui.html(chip("⭐ 参考案例", "#C9870A"))
                if level:
                    ui.label(f"影响:{level}").classes("text-xs text-grey")
                extra = ""
                if src == case_store.SOURCE_PANEL:
                    extra = f"专家 {len(c.get('reviews', []))}/{c.get('n_experts', 0)}　·　"
                ui.label(f"{extra}案例码 {cid}　·　{c.get('created', '')}").classes(
                    "text-xs text-grey")

        # —— 10 题判定一览 ——
        items, lv, opinion, finalized = _case_export_payload(c)
        amap = {it["q"]: it.get("answer", "否") for it in items}
        with ui.row().classes("w-full gap-1 q-mt-xs"):
            for q in range(1, 11):
                a = amap.get(q, "否")
                ui.html(f'<div title="{q}. {hs.SHORT_Q[q-1]}:{ANSWER_LABEL[a]}" '
                        f'style="flex:1;height:12px;border-radius:3px;'
                        f'background:{ANSWER_COLOR[a]};"></div>').classes("flex-grow")
        tag = "专家组共识" if (finalized and src == case_store.SOURCE_PANEL) else (
            "专家核定" if finalized else "AI 初判草案(未定稿)")
        ui.label(f"判定依据:{tag}" + (f"　|　总体影响:{lv}" if finalized else "")).classes(
            "text-xs text-grey")
        if opinion:
            ui.label("专家意见:" + opinion).classes("text-xs text-grey")

        # —— 操作区 ——
        with ui.row().classes("items-center gap-2 q-mt-sm flex-wrap"):
            def do_reexport(case=c):
                its, lvl, op, _ = _case_export_payload(case)
                header = {"name": case["name"], "category": "政府发布/实施", "dept": "",
                          "submitter": "", "phone": "",
                          "screen_date": (case.get("created") or "")[:10] or str(date.today()),
                          "method": ("AI 辅助 + 专家组协同核定(共识)"
                                     if case.get("source") == case_store.SOURCE_PANEL
                                     else "智能分析辅助 + 专家核定"),
                          "related_dept": ""}
                adopted = case_store.adopted_pathways(case)
                buf = hs.build_screen_docx(header, its, adopted, lvl, op)
                ui.download(buf.getvalue(),
                            f"健康影响评估初筛表_{case['name']}.docx")
            ui.button("📄 重新导出初筛表", on_click=do_reexport).props("dense flat color=primary")

            dp = case_store.doc_path(c)
            if dp:
                ui.button("📎 政策原文", on_click=lambda d=dp, n=c.get("doc_name") or "policy":
                          ui.download(d, n)).props("dense flat color=primary")

            if src == case_store.SOURCE_PANEL:
                ui.button("👥 去经办台", on_click=lambda: ui.navigate.to("/panel")).props(
                    "dense flat color=primary")

            # 状态流转
            def chg(new_status, case_id=cid):
                case_store.set_status(case_id, new_status)
                ui.notify(f"状态已更新:{new_status if new_status != '恢复' else '已恢复'}",
                          type="positive")
                refresher.refresh()
            if status in ("已定稿",):
                ui.button("📦 归档", on_click=lambda: chg("已归档")).props("dense flat")
            if status in ("评审中", "已定稿"):
                ui.button("🚫 作废", on_click=lambda: chg("作废")).props("dense flat color=grey")
            if status in ("已归档", "作废"):
                ui.button("↩ 恢复", on_click=lambda: chg("恢复")).props("dense flat color=primary")

            # 发布/取消「参考案例」(仅已定稿可发布)
            def toggle_ref(case_id=cid, cur=bool(c.get("reference"))):
                case_store.set_reference(case_id, not cur)
                ui.notify("已发布为参考案例。" if not cur else "已从参考案例中移除。",
                          type="positive")
                refresher.refresh()
            if c.get("reference"):
                ui.button("⭐ 取消参考案例", on_click=toggle_ref).props("dense flat color=amber")
            elif status == "已定稿":
                ui.button("📣 发布为参考案例", on_click=toggle_ref).props("dense flat color=primary")

            # 删除(二次确认)
            def ask_delete(case=c):
                with ui.dialog() as dlg, ui.card():
                    ui.label(f"确认删除「{case['name']}」?").classes("font-medium")
                    ui.label("将彻底删除该项目记录与政策原文,不可恢复。").classes(
                        "text-xs text-grey")
                    with ui.row().classes("justify-end w-full"):
                        ui.button("取消", on_click=dlg.close).props("flat")

                        def really():
                            case_store.delete_case(case["id"])
                            dlg.close()
                            ui.notify("已删除。", type="positive")
                            refresher.refresh()
                        ui.button("删除", on_click=really).props("color=negative")
                dlg.open()
            ui.button("🗑 删除", on_click=ask_delete).props("dense flat color=negative")


# ==================== 门户首页 / 新建评估分流 / 案例参考 ====================

def _portal_card(icon, title, desc, href, accent=GREEN):
    with ui.card().classes("cursor-pointer").style(
            "width:280px;border:1px solid #DCEEE3;border-radius:14px;padding:20px;"
            "transition:box-shadow .15s;").on("click", lambda: ui.navigate.to(href)):
        ui.label(icon).style("font-size:2.2rem;")
        ui.label(title).style(f"color:{GREEN_DEEP};font-size:1.15rem;font-weight:700;margin-top:4px;")
        ui.label(desc).classes("text-xs").style("color:#5a7a66;line-height:1.6;min-height:48px;")
        ui.element("div").style(f"height:3px;width:38px;background:{accent};border-radius:2px;")


# ==================== 证据库管理(自助维护证据卡)====================

EV_Q_OPTS = {f"Q{i}": f"Q{i} · {hs.SHORT_Q[i-1]}" for i in range(1, 11)}


def _ev_split(s):
    return [x.strip() for x in re.split(r"[、,，;；\s]+", s or "") if x.strip()]


def _ev_lines(s):
    return [x.strip() for x in (s or "").splitlines() if x.strip()]


def _ev_derive(keys, q, note, sources, kind):
    """据当前输入派生 (kind, 来源等级) 供保存前预览。"""
    card = {"keys": keys, "q": q, "note": note, "sources": sources}
    if kind in ("因果", "基准"):
        card["kind"] = kind
    return hia_evidence.card_kind(card), hia_evidence.card_tier(card)[1]


def _ev_kind_color(kind):
    return GREEN_DEEP if kind == "因果" else "#5F5E5A"   # 因果=绿(健康因果) / 基准=灰(国标基准)


def _ev_kind_label(kind):
    """给零基础用户的大白话类型名(界面显示用;内部仍是 因果/基准)。"""
    return "权威研究证据" if kind == "因果" else "国家标准限值"


@ui.page("/evidence")
def evidence_admin():
    if not require_app_login():
        return
    _page_head()
    _top_nav("")
    with ui.row().classes("w-full items-center q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("证据库管理").style(
                f"color:{GREEN_DEEP};font-size:1.5rem;font-weight:700;")
            ui.label("AI 初筛每条健康影响时,会自动配上「依据」(WHO 权威研究或国家标准)。"
                     "在这里可以补充新的依据卡:填好关键词和来源,保存后立即生效——"
                     "下次 AI 遇到相关内容就会引用它。系统自带的依据随版本发布;你补充的卡存在本机、可随时导出备份。").style(
                "color:#5a7a66;font-size:.85rem;line-height:1.7;")

    # —— 怎么用:三步 ——
    with ui.row().classes("w-full gap-2 q-mt-sm").style("flex-wrap:wrap;"):
        for i, (t, d) in enumerate([
                ("先查重", "在下方「已有依据」搜一下,系统是否已覆盖"),
                ("填写", "填下面的表单,可先点「填入示例」看样例"),
                ("保存即生效", "保存后 AI 初筛立即开始引用这条依据")], 1):
            with ui.row().classes("items-center gap-2").style(
                    "background:#F2F8F4;border-radius:8px;padding:6px 12px;"):
                ui.html(f'<span style="width:20px;height:20px;border-radius:50%;background:{GREEN};'
                        f'color:#fff;display:inline-flex;align-items:center;justify-content:center;'
                        f'font-size:12px;font-weight:500;">{i}</span>')
                ui.label(t).classes("text-sm").style(f"color:{GREEN_DEEP};font-weight:500;")
                ui.label(d).classes("text-xs").style("color:#5a7a66;")

    ui.label("⚠ 只填已核实的真实来源(标准号、限值、网址须真实)——不要编造。").classes(
        "text-xs q-mt-xs").style("color:#B07A00;")

    edit = {"id": None}

    # ===== 新增 / 编辑表单 =====
    with ui.card().classes("w-full q-mt-sm").style("border:1px solid #DCEEE3;"):
        title = ui.label("➕ 填写一张新的依据卡").classes("font-medium").style(f"color:{GREEN_DEEP};")
        with ui.row().classes("w-full gap-3 items-center"):
            q_sel = ui.select(EV_Q_OPTS, value="Q1", label="这条依据属于哪个健康方面?").props(
                "dense").style("min-width:240px;")
            kind_sel = ui.select(
                {"": "自动判断(推荐)", "因果": "权威研究(WHO/文献)", "基准": "国家标准限值(GB 等)"},
                value="", label="依据类型").props("dense").style("min-width:210px;")
            status_sw = ui.switch("这条来源我已核实", value=True)
        ui.label("一般「依据类型」选『自动判断』即可:来源里含 GB/国家标准的,自动当『国家标准限值』,"
                 "其余当『权威研究』。").classes("text-xs").style("color:#9AA0A6;")

        keys_in = ui.input("关键词").classes("w-full")
        ui.label("AI 初筛的影响链里出现这些词,就会引用这张卡。多写几个同义说法,用、或逗号分隔。"
                 "例:噪声、交通噪声、施工噪声、声环境。").classes("text-xs").style("color:#9AA0A6;")
        note_in = ui.textarea("依据要点 / 限值").classes("w-full")
        ui.label("一句话写清已核实的关键结论或限值。例:夜间社会生活噪声限值约 55 分贝,"
                 "长期超标与高血压、睡眠障碍相关。").classes("text-xs").style("color:#9AA0A6;")
        src_in = ui.textarea("来源出处").classes("w-full")
        ui.label("每行一条,写清『标准名 标准号. 发布机构. 网址』。"
                 "例:声环境质量标准 GB 3096-2008. 生态环境部.").classes("text-xs").style(
            "color:#9AA0A6;")

        @ui.refreshable
        def kind_preview():
            keys = _ev_split(keys_in.value)
            k, _ = _ev_derive(keys, q_sel.value, note_in.value or "",
                              _ev_lines(src_in.value), kind_sel.value or None)
            if not keys:
                ui.html('<div style="background:var(--hia-source-50);color:var(--hia-source-800);'
                        'border-radius:8px;padding:8px 12px;font-size:12.5px;">'
                        '📌 填好关键词后,这里会说明这张卡何时会被 AI 引用。</div>')
                return
            kws = "、".join(keys[:3]) + ("…" if len(keys) > 3 else "")
            ui.html('<div style="background:var(--hia-source-50);color:var(--hia-source-800);'
                    'border-radius:8px;padding:8px 12px;font-size:12.5px;line-height:1.6;">'
                    f'📌 保存后:AI 初筛遇到含「{_esc(kws)}」的健康影响时,'
                    f'会自动把这张卡作为〔<b>{_ev_kind_label(k)}</b>〕依据列出。</div>')
        kind_preview()
        keys_in.on_value_change(lambda e: kind_preview.refresh())
        src_in.on_value_change(lambda e: kind_preview.refresh())
        kind_sel.on_value_change(lambda e: kind_preview.refresh())

        def reset_form():
            edit["id"] = None
            title.set_text("➕ 填写一张新的依据卡")
            q_sel.value, kind_sel.value, status_sw.value = "Q1", "", True
            keys_in.value = note_in.value = src_in.value = ""
            kind_preview.refresh()

        def fill_example():
            edit["id"] = None
            title.set_text("➕ 填写一张新的依据卡")
            q_sel.value, kind_sel.value, status_sw.value = "Q2", "", True
            keys_in.value = "噪声、交通噪声、施工噪声、声环境"
            note_in.value = ("夜间(22:00–6:00)社会生活噪声排放限值约 55 分贝;"
                             "长期噪声暴露与高血压、睡眠障碍相关。")
            src_in.value = ("声环境质量标准 GB 3096-2008. 生态环境部.\n"
                            "社会生活环境噪声排放标准 GB 22337-2008. 生态环境部.")
            kind_preview.refresh()
            ui.notify("已填入一个示例,可直接保存,或改成你自己的内容。", type="info")

        def fill_form(c):
            edit["id"] = c.get("id")
            title.set_text("✏ 编辑证据卡")
            q_sel.value = c.get("q", "Q1")
            kind_sel.value = c.get("kind", "") if c.get("kind") in ("因果", "基准") else ""
            status_sw.value = c.get("status", "done") != "todo"
            keys_in.value = "、".join(c.get("keys", []))
            note_in.value = c.get("note", "")
            src_in.value = "\n".join(c.get("sources", []))
            kind_preview.refresh()

        def do_save():
            keys = _ev_split(keys_in.value)
            srcs = _ev_lines(src_in.value)
            if not keys:
                ui.notify("请至少填写一个关键词。", type="warning"); return
            if not srcs:
                ui.notify("请至少填写一条来源(标准号/权威出处)。", type="warning"); return
            card = {"keys": keys, "q": q_sel.value, "note": note_in.value or "",
                    "sources": srcs, "status": "done" if status_sw.value else "todo",
                    "kind": kind_sel.value or None}
            if edit["id"]:
                hia_evidence.update_user_card(edit["id"], card)
                ui.notify("✅ 已更新该证据卡。", type="positive")
            else:
                hia_evidence.add_user_card(card)
                ui.notify("✅ 已新增证据卡,已并入匹配。", type="positive")
            reset_form()
            user_cards_view.refresh()

        with ui.row().classes("items-center gap-2 q-mt-sm"):
            ui.button("保存卡片", on_click=do_save).props("color=primary")
            ui.button("填入示例", on_click=fill_example).props("flat color=primary")
            ui.button("清空 / 取消编辑", on_click=reset_form).props("flat")

    # ===== 我补充的依据卡 =====
    with ui.row().classes("w-full items-center justify-between q-mt-md"):
        ui.label("我补充的依据卡").classes("text-base font-medium")

        def do_export():
            data = json.dumps(hia_evidence.list_user_cards(), ensure_ascii=False, indent=2)
            ui.download(data.encode("utf-8"), "evidence_user.json")
        ui.button("⬇ 导出全部用户卡(JSON)", on_click=do_export).props(
            "flat dense color=primary")

    @ui.refreshable
    def user_cards_view():
        cards = hia_evidence.list_user_cards()
        if not cards:
            ui.label("还没有补充任何依据卡。用上面的表单添加(可先点「填入示例」);保存后立即生效。").classes(
                "text-xs text-grey")
            return
        for c in cards:
            kind = hia_evidence.card_kind(c)
            with ui.card().classes("w-full").style(
                    "border:0.5px solid var(--hia-border);border-radius:8px;padding:10px 12px;gap:3px;"):
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    ui.html(chip(EV_Q_OPTS.get(c["q"], c["q"]), GREEN_DEEP))
                    ui.html(chip(_ev_kind_label(kind), _ev_kind_color(kind)))
                    ui.html(chip(hia_evidence.card_tier(c)[1], "#888"))
                    ui.html(chip("已核实" if c.get("status") != "todo" else "待补强",
                                 GREEN_DEEP if c.get("status") != "todo" else "#B07A00"))
                    ui.element("div").style("flex:1;")
                    ui.button("编辑", on_click=lambda c=c: fill_form(c)).props(
                        "dense flat size=sm color=primary")

                    def _del(c=c):
                        hia_evidence.delete_user_card(c["id"])
                        ui.notify("已删除。", type="positive")
                        user_cards_view.refresh()
                    ui.button("删除", on_click=_del).props("dense flat size=sm color=grey")
                ui.label("关键词:" + "、".join(c.get("keys", []))).classes("text-xs")
                if c.get("note"):
                    ui.label("要点:" + c["note"]).classes("text-xs").style("color:#5a7a66;")
                for s in c.get("sources", []):
                    ui.label("来源:" + s).classes("text-xs").style("color:#5a7a66;")
    user_cards_view()

    # ===== 内置证据卡(只读参考,避免重复建卡)=====
    ui.separator().classes("q-mt-md")
    ui.label("已有依据(系统自带 · 只读)").classes("text-base font-medium q-mt-sm")
    ui.label("新增前先在这里搜一下,看系统是否已经覆盖,避免重复建卡。可按健康方面 + 关键词筛选。").classes(
        "text-xs text-grey")
    bflt = {"q": "全部", "kw": ""}
    with ui.row().classes("w-full items-center gap-3"):
        bq = ui.select({"全部": "全部题号", **EV_Q_OPTS}, value="全部", label="题号").props(
            "dense options-dense").style("min-width:200px;")
        bkw = ui.input("关键词筛选").props("dense clearable").classes("flex-grow")
        bq.on_value_change(lambda e: (bflt.__setitem__("q", e.value), builtin_view.refresh()))
        bkw.on_value_change(lambda e: (bflt.__setitem__("kw", (e.value or "").strip()),
                                       builtin_view.refresh()))

    @ui.refreshable
    def builtin_view():
        builtin = [c for c in hia_evidence._BUILTIN_CARDS
                   if (bflt["q"] == "全部" or c["q"] == bflt["q"])
                   and (not bflt["kw"] or any(bflt["kw"] in k for k in c["keys"])
                        or bflt["kw"] in c.get("note", ""))]
        ui.label(f"命中 {len(builtin)} 张(内置共 {len(hia_evidence._BUILTIN_CARDS)} 张)").classes(
            "text-xs text-grey")
        for c in builtin[:40]:
            kind = hia_evidence.card_kind(c)
            with ui.row().classes("w-full items-start gap-2 no-wrap").style(
                    "padding:5px 4px;border-bottom:1px solid #F0F5F2;"):
                ui.html(chip(c["q"], GREEN_DEEP))
                ui.html(chip(_ev_kind_label(kind), _ev_kind_color(kind)))
                with ui.column().classes("gap-0"):
                    ui.label("、".join(c["keys"])).classes("text-xs")
                    if c.get("note"):
                        ui.label(c["note"][:80] + ("…" if len(c.get("note", "")) > 80 else "")
                                 ).classes("text-xs").style("color:#5a7a66;")
        if len(builtin) > 40:
            ui.label(f"(仅显示前 40 张,共 {len(builtin)} 张;请用关键词进一步筛选)").classes(
                "text-xs text-grey")
    builtin_view()


@ui.page("/")
def home():
    if not require_app_login():
        return
    _page_head()
    ui.query(".nicegui-content").style("max-width:980px;")
    with ui.column().classes("w-full items-center q-pt-lg gap-1"):
        ui.label("HEALTH IMPACT ASSESSMENT").style(
            f"color:{GREEN};letter-spacing:4px;font-size:.85rem;font-weight:600;")
        ui.label(PLATFORM_NAME).style(
            f"color:{GREEN_DEEP};font-size:2.2rem;font-weight:800;letter-spacing:2px;")
        ui.label("面向卫生健康主管部门 · 政策与规划的健康影响智能初筛、专家协同评估与项目管理").classes(
            "text-sm").style("color:#5a7a66;")
    with ui.row().classes("w-full justify-center gap-5 q-mt-xl flex-wrap"):
        _portal_card("🆕", "新建健康影响评估",
                     "上传政策/规划文档,AI 展开健康影响路径、对照初筛表。可选单人快速初筛或多专家协同评估。",
                     "/new")
        _portal_card("🩺", "批量政策体检",
                     "一次上传多份政策文档,AI 逐份初筛,汇总成「政策 × 健康维度」体检表与监管视角,快速扫描重点。",
                     "/batch", accent="#2E6DB4")
        _portal_card("🗂", "项目管理",
                     "查阅既往全部评估项目,搜索/筛选、重新导出初筛表、归档与发布参考案例。",
                     "/ledger")
        _portal_card("📚", "案例参考",
                     "浏览已发布为范例的评估项目,学习健康影响识别与判定的参考写法。",
                     "/reference")
    with ui.column().classes("w-full items-center q-mt-xl gap-1"):
        ui.label("⚠ 本平台借助 AI 辅助梳理,结论与签字以专家判断为准,不替代专家。").classes(
            "text-xs text-grey")
        ui.link("📖 证据库管理(维护 WHO/国标依据卡)", "/evidence").props("no-underline").style(
            "color:#5a7a66;font-size:.8rem;")


@ui.page("/new")
def new_assessment():
    if not require_app_login():
        return
    _page_head()
    _top_nav("new")
    with ui.column().classes("w-full items-center q-pt-md gap-1"):
        ui.label("新建健康影响评估").style(
            f"color:{GREEN_DEEP};font-size:1.6rem;font-weight:700;")
        ui.label("选择评估方式 —— 单人快速初筛,或组织多位专家协同评估。").classes(
            "text-sm").style("color:#5a7a66;")
    with ui.row().classes("w-full justify-center gap-5 q-mt-lg flex-wrap"):
        _portal_card("⚡", "独立完成初筛",
                     "经办人独立完成:上传文档 → AI 初筛 → 逐方面核对 → 导出初筛表。一人即可,最快得到结果。",
                     "/screen")
        _portal_card("📤", "发起专家组协同评估",
                     "经办人发起:上传文档 → AI 初筛 → 生成「评审链接+口令」邀请多位专家独立评定 → 汇总共识、组长定稿。",
                     "/panel", accent="#2E6DB4")


# ==================== 批量政策体检 / 监管看板 ====================

def _batch_dims_header_html():
    """体检表 10 维表头:编号 + tooltip 全称(与下方色格对齐)。"""
    cells = ""
    for q in range(1, 11):
        cells += (f'<div title="{q}. {_esc(hs.SHORT_Q[q-1])}" style="flex:1;text-align:center;'
                  f'font-size:11px;color:var(--hia-neutral-500);">{q}</div>')
    return f'<div style="display:flex;flex:1;gap:2px;">{cells}</div>'


@ui.page("/batch")
def batch():
    if not require_app_login():
        return
    _page_head()
    ui.query(".nicegui-content").style("max-width:1180px;")   # 体检表较宽,放宽页面
    _top_nav("batch")
    with ui.row().classes("w-full items-center q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("批量政策体检").style(
                f"color:{GREEN_DEEP};font-size:1.5rem;font-weight:700;")
            ui.label("一次上传多份政策/规划文档,AI 逐份初筛,汇总成一张「政策 × 健康维度」体检表,"
                     "快速扫描哪些政策、哪些健康维度需要关注。").style(
                "color:#5a7a66;font-size:.85rem;")

    state = {"files": [], "results": [], "running": False}     # files:[{name,bytes}] results:[rec]
    prog = {"done": 0, "total": 0, "cur": ""}

    # ===== 上传(多份)=====
    async def on_upload(e):
        data = await e.file.read()
        state["files"] = [f for f in state["files"] if f["name"] != e.file.name]  # 同名去重
        state["files"].append({"name": e.file.name, "bytes": data})
        file_list.refresh()

    ui.upload(on_upload=on_upload, auto_upload=True, multiple=True).props(
        'accept=".pdf,.docx" flat bordered label="拖入或选择多份 PDF / Word"').classes(
        "w-full q-mt-sm")
    key_in = ui.input("分析服务密钥(API Key)", password=True, value=_get_key(),
                      placeholder="sk-...").classes("w-full q-mt-sm")

    @ui.refreshable
    def file_list():
        if not state["files"]:
            ui.label("尚未添加文件。可一次拖入多份政策/规划文档。").classes("text-xs text-grey")
            return
        with ui.row().classes("items-center gap-2 flex-wrap q-mt-xs"):
            ui.label(f"待体检 {len(state['files'])} 份:").classes("text-xs text-grey")
            for f in state["files"]:
                nm = f["name"] if len(f["name"]) <= 26 else f["name"][:26] + "…"
                ui.html(chip(nm, "#5a7a66"))
    file_list()

    # ===== 单份/批量入库 =====
    def _save_one(r):
        lvl = r.get("level") if r.get("level") in ("很小", "轻度", "重大") else "轻度"
        case = case_store.save_single_case(
            r.get("title") or os.path.splitext(r["fname"])[0],
            r["res"], r["info"], r["items"], lvl,
            "(批量体检 AI 自动初筛,尚未经专家核定)",
            doc_bytes=r.get("bytes"), doc_filename=r["fname"],
            adopted_ids=r.get("adopted_ids"))
        case_store.set_status(case["id"], "评审中")   # AI 初筛态,待专家核定,不直接定稿
        r["saved_id"] = case["id"]
        return case["id"]

    def _save_row(r):
        _save_one(r)
        ui.notify(f"✅ 已存入项目管理(案例码 {r['saved_id']});可在「项目管理」查阅、核定、重导出。",
                  type="positive", timeout=5000)
        dashboard.refresh()

    def _save_all(recs):
        n = 0
        for r in recs:
            if not r.get("saved_id"):
                _save_one(r); n += 1
        ui.notify(f"✅ 已把 {n} 份存入项目管理(状态=评审中,待专家核定)。", type="positive")
        dashboard.refresh()

    def _batch_row(r):
        with ui.row().classes("w-full items-center gap-2 no-wrap").style(
                "padding:5px 6px;border-bottom:1px solid #F0F5F2;"):
            ui.label(r.get("title") or r["fname"]).classes("text-xs").style(
                "min-width:200px;max-width:200px;overflow:hidden;text-overflow:ellipsis;"
                "white-space:nowrap;").tooltip(r["fname"])
            cells = ""
            for q in range(1, 11):
                a = r["ans"].get(q, "否")
                cells += (f'<div title="{q}. {_esc(hs.SHORT_Q[q-1])}:{ANSWER_LABEL[a]}" '
                          f'style="flex:1;height:15px;border-radius:3px;'
                          f'background:{ANSWER_COLOR[a]};"></div>')
            ui.html(f'<div style="display:flex;flex:1;gap:2px;">{cells}</div>').classes("flex-grow")
            ui.label(r.get("level") or "—").classes("text-xs").style(
                "min-width:42px;text-align:center;color:var(--hia-neutral-700);")
            if r.get("saved_id"):
                ui.label("✓ 已入库").classes("text-xs").style(
                    "min-width:86px;color:var(--hia-benefit-600);")
            else:
                ui.button("存入台账", on_click=lambda r=r: _save_row(r)).props(
                    "dense flat color=primary size=sm").style("min-width:86px;")

    # ===== 看板 =====
    @ui.refreshable
    def dashboard():
        done = [r for r in state["results"] if not r.get("error")]
        failed = [r for r in state["results"] if r.get("error")]
        if not state["results"]:
            ui.label("体检结果将在这里汇总成「政策 × 健康维度」热力图与监管视角。").classes(
                "text-sm text-grey")
            return
        relevant = [r for r in done if r.get("relevant")]
        attention = [r for r in done if any(v == "是" for v in r["ans"].values())]
        total_path = sum(r.get("n_path", 0) for r in done)
        metrics = [("体检政策", len(state["results"]), GREEN_DEEP),
                   ("有健康关联", len(relevant), "#2E6DB4"),
                   ("含需关注维度", len(attention), ANSWER_COLOR["是"]),
                   ("健康影响路径", total_path, GREEN_DEEP)]
        with ui.row().classes("w-full gap-3"):
            for label, val, col in metrics:
                with ui.card().classes("items-center").style(
                        f"flex:1;border-left:4px solid {col};padding:10px;"):
                    ui.label(str(val)).style(f"font-size:1.6rem;font-weight:500;color:{col};")
                    ui.label(label).classes("text-xs text-grey")

        # —— 体检表(政策 × 10 维)——
        with ui.row().classes("w-full items-center justify-between q-mt-md"):
            ui.label("政策 × 健康维度 体检表").classes("text-base font-medium")
            ui.label("色格:🔴需关注 🟡尚不确定 🟢暂未发现(悬停看维度与判定)").classes(
                "text-xs text-grey")
        with ui.row().classes("w-full items-center gap-2 no-wrap").style("padding:0 6px;"):
            ui.label("政策").classes("text-xs").style(
                "min-width:200px;color:var(--hia-neutral-500);")
            ui.html(_batch_dims_header_html()).classes("flex-grow")
            ui.label("程度").classes("text-xs").style(
                "min-width:42px;text-align:center;color:var(--hia-neutral-500);")
            ui.element("div").style("min-width:86px;")
        for r in done:
            _batch_row(r)
        for r in failed:
            with ui.row().classes("w-full items-center gap-2").style(
                    "padding:5px 6px;border-bottom:1px solid #F0F5F2;"):
                ui.label("⚠ " + r["name"]).classes("text-xs").style("min-width:200px;")
                ui.label("解析失败:" + str(r.get("error"))).classes("text-xs").style(
                    "color:#B07A00;")

        unsaved = [r for r in relevant if not r.get("saved_id")]
        if unsaved:
            ui.button(f"🗂 把全部有健康关联的存入项目管理({len(unsaved)} 份)",
                      on_click=lambda: _save_all(unsaved)).props("outline color=primary").classes(
                "q-mt-sm")

        # —— 监管视角:各维度被政策触及情况 ——
        if done:
            ui.label("监管视角 · 各健康维度被政策触及情况").classes("text-base font-medium q-mt-md")
            ui.label("条形 = 触及该维度的政策占比(红=需关注 / 黄=尚不确定);"
                     "一眼看出哪些健康维度被政策普遍涉及、哪些被忽视。").classes("text-xs text-grey")
            tot = len(done)
            for q in range(1, 11):
                nyes = sum(1 for r in done if r["ans"].get(q) == "是")
                nmaybe = sum(1 for r in done if r["ans"].get(q) == "不知道")
                wyes = nyes / tot * 100
                wmaybe = nmaybe / tot * 100
                with ui.row().classes("w-full items-center gap-2 no-wrap").style("padding:3px 0;"):
                    ui.label(f"{q}. {hs.SHORT_Q[q-1]}").classes("text-xs").style(
                        "min-width:130px;color:var(--hia-neutral-700);")
                    ui.html(
                        f'<div style="flex:1;height:14px;background:var(--hia-neutral-50);'
                        f'border-radius:7px;overflow:hidden;display:flex;">'
                        f'<div style="width:{wyes:.0f}%;background:{ANSWER_COLOR["是"]};"></div>'
                        f'<div style="width:{wmaybe:.0f}%;background:{ANSWER_COLOR["不知道"]};">'
                        f'</div></div>').classes("flex-grow")
                    txt = (f"{nyes} 需关注" if nyes else "—") + (
                        f" · {nmaybe} 待定" if nmaybe else "")
                    ui.label(txt).classes("text-xs text-grey").style("min-width:110px;")

    # ===== 跑批 =====
    async def run_batch():
        key = (key_in.value or "").strip()
        if not state["files"]:
            ui.notify("请先上传至少一份文件。", type="warning"); return
        if not key:
            ui.notify("请先填写分析服务密钥。", type="warning"); return
        state["running"] = True
        state["results"] = []
        prog.update(done=0, total=len(state["files"]), cur="")
        run_btn.disable()
        progress_view.refresh(); dashboard.refresh()
        for f in state["files"]:
            prog["cur"] = f["name"]; progress_view.refresh()
            rec = {"name": f["name"], "fname": f["name"], "bytes": f["bytes"]}
            try:
                text, info = hs.extract_text(f["name"], f["bytes"])
                if info.get("error"):
                    rec["error"] = info["error"]
                else:
                    res = await run.io_bound(hs.analyze, text, key,
                                             project_name=os.path.splitext(f["name"])[0])
                    adopted = [p for p in res["pathways"] if _adopt_default(p)]
                    items = hs.compute_items(adopted)
                    n_path = len(res["pathways"])
                    n_src = sum(1 for p in res["pathways"] if p.get("cards"))
                    rec.update(res=res, info=info, items=items,
                               ans={it["q"]: it["answer"] for it in items},
                               adopted_ids=[p["id"] for p in adopted],
                               title=hs.guess_title(text, fallback=os.path.splitext(f["name"])[0]),
                               level=res.get("suggest_level") or "—",
                               n_actions=len(res["actions"]), n_path=n_path,
                               n_gap=n_path - n_src, relevant=n_path > 0)
            except Exception as ex:                       # noqa: BLE001
                rec["error"] = str(ex)
            state["results"].append(rec)
            prog["done"] += 1
            progress_view.refresh(); dashboard.refresh()
        state["running"] = False
        prog["cur"] = ""
        run_btn.enable()
        progress_view.refresh(); dashboard.refresh()
        ui.notify(f"✅ 体检完成:共 {prog['done']} 份。", type="positive")

    run_btn = ui.button("🩺 开始批量体检", on_click=run_batch).props("color=primary").classes(
        "q-mt-sm")
    ui.label("逐份分析,每份约 30–60 秒;期间请保持页面打开。").classes("text-xs text-grey")

    @ui.refreshable
    def progress_view():
        if not state["running"]:
            return
        cur = (prog["cur"][:30] + "…") if len(prog["cur"]) > 30 else prog["cur"]
        with ui.row().classes("items-center gap-3 w-full q-mt-xs"):
            ui.spinner(size="sm")
            ui.label(f"体检中… {prog['done']}/{prog['total']}　当前:{cur}").classes("text-sm")
    progress_view()

    ui.separator().classes("q-mt-md")
    dashboard()


@ui.page("/reference")
def reference():
    if not require_app_login():
        return
    _page_head()
    _top_nav("reference")
    with ui.row().classes("w-full items-center justify-between q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("案例参考 · 评估范例").style(
                f"color:{GREEN_DEEP};font-size:1.5rem;font-weight:700;")
            ui.label("以下为在「项目管理」中发布为参考案例的既往评估,供学习健康影响识别与判定写法(只读)。").style(
                "color:#5a7a66;font-size:.85rem;")

    refs = case_store.list_reference()
    if not refs:
        with ui.card().classes("w-full q-mt-md").style("border:1px dashed #CFE0D5;background:#FAFEFB;"):
            ui.label("暂无参考案例。").classes("font-medium")
            ui.label("在「项目管理」里选一个已定稿的项目,点「📣 发布为参考案例」,即可在此展示。").classes(
                "text-xs text-grey")
        return
    for c in refs:
        _reference_row(c)


def _reference_row(c):
    src = c.get("source", case_store.SOURCE_PANEL)
    items, lv, opinion, finalized = _case_export_payload(c)
    amap = {it["q"]: it.get("answer", "否") for it in items}
    with ui.expansion().classes("w-full").style(
            "border:1px solid #DCEEE3;border-radius:10px;margin-bottom:6px;") as exp:
        with exp.add_slot("header"):
            with ui.row().classes("items-center gap-3 w-full no-wrap"):
                ui.html(chip("⭐ 参考案例", "#C9870A"))
                ui.label(c.get("name") or "评估对象").classes("text-sm font-medium").style(
                    "min-width:160px;")
                ui.html(chip(src, SOURCE_COLOR.get(src, "#888")))
                if lv:
                    ui.label(f"总体影响:{lv}").classes("text-xs text-grey")
                ui.label(c.get("created", "")).classes("text-xs text-grey")
        # 10 题判定一览
        with ui.row().classes("w-full gap-1 q-mt-xs"):
            for q in range(1, 11):
                a = amap.get(q, "否")
                ui.html(f'<div title="{q}. {hs.SHORT_Q[q-1]}:{ANSWER_LABEL[a]}" '
                        f'style="flex:1;height:12px;border-radius:3px;'
                        f'background:{ANSWER_COLOR[a]};"></div>').classes("flex-grow")
        if opinion:
            ui.label("专家组意见:" + opinion).classes("text-xs text-grey q-mt-xs")
        # 逐题判定 + AI 梳理的影响路径(只读)
        doc_text = _case_doc_text(c)              # 供范例查阅时在原文里核对依据
        allp = (c.get("res") or {}).get("pathways", [])
        for q in range(1, 11):
            ps = [p for p in allp if p.get("outcome_q") == q]
            a = amap.get(q, "否")
            with ui.expansion(value=False).classes("w-full").style(
                    "border:1px solid #ECF5EF;border-radius:8px;margin-top:4px;") as e2:
                with e2.add_slot("header"):
                    with ui.row().classes("items-center gap-3 w-full"):
                        ui.label(f"{q}. {hs.SHORT_Q[q-1]}").classes("text-sm").style(
                            "min-width:120px;")
                        ui.html(chip(ANSWER_LABEL[a], ANSWER_COLOR[a]))
                        ui.label(f"{len(ps)} 条影响" if ps else "无影响").classes(
                            "text-xs text-grey")
                for p in ps:
                    render_pathway_ro(p, (c.get("res") or {}).get("actions", []), doc_text)
                if not ps:
                    ui.label("该方面未梳理出影响。").classes("text-xs text-grey")
        # 下载范例初筛表
        def dl(case=c):
            its, lvl, op, _ = _case_export_payload(case)
            header = {"name": case["name"], "category": "政府发布/实施", "dept": "",
                      "submitter": "", "phone": "",
                      "screen_date": (case.get("created") or "")[:10] or str(date.today()),
                      "method": "参考范例", "related_dept": ""}
            buf = hs.build_screen_docx(header, its, case_store.adopted_pathways(case), lvl, op)
            ui.download(buf.getvalue(), f"参考案例_健康影响评估初筛表_{case['name']}.docx")
        ui.button("📄 下载范例初筛表", on_click=dl).props("dense flat color=primary q-mt-sm")


ui.run(host="0.0.0.0", port=APP_PORT, title=PLATFORM_NAME,
       show=False, reload=False, storage_secret=STORAGE_SECRET)
