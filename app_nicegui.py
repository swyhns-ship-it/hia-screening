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
import os
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
        ui.label("🔒 健康影响评估智能初筛系统").style(
            f"color:{GREEN_DEEP};font-size:1.3rem;font-weight:700;")
        ui.label("本系统供卫健委工作人员使用,请输入访问口令。").classes("text-sm text-grey")

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
ANSWERS = list(hs.ANSWERS)                      # ('是','不知道','否')
# 简短形(仅用于顶部汇总卡/单选,语境已明确)
ANSWER_LABEL = {"是": "需要关注", "不知道": "尚不确定", "否": "暂未发现"}
# 完整形(用于方面标题徽标,力求自解释、不缩略)
ANSWER_FULL = {"是": "该维度健康影响需重点关注",
               "不知道": "该维度健康影响尚不确定、建议进一步评估",
               "否": "暂未发现明显健康影响"}
ANSWER_COLOR = {"是": "#C62828", "不知道": "#B07A00", "否": "#1B6B3A"}
# 机制证据强度(AI 对该条机制成立的把握),完整表述
STRENGTH_LABEL = {"强": "机制证据较充分", "中": "机制证据中等", "推测": "尚属机制推测"}
STRENGTH_COLOR = {"强": "#C62828", "中": "#E07B39", "推测": "#9AA0A6"}
# 风险/效益 = 负面/正面健康影响效应
DIR_FULL = {"风险": "🔴 负面健康影响(风险)", "效益": "🟢 正面健康影响(效益)"}
STATUS_LABEL = {"文档支持": "线索源自上传文件原文", "路径库/文献": "机制有文献/指南支持",
                "假设待证": "属推断假设、有待证实", "专家补充": "专家手动补充"}


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


def build_mermaid(actions, pathways):
    """把已采纳路径渲成 mermaid 流程图(措施→环节→健康方面)。无颜色,求稳。"""
    act_label = {a["id"]: a["action"] for a in actions}
    lines = ["flowchart LR"]
    ids, edges = {}, []

    def node(prefix, text):
        key = (prefix, text)
        if key not in ids:
            nid = prefix + str(abs(hash(text)) % 100000)
            ids[key] = nid
            safe = str(text).replace('"', "'").replace("\\", "/")[:28]
            lines.append(f'{nid}["{safe}"]')
        return ids[key]

    for p in pathways:
        seq = [node("A", act_label.get(p["action_id"], p["action_id"]))]
        for step in p["chain"]:
            seq.append(node("D", step))
        seq.append(node("Q", f"Q{p['outcome_q']} {hs.SHORT_Q[p['outcome_q']-1]}"))
        for n1, n2 in zip(seq, seq[1:]):
            e = f"{n1} --> {n2}"
            if e not in edges:
                edges.append(e)
    return "\n".join(lines + edges)


def chip(text, color):
    return (f'<span style="background:{color};color:#fff;border-radius:9px;'
            f'padding:1px 8px;font-size:.72rem;white-space:nowrap;">{text}</span>')


def soft_chip(text, color):
    return (f'<span style="color:{color};border:1px solid {color};border-radius:9px;'
            f'padding:0 7px;font-size:.72rem;white-space:nowrap;">{text}</span>')


def prov_of(p):
    """一条影响'健康端'的出处标签:(文本, 颜色)。WHO 证据只支撑链条最后一段(→健康结果),
    故标注为'健康端'。有权威来源→已核实/待补强;无→证据待补。"""
    cards = p.get("cards") or []
    if not cards:
        return "⚠ 健康结局端证据待补(暂为机制推断)", "#B07A00"
    done = any(c.get("status") != "todo" for c in cards)
    return ("📚 健康结局端有权威依据" if done else "📚 健康结局端依据待补强",
            GREEN_DEEP if done else "#B07A00")


@ui.page("/")
def index():
    if not require_app_login():
        return
    ui.colors(primary=GREEN)
    ui.add_head_html('<meta name="robots" content="noindex,nofollow,noarchive">')
    ui.add_head_html(
        "<style>"
        "body{font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;}"
        ".hia-chain{line-height:1.5;}"
        "</style>")
    # 内容居中 + 限宽,避免全屏过宽难读
    ui.query(".nicegui-content").classes("mx-auto").style("max-width:1000px;")

    # —— 每会话状态(闭包持有)——
    st = {"file_bytes": None, "file_name": "", "res": None, "docinfo": None}
    adopt, ans, note, sysans = {}, {}, {}, {}   # pid->bool / q->str / q->str / q->str(系统初判)
    overridden = set()                           # 专家手动改过判定的方面(不再被勾选自动覆盖)
    fb = {}                                      # pid -> {"flag":问题类型, "note":备注}(专家反馈)

    def all_pathways():
        return list((st["res"] or {}).get("pathways", []))

    # ===== 顶部品牌条 =====
    with ui.row().classes("w-full items-center justify-between q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("健康影响评估(HIA)· 辅助决策工具").style(
                f"color:{GREEN};letter-spacing:2px;font-size:.85rem;font-weight:600;")
            ui.label("健康影响评估智能初筛系统").style(
                f"color:{GREEN_DEEP};font-size:1.7rem;font-weight:700;")
            ui.label("智能分析展开健康影响路径 · 对照《健康影响评估初筛表》· 专家核定").style(
                "color:#5a7a66;font-size:.85rem;")
        ui.link("专家组协同初筛 →", "/panel").style(
            f"color:{GREEN_DEEP};font-weight:600;font-size:.9rem;").props("no-underline")

    # ===== 使用说明 =====
    with ui.expansion("📖 使用说明(第一次使用请先看这里)", value=True).classes(
            "w-full").style("border:1px solid #DCEEE3;border-radius:10px;"):
        ui.markdown(
            "**怎么用?三步:** ①上传要评估的政策/规划文件 → ②点「开始分析」,"
            "系统自动梳理可能的健康影响 → ③逐方面核对、下载初筛表。\n\n"
            "**看结果:** 先看顶部 10 个健康方面的红/黄/绿一览;想细看某一方面,点开那一行,"
            "里面是系统找到的影响(勾掉不认可的),「依据/详情」按需展开。\n\n"
            "⚠️ 本系统借助智能分析技术辅助梳理,**结论和签字以专家判断为准**,不替代专家。")

    # ===== 第 1–2 步:上传 + 分析 =====
    with ui.card().classes("w-full").style("border:1px solid #DCEEE3;"):
        ui.label("第 1 步 · 上传要评估的文件").classes("text-base font-medium")
        ui.label("支持 PDF 或 Word(.docx)。扫描成图片的 PDF 暂不支持。").classes(
            "text-xs text-grey")

        async def on_upload(e):
            st["file_bytes"] = await e.file.read()
            st["file_name"] = e.file.name
            st["name"] = e.file.name.rsplit(".", 1)[0]
            ui.notify(f"已上传:{e.file.name}", type="positive")

        ui.upload(on_upload=on_upload, auto_upload=True, max_files=1).props(
            'accept=".pdf,.docx" flat bordered').classes("w-full")

        ui.label("第 2 步 · 开始智能分析").classes("text-base font-medium q-mt-md")
        key_in = ui.input("分析服务密钥(API Key)", password=True,
                          value=_get_key(), placeholder="sk-...").classes("w-full")

        async def do_analyze():
            if not st["file_bytes"]:
                ui.notify("请先在第 1 步上传文件。", type="warning")
                return
            key = (key_in.value or "").strip()
            if not key:
                ui.notify("请先填写分析服务密钥。", type="warning")
                return
            text, info = hs.extract_text(st["file_name"], st["file_bytes"])
            if info.get("error"):
                ui.notify(info["error"], type="negative")
                return
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
            adopt.clear(); ans.clear(); note.clear(); sysans.clear()
            for p in res["pathways"]:
                adopt[p["id"]] = _adopt_default(p)
            for it in hs.compute_items([p for p in res["pathways"] if adopt[p["id"]]]):
                sysans[it["q"]] = it["answer"]
                ans[it["q"]] = it["answer"]
            tip = f"已解析{info['kind']}" + (f"·{info['pages']}页" if info["pages"] else "")
            ui.notify(f"✅ {tip};识别 {len(res['actions'])} 项措施、"
                      f"梳理 {len(res['pathways'])} 条影响。", type="positive")
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
                        f"border-left:4px solid {ANSWER_COLOR[a]};"):
                    ui.label(str(cnt[a])).style(
                        f"font-size:1.7rem;font-weight:700;color:{ANSWER_COLOR[a]};")
                    ui.label(ANSWER_LABEL[a]).classes("text-xs text-grey")
        # 10 格红绿灯
        with ui.row().classes("w-full gap-1 q-mt-xs"):
            for q in range(1, 11):
                a = ans.get(q, "否")
                ui.html(f'<div title="{q}. {hs.SHORT_Q[q-1]}:{ANSWER_LABEL[a]}" '
                        f'style="flex:1;height:10px;border-radius:3px;'
                        f'background:{ANSWER_COLOR[a]};"></div>').classes("flex-grow")

    @ui.refreshable
    def graph():
        adopted = [p for p in all_pathways() if adopt.get(p["id"])]
        if not adopted:
            ui.label("(暂无已认可的影响,勾选后显示关系图。)").classes("text-xs text-grey")
            return
        ui.label("图较大,可在框内左右、上下拖动查看。").classes("text-xs text-grey")
        try:
            # useMaxWidth=False:按自然尺寸渲染(不被压扁),放进可滚动框查看
            cfg = {"flowchart": {"useMaxWidth": False, "nodeSpacing": 40,
                                 "rankSpacing": 60, "htmlLabels": True}}
            with ui.element("div").style(
                    "overflow:auto;max-height:640px;width:100%;border:1px solid #EAEAEA;"
                    "border-radius:8px;background:#fff;padding:6px;"):
                ui.mermaid(build_mermaid(st["res"]["actions"], adopted), config=cfg)
        except Exception:                                  # noqa: BLE001
            ui.label("(关系图渲染失败,可忽略,不影响判断与导出。)").classes("text-xs text-grey")

    def pathway_row(p, on_toggle):
        """一条影响 = 一行:勾选 + 把握色块 + 风险/益处 + 影响链;依据/详情按需展开。"""
        with ui.row().classes("items-start no-wrap w-full gap-2"):
            cb = ui.checkbox(value=adopt.get(p["id"], _adopt_default(p))).props("dense")

            def _toggle(e, pid=p["id"]):
                adopt[pid] = e.value
                on_toggle()
            cb.on_value_change(_toggle)
            dirc = "#C62828" if p["direction"] == "风险" else GREEN_DEEP
            dirt = DIR_FULL.get(p["direction"], p["direction"])
            prov_t, prov_c = prov_of(p)
            # 徽标单独成行(留出空间放完整表述),影响链在下一行
            meta = (soft_chip(STRENGTH_LABEL.get(p["strength"], p["strength"]),
                              STRENGTH_COLOR[p["strength"]])
                    + " " + soft_chip(dirt, dirc)
                    + " " + soft_chip(prov_t, prov_c))
            ui.html(f'<div style="margin-bottom:3px;line-height:1.9;">{meta}</div>'
                    f'<div class="hia-chain">{" → ".join(p["chain"])}</div>')
        cards = p.get("cards") or []
        with ui.expansion("依据 / 详情(点此展开)", icon="menu_book").props(
                "dense").classes("w-full q-ml-lg").style(
                "border:1px dashed #CFE0D5;border-radius:8px;background:#FAFEFB;"):
            if p.get("population"):
                ui.label("主要影响人群:" + p["population"]).classes("text-xs")
            ui.label("证据强度评估:" + STRENGTH_LABEL.get(p["strength"], p["strength"])
                     + "　|　依据来源:" + STATUS_LABEL.get(p["status"], p["status"])).classes("text-xs")
            # 文件原句依据(锚住链路起点)
            if p.get("status") == "文档支持" and p.get("evidence"):
                ui.html(f'<div style="font-size:.78rem;background:#F1F8F4;'
                        f'border-left:3px solid {GREEN};padding:4px 8px;border-radius:4px;">'
                        f'📄 <b>文件原文依据</b>(对应链条最前段):{p["evidence"]}</div>')
            # 健康端权威来源(带证据等级 + 核实状态),或证据待补
            if cards:
                last = p["chain"][-1] if p.get("chain") else "健康结果"
                ui.html(f'<div style="font-size:.75rem;color:#5a7a66;margin-top:2px;">'
                        f'📚 下列来源支撑本条<b>最后一段「→ {last}」的健康影响</b>;'
                        f'链条前段的政策/行为/暴露环节,请结合上传文件与本地情况判断。</div>')
                for c in cards:
                    badge = (soft_chip(c.get("tier", "WHO 资料"), GREEN_DEEP) + " "
                             + (soft_chip("已核实", GREEN_DEEP) if c.get("status") != "todo"
                                else soft_chip("待补强", "#B07A00")))
                    ui.html(f'<div style="font-size:.78rem;">{badge}</div>')
                    ui.markdown("　来源:" + "；".join(c["sources"])).classes("text-xs")
                    if c.get("note"):
                        ui.label("　要点(概括,以原文链接为准):" + c["note"]).classes(
                            "text-xs text-grey")
            else:
                ui.html('<div style="font-size:.78rem;background:#FFF7E6;'
                        'border-left:3px solid #B07A00;padding:4px 8px;border-radius:4px;">'
                        '⚠ <b>健康端证据待补</b>:暂无权威来源支撑这条的健康影响,'
                        '需专家补证后再采纳。</div>')
            # —— 专家反馈(可选):标出这条的问题,用于改进系统 ——
            pid = p["id"]
            fb.setdefault(pid, {"flag": "", "note": ""})
            ui.separator()
            with ui.row().classes("items-center gap-2 w-full no-wrap"):
                ui.label("🚩 专家反馈:").classes("text-xs").style("color:#888;")
                sel = ui.select(["", *fb_engine.FLAGS], value=fb[pid]["flag"]).props(
                    "dense options-dense").style("min-width:130px;font-size:.78rem;")
                sel.on_value_change(lambda e, i=pid: fb[i].__setitem__("flag", e.value or ""))
                ni = ui.input(placeholder="问题说明(可选)").props("dense").classes("flex-grow")
                ni.on_value_change(lambda e, i=pid: fb[i].__setitem__("note", e.value or ""))

    def render_dimension(q, allp):
        """单个健康方面:标题色块(实时) + 影响勾选 + 专家判定(实时联动)。"""
        ps = [p for p in allp if p["outcome_q"] == q]

        def cur():
            return ans.get(q, sysans.get(q, "否"))

        @ui.refreshable
        def head_chip():
            a = cur()
            ui.html(chip("研判:" + ANSWER_FULL[a], ANSWER_COLOR[a]))

        @ui.refreshable
        def judge_row():
            a = cur()
            with ui.row().classes("items-center gap-4 w-full"):
                ui.label("您的判断:").classes("text-sm")
                rad = ui.radio({x: ANSWER_LABEL[x] for x in ANSWERS},
                               value=a).props("inline dense")

                def _setans(e, qq=q):
                    ans[qq] = e.value
                    overridden.add(qq)              # 专家手动定过 → 不再被勾选自动覆盖
                    head_chip.refresh()
                    summary.refresh()
                rad.on_value_change(_setans)

        def after_toggle():
            sub = [p for p in ps if adopt.get(p["id"])]
            sysans[q] = hs.compute_items(sub)[q - 1]["answer"]
            if q not in overridden:                 # 未手动改判 → 判定跟随系统重算
                ans[q] = sysans[q]
                judge_row.refresh()
            head_chip.refresh()
            summary.refresh()
            graph.refresh()

        open_default = sysans.get(q) == "是"        # "需要关注"默认展开,聚焦重点
        with ui.expansion(value=open_default).classes("w-full").style(
                "border:1px solid #DCEEE3;border-radius:10px;margin-bottom:6px;") as exp:
            with exp.add_slot("header"):
                with ui.row().classes("items-center gap-3 w-full"):
                    ui.icon("expand_more").classes("text-grey")
                    ui.label(f"{q}. {hs.SHORT_Q[q-1]}").classes(
                        "text-sm font-medium").style("min-width:96px;")
                    head_chip()
                    ui.label(f"{len(ps)} 条影响" if ps else "无影响").classes(
                        "text-xs text-grey")
            ui.label("初筛表问题:" + hs.QUESTIONS[q - 1]).classes("text-xs text-grey")
            if ps:
                n_src = sum(1 for p in ps if p.get("cards"))
                n_gap = len(ps) - n_src
                ui.html(f'<div style="font-size:.75rem;color:#5a7a66;">证据情况:'
                        f'<b>{n_src}</b> 条有权威来源 · '
                        f'<b style="color:#B07A00">{n_gap}</b> 条证据待补(机制推断)</div>')
                for p in ps:
                    pathway_row(p, after_toggle)
            else:
                ui.label("系统未找到这一方面的影响,默认「暂未发现」。").classes("text-xs text-grey")
            ui.separator()
            judge_row()
            note_in = ui.input("说明 / 备注(可选)").classes("w-full")
            note_in.on_value_change(lambda e, qq=q: note.__setitem__(qq, e.value))

    @ui.refreshable
    def results():
        if not st["res"]:
            return
        res = st["res"]
        allp = all_pathways()

        if res.get("summary"):
            with ui.card().classes("w-full").style(
                    "background:#EAF4FF;border:1px solid #CFE3FB;"):
                ui.markdown("🧭 **总体研判(供参考):** " + res["summary"])

        ui.label("健康影响一览").classes("text-base font-medium q-mt-sm")
        ui.label("先看全局:每个方块/数字代表一个健康方面的判断(红=需要关注 黄=尚不确定 绿=暂未发现)。").classes("text-xs text-grey")
        summary()

        with ui.expansion("🔗 健康影响关系图(措施 → 环节 → 健康方面)",
                          icon="account_tree").classes("w-full").style(
                "border:1px solid #DCEEE3;border-radius:10px;"):
            graph()

        ui.label("第 3 步 · 逐方面核对、给出判断").classes("text-base font-medium q-mt-md")
        ui.label("下面 10 行 = 10 个健康方面(标着「需要关注」的已自动展开)。点行首箭头可展开/收起;"
                 "每条影响可勾选(认可/排除),勾选会实时更新该方面判断与顶部一览;"
                 "「依据/详情」按需展开。").classes("text-xs text-grey")

        for q in range(1, 11):
            render_dimension(q, allp)

        # ===== 第 4 步:结论 + 下载 =====
        ui.label("第 4 步 · 得出结论并下载初筛表").classes("text-base font-medium q-mt-md")
        with ui.row().classes("items-center gap-3 w-full"):
            ui.label("总体影响程度:").classes("text-sm")
            lv_default = res.get("suggest_level") if res.get("suggest_level") in (
                "很小", "轻度", "重大") else "轻度"
            level_radio = ui.radio(["很小", "轻度", "重大"], value=lv_default).props(
                "inline dense")
        with ui.row().classes("w-full items-center"):
            name_in = ui.input("评估对象名称(用于初筛表标题,可改)",
                               value=st.get("name", "")).classes("flex-grow")
        opinion_in = ui.textarea("评估专家组意见(可选)").classes("w-full")

        def do_download():
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

        ui.button("📄 下载《健康影响评估初筛表》(Word)", on_click=do_download).props(
            "color=primary").classes("q-mt-sm")
        ui.label("初筛表已填好 10 项判断、各项采纳的影响与依据、结论与签字栏。"
                 "系统仅辅助梳理,签字与最终结论以专家为准。").classes("text-xs text-grey")

        # ===== 第 5 步(可选):提交专家反馈,用于持续改进系统 =====
        ui.separator()
        ui.label("第 5 步 · 提交专家反馈(可选,帮助改进系统)").classes(
            "text-base font-medium q-mt-md")
        ui.label("您在各条影响处标记的问题、采纳/排除与判定,将匿名留痕,用于改进路径推断与证据库。").classes(
            "text-xs text-grey")
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

    results()


# ==================== 专家组协同初筛(独立板块)====================

def _page_head():
    ui.query(".nicegui-content").classes("mx-auto").style("max-width:1000px;")
    ui.add_head_html('<meta name="robots" content="noindex,nofollow,noarchive">')
    ui.add_head_html("<style>body{font-family:'Microsoft YaHei','Noto Sans SC',sans-serif;}"
                     ".hia-chain{line-height:1.5;}</style>")
    ui.colors(primary=GREEN)


def render_pathway_ro(p):
    """只读渲染一条影响(供专家评审/汇总页):徽标行 + 影响链 + 依据折叠。"""
    dirc = "#C62828" if p["direction"] == "风险" else GREEN_DEEP
    prov_t, prov_c = prov_of(p)
    meta = (soft_chip(STRENGTH_LABEL.get(p["strength"], p["strength"]), STRENGTH_COLOR[p["strength"]])
            + " " + soft_chip(DIR_FULL.get(p["direction"], p["direction"]), dirc)
            + " " + soft_chip(prov_t, prov_c))
    ui.html(f'<div style="margin:2px 0;line-height:1.9;">{meta}</div>'
            f'<div class="hia-chain">{" → ".join(p["chain"])}</div>')
    cards = p.get("cards") or []
    with ui.expansion("依据 / 详情", icon="menu_book").props("dense").classes(
            "w-full q-ml-md").style("border:1px dashed #CFE0D5;border-radius:8px;background:#FAFEFB;"):
        if p.get("population"):
            ui.label("主要影响人群:" + p["population"]).classes("text-xs")
        if p.get("status") == "文档支持" and p.get("evidence"):
            ui.label("📄 文件原文依据:" + p["evidence"]).classes("text-xs")
        for c in cards:
            vs = "·待补强" if c.get("status") == "todo" else "·已核实"
            ui.markdown(f"📚 来源[{c.get('tier','资料')}{vs}]:" + "；".join(c["sources"])).classes(
                "text-xs")
        if not cards:
            ui.label("⚠ 健康结局端证据待补(暂为机制推断)").classes("text-xs")


@ui.page("/panel")
def panel():
    if not require_app_login():
        return
    _page_head()
    with ui.row().classes("w-full items-center justify-between q-pa-md").style(
            f"background:linear-gradient(90deg,#EAF7EF,#F6FCF8);border-left:6px solid {GREEN};"
            "border-radius:8px;"):
        with ui.column().classes("gap-0"):
            ui.label("专家组协同初筛 · 经办台").style(
                f"color:{GREEN_DEEP};font-size:1.5rem;font-weight:700;")
            ui.label("上传文档→AI 初筛→创建案例→把「案例码+口令」发给专家→汇总共识→组长定稿").style(
                "color:#5a7a66;font-size:.85rem;")
        ui.link("← 返回单人初筛", "/").props("no-underline").style(
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
                with ui.card().classes("w-full").style("background:#F1F8F4;border:1px solid #CFE0D5;"):
                    ui.label(f"✅ 案例已创建:{case['name']}").classes("font-medium")
                    ui.label(f"案例码:{case['id']}　|　专家口令:{case['expert_pwd']}").style(
                        "font-family:monospace;")
                    ui.label("把下面这条「专家评审链接 + 口令」发给各位专家(微信/邮件均可):").classes(
                        "text-xs text-grey")
                    ui.input("专家评审链接", value=f"/review/{case['id']}").props(
                        "readonly dense").classes("w-full").style("font-family:monospace;")
                    ui.label("提示:部署后把链接前补上服务器地址(如 http://你的域名/review/"
                             + case["id"] + ");口令单独告知专家。").classes("text-xs text-grey")
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
            ui.label("专家组协同初筛 · 专家评审台").style(
                f"color:{GREEN_DEEP};font-size:1.4rem;font-weight:700;")
            ui.label(f"评估对象:{case['name']}").style("color:#5a7a66;font-size:.9rem;")

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
        ui.label("请输入经办人员提供的评审口令:").classes("q-mt-md")
        pwd_in = ui.input("评审口令", password=True).on("keydown.enter", check_pwd)
        ui.button("进入评审", on_click=check_pwd).props("color=primary")


def _render_review_form(case):
    res = case["res"]
    allp = res.get("pathways", [])
    res_items = {it["q"]: it for it in res.get("items", [])}
    ans, note = {}, {}

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
                render_pathway_ro(p)
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


ui.run(host="0.0.0.0", port=APP_PORT, title="健康影响评估智能初筛系统",
       show=False, reload=False, storage_secret=STORAGE_SECRET)
