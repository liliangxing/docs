# 近100天大模型重要新闻 · Agent方向开发向综述

> 时间范围：2026-05 ~ 2026-08
> 视角：对程序开发有直接帮助的进展，聚焦 Agent（大脑+手脚）工程化
> 作者：liliangxing

---

## 一、核心判断

大模型"大脑"的参数竞赛已让位于 **Agent"手脚"的工程化竞争**。
纯模型能力差距在缩小，真正拉开差距的是：

- 工具调用可靠性（MCP / Function Calling）
- 状态管理与长程任务持久化
- 多 Agent 协作与子 Agent 编排
- 安全护栏（权限、预算、人工审批）

一句话：**大脑决定下限，手脚决定上限。**

---

## 二、Agent 框架收敛：四大通用原语成为标配

主流框架（LangGraph、OpenAI Agents SDK、Claude Agent SDK、Google ADK、CrewAI 等）已趋同于同一套架构范式。

| 原语 | 作用 | 代表实现 |
|---|---|---|
| 状态图 State Graph | 有向图 + 类型化状态，支持断点/回退/人工审批 | LangGraph、CrewAI Flow |
| 结构化工具调用 MCP | 工具接入事实标准，跨框架复用 | Model Context Protocol |
| 子 Agent 委派 Handoff | 父 Agent 拆解，子 Agent 独立上下文并行 | Claude Agent SDK、Cursor 3 |
| 生命周期钩子 Hooks | 权限/预算等硬性约束，不依赖 Prompt | pre_tool_execution 等 |

**开发启示**：选型时优先支持以上四项的框架，避免被单一模型锁定，采用"可插拔大脑"架构。

---

## 三、编程智能体（Coding Agent）关键进展

### 1. 多 Agent 协作进入"舰队模式"

- **Cursor 3**：支持子 Agent 嵌套，前端 / 后端 / 测试分工作业
- **Claude Code 2.1**：支持五层深度子 Agent 嵌套，仅向父 Agent 返回结果摘要
- **Qwen3.7-Max**：实现 35 小时超长程自主任务，超 1000 次工具调用，适配 Claude Code、Qwen Code 等多框架
- **百度伐谋 Agent 2.0**：登顶 MLE-Bench，验证 Agent 在 ML 工程全流程（数据→训练→调优）的端到端能力

### 2. 工具链与运行时升级

- **Google Gemini Enterprise Agent Platform**
  - Agent Runtime：次秒级冷启动、长时运行
  - Agent Sandbox：隔离执行代码 / 浏览器自动化
  - Agent Identity：加密身份追踪

- **GitHub Copilot**
  - Agent Skills + MCP 正式 GA
  - `SKILL.md` 编码团队规范
  - 代码评审中支持只读 MCP 调用

- **OpenAI Codex**
  - 插件 + 子 Agent + Guardian Approvals（风险分级自动审批）
  - 周活达 300 万

### 3. 国产模型追上第一梯队

| 模型 | 亮点 |
|---|---|
| Qwen3.7 / Qwen3-Coder | 长程任务、代码能力逼近国际一线，性价比高 |
| GLM-5.1（智谱） | 中文场景、工具调用稳定 |
| DeepSeek V4 | 推理 + 代码双强，适合本地/私有化部署 |

---

## 四、协议与生态标准化

- **MCP 2026-07 规范 RC 版**：工具描述、鉴权、流式返回进一步规范化
- **A2A 协议**：跨 150+ 组织采用，Agent 间互操作成趋势
- **Agent 内存分层**：短期 / 长期 / 沉淀记忆成为生产级刚需，Mem0、Letta 等方案值得关注

---

## 五、对开发者的实操建议

### 1. 框架与模型选型
- 优先"状态图 + MCP + 子 Agent + Hooks"四件套齐全的框架
- 大脑可插拔：同一套工具链切换 Qwen / DeepSeek / Claude / GPT
- 国产模型在成本敏感、私有化、中文场景有显著优势

### 2. Agent 安全（重点）
- **硬性规则写入 Hooks，而非 System Prompt**
  - 工具权限白名单
  - 单次 / 单日预算上限
  - 敏感操作人工审批
- 长文档策略遵从率仅约 36%，**不能依赖 Prompt 做强制约束**

### 3. 编程工作流组合
- 复杂任务 → Claude Code / Cursor 多 Agent 协作
- 日常补全 → Copilot / 通义灵码
- 本地轻量 → Qwen2.5-Coder / DeepSeek 本地部署（参见本仓库其他指南）

### 4. 值得跟踪的后续信号
- MCP 正式版发布与 Registry 生态
- A2A 跨组织 Agent 互通
- Agent 内存/状态分层成为框架标配

---

## 六、本仓库相关指南索引

本仓库已收录大量本地模型 + Agent 工具链搭建指南，可作为落地参考：

- `Roo-Code-智谱GLM和DeepSeek配置完整指南.md` — Roo Code + 国产模型
- `Kilo-Code-DeepSeek-搭建指南.md` — Kilo Code + DeepSeek V4
- `GlmCoder-搭建指南.md` / `GlmCoder-微服务开发实战指南.md` — 智谱 Coder 实战
- `Qwen2.5-Coder-1.5B-本地CPU部署指南.md` — 本地轻量代码模型
- `Codebase-Indexing-搭建指南.md` — 代码库索引（Agent 的"空间记忆"）
- `aider-build-guide.md` — Aider 终端编程 Agent
- `continue-jetbrains-build-guide.md` — Continue + JetBrains 集成
- `Dify-LiteLLM-搭建指南.md` — Dify + LiteLLM 统一模型网关

---

## 七、一句话总结

> 2026 年 AI 编程的主动权，不在"谁的参数多"，而在"谁的手脚更伶俐"。
> 把工具调用、状态管理、安全护栏、多 Agent 协作做扎实，比追一个新模型更值钱。

---

*本文由 AI 整理，欢迎在仓库中补充修正。*
