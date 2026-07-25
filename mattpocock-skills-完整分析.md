# Matt Pocock Skills 仓库完整分析

> 仓库地址: https://github.com/mattpocock/skills
> 版本: v1.1.0
> 协议: MIT
> 作者: Matt Pocock (Total TypeScript 创始人)

---

## 一、项目概览

这是一个由 TypeScript 社区知名人物 Matt Pocock 创建的 **AI 编程助手技能集**（Agent Skills），专为"真正的工程工作"而设计，明确反对"氛围编程"（vibe coding）。

核心理念：软件工程的基本原则比以往任何时候都重要。这些技能将几十年的工程经验凝练成可复用的实践，解决 AI 编程助手的四大常见失败模式。

当前约 6 万开发者订阅了相关 newsletter。

### 四大问题与对策

**问题 1：Agent 不理解你的意图**

> "No-one knows exactly what they want" -- David Thomas & Andrew Hunt, The Pragmatic Programmer

软件开发中最常见的失败模式是错位——你以为开发者懂你的需求，看到成果后才发现他完全没理解。AI 时代同样如此。

对策：`/grill-me` 和 `/grill-with-docs`——在动手之前通过 relentless（无情的、持续的）追问强制对齐理解。这是他最受欢迎的技能。

**问题 2：Agent 过于啰嗦**

> "With a ubiquitous language, conversations among developers and expressions of the code are all derived from the same domain model." -- Eric Evans, Domain-Driven Design

项目初期，开发者和领域专家通常说不同的语言。Agent 被扔进项目后被迫自行摸索术语，导致用 20 个词说 1 个概念。

对策：**共享语言（Ubiquitous Language）**。通过 `CONTEXT.md` 建立项目术语表，让 Agent 用精确定义的术语思考。示例——"There's a problem with the materialization cascade" 比 "There's a problem when a lesson inside a section of a course is made 'real'" 简洁得多。

连锁收益：
- 变量、函数和文件命名一致，使用共享语言
- 代码库更容易被 Agent 导航
- Agent 消耗更少 token 在思考上

**问题 3：代码不能正常工作**

> "Always take small, deliberate steps. The rate of feedback is your speed limit." -- The Pragmatic Programmer

即使你和 Agent 目标一致，代码仍然可能很糟糕。问题在于缺少反馈循环。

对策：静态类型 + 浏览器访问 + 自动化测试。核心技能是 `/tdd`（红-绿-重构循环）和 `/diagnosing-bugs`（结构化排错流程）。红-绿-重构循环给 Agent 持续的反馈，产出更好的代码。

**问题 4：系统膨胀成泥球（Ball of Mud）**

> "Invest in the design of the system every day." -- Kent Beck, Extreme Programming Explained

因为 Agent 加速了编码，也加速了软件熵增。代码库以前所未有的速度变复杂。

对策：全新方式的 AI 驱动开发——**关心代码的设计**。核心技能：`/to-spec`（生成规格前询问涉及哪些模块）、`/improve-codebase-architecture`（每几天跑一次）、`/codebase-design`（深度模块设计词汇表）。

---

## 二、仓库目录结构

```
skills/
  engineering/     # 日常编码工作技能（主打，17 个）
  productivity/    # 通用工作流工具（主打，5 个）
  misc/            # 较少使用，不推广（4 个）
  personal/        # Matt 个人专用，不推广（2 个）
  in-progress/     # 开发中的草稿（8 个）
  deprecated/      # 已废弃（4 个）
docs/              # 面向用户的文档页面（仅 engineering + productivity）
.agents/           # Agent 配置和 ADR（架构决策记录）
scripts/           # 安装/链接脚本
.claude-plugin/    # Claude Code 插件清单（marketplace.json + plugin.json）
.github/           # GitHub 配置
```

### 技能分类原则

- `engineering/` 和 `productivity/` 是 **推广桶**（promoted buckets）：必须在顶层 `README.md` 中有引用，必须在 `.claude-plugin/plugin.json` 的 `skills` 数组中注册
- 其余桶不得出现在以上两个位置
- `engineering/` 和 `productivity/` 中的每个技能还有面向用户的文档页面 `docs/<bucket>/<skill-name>.md`，线上 URL 统一为 `https://aihero.dev/skills-<skill-name>`
- 非推广桶的技能没有文档页
- 每个桶文件夹有自己的 `README.md`，推广桶按 **用户调用/模型调用** 分组，非推广桶使用平铺列表

### 技能的两种调用模式

| 模式 | 调用方式 | 配置 | 优缺点 |
|------|---------|------|--------|
| **用户调用**（User-invoked） | 仅可人工输入 `/skill-name` | `disable-model-invocation: true` + `agents/openai.yaml` 中 `allow_implicit_invocation: false` | 零上下文负载，但消耗认知负载（靠人记忆） |
| **模型调用**（Model-invoked） | 模型可根据上下文自动触发，也可人工调用 | 不设置 `disable-model-invocation`，description 中写触发词 | 自动触发方便，但每个回合占用上下文 |

---

## 三、Engineering 工程技能详解（17 个）

### 用户调用技能（10 个）

#### 1. `/ask-matt` —— 技能路由表

不记得有哪些技能时就用它。它是一个完整的**工作流地图**，将所有技能组织成清晰路径。

**主线（idea -> ship）：**
1. `/grill-with-docs` —— 通过追问锐化想法。有代码库时从此开始（状态化，保留学习成果到 `CONTEXT.md` 和 ADR）
2. 分支——问题能否在对话中解决？需要可运行答案时走原型绕行，用 `/handoff` 双向桥接：`/handoff` 出去 → `/prototype` → `/handoff` 回来
3. 分支——是否多会话构建？
   - **是** → `/to-spec`（生成规格）→ `/to-tickets`（拆解为曳光弹工单，声明阻塞依赖）→ `/implement` 逐个工单，每轮清上下文
   - **否** → 直接 `/implement`

**上下文卫生：** 步骤 1-3 保持在一个连续上下文窗口中，不要压缩或清空直到 `/to-tickets` 完成。每个 `/implement` 从干净的工单开始。限制在 **Smart Zone**（~120k token）内。

**两条匝道（On-ramps）：**
- **Bug 和请求堆积** → `/triage`：将 Issue 流经分诊状态机，产出 Agent 可执行的 Issue
- **有东西坏了** → `/diagnosing-bugs`：结构化排错流程，输出回归测试和 post-mortem
- **超大型任务，超过一个会话容量** → `/wayfinder`：决策地图，用决策工单推进直到路清晰，然后汇入主线 `/to-spec`

**代码健康（旁路）：**
- `/improve-codebase-architecture` —— 有空就跑，发现深化机会
- `/codebase-design` —— 深度模块设计词汇表，其他技能的基础语言

**独立技能：**
- `/grill-me` —— 无代码库版的追问
- `/prototype` —— 一次性原型
- `/research` —— 后台调研
- `/teach` —— 多会话教学
- `/writing-great-skills` —— 技能编写参考

---

#### 2. `/setup-matt-pocock-skills` —— 初始化配置

每个仓库执行一次。配置内容：
- **Issue Tracker**：默认 GitHub，也支持 Linear 和本地 Markdown 文件（`.scratch/`）
- **Triage 标签**：五个标准分诊角色的实际标签字符串映射
- **领域文档布局**：`docs/agents/issue-tracker.md` 等配置文件的生成

详细子文档：
- `domain.md` —— 领域模型配置
- `issue-tracker-github.md`、`issue-tracker-gitlab.md`、`issue-tracker-local.md` —— 各 tracker 的具体操作
- `triage-labels.md` —— 标签映射

---

#### 3. `/grill-with-docs` —— 带文档的追问会话

对计划或设计进行 relentless 追问，同时构建项目的领域模型。内部驱动 `/grilling` 和 `/domain-modeling`。

与 `/grill-me` 的区别：它是 **状态化的**——保留学习成果到 `CONTEXT.md`（术语表）和 ADR（架构决策记录）。这是 `/grilling` 的"留纸面痕迹"版本。

---

#### 4. `/to-spec` —— 生成需求规格文档

将当前对话内容综合为一份 PRD 规格文档并发布到 Issue Tracker。**不采访用户**——只综合已有讨论。

规格模板：

```
## Problem Statement（问题陈述）
从用户视角描述问题

## Solution（解决方案）
从用户视角描述解决方案

## User Stories（用户故事）
长时间编号列表，格式为：
1. As an <角色>, I want a <功能>, so that <收益>

## Implementation Decisions（实现决策）
- 将被构建/修改的模块
- 模块接口的修改
- 技术澄清
- 架构决策
- Schema 变更
- API 契约
- 特定交互
注意：不包含具体文件路径或代码片段（很快过时）
例外：原型产出的代码片段如编码了精确决策，可内联

## Testing Decisions（测试决策）
- 什么是好测试的描述
- 哪些模块将被测试
- 测试先例参考

## Out of Scope（范围外）

## Further Notes（补充说明）
```

生成后标记为 `ready-for-agent` 标签。

---

#### 5. `/to-tickets` —— 拆解为曳光弹工单

将计划/规格/对话拆解为 **曳光弹工单**（Tracer Bullet Tickets）。

**曳光弹规则：**
- 每个切片是贯穿所有层（Schema、API、UI、测试）的 **窄但完整** 路径——垂直切片，不是水平分层
- 完成的切片可独立演示或验证
- 每个切片适合一个干净上下文窗口
- 任何预重构（prefactoring）应优先做

**阻塞依赖：** 每个工单声明那些工单必须先完成才能开始。无阻塞的立即可开始。

**宽泛重构例外（Expand-Contract 模式）：**
宽泛重构是一个机械变更，爆炸半径覆盖整个代码库：
1. **Expand**：添加新形式在旧形式旁边，不破坏任何东西
2. **Migrate**：分批迁移调用方（按包/目录），每批一个工单，阻塞在 Expand 上，因为旧形式仍存在，CI 保持绿色
3. **Contract**：删除旧形式，在一个阻塞在所有 Migrate 批次上的工单中

**本地文件模式：** `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，按依赖顺序编号
**真实 Tracker 模式：** 使用平台原生阻塞关系

最终每个工单标记 `ready-for-agent`。

---

#### 6. `/implement` —— 执行实现

基于规格或工单进行实现。工作流程：
- 在预定义 seam 上驱动 `/tdd` 做红绿循环
- 频繁运行类型检查
- 频繁运行单文件测试
- 最后运行完整测试套件
- 使用 `/code-review` 做双轴审查
- 提交到当前分支

---

#### 7. `/triage` —— 问题分诊

将 Issue 流经状态机。两类角色：

**分类角色（2 个）：**
- `bug` —— 有东西坏了
- `enhancement` —— 新功能或改进

**状态角色（5 个）：**
- `needs-triage` —— 维护者需评估
- `needs-info` —— 等待报告者提供更多信息
- `ready-for-agent` —— 完全指定，Agent 可取走
- `ready-for-human` —— 需要人工实现
- `wontfix` —— 不处理

状态流转：未标记 → `needs-triage` → `needs-info`/`ready-for-agent`/`ready-for-human`/`wontfix`。`needs-info` 回复后回到 `needs-triage`。

**分诊一个 Issue 的流程：**

1. **收集上下文**——阅读完整 Issue（正文、评论、标签、作者、日期），解析之前的分诊记录
2. **冗余检查**——按领域概念搜索代码库是否已有实现，报告搜索位置。若已有实现则为 `wontfix`
3. **拒绝历史检查**——读取 `.out-of-scope/*.md`，检查是否之前被拒绝过
4. **推荐**——向维护者提供分类和状态建议及理由
5. **验证声明**——bug 按步骤复现，PR 检出并运行测试
6. **追问（如需要）**——驱动 `/grilling` 和 `/domain-modeling`
7. **应用结果**：
   - `ready-for-agent` → 发布 Agent 执行简报
   - `ready-for-human` → 类似 Agent 简报，注明为什么不可委派
   - `needs-info` → 发布分诊记录
   - `wontfix` → 关闭（已有实现/拒绝 bug/拒绝 enhancement 写入 `.out-of-scope/`）
8. 每个评论以 "This was generated by AI during triage." 开头

**外部 PR 视为带代码的 Issue**，走同样的状态机。

---

#### 8. `/improve-codebase-architecture` —— 改进代码架构

扫描代码库寻找 **深化机会**（deepening opportunities）——将浅模块重构为深模块。

**流程：**

**步骤 1：探索**
- 先决定范围再扫描（YAGNI 原则）。重点看最近频繁变更的热点文件
- 读取 `CONTEXT.md` 和 ADR
- 用 Explore Agent 走查代码库，记录摩擦点：
  - 理解一个概念需要跨多个小模块跳转
  - 模块太浅——接口几乎和实现一样复杂
  - 纯粹为测试提取的纯函数但真正的 bug 藏在调用方式里
  - 紧耦合模块泄漏过缝合点
  - 哪些部分不可测试或难以测试
- 对可疑的浅模块用 **删除测试**：删除它后复杂性是集中还是只是转移？

**步骤 2：以 HTML 报告呈现**
写入 OS 临时目录，用 `xdg-open`/`open`/`start` 打开。使用 Tailwind CDN + Mermaid CDN。

每个候选卡片包含：
- **Files** —— 涉及的文件/模块
- **Problem** —— 当前架构摩擦
- **Solution** —— 纯文本描述变更
- **Benefits** —— 用 locality 和 leverage 解释，以及测试改进
- **Before/After 图表** —— 并排自定义绘制
- **Recommendation strength** —— Strong / Worth exploring / Speculative 标签

报告末尾有 **Top recommendation** 区域。

**ADR 冲突**：如果候选与已有 ADR 矛盾，只在摩擦足够重现时标记，带警告标注。

**步骤 3：追问循环**

用户选定候选后，运行 `/grilling` 追问决策树。期间运行 `/domain-modeling`：
- 深化的模块名未在 `CONTEXT.md` 中 → 添加
- 对话中模糊术语被磨尖 → 立即更新 `CONTEXT.md`
- 用户拒绝候选且理由持久有效 → 提议 ADR
- 想探索替代接口 → 运行 `/codebase-design` 的 "设计两次" 并行子 Agent 模式

---

#### 9. `/wayfinder` —— 路径探寻

处理超大任务（无法在一个会话窗口容纳）。一个模糊的想法到达——太大，被迷雾包裹。

**核心概念：**
- **目的地（Destination）**：命名目的地是第一件事，它塑造每个工单
- **决策工单（Decision Tickets）**：问题是决策而非可执行工作
- **地图（Map）**：单个 Issue，标签 `wayfinder:map`，子 Issues 为其工单
- **迷雾（Fog of War）**：视线之外的未知领域，记录在 "Not yet specified" 区域
- **前沿（Frontier）**：开放的、无阻塞的、无人认领的工单——已知的边界

**工单类型：**

| 类型 | HITL/AFK | 说明 |
|------|----------|------|
| **Research** | AFK | 读取文档、第三方 API，通过 `/research` 子 Agent 解决 |
| **Prototype** | HITL | 提高讨论保真度，用 `/prototype` 技能 |
| **Grilling** | HITL | 用 `/grilling` 和 `/domain-modeling` 对话，默认情况 |
| **Task** | HITL or AFK | 必须完成的体力活，Agent 能独自做的就 AFK，否则给人类清单 |

**原则：**
- 默认规划而非执行——产出决策，不是可交付物
- 每次只用名称引用工单，不用裸 ID
- **每会话最多解决一个工单**（Research 除外）
- 解决一个工单 → 记录答案 → 清除前方迷雾 → 更新前沿

**调用模式：**
- **绘制地图**：命名目的地 → 宽度优先追问展开发掘 → 创建地图 Issue → 创建工单 → 连接阻塞关系 → 启动 Research 子 Agent → 结束（绘制是一会话的工作）
- **推进地图**：加载地图 → 选择工单 → 认领 → 解决 → 记录 → 添加新浮现的工单 → 更新迷雾

---

#### 10. `/code-review` —— 双轴代码审查

审查 HEAD 与固定点之间的 diff。两个轴用 **并行子 Agent** 运行，防止互相污染。

**步骤：**

1. **锁定固定点**——commit SHA、分支名、tag、`main`、`HEAD~5` 等。Diff 命令：`git diff <fixed-point>...HEAD`（三点）

2. **识别规格来源**——顺序搜索：
   - 提交信息中的 Issue 引用
   - 用户传入的参数路径
   - `docs/`、`specs/`、`.scratch/` 中匹配的 PRD/规格文件
   - 若无则问用户，用户说没有则 Spec 子 Agent 报告 "no spec available"

3. **识别编码标准来源**——仓库中任何记录了代码规范的文档

4. **代码坏味基线**（Fowler smells，始终适用，仓库标准可覆盖）：

| 坏味 | 含义 | 修复 |
|------|------|------|
| Mysterious Name | 命名不揭示其功能 | 重命名 |
| Duplicated Code | 同样逻辑出现在多处 | 提取共享 |
| Feature Envy | 方法访问别人数据比自己的多 | 移动方法 |
| Data Clumps | 同样字段总是结伴出现 | 打包为类型 |
| Primitive Obsession | 基本类型代替领域概念 | 创建专用类型 |
| Repeated Switches | 同样 switch 在多处重复 | 多态替代 |
| Shotgun Surgery | 一个变更要改散布各处的文件 | 集中到一模块 |
| Divergent Change | 一个模块因多种不相关原因被改 | 拆分 |
| Speculative Generality | 为不存在需求加的抽象 | 删除 |
| Message Chains | 长链式调用 | 隐藏在一方法后 |
| Middle Man | 类/函数只是转发 | 砍掉，直接调目标 |
| Refused Bequest | 子类忽略/覆盖大部分继承 | 用组合替代继承 |

5. **并行启动子 Agent：**

**Standards 子 Agent**：报告 (a) 违反文档标准的每处位置 (b) 发现的任何基线坏味。区分硬违规与判断调用。跳过工具已强制执行的内容。400 词以内。

**Spec 子 Agent**：报告 (a) 规格要求但缺失或不完整的需求 (b) 未请求的行为（范围蔓延）(c) 看起来实现错误的需求。引用规格原文。400 词以内。

6. **聚合**——在 `## Standards` 和 `## Spec` 标题下呈现，不合并不重排。以每轴发现总数和最严重问题做一行总结。不跨轴选胜者——正是这种分离的目的。

---

### 模型调用技能（7 个）

#### 11. `/tdd` —— 测试驱动开发

红-绿循环的参考技能。所有部分在每个循环中都要查阅。

**核心原则：**
- 测试通过公共接口验证行为，不是实现细节
- 代码可以完全改变，测试不该变
- 好测试读起来像规格——"user can checkout with valid cart"

**Seam（缝合点）——测试的位置：**
- Seam 是测试所在的公共边界：你观察行为的接口，不伸入内部
- **只在预定义的 seam 上测试**——写任何测试前，写下测试的 seam 并与用户确认
- 无法测试所有东西——商定 seam 使测试落在关键路径和复杂逻辑上

**反模式：**
- **实现耦合**：mock 内部协作者、测私有方法、通过侧信道验证。标志：重构时测试挂了但行为没变
- **同义反复**：断言以同样方式重新计算期望值，构造上永远正确——期望值必须来自独立真源
- **水平切片**：先写所有测试再写所有实现。应该用 **垂直切片**：一个测试 → 一个实现 → 重复

**循环规则：**
- **红前绿后**：先写失败测试，再写最少代码使它通过；不预测未来测试
- **一次一个切片**：每周期一个 seam、一个测试、一个最小实现
- **重构不在循环内**——属于审查阶段（`/code-review`），不在红绿循环中

---

#### 12. `/diagnosing-bugs` —— 结构化排错

六阶段流程。对于难解的 bug 使用。按阶段推进，跳过需明确理由。

**阶段 1 —— 构建反馈循环（核心）**

这是整个技能的精华。如果你有一个 **紧凑的** 通过/失败信号——红在当前 bug 上——就能找到原因。没有的话，看再多代码也没用。在这里投入不成比例的努力。**激进、创造、拒绝放弃。**

构建方法（按推荐顺序尝试）：

1. 失败测试——在任何到达 bug 的 seam 上
2. Curl/HTTP 脚本——对运行中的开发服务器
3. CLI 调用——带 fixture 输入，diff stdout 与已知正确快照
4. 无头浏览器脚本——Playwright/Puppeteer
5. 重放捕获的追踪——保存真实网络请求/事件日志到磁盘，隔离重放
6. 一次性测试程序——启动系统的极小子集
7. 属性/模糊测试——如果 bug 是"有时输出错误"，跑 1000 个随机输入
8. 二分测试——如果 bug 在两个已知状态间出现，自动化 `git bisect run`
9. 差分测试——同样输入跑旧版本 vs 新版本，diff 输出
10. HITL bash 脚本——最后手段，如果人类必须点击，用 `scripts/hitl-loop.template.sh` 驱动他们

**收紧循环：**
- 能更快吗？（缓存设置、跳过无关初始化、缩小测试范围）
- 信号能更尖锐吗？（断言具体症状，不是"没崩溃"）
- 能更确定性吗？（锁定时间、种子随机数、隔离文件系统、冻结网络）

30 秒的偶发循环几乎不比无循环好；2 秒确定性的才是紧凑的——排错超能力。

**非确定性 bug：** 目标不是干净复现而是 **更高的复现率**。循环触发 100 次，并行化，加压力，缩小时序窗口。50% 的偶发 bug 可排错；1% 不可——持续提高到可排错。

**完成标准 —— 一个紧凑的、能红的循环：**
- 能红：驱动真正的 bug 代码路径，断言用户的精确症状
- 确定性：每次运行同样判定
- 快速：秒级，非分钟级
- Agent 可运行：无人值守

在达到此标准前，**绝不**进入阶段 2。

**阶段 2 —— 复现 + 最小化**

运行循环看它红了。确认：
- 循环产生的故障模式是用户描述的——不是碰巧附近的另一个故障
- 多次运行可复现
- 捕获精确症状

然后最小化：逐次削减输入、调用方、配置、数据、步骤，每次削减后重跑循环——只保留对故障有载荷的元素。最终每个剩余元素都是载荷性的。

**阶段 3 —— 假设**

**生成 3-5 个可证伪假设**再测任何一个。单个假设生成会锚定在第一个可行想法上。

格式："If <X> is the cause, then <changing Y> will make the bug disappear / <changing Z> will make it worse."

如果无法陈述预测，假设就是感觉——丢弃或磨尖。

**向用户展示排名列表再测试**——他们常有领域知识能即时重排。不阻塞于此——如果用户不在线，按自己的排名继续。

**阶段 4 —— 检测**

每个探测必须映射到阶段 3 的具体预测。**每次只改变一个变量。**

工具偏好：
1. Debugger/REPL 检查（如果环境支持）
2. 目标日志——在区分假设的边界上
3. 永远不要"全记录然后 grep"

**每个调试日志都用唯一前缀标记**，如 `[DEBUG-a4f2]`。清理时一个 grep 搞定。

**性能回归**：日志通常错误。改为：建立基线测量（计时程序、`performance.now()`、profiler、查询计划），然后二分。先测后修。

**阶段 5 —— 修复 + 回归测试**

修复前写回归测试——但只在有 **正确的 seam** 时。正确 seam 是测试运行的 bug 模式与调用点实际发生的一致。如果唯一可用 seam 太浅，那里的回归测试给虚假信心。

**若无正确的 seam，那就是发现本身**——标记它。代码库架构阻止了 bug 被锁定。交给下一阶段。

如果有正确 seam：
1. 将最小复现转为该 seam 上的失败测试
2. 看它失败
3. 应用修复
4. 看它通过
5. 在原始（未最小化）场景上重跑阶段 1 反馈循环

**阶段 6 —— 清理 + Post-Mortem**

声明完成前必须：
- 原始复现不再出现
- 回归测试通过（或缺少 seam 已记录）
- 所有 `[DEBUG-...]` 检测代码已移除
- 一次性原型已删除（或移到明确标记位置）
- 证明正确的假设写入 commit/PR 信息——让下一个排错者学习

**然后问：什么能预防这个 bug？** 如果答案涉及架构变更（缺少测试 seam、纠缠的调用方、隐藏耦合）则用具体信息交给 `/improve-codebase-architecture`。**修好后提建议**，不是修之前——你现在比开始时知道更多。

---

#### 13. `/codebase-design` —— 深度模块设计词汇表

所有其他技能的底层共享语言。设计 **深模块**：大量行为藏在小组口后面，放在干净缝合点，可通过该接口测试。

**核心术语：**

| 术语 | 定义 | 避免用 |
|------|------|--------|
| **Module（模块）** | 有接口和实现的东西。不关心规模：函数、类、包、跨层切片 | unit, component, service |
| **Interface（接口）** | 调用者必须知道才能正确使用模块的一切：类型签名、不变量、顺序约束、错误模式、必需配置、性能特性 | API, signature（太窄，仅指向类型层面） |
| **Implementation（实现）** | 模块内部的代码。与 Adapter 区别：东西可以是小 adapter+大实现或大 adapter+小实现 | — |
| **Depth（深度）** | 接口上的杠杆力：调用者（或测试）能在每单位需学习的接口下运用的行为量 | — |
| **Seam（缝合点）** | 不改那个位置就能改变行为的地方；模块接口所在的**位置** | boundary（DDD 限界上下文过载） |
| **Adapter（适配器）** | 满足缝合点上接口的具体东西。描述**角色**而非实质 | — |
| **Leverage（杠杆力）** | 调用者从深度得到的：每单位已学接口获得更多能力 | — |
| **Locality（局部性）** | 维护者从深度得到的：变更、bug、知识、验证集中在一处 | — |

**深与浅的对比：**

深模块 = 小接口 + 大量实现
```
*─────────────────────*
│   Small Interface   │  ← 少量方法，简单参数
├─────────────────────┤
│                     │
│  Deep Implementation│  ← 隐藏复杂逻辑
│                     │
*─────────────────────*
```

浅模块 = 大接口 + 少量实现（避免）
```
*─────────────────────────────────*
│       Large Interface           │  ← 许多方法，复杂参数
├─────────────────────────────────┤
│  Thin Implementation            │  ← 只是透传
*─────────────────────────────────*
```

**设计原则：**
- **深度是接口的属性，不是实现的。** 深层模块内部可以由小型的、可 mock 的、可替换的部件组成——它们只是不在接口中
- **删除测试：** 想象删除该模块。如果复杂性消失了，它就是个透传。如果复杂性在 N 个调用方重现，它就在发挥作用
- **接口是测试面：** 调用者和测试穿越同一个缝合点。如果想测试**越过**接口，模块可能形状不对
- **一个 adapter = 假设的缝合点。两个 adapter = 真实的。** 除非有东西确实在这个缝合点上变化，否则不要引入

**可测试性设计：**
1. 接受依赖，不创造依赖
2. 返回结果，不产生副作用
3. 小表面积——更少方法=更少测试=更简单设置

额外参考文件：
- `DEEPENING.md` —— 在给定依赖下深化集群
- `DESIGN-IT-TWICE.md` —— 启动并行子 Agent 以几种激进不同的方式设计接口，然后比较

---

#### 14. `/domain-modeling` —— 领域建模

主动构建和打磨项目的领域模型。这是**主动**的——挑战术语、发明边界场景、在结晶那一刻写下术语表和决策。（仅是读取 `CONTEXT.md` 获取词汇不算这个技能——那是任何技能都能做的一行习惯。）

**会话期间的行为：**

- **挑战术语表** —— 用户使用的术语与 `CONTEXT.md` 矛盾时立即指出
- **磨尖模糊语言** —— 用户使用模糊或过载术语时，提出精确的规范术语
- **讨论具体场景** —— 用具体场景压力测试领域关系，发明探查边界情况的场景
- **代码交叉引用** —— 用户声明某事如何运作时，检查代码是否一致。发现矛盾时立即指出
- **即时更新 CONTEXT.md** —— 术语确定后立即更新，不批量处理。`CONTEXT.md` 必须是纯粹的术语表，不含实现细节
- **有选择地提议 ADR** —— 仅在三条件全部满足时：
  1. **难以逆转**——改主意的成本有意义
  2. **无上下文会令人惊讶**——未来读者会好奇"为什么这样做"
  3. **真实权衡的结果**——存在真正的替代方案，为特定原因选择了这个

文件结构支持多上下文项目：
- 单一上下文：`CONTEXT.md` + `docs/adr/`
- 多上下文：`CONTEXT-MAP.md` 指向各自的 `CONTEXT.md` 和 `docs/adr/`

---

#### 15. `/prototype` —— 快速原型

一次性代码，回答一个设计问题。问题的类型决定形状。

**两个分支：**

**逻辑分支（"这个状态模型感觉对吗？"）：**
- 构建一个微小的交互式终端应用
- 将状态机推过难以在纸上推理的场景
- 每次操作后打印完整状态

**UI 分支（"这个应该长什么样？"）：**
- 生成几种激进不同的 UI 方案
- 所有方案放在同一路由
- 通过 URL 搜索参数 + 浮动底部栏切换

**共同规则：**
1. 从第一天起就是一次性的，并明确标记
2. 一条命令即可运行
3. 默认不持久化——状态在内存中
4. 跳过润色——无测试、无错误处理、无抽象
5. 每次操作后显露状态
6. 完成后捕获：将验证过的决定折叠进真实代码，原型本身提交到一次性分支留在 main 之外

---

#### 16. `/research` —— 后台调研

启动 **后台 Agent** 进行调研，主 Agent 继续工作。

任务：
1. 只对**一手来源**调研——官方文档、源码、规范、第一方 API
2. 将发现写入单个 Markdown 文件，每个声明引用来源
3. 按仓库已有约定保存

---

#### 17. `/resolving-merge-conflicts` —— 解决合并冲突

1. 查看合并/rebase 的当前状态
2. **为每个冲突找到一手来源**——深刻理解每次改动的意图。阅读提交信息，检查 PR，检查原始 Issue/Ticket
3. **逐块解决**——可能的情况下保留双方意图。不兼容时选匹配合并宣称目标的那一个并注明权衡。**不发明新行为。** 总是解决；永不 `--abort`
4. 发现项目的自动检查并运行——类型检查，然后测试，然后格式化
5. **完成合并/rebase**——暂存一切并提交。如果是 rebase，继续直到所有提交都被 rebase

---

## 四、Productivity 生产力技能详解（5 个）

### 用户调用技能（4 个）

#### 1. `/grill-me` —— 追问会话（无代码库版）

运行一个 `/grilling` 会话。与 `/grill-with-docs` 同样的 relentless 追问，但是无状态——不保存任何东西到本地，不构建 `CONTEXT.md`。用于不涉及代码库的任何计划或设计。

---

#### 2. `/handoff` —— 会话交接

将当前对话压缩为交接文档供新 Agent 接手。保存到用户 OS 的临时目录——不在当前工作空间。

包含：
- 会话的完整摘要
- **"Suggested skills"** 部分——建议 Agent 应调用的技能
- 不重复已在其他产出的内容（规格、计划、ADR、Issue、提交）——引用路径或 URL
- 脱敏任何敏感信息（API 密钥、密码、个人身份信息）

如果用户传入参数，视为下一会话焦点的描述。

---

#### 3. `/teach` —— 教学系统

一个极其详尽的多会话教学框架，在当前目录创建状态化教学工作空间。

**工作空间文件：**

| 文件 | 用途 |
|------|------|
| `MISSION.md` | 用户对主题感兴趣的**原因**——所有教学的基础 |
| `lessons/*.html` | 自包含的 HTML 课程——教学的主要产出单元 |
| `reference/*.html` | 参考材料——课程的压缩精华，设计为快速参考 |
| `learning-records/*.md` | 学习记录（类似 ADR）——捕获不明显教训和关键洞察 |
| `RESOURCES.md` | 高质量资源列表，支撑教学 |
| `NOTES.md` | Agent 记录用户偏好的草稿本 |
| `assets/*` | 跨课程共享的可复用组件 |

**教学哲学：**
- 三要素：**知识**（来自高质量来源） + **技能**（通过高相关互动课程获取） + **智慧**（与其他学习者和实践者互动获得）
- 区分 **流利强度**（当下检索）和 **存储强度**（长期保持）。目标是存储强度
- 用必要难度建立长期保持：检索练习、间隔重复、交错练习（仅技能练习）

**课程设计：**
- 每课一个自包含 HTML 文件，干净、可读、美观
- 短小精悍——学习者的工作记忆很小
- 直接绑定到 Mission
- 在用户的最近发展区
- 每个课包含外部资源引用
- 每个课鼓励用户追问 Agent

**Asset 复用：** 共享样式表是第一组件。读取 `assets/` 复用已有组件而非重复。

---

#### 4. `/writing-great-skills` —— 技能编写指南（元技能）

整个仓库的元技能——教你怎么写好一个 Skill。核心原则：**可预测性是根本美德**——Agent 每次跑同样的流程，不是产出相同的结果。

**核心概念词汇表（来自 `GLOSSARY.md`）：**

| 概念 | 含义 |
|------|------|
| **Predictability（可预测性）** | 根本美德——同样的步骤每次产生同样的过程 |
| **Leading Word（前置词）** | 一个紧凑的概念词，激活模型的预训练知识，用一个 token 锚定整片行为 |
| **Context Load（上下文负载）** | 模型调用技能的 description 每回合占用的上下文窗口空间 |
| **Cognitive Load（认知负载）** | 用户记住技能名和何时使用的心理负担 |
| **Router Skill（路由技能）** | 一个用户调用技能，列出其他技能及何时用——当用户调用技能多到记不住时的补救 |
| **Completion Criterion（完成标准）** | 告诉 Agent 工作做完的可检查条件。要能判断（Agent 能区分做了和没做吗？）和彻底（"每个修改的模型都算了"不是"产生变更列表"） |
| **Premature Completion（过早完成）** | Agent 在步骤真正完成前结束步骤，注意力滑向"完成" |
| **Legwork（深入工作）** | Agent 在技能内的挖掘——因为"应用了每条规则"意味着深入 |
| **Information Hierarchy（信息层级）** | 步骤 > 技能内参考 > 外部参考——渐进披露的阶梯 |
| **Progressive Disclosure（渐进披露）** | 向下移动层级——将材料推出 `SKILL.md` 到链接文件——保持顶层清晰 |
| **Context Pointer（上下文指针）** | 指向外部参考的链接；其措辞决定 Agent 何时和多大程度上访问该材料 |
| **Co-location（共置）** | 将一个概念的各方面（定义、规则、警告）放在同一标题下而非分散 |
| **Branch（分支）** | 一个技能的不同路径——不同运行走技能的不同部分。分支是最干净的披露测试 |
| **Single Source of Truth（单点真源）** | 一个权威位置——改行为只改一处 |
| **Granularity（粒度）** | 技能的切分精细度。每次切分花费两种负载之一：模型调用切分花费上下文负载，序列切分花费认知负载 |
| **No-op（无操作）** | 一行或一句如果删除后行为不变——需删除 |
| **Duplication（重复）** | 同样的含义存在两个地方——破坏单点真源 |
| **Scope Creep（范围蔓延）** | 技能做了不该做的事。防御：问"这个还在范围内吗？" |

**调用模式选择：**
- 模型调用：Agent 必须自行触达（或另一技能必须触达）才选。付出上下文负载
- 用户调用：只靠打字触发。零上下文负载，但消耗认知负载

**信息层级决策：**
- **步骤**：有序动作，每个带完成标准
- **技能内参考**：定义、规则、事实——合法的平级集合
- **外部参考**：推出到单独文件，通过上下文指针访问

**分支**是对技能做的最干净的披露测试：内联所有分支都需要的，把只有部分分支需要的推到指针后面。

**何时切分技能：**
- **按调用方式切**——有独特前置词应独立触发，或另一技能必须触达时才切出模型调用技能
- **按序列切**——当后续步骤诱惑 Agent 匆忙完成当前步骤时（过早完成），隐藏后续步骤

**剪枝四步法：**
1. 单点真源——每个含义只在一个位置
2. 相关性——每一行仍承载技能行为吗？
3. 无操作测试——逐句，不是逐行。删除整句而非修剪词
4. 前置词——寻找将多处复述压缩为一个 token 的机会

---

### 模型调用技能（1 个）

#### 5. `/grilling` —— 追问引擎

`/grill-me` 和 `/grill-with-docs` 的基础引擎。

规则：
- 对我 relentless 追问计划的每个方面直到达成共识
- 走遍决策树的每一个分支，逐一解决分支间的依赖
- **每次只问一个问题**，等用户反馈再继续。同时问多个令人困惑
- 如果能通过探索环境找到**事实**，自己去查不要问用户
- **决策**是用户的——每个摆到用户面前等答案

---

## 五、Misc 技能（4 个）

### `git-guardrails-claude-code` —— Git 安全护栏

为 Claude Code 设置钩子阻止危险 Git 命令：
- `git push`（包括 `--force`）
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D`
- `git checkout .` / `git restore .`

步骤：问范围（项目/全局）→ 复制脚本 → 添加到 settings.json → 自定义 → 验证。

### `migrate-to-shoehorn` —— 迁移到 shoehorn

将测试文件中 `as` 类型断言迁移到 `@total-typescript/shoehorn`：
- `as Type` → `fromPartial()`（部分数据仍类型检查）
- `as unknown as Type` → `fromAny()`（故意错的数据，保留自动完成）

仅用于测试代码，不用于生产。

### `scaffold-exercises` —— 搭建练习目录

为 AI Hero 课程创建练习目录结构：
- `exercises/XX-section-name/XX.YY-exercise-name/`
- 变体：`problem/`、`solution/`、`explainer/`
- 必需文件：`readme.md`（非空）+ `main.ts`（如有代码）
- 完成后跑 `pnpm ai-hero-cli internal lint` 验证

### `setup-pre-commit` —— 设置提交前钩子

一键设置：Husky + lint-staged + Prettier + typecheck + test。
- 检测包管理器（npm/pnpm/yarn/bun）
- 安装依赖
- 创建 `.husky/pre-commit`、`.lintstagedrc`、`.prettierrc`
- 验证所有文件存在且可运行

---

## 六、Personal 个人技能（2 个）

### `edit-article` —— 编辑文章

1. 根据标题将文章划分为节，考虑信息的有向无环图依赖
2. 与用户确认节
3. 每节改写提高清晰度、连贯性和流畅度，每段最多 240 字符

### `obsidian-vault` —— Obsidian 笔记库管理

管理 Matt 的 Obsidian 笔记库（`/mnt/d/Obsidian Vault/AI Research/`）：
- 使用 `[[wikilinks]]` 链接
- 索引笔记聚合相关主题
- 支持搜索、创建、相关笔记查找、索引笔记查找

---

## 七、In-Progress 开发中技能（8 个）

### `batch-grill-me` —— 批量追问

一次问所有前沿问题的追问模式。将决策映射为 **设计树**：每个决策分支到它下面的决策。每轮问整个前沿——所有其前置已解决的问题。批量编号+推荐答案，用户回答后重算前沿进入下一轮。

### `claude-handoff` —— Claude 交接

将当前对话交接给新鲜的 Claude 后台 Agent，执行 `claude --bg --name "<描述>" "<交接摘要>"`。

### `loop-me` —— 生活/工作循环设计

为生活中的循环模式设计 Workflow 规格。核心概念：
- **Loop** —— 用户生活中的重复模式
- **Workflow** —— 一个循环的规格
- **Trigger** —— 事件触发或定时触发
- **Checkpoint** —— 人类在环验证点，尽量**推右**——在涉及人类前做最多工作
- **Brief** —— 呈现给人类的决策就绪摘要

### `setup-ts-deep-modules` —— TypeScript 深层模块

用 dependency-cruiser 强制每个包成为深模块：
```
src/packages/<name>/
  index.ts        ← 入口点（公共），外部只能导入此
  client.ts       ← 另一个入口点
  lib/            ← 实现（隐藏）
  tests/          ← 协同测试（隐藏）
```

四条规则：入口边界、包内自由、通过入口测试、无循环。鼓励多个小入口点而非一个大桶文件。

### `to-questionnaire` —— 生成问卷

将用户无法独自回答的决策转化为问卷让别人填写。步骤：确定收件人角色→确定需要什么→起草问题（最重要优先，最坏只能获得一回合）。

### `wizard` —— 交互式 bash 向导

生成交互式 bash 脚本引导人类走手动流程：
- 显示进度和剩余时间
- 打开 URL 并说要点什么
- 捕获值写入 `.env` 和 GitHub Secrets
- 使用隐藏输入保护敏感值
- 基于 `template.sh` 模板

### `writing-beats` —— 节拍式写作

以"节拍"为单位逐步构建文章。核心概念：
- **Grounding（接地）** —— 每个概念必须先被定义（通过前置知识或前期节拍），后续节拍才能依赖它
- **Beat（节拍）** —— 旅程中的一步。做完一件事就停，让下一节拍能转向
- 每次提供 2-3 个候选下一步，用户选择，写入文件，重读，再选下步

### `writing-fragments` —— 写作碎片收集

探索阶段——不承诺结构地挖掘可写之物。用 `\n---\n` 分隔碎片。前置词（leading word）是最有价值的碎片——它能塑造后续整个结构、过渡和标题。

### `writing-shape` —— 写作塑形

利用阶段——将素材塑造成文章，段落接段落。核心循环：建立读者前置知识 → 起草 2-3 个候选开篇 → 逐段增长。每段必须回答"读到这，读者需要听到什么？"

---

## 八、Deprecated 已废弃技能（4 个）

- `design-an-interface` —— 用于设计模块接口的并行子 Agent 方案（已被 `/codebase-design` 的 DESIGN-IT-TWICE 取代）
- `qa` —— 旧的 QA 流程
- `request-refactor-plan` —— 旧的重构计划请求
- `ubiquitous-language` —— 旧的通用语言构建（已被 `/domain-modeling` 取代）

---

## 九、安装与分发

### 两种安装途径

**方式 1：skills.sh 安装器（推荐）**
```bash
npx skills@latest add mattpocock/skills
```
- 选择需要的技能和目标 Agent
- 务必选择 `/setup-matt-pocock-skills`
- 运行配置向导
- 技能复制到项目中，可自由修改和定制

**方式 2：Claude Code 插件**
```
/plugin marketplace add mattpocock/skills
/plugin install mattpocock-skills@mattpocock
```
- 只读托管包
- 跟随 Matt 发布自动更新
- 类似订阅而非 fork

**symlink 安装：**
```bash
scripts/link-skills.sh
```
每个条目是到仓库的 symlink，`git pull` 即保持更新。

### 版本管理

- `package.json` 和 `.claude-plugin/plugin.json` 的 `version` 必须同步
- Claude 使用 plugin 的 `version` 决定何时通知用户更新
- 修改清单后运行 `claude plugin validate . --strict`
- 使用 Changeset 管理版本发布

---

## 十、整体工作流示意

```
                   /grill-with-docs（有代码库）
                  /                       \
           /grill-me（无代码库）         /prototype
                  |                    /handoff
                  |                        |
          ┌───────┴────────┐               |
          │  一会话可解决？  │───────────────┘
          └───────┬────────┘
                  |
        ┌─────────┴──────────┐
        │ 多会话构建？       │
        └──┬─────────────┬───┘
           │是           │否
    /to-spec              │
    /to-tickets           │
    /implement            /implement
    (每工单干净上下文)    (当前窗口)

匝道 1: /triage → 主线
匝道 2: /diagnosing-bugs → (可选) /improve-codebase-architecture

大型探路: /wayfinder → /to-spec → 主线
代码健康: /improve-codebase-architecture → /grill-with-docs

交叉会话: /handoff（分叉）/ /compact（继续）
```

---

## 十一、关键设计洞察

1. **共享语言是最深刻的优化**——不是 prompt 技巧，而是工程实践。一个精确的术语表减少的 token 和歧义远胜任何提示工程。

2. **曳光弹垂直切片 > 水平分层**——每个工单是一个完整的端到端路径，可独立演示。这天然防止了"所有数据库层写完了但 UI 层还没开始"的集成噩梦。

3. **深度模块从源头防止熵增**——用 leverage（杠杆力）和 locality（局部性）两个维度衡量设计质量，在每次变更中投资设计。

4. **双轴并行审查防止认知污染**——标准和规格分开审查，一项通过不掩盖另一项的失败。

5. **反馈循环压倒一切**——`/diagnosing-bugs` 阶段 1 是整技能的灵魂：没有紧凑的、能红的循环，任何假设都是瞎猜。

6. **决策地图处理超大会话**——用 wayfinder 的 fog of war 和前沿概念，将不可控的超大任务分解为可控的决策步骤。

7. **技能本身也要工程化**——`/writing-great-skills` 用上下文负载、认知负载、单点真源、前置词等概念，将写技能变成一门有方法论支撑的学科。

8. **预定义 seam 是测试的轴心**——不在未确认的 seam 上写测试，不测试实现细节。接口就是测试面。

---

*本分析基于 mattpocock/skills v1.1.0 仓库，阅读了所有 40 个技能文件及相关的配置文档、ADR、bucket README 等全部内容。*
