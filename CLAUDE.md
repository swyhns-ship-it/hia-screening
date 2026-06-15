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
- `hia_screen.py` — 引擎:3 段 DeepSeek 流水线(行动抽取→多视角路径展开→完整性批判)+ 确定性聚合到 10 题 + 初筛表 docx。坑:DeepSeek json_object 偶发吐空白,需"加扰动重试"(`_chat_json` 已处理)。提示词已:去重复/去政策元评论/严标强度。`_norm_pathways` 归一化 chain:字符串别按"字"拆、元素内 `→` 拆成独立节点、**节点去重**(LLM 偶让链条绕回先前节点)。
- `hia_evidence.py` — 证据库(**两轨·89 张卡**)。`card_kind`:**因果**(WHO/文献,锁题号·支撑「→健康结果」)/ **基准**(国标 GB/GBZ/GB·按来源等级自动判,跨题号·按暴露/环节命中,作限值与管控基准)。`match()` 双轨各最多 2 张,输出带 `kind`;`source_tier` 来源分级(认 GB/GBZ/GB/T→「国家标准」);`_STOP_KEYS` 停用表;`_SYN_GROUPS`(24 组)同义词扩展。**仅确定性关键词+同义词匹配,已停用 LLM 语义匹配**(会乱配,损"有据可查")。国标卡 31 张(空气/噪声/排放/固废危废/食品/职业/电磁/适老/交通…),来源只写「标准名 标准号. 发布机构.」**不附 URL**,note 写 PDF/官方**核实**的关键限值(如 GB3095-2026 PM2.5 年均 25/日均 50 μg/m³)。
- `cases.py` — 案例/项目库(文件级 `cases/<案例码>.json` + 政策原文 `cases/<案例码>.<ext>`),单人与协同共用。字段含 `source`(单人初筛/专家协同)、`status`(评审中/已定稿/已归档/作废)、`reference`(参考案例)、`adopted_ids`(单人当时采纳的影响路径)。`consensus_view` 逐题算共识/分歧;`doc_path` 取原文;`save_single_case` 单人一键落库(直接已定稿,判定存 `consensus`);`set_status`/`set_reference`/`delete_case`/`adopted_pathways`/`list_reference` 供项目管理与案例参考用。`app_nicegui._case_export_payload`+`adopted_pathways` 统一供台账/案例参考重新导出 docx。
- `feedback.py` — 专家反馈留痕(`feedback/feedback_log.jsonl`)+ `summarize`;`eval/feedback_report.py` 出回流报告。
- `theme.py` 主题/品牌;`views/screen.py`、`app.py`、`auth.py` 是**旧 Streamlit 版**(保留,部署不用)。
- `eval/` 批测:`run_eval.py`(支持目录参数)、`make_*_policies.py`(合成/真实测试政策)、`REVIEW_GUIDE.md`。
- `docs/` 取证与部署:`standards_master_list.md`(国标主清单)、`gb_standards_shoplist.md`、`kb_expansion_worklist.md`、`DEPLOY.md`、`DEPLOY_HTTPS.md`。

## 本会话新增(2026-06-14 第二段:UI 大改 + 两轨证据库 + 国标库)
- **健康影响初筛 UI(`/screen`)重做**:10 题从纵向下拉改为**横向选项卡 + 单维度面板**(吸顶、彩色=判断、上一/下一)、顶部步骤条、上传区分析后自动收起、红绿灯汇总。每条影响渲成**路径节点流**(📄政策原文引文 → 环节 → 健康结果,末端按方向红/绿),整条 hover 高亮;`_path_flow_html`/`_ARROW_RE` 拆箭头+去重。
- **角色感**:发起方(卫健委)= `/new`「发起专家组协同评估」、`/panel` 经办台;受邀专家 `/review` 无平台导航 + 「您的任务三步」+ 经办台「📋 复制完整邀请」(JS 取 `window.location.origin`)。
- **评估地图(按钮「健康影响评估因果机制路径」)**:几经折腾(mermaid 连线树→分列 subgraph→pan/zoom 全失败/布局不可控)→ 最终落到**确定性方案**:弹窗里**按 HIA 维度分组、每行一条横向路径流**(纯 HTML,稳定不崩),点维度标题跳选项卡。**结论:mermaid 自动排版对不同政策时好时崩、pan/zoom(svg-pan-zoom/自写)都不稳,已弃用**(`build_mermaid` 留作死代码)。
- **两轨证据库**:见上 `hia_evidence.py`。显示端 `render_evidence` 分两块——📚 健康因果依据(WHO)/ 📐 相关国家标准(暴露限值·**非因果证据**);`prov_of` 健康端徽标**只看因果轨**。
- **国标库批量入库(已基本建完)**:本地 58 份 GB/HJ PDF(`E:/projects/26.06.13国家标准清单`,未入库)→ pypdf 抽到 `.std_text/`(gitignored)→ 三态(36 可读/10 CID 乱码/13 扫描)。可读的逐份读正文抽限值建卡;乱码/扫描的**联网核实**现行版限值(如 GBT18883 甲醛≤0.08、GB15618 农用地镉 0.3–0.8/铅 80–240 mg/kg、GB50325 装修污染等)。**共 48 张基准卡(总卡 106)**,覆盖空气/室内空气/水/土壤/排放/固废危废/噪声/振动/食品/职业/公共场所/适老/住房/消防/电磁/交通/辐射。`docs/gb_kb_worklist.md`/`gb_extract_digest.md` 跟踪。未做:HJ 环评导则(是方法非限值,不做基准卡)、极 niche 项。键收紧记录:电动车卡去 "火灾"、危废填埋卡去 "重金属"(防误配)。

## 引擎假阳性修复(2026-06-14,36 份真实政策批测后)
- **测试发现**:对**表彰/任免/防空警报试鸣/财税/行政程序**等无健康关联政策,旧引擎硬造 8–25 条路径(假阳性)。烟枪:行动抽取提示词里的示例「新建某设施/新增某类交通…」被 LLM 在无内容时**照抄成措施**,再据此造路径,还因含 PM2.5/噪声等词被挂上"有据"。
- **三道防线修复**(`hia_screen.py`):① 抽取提示词**删示例**+让模型显式输出 `health_relevant`,非健康(false)→ analyze **门控返回 0 路径**;② 展开提示词加**逐行动健康关联门控**(非健康行动→0 条)+ 总数≤12、批判阶段默认不补;③ **安全网**:模型把"绿色低碳/生态/能源"误判 false 时,标题(文件名)含强关键词则纠回 true;健康相关但未枚举出行动→用「政策主题」(去「关于印发…的通知」壳、取《》标题)兜底 + 展开时提示"据文档充分展开不要返空"。
- **重测效果**:防空警报/表彰/税务/程序类 20+ 条 → **绝大多数归 0**;绿色低碳/气象/节能/健康上海等正样本路径完整保留(09 从误判 0 恢复 10 条)。残留少数治理/经济类(慈善奖/监管/计量/知产)仍出 5–10 条推测路径但**待补占比 60–100%**(已如实标注、易剔除)。`eval/run_eval.py <目录>` 批测,out/ 已 gitignore。

## 关键决策 / 铁律
- **证据可靠:精准 > 召回**;匹配不到宁标「证据待补」也不贴错卡(贴错比没有更糟)。
- **假阳性 > 漏报更糟**:无健康关联的政策(表彰/任免/纪念/财税/程序)应判「关联很弱、0 路径」,绝不硬造;health_relevant 门控 + 逐行动门控 + 标题安全网三道防线。
- **两轨**:WHO/文献=因果(锁题号·健康端);国标=基准(跨题号·暴露端·带核实限值),**不让国标冒充因果**。
- **绝不臆造来源**(URL/标准号/原文摘录/限值数字)——加卡前必须联网或从 PDF **核实现行版**(踩过 GB 3095-2012 已废、换 2026 版的坑);国标卡只写「标准号+发布机构」不附 URL。
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

## 本会话新增(2026-06-15,前端样式改版 · 纯视觉)
按规范 `docs/HIA_前端样式规范.md`(随仓库,新拷入)对 `/screen` 等页做纯视觉改版,**未动任何判定逻辑/数据流/引擎/文案内容**。全部改动只在 `app_nicegui.py`。
- **设计 Token(规范 §1)**:新增 `_TOKENS_CSS`(`:root` 五语义色族:害=红/益=绿/政策来源=蓝/证据等级=橙/中性=灰 + 表面/边框/圆角)。在两个 CSS 入口注入:`screen()` 内联 `<style>` 与共享 `_page_head()`。后续所有组件改用 `var(--hia-*)`。**色彩铁律:红只给"害/警示",橙只给"证据等级"这一程度量,字重只用 400/500**。
- **导航标签(§2)** `tabstrip()`:选中=填实底色(需关注红/尚不确定橙/暂未发现绿)+白字无描边;未选中=0.5px 灰边 + 7px 状态圆点(红/橙/灰)。新增 `TAB_DOT/TAB_ACTIVE_BG/TAB_ACTIVE_SUB`。
- **状态徽章(§3)**:新增 `dir_badge/grade_badge/status_badge/badge_row`,三级层级 **影响方向(色块+↑↓/13px·500)→ 证据等级(橙块/12px)→ 证据状态(灰字+ⓘ,无底无边)**。接入 `pathway_row` 与只读 `render_pathway_ro`。**证据等级徽章用简写「证据等级 强/中/弱」**(`GRADE_SHORT`,推测→弱);「依据/详情」折叠内仍保留完整自解释文案(机制证据较充分/中等/推测)。原"强=红"已去。
- **因果路径链(§4)**:重写 `_FLOW_CSS`(浅灰容器 `--hia-surface-muted` + 三段编码:政策原文=蓝 `.origin`/中间环节=白底细灰中性字/末端=实色块 益绿 benefit-100·害红 danger-200,13px·500);`_path_flow_html` 末端结果带 ↑↓ 收尾,**指向结果的箭头染语义色**(`.hia-arrow--benefit/--risk`)。`screen()` 头部改用同一 `_FLOW_CSS`(单一来源)。政策原文框 `max-width` 取 **340px**(规范建议 150px 太窄、会截断引文,故放宽)。
- **底部入口(§6·方案A)**:原全宽绿条(持续遮挡、移动端尤甚)`ui.page_sticky` → 收为**右下角紧凑胶囊**「因果机制路径图」,点击照常开弹窗;底部留白 96px→40px。
- **顶部导航(§7)** `_top_nav`:四项统一 **14px** + 间距,字重 400/500;🆕 emoji → **9px 小 `NEW` 角标**(`_NEW_BADGE`,绿底上标);`_NAV_ITEMS` 增 `is_new` 字段,改用 `with ui.link(target=…): ui.html(…)` 以嵌入角标。
- **验收(§8)**:除"暗色模式"(工具强制浅色,N/A)外全部达标。预览:`docs/HIA_前端样式规范.md` 旁无;曾在本机 `Downloads/hia_style_preview.html` 做静态预览(**不在仓库**,可删)。
- ⚠ **改 NiceGUI 内联样式后**:`/screen` 的徽章/路径只有"上传文档→AI 分析"出路径后才出现,纯静态看不到;本机校验用 `import` + 直接调 `badge_row/_path_flow_html/grade_badge` 看 HTML 串(已过)。

## 本会话新增(2026-06-15 第二段,依据区改版 + 收尾微调 + 少量逻辑)
延续样式改版,做依据区结构化(纯视觉)+ 几处带逻辑的收尾。改动在 `app_nicegui.py`(主)与 `hia_screen.py`。
- **依据区三类小标题锚点**(`_ev_header`):📄 文件原文依据(蓝=政策来源)/ 📚 健康因果依据(绿·带「核心」标·字号最大)/ 📐 相关国家标准(灰=中性基准)。三色互不撞且守色彩铁律(红只给害、橙只给证据等级,故国标用**灰**不用橙)。每块标题下带一行小字说明。
- **来源条目结构化**(重写 `_render_source_card`):每条来源 = 一张缩进白底小卡;加粗标题(`_split_source` 把「标准名 标准号. 机构. URL」拆成标题 + URL);裸 URL 收成可点的「查看原文 ↗」(蓝、新窗口);要点小字。无 URL 的国标卡只显标题+机构。
- **「已核实」标记统一**(`_verified_chip`):弃旧 `soft_chip`(描边胶囊),改成与卡顶徽章同一视觉语言(实底软块·圆角6·12px·400)。已核实=绿(benefit-50/800),待补强=橙(grade-50/800)。
- **国标限值出小表**(`_limit_table_html` + `_LIMIT_ITEM_RE`/`_UNIT_RE`):密集数值(PM2.5/PM10/NO₂/SO₂ 年/日均)解析成「污染物/年均/日均」三列小表;**单位(µg/m³ 等)从 note 原文自动识别**填进表头,识别不出则不标(守不臆造);解析不到 ≥2 条自动退回纯文字。
- **专家反馈入口更显眼**:`pathway_row` 里灰扑扑的「🚩 专家反馈:」label 升级为**红旗色条标题 + 引导小字**;下拉/输入控件本身与第5步「💾 保存专家反馈」按钮**未动**(刻意保持紧凑,不压过主操作)。
- **收尾微调(部分带逻辑)**:① 导航标签未选中态收为单行【圆点+编号标题】、副信息移 hover,选中/未选中**高度对齐**(`tabstrip` row `align-items:stretch`);② 统计大数用语义色(`STAT_COLOR`);③ 路径链中间节点去边、末端**去 ↑↓ 箭头**(与"降低/增加"动词打架)、首环节与原文近一字不差时**去重**(`_norm_cmp`+difflib);④ 第4步总体影响程度**不预选最高档**(改无预选 `value=None` + AI 初判提示 + 导出/落库前校验必选);⑤ 第4步评估对象名称**自动填充政策标题**(`do_analyze` 调 `hs.guess_title`);⑥ 第5步反馈说明提炼重点句加粗。
- **引擎(`hia_screen.py`)**:新增 `guess_title(doc_text, fallback)` 从「印发《…》」抽政策名(PDF 把《》抽成 «»,正则兼容 `[《«〈]…[》»〉]`);`_SYS_EXPAND` 加提示——链条首节点用**提炼短行动**而非逐字照抄原文(原文进 evidence 字段)。
- **本机冒烟测试** `.smoketest.py`(已 gitignore):**monkeypatch `nicegui.ui.run` 为空操作**后再 `import app_nicegui`,即可不绑 8502 直接调用已上线助手(无重复逻辑);跑引擎→真实卡片→过 `_render_source_card/_limit_table_html` 等,输出静态预览 `Downloads/hia_evidence_preview.html`。节能减排样例:10 行动/10 路径、是2否8、9 张国标卡渲出限值表(含单位)。
- ⚠ **`ui.run(reload=False)` 无热重载**:改任何代码后必须杀 8502 进程 + 重启才生效(重启清会话,需重传 PDF)。

## 本会话新增(2026-06-15 第三段:批量体检 + 溯源高亮 + 证据库自助管理)
三个新功能,均在 `app_nicegui.py`(引擎/数据接口在 `hia_evidence.py`),复用既有 `hs.extract_text/analyze/compute_items` 管线与色彩 token,未动判定逻辑。
- **批量政策体检 / 监管看板** `/batch`(首页第 2 卡 + 顶部导航「🩺 批量体检」,`require_app_login`):多份上传 → 逐份跑 `analyze`(进度条、单份失败不中断)→ 看板=① 指标卡 ② **政策×10 健康维度热力图**(复用台账色带:红需关注/黄不确定/绿暂无)③ **监管视角**各维度被触及占比条。每份可「存入项目管理」(`save_single_case` 后 `set_status` 改**评审中**,不直接定稿,opinion 标"AI 自动初筛待核定")。数据源=**本批上传**(看板汇总未并入台账,留作后续扩展)。`ui.upload(multiple=True)`。
- **政策原文溯源高亮**(强化"有据可查/可审计"):每条影响「依据/详情」里加「🔎 在原文中定位这段依据」→ 弹窗显示政策原文全文、把该条逐字摘录**蓝高亮**(政策来源色)并自动滚动到位。`_locate_quote`(`_collapse_for_match` 去空白+`«»→《》`+**NFKC 全角→半角**;精确 find → 近似:最长公共片段为锚点按引文长度框出,标「近似·请核对」;定位不到→不臆造高亮、提示人工核对)。`/screen` 存 `st["text"]`;`render_pathway_ro(p, actions, doc_text)` 加 `doc_text` 参;`/review`、`/reference` 用 `_case_doc_text(case)`(从随附原文重抽)。`_path_flow_html` 抽出 `_origin_quote(p, actions)` 共用。
- **证据库自助管理** `/evidence`(首页页脚「📖 证据库管理」入口,`require_app_login`):非程序员也能增/改/删证据卡。`hia_evidence.py` 加**运行时覆盖层**:内置卡 = 源码 `_BUILTIN_CARDS`(只读基线);用户卡存 `evidence_user.json`、`load_user_cards()` 启动并入 `CARDS`(`CARDS[:]=builtin+user` 原地替换保引用)、即时参与 `match()`;`add/update/delete/list_user_cards`。页面:大白话引导(术语改「权威研究证据/国家标准限值」、题号→健康方面)、每字段带示例、「填入示例」一键样例、效果预览("保存后 AI 遇到含『…』时会把这张卡作为〔X〕依据列出")、内置库查重检索、导出 JSON。`kind/tier` 仍由 `card_kind/card_tier` 自动判定(含 GB→基准)。
- **坑/约定**:`evidence_user.json` 已 **gitignore**(防 server 端 `git pull` 冲突;用界面「导出」备份或合并回 `hia_evidence.py`);`_SYN_GROUPS` 同义词仍在代码里(卡片 keys 可直接多写同义词,够用)。`.claude/launch.json`(预览用,gitignore)。验证:浏览器实测三页 + 引擎单测(溯源精确/近似/全角/定位不到;覆盖层增改删/合并/匹配)。

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
