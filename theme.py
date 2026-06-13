# -*- coding: utf-8 -*-
"""全站视觉:健康绿主题色、全局 CSS、顶部品牌条、统一页头。

被 app.py(注入 CSS / banner)与 views 页面(page_header / 颜色常量)引用。
本工具为「健康影响评估智能初筛系统」(面向卫健委的独立交付版),品牌为中性政务风。
"""
import re

import streamlit as st


HEALTH_GREEN = "#2E9E5B"      # 主强调色
GREEN_DEEP = "#1B6B3A"        # 深绿(标题)


def md_bold(s):
    """把 Markdown 的 **加粗** 转成 HTML <b>,供 unsafe_allow_html 的 HTML 文本用
    (否则 ** 会原样显示成星号)。普通 st.markdown 文本不要用本函数。"""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s or "")


def inject_css():
    """注入全局样式(字体、指标卡、按钮、侧栏、页头、折叠面板等)。"""
    # 防搜索引擎收录(工具仅向特定客户开放,不希望被检索到/留缓存快照)
    st.markdown('<meta name="robots" content="noindex, nofollow, noarchive">',
                unsafe_allow_html=True)
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@500;600;700&display=swap');

        html, body, [class*="css"], .stMarkdown, .stMetric {{
            font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
        }}
        h1, h2, h3, h4, h5 {{
            font-family: 'Noto Serif SC', 'SimSun', serif !important;
            color: {GREEN_DEEP};
            letter-spacing: 0.5px;
        }}
        /* 主区留白更舒展 */
        .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1100px; }}

        /* 指标卡:浅绿底 + 绿色左边线,数字大而醒目 */
        div[data-testid="stMetric"] {{
            background: #F6FCF8;
            border: 1px solid #DCEEE3;
            border-left: 4px solid {HEALTH_GREEN};
            padding: 0.7rem 0.95rem;
            border-radius: 10px;
            box-shadow: 0 1px 2px rgba(27,107,58,0.05);
        }}
        div[data-testid="stMetricValue"] {{
            font-size: 1.9rem; font-weight: 700; color: {GREEN_DEEP};
        }}
        div[data-testid="stMetricLabel"] p {{ color: #5a7a66; font-weight: 500; }}

        /* 按钮:健康绿、圆角、加粗 */
        .stButton > button, .stDownloadButton > button {{
            border-radius: 9px; font-weight: 600; border: 1px solid {HEALTH_GREEN};
        }}
        .stButton > button[kind="primary"] {{
            background: {HEALTH_GREEN}; border-color: {HEALTH_GREEN};
        }}
        .stButton > button[kind="primary"]:hover {{
            background: {GREEN_DEEP}; border-color: {GREEN_DEEP};
        }}

        /* 侧栏:浅绿底 + 右侧细分隔 */
        section[data-testid="stSidebar"] {{
            background: #EAF7EF; border-right: 1px solid #DCEEE3;
        }}

        /* 结果表:表头浅绿、行距舒适 */
        .stTable thead tr th {{
            background: #EAF7EF !important; color: {GREEN_DEEP} !important; font-weight: 600;
        }}
        .stTable td, .stTable th {{ padding: 0.55rem 0.7rem !important; }}

        /* 统一页头:小色条 + 衬线标题 + 副标题 + 细分隔线 */
        .page-head {{ margin: 0.2rem 0 1.1rem 0; }}
        .page-head-title {{
            font-family: 'Noto Serif SC','SimSun',serif; font-size: 1.5rem; font-weight: 700;
            color: {GREEN_DEEP}; letter-spacing: 0.5px; line-height: 1.3;
            border-left: 5px solid {HEALTH_GREEN}; padding-left: 0.7rem;
        }}
        .page-head-sub {{
            color: #5a7a66; font-size: 0.9rem; line-height: 1.65;
            margin: 0.5rem 0 0.7rem 0.95rem;
        }}
        .page-head-rule {{ border: none; border-top: 1px solid #DCEEE3; margin: 0 0 1.1rem 0; }}

        /* 折叠面板:浅绿表头、圆角、细边 */
        details[data-testid="stExpander"], div[data-testid="stExpander"] {{
            border: 1px solid #DCEEE3 !important; border-radius: 10px !important;
            background: #FBFEFC; overflow: hidden;
        }}
        div[data-testid="stExpander"] summary {{
            font-weight: 600; color: {GREEN_DEEP};
        }}
        div[data-testid="stExpander"] summary:hover {{ color: {HEALTH_GREEN}; }}

        /* 分隔线:柔和绿,而非刺眼灰 */
        hr {{ border-top: 1px solid #DCEEE3 !important; }}

        /* 说明文字(caption)略暖的绿灰 */
        div[data-testid="stCaptionContainer"], .stCaption {{ color: #6a8a76 !important; }}

        /* 选项卡 / 单选(segmented)选中态用健康绿 */
        button[data-baseweb="tab"][aria-selected="true"] {{ color: {GREEN_DEEP} !important; }}
        div[data-baseweb="tab-highlight"] {{ background-color: {HEALTH_GREEN} !important; }}

        /* dataframe 表头与 st.table 对齐到浅绿 */
        div[data-testid="stDataFrame"] thead th {{
            background: #EAF7EF !important; color: {GREEN_DEEP} !important;
        }}

        /* 隐藏顶部菜单与页脚,演示更干净 */
        #MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_banner():
    """顶部品牌标题条(中性政务风,无机构署名)。"""
    st.markdown(
        f"""
        <div style="background:linear-gradient(90deg,#EAF7EF 0%,#F6FCF8 100%);
                    border-left:6px solid {HEALTH_GREEN};
                    border-radius:8px; padding:0.9rem 1.2rem; margin-bottom:1.2rem;">
          <div style="color:{HEALTH_GREEN}; font-size:0.95rem; letter-spacing:2px; font-weight:600;">
            健康影响评估(HIA)· 辅助决策工具
          </div>
          <div style="font-family:'Noto Serif SC','SimSun',serif; font-size:1.9rem;
                      font-weight:700; color:{GREEN_DEEP}; letter-spacing:1px;">
            健康影响评估智能初筛系统
          </div>
          <div style="color:#5a7a66; font-size:0.9rem;">
            智能分析展开健康影响路径 · 对照《健康影响评估初筛表》· 专家核定
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title, subtitle=None):
    """统一页头:小色条 + 衬线标题 +(可选)副标题 + 细分隔线。全站一致。"""
    sub = f"<div class='page-head-sub'>{md_bold(subtitle)}</div>" if subtitle else ""
    st.markdown(
        f"<div class='page-head'><div class='page-head-title'>{md_bold(title)}</div>{sub}</div>"
        "<hr class='page-head-rule'/>",
        unsafe_allow_html=True)
