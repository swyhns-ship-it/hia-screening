# 健康影响评估智能初筛系统 — 项目说明(给 Claude Code · 跨机器上下文)

> 本文件随仓库提交。另一台电脑 `git clone` 本仓库后,Claude Code 自动读取接续工作。
> ⚠️ 本仓库**公开**,严禁把任何密钥/口令写进任何入库文件(DeepSeek key、APP_PASSWORD、案例口令、STORAGE_SECRET 等)。
> 用户:孙文尧(同济 CAUP · 王兰团队 · 健康城市方向)。Python 熟、前端不熟。中文回复、简明、给可执行下一步。

## 是什么
面向**卫健委**的独立 HIA(健康影响评估)**智能初筛**工具。由「健康城市智能规划与评估平台」(另一仓库 hia_demo)的同名模块剥离独立而成。中性政务品牌(界面无同济实验室字样),界面用 **NiceGUI**(不是 Streamlit)。**平台名:「AI辅助健康影响评估」**(`PLATFORM_NAME`)。
**信息架构(2026-06-14 重构为门户+两级层级)**:
- **门户首页 `/`**:平台名 + 三卡片(🆕 新建健康影响评估 / 🗂 项目管理 / 📚 案例参考)。内页统一顶部导航 `_top_nav`(左「← 返回首页」+ 三板块高亮)。
- **新建健康影响评估 `/new`**:分流两张卡 → ① 独立完成初筛(`/screen`,**发起方/经办**单人)② 发起专家组协同评估(`/panel`)。
- **健康影响初筛 `/screen`**(原 `/`):经办上传政策/规划文档 → AI(DeepSeek)三段流水线展开「政策行动 → 健康决定因素(多级、间接)→ 健康结果」因果路径 → 对照《健康影响评估初筛表》10 题 → 专家核对/改判 → 导出初筛表 docx / **存入项目管理**。步骤条(上传→分析→核对→导出)、上传区分析后自动收起、红绿灯汇总吸顶。
- **专家组协同评估**(`/panel` 经办/**发起方**台 + `/review/<案例码>` **受邀专家**台):经办创建案例、生成「案例码+口令」发给专家(`/panel` 创建后「📋 复制完整邀请」一键复制带服务器地址的链接+口令);专家凭口令**独立**评定(`/review` 不带平台导航、顶部「您的任务三步」卡,直达评审);经办/组长在 `/panel` 看**逐题共识/分歧**、组长定稿导出共识初筛表。专家无需账号。
- **项目管理 `/ledger`**:单人+协同所有项目统一台账。搜索/按状态/来源筛选;重新导出初筛表 docx;状态流转(评审中/已定稿/已归档/作废+恢复);删除;**发布为参考案例**。单人初筛在 `/screen` 第 4 步「🗂 存入项目管理」落库。
- **案例参考 `/reference`**:只读展示在项目管理中「发布为参考案例」的项目(10 题一览+逐题影响路径只读+下载范例初筛表)。

## 运行(本地开发)
- **Python 3.11**(关键:NiceGUI 跑不了 3.6;旧 Streamlit 版的 numpy/3.11 约束已不适用本工具)。
- `python -m venv .venv` → `.venv/bin/pip install -r requirements.txt`(nicegui 3.13 / python-docx / pypdf / requests)。
- 密钥走**环境变量**或 `.streamlit/secrets.toml`(已 gitignore):`DEEPSEEK_API_KEY` 必填;`APP_PASSWORD` 选填(经办台口令门,未配则不拦,本地开发用)。
- 启动:`python app_nicegui.py`(默认端口 8502)→ 浏览器 `http://localhost:8502`。

## 架构 / 文件
- `app_nicegui.py` — NiceGUI 入口 + 三页面(`/` 单人初筛、`/panel` 经办台、`/review/<案例码>` 专家台)+ 访问口令门 `require_app_login`(env `APP_PASSWORD`)。端口/口令/会话密钥走环境变量。
- `hia_screen.py` — 引擎:3 段 DeepSeek 流水线(行动抽取→多视角路径展开→完整性批判)+ 确定性聚合到 10 题 + 初筛表 docx。坑:DeepSeek json_object 偶发吐空白,需"加扰动重试"(`_chat_json` 已处理)。提示词已:去重复/去政策元评论/严标强度。
- `hia_evidence.py` — 证据库(**62 张卡**:WHO + 国标/国家政策)。`source_tier` 来源分级;`_STOP_KEYS` 结果/泛化词停用表;`_SYN_GROUPS`(24 组)同义词扩展匹配;`match()` 仅用**确定性关键词+同义词**匹配。**已停用 LLM 语义匹配**(它会把同题号但机制不相干的卡乱配,损"有据可查")。
- `cases.py` — 案例/项目库(文件级 `cases/<案例码>.json` + 政策原文 `cases/<案例码>.<ext>`),单人与协同共用。字段含 `source`(单人初筛/专家协同)、`status`(评审中/已定稿/已归档/作废)、`reference`(参考案例)、`adopted_ids`(单人当时采纳的影响路径)。`consensus_view` 逐题算共识/分歧;`doc_path` 取原文;`save_single_case` 单人一键落库(直接已定稿,判定存 `consensus`);`set_status`/`set_reference`/`delete_case`/`adopted_pathways`/`list_reference` 供项目管理与案例参考用。`app_nicegui._case_export_payload`+`adopted_pathways` 统一供台账/案例参考重新导出 docx。
- `feedback.py` — 专家反馈留痕(`feedback/feedback_log.jsonl`)+ `summarize`;`eval/feedback_report.py` 出回流报告。
- `theme.py` 主题/品牌;`views/screen.py`、`app.py`、`auth.py` 是**旧 Streamlit 版**(保留,部署不用)。
- `eval/` 批测:`run_eval.py`(支持目录参数)、`make_*_policies.py`(合成/真实测试政策)、`REVIEW_GUIDE.md`。
- `docs/` 取证与部署:`standards_master_list.md`(国标主清单)、`gb_standards_shoplist.md`、`kb_expansion_worklist.md`、`DEPLOY.md`、`DEPLOY_HTTPS.md`。

## 关键决策 / 铁律
- **证据可靠:精准 > 召回**;匹配不到宁标「证据待补」也不贴错卡(贴错比没有更糟)。
- **绝不臆造来源**(URL/标准号/原文摘录)——加卡前必须联网核实**现行版**(踩过 GB 3095-2012 已废、换 2026 版的坑)。
- WHO 证据只支撑链条「最后一段→健康结果」;中间政策/行为/暴露环节需结合文件+本地判断(界面已注明)。
- 文案面向**零基础政务用户**:自解释、不缩略;强制浅色主题。
- 召回主要杠杆 = 卡片关键词覆盖 AI 常用**同义措辞**(`_SYN_GROUPS`)。
- 离线 `eval` 批测(上线前自检)与界面专家反馈(上线后校准)用同一套改进动作(改 keys/同义词/停用词/提示词)。

## 部署现状(2026-06-13)
- **已上线 + 端到端验证通过**:阿里云 ECS(华东2·上海,2核2G,Alibaba Cloud Linux 3,Python 3.11)。systemd 服务名 **`hia`**,部署目录 `/opt/hia-screening`(内有 `.venv`),监听 **8502**,环境变量在 **`/etc/hia-screening.env`**(含 DEEPSEEK_API_KEY / APP_PASSWORD / STORAGE_SECRET / PORT,**不入库**)。内存占用 ~55M。
- 已公网走通整条:口令门 → 上传政策 PDF → AI 初筛 → 创建案例(案例码+口令)→ 专家凭口令独立评定 → 逐题共识/分歧 → 组长定稿导出 → 政策原文下载。
- **更新部署**(服务器上):`cd /opt/hia-screening && git pull && .venv/bin/pip install -r requirements.txt && systemctl restart hia`
- 公网访问目前走 `IP:8502`(IP/口令见本地/控制台记录,不写入本公开仓库)。安全组已放行 8502。

## 大局:实验室统一站(2026-06-13 定的方向)
有了域名后,要把**实验室门户 + 分析平台(hia_demo)+ HIA 初筛工具**拢成"一个成品级实验室站",架构=**一个域名 + 统一品牌 + 门户串子应用**(不做单体):
- `tjhealthycitylab.com`(主域名)→ **实验室门户**(静态站,已起草,见下"相关项目")。
- `hia.tjhealthycitylab.com` → 本 HIA 工具(已上线,阿里云)。
- `platform.tjhealthycitylab.com` → 分析平台 hia_demo(待部署;Streamlit;UI 后续可增量迁 NiceGUI)。
- 域名 `tjhealthycitylab.com` 已注册(个人实名),**ICP 备案进行中**(大陆服务器必须,3–20 天);备案通过按 `docs/DEPLOY_HTTPS.md` 上 HTTPS。

## 相关项目(同一台开发机,各自独立)
- **实验室门户**:`E:\projects\healthycitylab_portal`(纯静态 index.html + style.css,健康绿主题,与本工具一套视觉)。已起草:Hero/关于/研究方向/平台与工具入口/方法亮点/团队/成果/页脚。**待补真实内容**(团队成员、代表性成果、联系邮箱——均标了"待补充",未编造)。本地预览 `python -m http.server`;部署=丢服务器 nginx 静态目录。**尚未建 git 远程**。
- **分析平台**:`E:\projects\hia_demo`(Streamlit,重型 ML+地图)。计划部署到服务器(见下);UI 升级单独立项、增量迁。
- **实验室自有服务器**:`ssh tongji@101.35.31.42 -p 2301`——实测为**腾讯云中转 + frp 内网穿透**到校内真机(私有 IP 192.168.x、带 Docker、出口上海电信)。**适合跑重型平台 + 校内/内部访问**;对外公开因隧道带宽/备案问题不划算 → **公开服务仍留阿里云**。今日暂不部署它。

## 本会话新增(2026-06-14,门户重构 + 项目管理 + 角色感)
- **项目管理 `/ledger`**:cases.py 加 source/状态流转/参考案例标记;单人初筛 `/screen` 第 4 步「存入项目管理」落库;统一搜索/筛选/重导出/归档/删除/发布范例。
- **门户两级层级**:平台改名「AI辅助健康影响评估」;`/` 改门户三卡片;初筛工作台移到 `/screen`;`/new` 分流;`/reference` 案例参考(只读展示已发布范例);`_top_nav` 全站统一导航。
- **内页打磨(/screen)**:步骤条、上传区分析后自动收起、红绿灯汇总吸顶、使用说明默认收起。
- **角色感**:发起方(卫健委)视角=「发起专家组协同评估」(`/new` 卡、`/panel` 头部);受邀专家视角=`/review` 不带平台导航、口令门+「您的任务三步」卡直达评审;`/panel` 创建后「📋 复制完整邀请」(JS 取 `window.location.origin` 拼完整链接+口令)。
- **下一步**:**智能助手(Copilot)**——拟从 hia_demo 的 `llm_agent.py` 移植精简版(解释 HIA 术语、引导经办、答疑)。

## 域名 / 备案进展(2026-06-14)
- 域名 `tjhealthycitylab.com` 已注册;**子域名 `hia.tjhealthycitylab.com` → 阿里云 ECS `106.15.57.87`**(A 记录已配,安全组放行 8502)。
- **备案进行中**:阿里云首次备案,**主体=单位「上海灵犀智屿科技有限公司」**(注意:单位备案要求域名持有者=该单位,个人实名须先过户);网站名取公司简称「灵犀智屿科技」避开"健康/医疗"前置审批词。
- ⚠ **备案没过前**:阿里云按域名(Host)拦截**所有端口**(含 8502),域名访问跳"备案状态不符"页;**只能用 IP 直连 `http://106.15.57.87:8502`**。备案通过后域名自动恢复,再按 `docs/DEPLOY_HTTPS.md` 上 HTTPS。

## 待办 / 进行中
1. **域名 + HTTPS**:`tjhealthycitylab.com` 备案通过后,按 `docs/DEPLOY_HTTPS.md` 配 `hia.` 子域名 DNS+Nginx+HTTPS。
2. **知识库扩充**(进行中):用户在 `std.samr.gov.cn` 按 `docs/gb_standards_shoplist.md` / `standards_master_list.md` 取证;拿到**现行编号+URL** 后加进 `hia_evidence.py` 的 `CARDS` + 配 `_SYN_GROUPS` + 跑 `eval` 验证。
3. **实验室门户**:补真实内容 → 建 git 仓库 → 备案后挂主域名。
4. **分析平台部署**:hia_demo 部署到实验室真机(校内/内部)或阿里云(若升配);先原样搬,UI 后议。
5. **安全收尾**:DeepSeek key 明文出现过,**需轮换**(改 `/etc/hia-screening.env` 后 `systemctl restart hia`);实验室服务器 **SSH 密码需改**;安全组从 `0.0.0.0/0` 收紧。
6. **可选功能**:项目台账状态流转、角色/权限、监管看板、站内推送。

## 跨机器工作流
- **开工** `git pull`;**收工** `git add -A && git commit -m "..." && git push`。
- 远程:`origin = github.com/swyhns-ship-it/hia-screening`(公开)。
- **密钥不入库**:本地 `.streamlit/secrets.toml`、服务器 `/etc/hia-screening.env`(均 gitignore / 仅本机各配一次)。换机器后这俩要重配。
- 运行时数据 `cases/`、`feedback/`、`eval/out*/` 已 gitignore(不随仓库同步;服务器上单独备份)。
- 新机器:`git clone` → 建 venv 装 `requirements.txt` → 配 secrets → `python app_nicegui.py`。
