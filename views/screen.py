# -*- coding: utf-8 -*-
"""健康影响评估:AI 辅助 HIA(定性初筛 · 因果路径版)。

上传评估对象文档(PDF/Word)→ 3 段流水线(行动抽取→多视角路径展开→完整性批判)展开
**政策行动→健康决定因素(多级间接)→健康结果** 的因果路径网 → 可编辑因果路径图 +
路径采纳/剪枝/补充 → 代码确定性聚合到 10 题 → 专家复核改判 → 导出初筛表 docx。
AI 仅辅助;路径采纳、判定与签字以专家为准。引擎 hia_screen.py。
"""
from datetime import date

import streamlit as st

import hia_screen as hs
import hia_evidence
from theme import page_header

ANSWERS = hs.ANSWERS
LEVELS = ["很小", "轻度", "重大"]
_BADGE = {"是": "#C62828", "不知道": "#B07A00", "否": "#1B6B3A"}
_STRENGTH_C = {"强": "#C62828", "中": "#E07B39", "推测": "#9AA0A6"}

# —— 把专业术语翻成通俗说法(面向无专业背景的政务用户)——
_STRENGTH_PLAIN = {"强": "把握较强(证据充分)", "中": "把握中等(较有依据)",
                   "推测": "仅为推测(待证实)"}
_STATUS_PLAIN = {"文档支持": "依据来自您上传的文件", "路径库/文献": "依据来自 WHO / 文献机制",
                 "假设待证": "推断的假设(尚需核实)", "专家补充": "专家手动补充"}
_DIR_PLAIN = {"风险": "🔴 可能带来风险", "效益": "🟢 可能带来益处"}
# 10 题判定的通俗解释
_ANSWER_PLAIN = {"是": "需要关注", "不知道": "尚不确定、建议核实", "否": "暂未发现相关影响"}


def _render_guide():
    """顶部「使用说明」—— 三步流程 + 名词通俗解释。面向零操作基础的政务用户,默认展开。"""
    with st.expander("📖 使用说明(第一次使用请先看这里)", expanded=True):
        st.markdown(
            "**这个工具是做什么的?**　帮您在政策 / 规划出台前,快速看出它可能影响到哪些方面的"
            "公众健康(如传染病、慢性病、医疗可及性等),并生成一份规范的《健康影响评估初筛表》。\n\n"
            "**怎么用?只需三步:**\n"
            "1. **上传文件** —— 把要评估的政策、规划或项目文件(PDF 或 Word)传上来。\n"
            "2. **点一下「开始分析」** —— 系统会自动阅读文件、梳理可能的健康影响,生成一份草案。\n"
            "3. **专家核对 + 下载** —— 逐条看看判断对不对(可勾选 / 取消),最后一键下载初筛表。\n\n"
            "**几个名词的通俗解释:**\n"
            "- **健康影响**:这项措施可能间接让人们更健康或更不健康的地方。\n"
            "- **影响关系图**:系统把「措施 → 会改变什么 → 影响哪方面健康」一步步连起来,方便看清来龙去脉。\n"
            "- **把握强/中/推测**:系统对每条影响有多大把握 —— 证据越足把握越强;「推测」表示只是可能、需要人工核实。")
        st.info("⚠️ 本系统借助智能分析技术辅助梳理,**结论和签字以专家判断为准**,不替代专家。")


def _get_key():
    try:
        return st.secrets.get("deepseek_api_key", "") or ""
    except Exception:
        return ""


def _clear_state():
    for k in list(st.session_state.keys()):
        if k.startswith(("hs_adopt_", "hs_ans_", "hs_note_")):
            del st.session_state[k]
    for k in ("hs_custom", "hs_wiz_i"):
        st.session_state.pop(k, None)


def _all_pathways():
    """模型路径 + 专家补充路径。"""
    res = st.session_state.get("hs_res") or {}
    return list(res.get("pathways", [])) + list(st.session_state.get("hs_custom", []))


def _adopt_default(p):
    return p.get("status") != "假设待证"          # 假设待证默认不采纳,需专家勾选


# —— 持久存储:引导式逐屏复核时,未渲染的控件状态会被 Streamlit 回收;
#    用普通 session_state 字典做"真值源",控件每次渲染时回填 + 写回,翻页也不丢。——
def _store(name):
    return st.session_state.setdefault(name, {})


def _is_adopted(p):
    """这条影响是否被采纳:优先取当前已渲染控件的实时值(翻页内即时生效),
    否则取持久存储,再否则取默认。"""
    k = f"hs_adopt_{p['id']}"
    if k in st.session_state:
        return bool(st.session_state[k])
    return _store("hs_adopt_store").get(p["id"], _adopt_default(p))


def _adopted():
    return [p for p in _all_pathways() if _is_adopted(p)]


def _final_answer(q, sys_default):
    k = f"hs_ans_{q}"
    if k in st.session_state:
        return st.session_state[k]
    return _store("hs_ans_store").get(q, sys_default)


def _final_note(q):
    k = f"hs_note_{q}"
    if k in st.session_state:
        return st.session_state[k]
    return _store("hs_note_store").get(q, "")


def _pathway_block(p):
    """渲染一条影响:把握/性质/依据元信息 + 采纳勾选框 + 人群/依据/来源。两种模式共用。"""
    col = _STRENGTH_C[p["strength"]]
    chain = " → ".join(p["chain"])
    meta = (f"<span style='color:{col};font-weight:600'>"
            f"{_STRENGTH_PLAIN.get(p['strength'], p['strength'])}</span>"
            f"<span style='color:#888'>　|　{_DIR_PLAIN.get(p['direction'], p['direction'])}"
            f"　|　{_STATUS_PLAIN.get(p['status'], p['status'])}</span>")
    st.markdown(meta, unsafe_allow_html=True)
    store = _store("hs_adopt_store")
    k = f"hs_adopt_{p['id']}"
    if k in st.session_state:                       # 控件已存在 → 不再传 value,避免重复默认值告警
        val = st.checkbox(chain, key=k, help="勾选=认可并计入判断;取消=排除。")
    else:                                           # 首次/翻页回来 → 用持久存储(或默认)回填
        val = st.checkbox(chain, value=store.get(p["id"], _adopt_default(p)), key=k,
                          help="勾选=认可并计入判断;取消=排除。")
    store[p["id"]] = bool(val)                       # 写回真值源,翻页不丢
    if p.get("population"):
        st.caption("　主要影响人群:" + p["population"])
    if p.get("status") == "文档支持" and p.get("evidence"):
        st.caption("　📄 文件中的依据:" + p["evidence"])
    cards = p.get("cards") or []
    if cards:
        for c in cards:
            st.caption("　📚 参考来源:" + "；".join(c["sources"])
                       + ("　(WHO 来源待补强)" if c.get("status") == "todo" else ""))
            if c.get("note"):
                st.caption("　　" + c["note"])
    else:
        st.caption("　📚 参考来源:基于机制推断,建议专家进一步补充佐证")


def _judge_block(q, sys_answer, n_path, gaps):
    """渲染一个健康方面的判定:系统初判徽标 + 专家判定单选 + 备注。两种模式共用。"""
    col = _BADGE[sys_answer]
    st.markdown(
        f"<span style='background:{col};color:#fff;padding:1px 8px;border-radius:9px;"
        f"font-size:0.8rem;'>系统初判:{_ANSWER_PLAIN.get(sys_answer, sys_answer)}</span> "
        f"<span style='color:#888;font-size:0.8rem;'>(基于 {n_path} 条已认可的影响)</span>",
        unsafe_allow_html=True)
    if gaps:
        st.caption("⚠ " + gaps)
    ans_store, note_store = _store("hs_ans_store"), _store("hs_note_store")
    ka, kn = f"hs_ans_{q}", f"hs_note_{q}"
    cc1, cc2 = st.columns([1, 2])
    with cc1:
        if ka in st.session_state:
            ans = st.radio("您的判断", ANSWERS, key=ka, horizontal=True,
                           format_func=lambda a: f"{a}({_ANSWER_PLAIN.get(a, a)})")
        else:
            cur = ans_store.get(q, sys_answer)
            ans = st.radio("您的判断", ANSWERS, index=ANSWERS.index(cur), key=ka, horizontal=True,
                           format_func=lambda a: f"{a}({_ANSWER_PLAIN.get(a, a)})")
    with cc2:
        if kn in st.session_state:
            note = st.text_input("说明 / 备注(可选)", key=kn,
                                 placeholder="可补充判断理由,或需进一步核实的地方")
        else:
            note = st.text_input("说明 / 备注(可选)", value=note_store.get(q, ""), key=kn,
                                 placeholder="可补充判断理由,或需进一步核实的地方")
    ans_store[q], note_store[q] = ans, note


def page_hia_screen():
    page_header(
        "健康影响评估 · 智能初筛",
        "本工具帮您快速判断一项<b>政策 / 规划 / 工程项目</b>可能带来哪些健康影响。"
        "您只需<b>上传文件</b>,系统会自动梳理出"
        "「这项措施 → 会改变什么 → 进而影响哪方面健康」的关系,并对照"
        "《健康影响评估初筛表》给出 10 个问题的初步判断,最后<b>一键生成可下载的初筛表</b>。"
        "<br>⚠️ 系统只做辅助梳理,<b>最终判断与签字仍由专家把关</b>。")

    _render_guide()

    # ===== ① 文档 + 表头 =====
    st.markdown("##### 📄 第 1 步 · 上传要评估的文件")
    st.caption("支持 PDF 或 Word(.docx)。比如某项政策文件、规划方案、项目说明书等。"
               "上传后,系统会阅读其中文字(扫描成图片的 PDF 暂不支持)。")
    up = st.file_uploader("点击下方选择文件,或把文件拖到这里",
                          type=["pdf", "docx"], key="hs_file")

    st.markdown("##### ✏️ 第 2 步 · 填写基本信息(将自动写入初筛表表头)")
    st.caption("这些信息只用于生成初筛表的表头,不影响分析结果。可先留空,稍后再补。")
    c1, c2 = st.columns(2)
    name = c1.text_input("评估对象名称", value=(up.name.rsplit(".", 1)[0] if up else ""), key="hs_name")
    category = c2.selectbox("发布/实施类别", ["政府发布/实施", "部门发布/实施"], key="hs_cat")
    c3, c4, c5 = st.columns(3)
    dept = c3.text_input("起草/提交部门", key="hs_dept")
    submitter = c4.text_input("提交人", key="hs_submitter")
    phone = c5.text_input("电话", key="hs_phone")
    c6, c7 = st.columns(2)
    screen_date = c6.date_input("初筛日期", value=date.today(), key="hs_date")
    related_dept = c7.text_input("涉及的相关部门", key="hs_related")
    method = st.text_input("初筛方法",
                           value="智能分析辅助 + 专家核定(健康影响路径展开)", key="hs_method")

    key = _get_key()
    if not key:
        st.caption("ℹ️ 系统尚未配置分析服务密钥。如已有密钥可在下方临时填入(仅本次使用有效);"
                   "正式部署时由管理员统一配置,使用者无需关心此项。")
        key = st.text_input("分析服务密钥(API Key)",
                            type="password", key="hs_key",
                            placeholder="sk-...").strip()

    st.markdown("##### 🔍 第 3 步 · 开始智能分析")
    gen = st.button("🔍 开始分析(约 30–60 秒,请稍候)", type="primary",
                    disabled=not (up and key))
    if not up:
        st.caption("👆 请先在第 1 步上传文件。")
    elif not key:
        st.caption("👆 还差一步:请先填入上方的分析服务密钥。")
    else:
        st.caption("一切就绪,点上方按钮即可。分析期间请不要关闭页面。")

    if gen:
        from auth import rate_limit
        ok, wait = rate_limit("hia_screen", 6, 60)
        if not ok:
            st.warning(f"⏳ 生成请求过于频繁,请约 {wait}s 后再试。")
        else:
            text, info = hs.extract_text(up.name, up.getvalue())
            if info.get("error"):
                st.error(info["error"])
            else:
                with st.status("正在分析(约 30–60 秒,分三步梳理健康影响)…", expanded=True) as status:
                    def prog(s):
                        status.write(s)
                    res = hs.analyze(text, key, project_name=name, progress=prog)
                    status.update(label="分析完成", state="complete", expanded=False)
                _clear_state()
                st.session_state["hs_res"] = res
                st.session_state["hs_docinfo"] = info
                tip = f"已解析{info['kind']}" + (f"·{info['pages']}页" if info["pages"] else "")
                if info.get("truncated"):
                    tip += "(文档较长已截断前 4 万字)"
                st.success(f"✅ 分析完成!{tip};共从文件中识别出 {len(res['actions'])} 项措施、"
                           f"梳理出 {len(res['pathways'])} 条可能的健康影响。"
                           f"请继续往下,逐条核对并下载初筛表。")

    res = st.session_state.get("hs_res")
    if not res:
        return

    # ===== 总体研判小结 =====
    st.divider()
    if res.get("summary"):
        st.info("🧭 **总体研判(供参考):**　" + res["summary"])
    if res.get("notes"):
        st.caption("⚠ 仍需专家补充核实之处:" + res["notes"])

    # ===== ③ 因果路径图(随采纳/剪枝实时重绘)=====
    st.markdown("##### 🔗 健康影响关系图(可视化:措施 → 改变了什么 → 影响哪方面健康)")
    st.caption("从左往右看:**最左是文件里的措施**,**中间是它会改变的环节**,**最右是受影响的健康方面**。"
               "线条颜色:🔴红/橙=可能的风险,🟢绿=可能的益处,灰=仅为推测;虚线=尚需核实的假设。"
               "图比较宽,可以在框里左右、上下拖动查看。图的内容会随下方第 4 步的勾选实时变化。")
    # 让 graphviz 按自然尺寸渲染 + 框内滚动(否则 Streamlit 会把超宽图缩到容器宽 → 字太小、压扁)
    st.markdown(
        '<style>'
        '[data-testid="stGraphVizChart"]{overflow:auto !important; max-height:600px;'
        'border:1px solid #DCEEE3; border-radius:8px; background:#fff;}'
        '[data-testid="stGraphVizChart"] svg{width:auto !important; height:auto !important;'
        'max-width:none !important;}'
        '</style>', unsafe_allow_html=True)
    adopted = _adopted()
    if adopted:
        # 不用 use_container_width:它会把超宽图的 SVG 宽高抹成 0 → 整图不显示。
        st.graphviz_chart(hs.build_dot(res["actions"], adopted))
    else:
        st.caption("(下方还没有勾选认可任何一条影响,勾选后这里会显示关系图。)")

    # ===== 第 4 步:复核 + 判定(两种模式:引导式 / 一次看全部)=====
    st.divider()
    allp = _all_pathways()
    items_live = hs.compute_items(_adopted())            # 系统初判,随采纳实时变化
    item_by_q = {it["q"]: it for it in items_live}
    dims = [q for q in range(1, len(hs.QUESTIONS) + 1)
            if any(p["outcome_q"] == q for p in allp)]   # 有影响、需复核的健康方面

    st.markdown("##### ✅ 第 4 步 · 核对健康影响、给出判断")
    if not dims:
        st.caption("(系统未梳理出可归类的健康影响。可在下方手动补充,或重新上传更完整的文件;"
                   "也可直接到最下方下载初筛表。)")
        mode = "一次看全部"
    else:
        mode = st.radio("查看方式", ["引导式(一个方面一个方面看,推荐)", "一次看全部(展开全部)"],
                        horizontal=True, key="hs_review_mode")

    def _dim_panel(q):
        """单个健康方面:问题 + 该方面全部影响的勾选 + 系统初判 + 专家判定。两模式共用。"""
        ps = [p for p in allp if p["outcome_q"] == q]
        st.caption("初筛表问题:" + hs.QUESTIONS[q - 1])
        st.markdown(f"**系统找到 {len(ps)} 条可能影响**(勾选 = 认可、取消 = 排除):")
        for p in ps:
            _pathway_block(p)
        st.divider()
        it = item_by_q.get(q, {"answer": "否", "gaps": ""})
        n_here = sum(1 for p in ps if _is_adopted(p))
        st.markdown("**这个方面的判断:**")
        _judge_block(q, it["answer"], n_here, it.get("gaps", ""))

    if dims and mode.startswith("引导式"):
        st.caption("跟着下方「下一项」按钮,一个方面一个方面看:先看系统找到的影响(勾掉不认可的),"
                   "再确认这个方面的判断。其它没有影响的方面,系统默认「暂未发现」,无需逐个查看。")
        n = len(dims)
        i = max(0, min(st.session_state.get("hs_wiz_i", 0), n - 1))
        st.progress((i + 1) / n, text=f"进度:第 {i + 1} / {n} 个需复核的健康方面")
        with st.container(border=True):
            st.markdown(f"##### 健康方面 {dims[i]} · {hs.SHORT_Q[dims[i]-1]}")
            _dim_panel(dims[i])
        b1, b2, b3 = st.columns([1, 1, 1])
        if b1.button("← 上一项", disabled=(i == 0), use_container_width=True):
            st.session_state["hs_wiz_i"] = i - 1
            st.rerun()
        b2.markdown(f"<div style='text-align:center;color:#6a8a76;padding-top:.5rem;'>"
                    f"{i + 1} / {n}</div>", unsafe_allow_html=True)
        if i < n - 1:
            if b3.button("下一项 →", type="primary", use_container_width=True):
                st.session_state["hs_wiz_i"] = i + 1
                st.rerun()
        else:
            b3.success("已是最后一项 ✓")
        # 未逐屏查看的方面也落库默认判定(系统初判),保证导出完整、不丢
        for q in range(1, len(hs.QUESTIONS) + 1):
            _store("hs_ans_store").setdefault(q, item_by_q.get(q, {}).get("answer", "否"))
    elif dims:
        st.caption("下面按健康方面分组列出全部影响。勾选 = 认可、取消 = 排除;"
                   "每个方面下可改判并填备注。点方面标题可展开 / 收起。")
        for q in dims:
            ps = [p for p in allp if p["outcome_q"] == q]
            it = item_by_q.get(q, {"answer": "否"})
            label = (f"健康方面 {q} · {hs.SHORT_Q[q-1]} —— {len(ps)} 条影响 · "
                     f"系统初判:{_ANSWER_PLAIN.get(it['answer'], it['answer'])}")
            with st.expander(label, expanded=False):
                _dim_panel(q)

    # —— 专家补充自定义路径 ——
    with st.expander("➕ 手动补充一条影响(供专家使用,可选)"):
        aopts = {a["id"]: f"{a['id']} {a['action'][:24]}" for a in res["actions"]}
        ca, cb = st.columns([1, 1])
        c_act = ca.selectbox("从哪项措施出发", list(aopts.keys()),
                             format_func=lambda x: aopts[x], key="hs_c_act")
        c_q = cb.selectbox("影响到哪个健康方面", list(range(1, 11)),
                           format_func=lambda q: f"{q}. {hs.SHORT_Q[q-1]}", key="hs_c_q")
        c_chain = st.text_input("影响是怎么发生的(各环节之间用 → 或 ; 分隔)",
                                placeholder="如:货运增加 → 道路阻隔 → 体力活动下降 → 慢性病", key="hs_c_chain")
        cc, cd = st.columns(2)
        c_str = cc.selectbox("把握程度", hs.STRENGTHS,
                             format_func=lambda s: _STRENGTH_PLAIN.get(s, s), key="hs_c_str")
        c_dir = cd.selectbox("是风险还是益处", ["风险", "效益"],
                             format_func=lambda d: _DIR_PLAIN.get(d, d), key="hs_c_dir")
        if st.button("添加这条影响"):
            steps = [s.strip() for s in c_chain.replace("；", ";").replace(";", "→").split("→") if s.strip()]
            if steps:
                st.session_state.setdefault("hs_custom", [])
                cid = f"C{len(st.session_state['hs_custom'])+1}"
                newp = {
                    "id": cid, "action_id": c_act, "chain": steps, "outcome_q": int(c_q),
                    "direction": c_dir, "population": "", "lens": "专家补充",
                    "strength": c_str, "status": "专家补充", "evidence": "(专家补充)",
                    "confidence": 0.8}
                hia_evidence.annotate([newp])      # 自动匹配 WHO/meta 证据卡片
                st.session_state["hs_custom"].append(newp)
                st.session_state[f"hs_adopt_{cid}"] = True
                st.rerun()
            else:
                st.warning("请先填写「影响是怎么发生的」。")

    # 汇总最终 10 题判定(从持久存储/控件取专家判定,未改判处用系统初判)
    items_out = [{"q": it["q"], "answer": _final_answer(it["q"], it["answer"]),
                  "note": _final_note(it["q"])} for it in items_live]

    # ===== 第 5 步:结论 + 导出 =====
    st.divider()
    st.markdown("##### 📥 第 5 步 · 得出结论并下载初筛表")
    st.caption("下方是 10 个健康方面的汇总判断(已综合您的核对结果)。确认总体结论、填写专家意见后,"
               "即可一键下载初筛表。")
    with st.expander("查看 10 题判断一览", expanded=False):
        for it in items_out:
            badge = _ANSWER_PLAIN.get(it["answer"], it["answer"])
            col = _BADGE[it["answer"]]
            st.markdown(
                f"<div style='margin:.15rem 0;'>{it['q']}. {hs.QUESTIONS[it['q']-1]}　"
                f"<span style='background:{col};color:#fff;padding:1px 8px;border-radius:9px;"
                f"font-size:0.8rem;'>{badge}</span></div>", unsafe_allow_html=True)
            if it["note"]:
                st.caption("　备注:" + it["note"])
    n_yes = sum(1 for x in items_out if x["answer"] == "是")
    n_unk = sum(1 for x in items_out if x["answer"] == "不知道")
    m1, m2, m3 = st.columns(3)
    m1.metric("需要关注", n_yes); m2.metric("尚不确定", n_unk)
    m3.metric("暂未发现", len(items_out) - n_yes - n_unk)
    yes_qs = [x["q"] for x in items_out if x["answer"] == "是"]
    if yes_qs:
        st.caption("👉 建议进入正式评估、重点关注这几个方面:第 "
                   + "、".join(map(str, yes_qs)) + " 项。")

    lv_default = res.get("suggest_level") or "轻度"
    level = st.radio("总体结论:这项措施对健康的影响程度", LEVELS,
                     index=LEVELS.index(lv_default), horizontal=True, key="hs_level",
                     help="系统参考建议:" + (res.get("suggest_level") or "—")
                          + "(仅供参考,以专家判断为准)")
    opinion = st.text_area("评估专家组意见", key="hs_opinion",
                           placeholder="可写明评估过程与结论;如建议进一步评估,可概述要评估的主要问题与方法。")

    header = {"name": name, "category": category, "dept": dept, "submitter": submitter,
              "phone": phone, "screen_date": str(screen_date), "method": method,
              "related_dept": related_dept}
    docx = hs.build_screen_docx(header, items_out, _adopted(), level, opinion)
    st.download_button("📄 下载《健康影响评估初筛表》(Word 文档)", data=docx,
                       file_name=f"健康影响评估初筛表_{name or '评估对象'}.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       type="primary")
    st.caption("下载的初筛表已填好 10 项判断、各项采纳的影响与依据、结论与签字栏,可直接打印用印。"
               "系统仅辅助梳理,签字与最终结论以专家为准。")
