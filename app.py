# -*- coding: utf-8 -*-
"""健康影响评估智能初筛系统 — Streamlit 单页入口(面向卫健委的独立交付版)。

仅含「AI 辅助 HIA 定性初筛」一个功能:上传政策/规划文档 → AI 三段流水线展开
「政策行动 → 健康决定因素(多级、间接)→ 健康结果」因果路径网 → 代码确定性聚合到
《健康影响评估初筛表》10 题 → 专家逐条复核改判 → 导出初筛表 docx。

结构(从「健康城市智能规划与评估平台」剥离、精简):
  app.py        入口:set_page_config + 注入主题 + banner + 口令门 + 渲染初筛页
  theme.py      健康绿主题色 + 全局 CSS + 品牌条 + 统一页头(中性政务风)
  auth.py       访问口令门(app_password)+ 会话级 API 限流
  hia_screen.py 引擎:3 段 DeepSeek 流水线 + 确定性聚合 + 因果路径 DOT 图 + 初筛表 docx
  hia_evidence.py  WHO 官方证据卡片库(56 张)
  views/screen.py  页面 UI(page_hia_screen)
详见 README.md。
"""
import streamlit as st

st.set_page_config(
    page_title="健康影响评估智能初筛系统",
    page_icon="📋",
    layout="wide",
)

from theme import inject_css, render_banner

inject_css()
render_banner()

from auth import require_login
require_login()   # 未通过口令则在此 st.stop();本地无 app_password secret 时不拦

from views.screen import page_hia_screen
page_hia_screen()
