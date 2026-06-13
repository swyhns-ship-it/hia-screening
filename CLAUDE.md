# 健康影响评估智能初筛系统 — 项目说明(给 Claude Code · 跨机器上下文)

> 本文件随仓库提交。另一台电脑 `git clone` 本仓库后,Claude Code 自动读取接续工作。
> ⚠️ 本仓库**公开**,严禁把任何密钥/口令写进任何入库文件(DeepSeek key、APP_PASSWORD、案例口令、STORAGE_SECRET 等)。
> 用户:孙文尧(同济 CAUP · 王兰团队 · 健康城市方向)。Python 熟、前端不熟。中文回复、简明、给可执行下一步。

## 是什么
面向**卫健委**的独立 HIA(健康影响评估)**智能初筛**工具。由「健康城市智能规划与评估平台」(另一仓库 hia_demo)的同名模块剥离独立而成。中性政务品牌(界面无同济实验室字样),界面用 **NiceGUI**(不是 Streamlit)。两个板块:
- **单人初筛工作台**(`/`):经办上传政策/规划文档 → AI(DeepSeek)三段流水线展开「政策行动 → 健康决定因素(多级、间接)→ 健康结果」因果路径 → 对照《健康影响评估初筛表》10 题 → 专家核对/改判 → 导出初筛表 docx。
- **专家组协同初筛**(`/panel` 经办台 + `/review/<案例码>` 专家台):经办创建案例、生成「案例码+口令」发给专家(微信/邮件,即"推送");专家凭口令**独立**评定;经办/组长在 `/panel` 看**逐题共识/分歧**、组长定稿导出共识初筛表。专家无需账号。

## 运行(本地开发)
- **Python 3.11**(关键:NiceGUI 跑不了 3.6;旧 Streamlit 版的 numpy/3.11 约束已不适用本工具)。
- `python -m venv .venv` → `.venv/bin/pip install -r requirements.txt`(nicegui 3.13 / python-docx / pypdf / requests)。
- 密钥走**环境变量**或 `.streamlit/secrets.toml`(已 gitignore):`DEEPSEEK_API_KEY` 必填;`APP_PASSWORD` 选填(经办台口令门,未配则不拦,本地开发用)。
- 启动:`python app_nicegui.py`(默认端口 8502)→ 浏览器 `http://localhost:8502`。

## 架构 / 文件
- `app_nicegui.py` — NiceGUI 入口 + 三页面(`/` 单人初筛、`/panel` 经办台、`/review/<案例码>` 专家台)+ 访问口令门 `require_app_login`(env `APP_PASSWORD`)。端口/口令/会话密钥走环境变量。
- `hia_screen.py` — 引擎:3 段 DeepSeek 流水线(行动抽取→多视角路径展开→完整性批判)+ 确定性聚合到 10 题 + 初筛表 docx。坑:DeepSeek json_object 偶发吐空白,需"加扰动重试"(`_chat_json` 已处理)。提示词已:去重复/去政策元评论/严标强度。
- `hia_evidence.py` — 证据库(**62 张卡**:WHO + 国标/国家政策)。`source_tier` 来源分级;`_STOP_KEYS` 结果/泛化词停用表;`_SYN_GROUPS`(24 组)同义词扩展匹配;`match()` 仅用**确定性关键词+同义词**匹配。**已停用 LLM 语义匹配**(它会把同题号但机制不相干的卡乱配,损"有据可查")。
- `cases.py` — 专家协同案例库(文件级 `cases/<案例码>.json` + 政策原文 `cases/<案例码>.<ext>`);`consensus_view` 逐题算共识/分歧;`doc_path` 取原文供专家下载。
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
- **已上线**:阿里云 ECS(华东2·上海,2核2G,Alibaba Cloud Linux 3,Python 3.11)。systemd 服务名 **`hia`**,部署目录 `/opt/hia-screening`(内有 `.venv`),监听 **8502**,环境变量在 **`/etc/hia-screening.env`**(含 DEEPSEEK_API_KEY / APP_PASSWORD / STORAGE_SECRET / PORT,**不入库**)。内存占用 ~55M,配置充裕。
- **更新部署**(服务器上):`cd /opt/hia-screening && git pull && .venv/bin/pip install -r requirements.txt && systemctl restart hia`
- 公网访问目前走 `IP:8502`(IP 与口令见本地/控制台记录,不写入本公开仓库)。安全组已放行 8502。

## 待办 / 进行中
1. **域名 + HTTPS**:已注册 `tjhealthycitylab.com`(个人实名),拟用子域名 **`hia.tjhealthycitylab.com`**。大陆服务器**必须先 ICP 备案**(3–20 天)。备案通过后按 `docs/DEPLOY_HTTPS.md` 配 DNS + Nginx + HTTPS。
2. **知识库扩充**(进行中):用户在 `std.samr.gov.cn` 按 `docs/gb_standards_shoplist.md` / `standards_master_list.md` 取证;拿到**现行编号+URL** 后,加进 `hia_evidence.py` 的 `CARDS` + 配 `_SYN_GROUPS` 同义词 + 跑 `eval` 验证(待补率下降、无错配)。
3. **安全收尾**:DeepSeek key 在协作过程中明文出现过,**需轮换**(改 `/etc/hia-screening.env` 后 `systemctl restart hia`);安全组从 `0.0.0.0/0` 收紧到委内 IP 段。
4. **可选功能**:项目台账状态流转、角色/权限、监管看板(跨案例统计)、站内推送通知。

## 跨机器工作流
- **开工** `git pull`;**收工** `git add -A && git commit -m "..." && git push`。
- 远程:`origin = github.com/swyhns-ship-it/hia-screening`(公开)。
- **密钥不入库**:本地 `.streamlit/secrets.toml`、服务器 `/etc/hia-screening.env`(均 gitignore / 仅本机各配一次)。换机器后这俩要重配。
- 运行时数据 `cases/`、`feedback/`、`eval/out*/` 已 gitignore(不随仓库同步;服务器上单独备份)。
- 新机器:`git clone` → 建 venv 装 `requirements.txt` → 配 secrets → `python app_nicegui.py`。
