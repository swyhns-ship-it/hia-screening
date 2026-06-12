# 健康影响评估智能初筛系统

面向卫健委的 **AI 辅助 HIA(健康影响评估)定性初筛** 工具。上传政策 / 规划 / 工程项目文档,
AI 分三步展开「**政策行动 → 健康决定因素(多级、间接)→ 健康结果**」因果路径网,生成可编辑的
路径图与依据;再由系统按确定性规则聚合到《健康影响评估初筛表》10 题,供专家逐条复核改判,
最终导出填好的初筛表 Word 文档。

> **AI 仅辅助研判**,因果路径的采纳 / 剪枝、10 题判定与签字结论以专家核定为准。

本工具由「健康城市智能规划与评估平台」的同名模块剥离、精简而成,**仅含初筛一个功能**,
不含任何机器学习模型或地理数据,依赖极轻。

## 功能流程

1. 上传评估对象文档(PDF / Word .docx)+ 填初筛表表头信息。
2. 点「AI 展开因果路径并生成草案」→ 三段 DeepSeek 流水线:
   - ① 行动抽取:文档 → 政策行动 / 要素;
   - ② 多视角路径展开:沿健康决定因素(环境 / 社会心理 / 公平 / 卫生系统)逐层、间接展开;
   - ③ 完整性批判:补漏的决定因素 / 脆弱群体 / 间接效应 + 整体小结 + 程度建议。
3. 复核可编辑的**因果路径图**(采纳 / 剪枝 / 专家补充路径)。
4. 系统按确定性规则聚合到 **10 题判定**(强/中且非假设→是;仅推测→不知道;无路径→否),专家可逐题改判。
5. 给结论(健康影响程度)与专家意见 → **导出《健康影响评估初筛表》docx**。

## 运行

```powershell
# 1. 安装依赖(建议新建干净的 Python 3.11 venv)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 配置密钥(见下)
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # 然后填真实值

# 3. 启动
.\run.ps1          # 或:streamlit run app.py
```

## 密钥配置(`.streamlit/secrets.toml`,已 gitignore,不入库)

| 键 | 必填 | 用途 |
|---|---|---|
| `deepseek_api_key` | 是 | AI 展开因果路径(DeepSeek,OpenAI 兼容接口)。也可在页面密码框临时输入(仅当次会话)。 |
| `app_password` | 否 | 访问口令门;配置后访客需输入口令,留空 / 不配则不拦(本地开发方便)。 |

云端部署(Streamlit Community Cloud):main 文件填 `app.py`,Python 选 3.11,
在 App → Settings → Secrets 填入同样内容。

## 文件结构

| 文件 | 角色 |
|---|---|
| `app.py` | 单页入口:set_page_config + 主题 + banner + 口令门 + 渲染初筛页 |
| `theme.py` | 健康绿主题色 + 全局 CSS + 品牌条 + 统一页头(中性政务风) |
| `auth.py` | 访问口令门(`require_login`)+ 会话级 API 限流(`rate_limit`) |
| `hia_screen.py` | 引擎:3 段 DeepSeek 流水线 + 确定性聚合 + 因果路径 DOT 图 + 初筛表 docx |
| `hia_evidence.py` | WHO 官方证据卡片库(56 张,带真实 URL) |
| `views/screen.py` | 页面 UI(`page_hia_screen`) |

## 说明

- 旧版 `.doc` 不支持,请另存为 `.docx` 或 PDF;扫描件 / 图片型 PDF 需 OCR,本工具暂不支持。
- 长文档(>4 万字)会截断前 4 万字。
- 证据卡片中标「待补强」的来源,表示 WHO 官网暂无独立旗舰文档,待系统综述 / meta 补。
