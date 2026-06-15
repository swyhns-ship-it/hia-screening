# 健康影响初筛工具 — 前端样式改版规范

> 给 Claude Code 的实施说明。目标是在不改动现有功能逻辑的前提下，
> 收敛配色语义、建立状态徽章层级、强化因果路径链的可读性。
> 改动以 CSS / 组件结构为主，不涉及数据流。

---

## 交给 Claude Code 的指令（直接复制下面这段）

```
我要对健康影响初筛工具做一次纯视觉改版，规范见本文档（HIA_前端样式规范.md）。
请严格按以下步骤执行，不要改动任何功能逻辑、数据流或后端：

1. 先通读这份规范，然后在代码库里定位这三个核心组件分别在哪些文件：
   (a) 顶部 10 个方面的导航标签
   (b) 每张卡片顶部的状态徽章（证据等级 / 影响方向 / 证据状态）
   (c) 因果路径链（政策原文 → 中间环节 → 健康结果）
   定位完成后先告诉我结果，等我确认，再开始改。

2. 按规范第 1 节先把 CSS 变量 token 加进全局样式，作为后续所有改动的基础。

3. 然后一次只改一个组件，顺序为：导航标签 → 状态徽章 → 因果路径链。
   每改完一个就停下来，告诉我改了哪些文件、对照规范的哪几条，让我先看效果再继续。

4. 最后按第 8 节的验收清单逐项自查，列出每一项的达成情况。

约束：颜色语义全程遵守"红=害、绿=益、蓝=政策来源、橙=证据等级、灰=中性"；
字重只用 400 / 500；不要为了改样式而动到判定逻辑或文案内容。
```

---

## 0. 核心原则

整套界面的颜色只承担四种语义，不要超出这个范围：

| 语义 | 颜色族 | 用途 |
|------|--------|------|
| 害 / 警示 | 红 | 负面健康影响、"需要关注"状态 |
| 益 | 绿 | 正面健康影响（效益）、最终健康结果 |
| 政策来源 | 蓝 | 政策原文引用框 |
| 中性 / 结构 | 灰 | 中间路径环节、未选中标签、"暂未发现" |

橙色**只**留给"证据等级"这一种程度量，不要用于其他任何地方。
红色要严格保留警示含义——一旦整排都是红框，红色就失去了作用。

---

## 1. 设计 Token

```css
:root {
  /* 语义色 — 害 / 警示（红） */
  --hia-danger-50:  #FCEBEB;
  --hia-danger-200: #F09595;
  --hia-danger-400: #E24B4A;
  --hia-danger-600: #A32D2D;
  --hia-danger-800: #791F1F;

  /* 语义色 — 益（绿） */
  --hia-benefit-50:  #EAF3DE;
  --hia-benefit-100: #C0DD97;
  --hia-benefit-400: #639922;
  --hia-benefit-600: #3B6D11;
  --hia-benefit-800: #27500A;
  --hia-benefit-900: #173404;

  /* 语义色 — 政策来源（蓝） */
  --hia-source-50:  #E6F1FB;
  --hia-source-600: #185FA5;
  --hia-source-800: #0C447C;

  /* 程度量 — 证据等级（橙） */
  --hia-grade-50:  #FAEEDA;
  --hia-grade-600: #BA7517;
  --hia-grade-800: #854F0B;

  /* 中性 / 结构（灰） */
  --hia-neutral-50:  #F1EFE8;
  --hia-neutral-200: #B4B2A9;
  --hia-neutral-500: #5F5E5A;
  --hia-neutral-700: #444441;

  /* 表面 */
  --hia-surface:        #FFFFFF;
  --hia-surface-muted:  #F7F6F2;
  --hia-border:         rgba(0,0,0,0.12);
  --hia-border-strong:  rgba(0,0,0,0.20);

  /* 圆角 */
  --hia-radius-md: 8px;
  --hia-radius-lg: 12px;
}
```

字号统一为：标签 13px，徽章 12–13px，正文 14px，路径节点 12px。
字重只用两档：常规 400、强调 500。不要用 700。

---

## 2. 导航标签（10 个方面）

### 现状问题
十个标签整排红/绿描边，选中项也是红色描边，跟未选中的差别只靠底色深浅，
扫读时无法快速分辨"哪个在看、哪些需关注、哪些没事"。

### 改后规则
- **选中态**：填实底色（需关注=红底 `--hia-danger-600`，暂未发现=绿底 `--hia-benefit-600`），白色文字，无描边。
- **未选中态**：细灰边框 `0.5px solid --hia-border`，文字用 `--hia-neutral-500`，
  左侧加一个 7px 状态圆点表示该方面的判定结果：
  - 红点 `--hia-danger-400` = 需要关注
  - 灰点 `--hia-neutral-200` = 暂未发现
  - 橙点 `--hia-grade-600` = 尚不确定
- 标题与"X 条 / 状态"副标题用两档颜色拉开层次。

```html
<!-- 选中态 -->
<button class="hia-tab hia-tab--active hia-tab--danger">
  <span class="hia-tab__title">2 重点慢病</span>
  <span class="hia-tab__sub">12 条 · 需要关注</span>
</button>

<!-- 未选中态 -->
<button class="hia-tab">
  <span class="hia-tab__dot hia-tab__dot--danger"></span>
  <span class="hia-tab__title">1 传染病</span>
</button>
```

```css
.hia-tab {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  border: 0.5px solid var(--hia-border);
  border-radius: var(--hia-radius-md);
  background: var(--hia-surface);
  color: var(--hia-neutral-500);
  font-size: 13px; cursor: pointer;
}
.hia-tab__dot {
  width: 7px; height: 7px; border-radius: 50%; flex: none;
}
.hia-tab__dot--danger  { background: var(--hia-danger-400); }
.hia-tab__dot--none    { background: var(--hia-neutral-200); }
.hia-tab__dot--unsure  { background: var(--hia-grade-600); }

.hia-tab--active { border: none; flex-direction: column; gap: 2px; }
.hia-tab--active.hia-tab--danger  { background: var(--hia-danger-600); }
.hia-tab--active.hia-tab--benefit { background: var(--hia-benefit-600); }
.hia-tab--active .hia-tab__title { color: #fff; font-weight: 500; }
.hia-tab--active .hia-tab__sub   { color: var(--hia-danger-200); font-size: 11px; }
```

---

## 3. 卡片状态徽章

### 现状问题
每张卡片顶部三个标签（机制证据等级 / 影响方向 / 证据状态）橙框、绿点、橙三角
混在一起，视觉权重相近，用户无法一眼抓到最关键的"影响方向"。

### 改后规则 — 建立明确的三级视觉层级

1. **影响方向（最显眼）**：色块 + 箭头图标 + 13px/500。
   - 益：绿底 `--hia-benefit-50`，文字 `--hia-benefit-800`，图标向上箭头。
   - 害：红底 `--hia-danger-50`，文字 `--hia-danger-800`，图标向下箭头。
2. **证据等级（次之）**：小橙色块 + 12px，文字"证据等级 强/中/弱"。
3. **证据状态（最弱）**：退为灰色次要文字 + info 图标，不加边框不加底色。

```html
<div class="hia-badges">
  <span class="hia-badge hia-badge--benefit">
    <i class="ti ti-arrow-up-right"></i>正面健康影响 · 效益
  </span>
  <span class="hia-badge hia-badge--grade">证据等级 中</span>
  <span class="hia-badge hia-badge--note">
    <i class="ti ti-info-circle"></i>结局端证据待补
  </span>
</div>
```

```css
.hia-badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.hia-badge {
  display: inline-flex; align-items: center; gap: 6px;
  border-radius: 6px; font-size: 12px;
}
.hia-badge--benefit {
  padding: 4px 12px; font-size: 13px; font-weight: 500;
  background: var(--hia-benefit-50); color: var(--hia-benefit-800);
}
.hia-badge--danger {
  padding: 4px 12px; font-size: 13px; font-weight: 500;
  background: var(--hia-danger-50); color: var(--hia-danger-800);
}
.hia-badge--grade {
  padding: 4px 10px;
  background: var(--hia-grade-50); color: var(--hia-grade-800);
}
.hia-badge--note {
  color: var(--hia-neutral-500); /* 无底色、无边框，退为次要 */
}
```

---

## 4. 因果路径链

### 现状问题
"政策原文 → 影响路径 → 健康结果"这条链是工具核心，但箭头和文字框样式偏弱，
最终的健康结果跟中间环节看起来差不多，结论不突出。

### 改后规则
- 整条链放进一个浅灰底容器 `--hia-surface-muted`，跟正文区分开。
- 三段用颜色编码层次：
  - **政策原文框**：蓝底 `--hia-source-50`，文字 `--hia-source-800`。
  - **中间路径环节**：白底 + 细灰边框，文字 `--hia-neutral-500`（保持低调）。
  - **最终健康结果框**：实色块（益=绿 `--hia-benefit-100`/文字 `--hia-benefit-900`，
    害=红），13px/500，带方向箭头收尾，让结论自然落在链尾。
- 箭头用 `ti-arrow-right`，灰色；指向最终结果的那个箭头染成对应语义色。

```html
<div class="hia-path">
  <span class="hia-path__node hia-path__node--source">政策原文：推进养老托育供需匹配…</span>
  <i class="ti ti-arrow-right hia-path__arrow"></i>
  <span class="hia-path__node">康复辅具可及性</span>
  <i class="ti ti-arrow-right hia-path__arrow"></i>
  <span class="hia-path__node">改善功能状态</span>
  <i class="ti ti-arrow-right hia-path__arrow hia-path__arrow--benefit"></i>
  <span class="hia-path__result hia-path__result--benefit">
    <i class="ti ti-arrow-down"></i>降低慢性病致残率
  </span>
</div>
```

```css
.hia-path {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  background: var(--hia-surface-muted);
  padding: 14px; border-radius: var(--hia-radius-lg);
}
.hia-path__node {
  padding: 8px 12px; border-radius: var(--hia-radius-md);
  font-size: 12px;
  background: var(--hia-surface);
  border: 0.5px solid var(--hia-border);
  color: var(--hia-neutral-500);
}
.hia-path__node--source {
  background: var(--hia-source-50);
  border: none; color: var(--hia-source-800);
  max-width: 150px;
}
.hia-path__arrow { color: var(--hia-neutral-200); }
.hia-path__arrow--benefit { color: var(--hia-benefit-600); }
.hia-path__arrow--danger  { color: var(--hia-danger-400); }

.hia-path__result {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 14px; border-radius: var(--hia-radius-md);
  font-size: 13px; font-weight: 500;
}
.hia-path__result--benefit { background: var(--hia-benefit-100); color: var(--hia-benefit-900); }
.hia-path__result--danger  { background: var(--hia-danger-200);  color: var(--hia-danger-800); }
```

---

## 5. 间距与卡片密度

- 卡片内部：顶部徽章行与正文之间至少 `12px` 垂直间距；路径链各段之间 `8px`。
- 卡片之间：`16px` 外边距。
- 卡片内边距：`16px 20px`（上下 16，左右 20）。
- 顶部"健康影响一览"的三张统计卡（需要关注 / 尚不确定 / 暂未发现）
  保留现有大数字样式即可，但数字颜色对应语义色（红 / 橙 / 绿）。

---

## 6. 底部悬浮说明条

现状：绿色悬浮条持续遮挡内容，移动端尤其明显。

改后二选一：
- **方案 A（推荐）**：改为可收起。默认收起为一个小标签，点击展开完整说明。
- **方案 B**：仅首次进入页面时展示，之后用 `localStorage` 记住已读状态隐藏。
  （注意：若在 Claude.ai Artifact 环境内预览，`localStorage` 不可用，需在真实环境部署；
   这一点只影响预览，不影响线上。）

---

## 7. 顶部导航栏

"返回首页 / 新建评估 / 项目管理 / 案例参考"四项统一字号（14px）和间距，
排成一个完整导航栏。"新建评估"的 NEW 标记保留，但缩小为小角标，不要喧宾夺主。

---

## 8. 验收清单

- [ ] 红色只出现在"害 / 警示"语境，导航整排不再全红。
- [ ] 每张卡片一眼能先看到"影响方向"，再看到证据等级，最后才是证据状态。
- [ ] 因果路径链的最终结果框明显比中间环节突出。
- [ ] 颜色语义全程一致：红=害、绿=益、蓝=政策来源、橙=证据等级、灰=中性。
- [ ] 字重只用 400 / 500 两档。
- [ ] 深色背景下文字仍可读（若工具支持暗色模式）。
- [ ] 移动端底部说明条不再持续遮挡内容。
