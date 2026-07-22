# x-code-cli vs MiMo-Code：自然语言「拉取 GitHub 项目 / 跑项目 / 修错误」能力对比

> 结论先行：**这是一次"各有胜负"的对比，不是一方碾压**。
> - **拉取 GitHub 项目**：MiMo-Code 略强（有真正的 GitHub/PR 命令原语）；但两者都没有"专用 clone 命令"，clone 都靠 LLM 调 shell。
> - **跑项目（启动 / 构建 / dev server）**：**x-code-cli 明显更强**（真·后台 shell，最长 30 分钟；MiMo 的 bash 120 秒超时被杀、无后台进程管理）。
> - **修错误（自动修复循环）**：旗鼓相当，MiMo 略胜一筹（独立"冷"judge 模型 + compose TDD 闭环 + 铁律）。
>
> 若把"拉取 → 跑 → 修"视为一条端到端流水线，**x-code-cli 是唯一能完整跑通三步的工具**（MiMo 会在"跑项目"这一步卡住）；但若只看"GitHub 操作"和"结构化自主修复"，MiMo 更成熟。

---

## 0. 两个项目是什么

| 维度 | x-code-cli | MiMo-Code (MiMoCode) |
| --- | --- | --- |
| 定位 | 终端原生开源 AI 编程助手 | 终端原生 AI 编程助手（"模型与 Agent 共进化"） |
| 血缘 | 基于 Claude Code 系 Agent SDK 改造 | **OpenCode 的 fork**（保留 OpenCode 核心，叠加小米 MiMo 能力） |
| 技术栈 | TypeScript + pnpm monorepo，核心在 `packages/core` + `packages/cli` | TypeScript + bun，核心在 `packages/opencode/src` |
| 模型 | 8 家厂商（Claude/GPT/DeepSeek/Gemini/Qwen/Grok/GLM/Kimi）+ 任意 OpenAI 兼容 | 内置 MiMo Auto 免费通道 + 小米 OAuth + 任意 OpenAI 兼容 |
| 主打能力 | 多模型、子 Agent、Plan 模式、持续目标循环 `/goal`、知识库、插件市场 | 持久记忆（SQLite FTS5）、智能上下文重建、subagent 编排、`/goal` + compose workflow、self-improve（dream/distill） |

两者都是**通用型 coding agent**，三大能力本质上都依赖「LLM 推理 + shell 工具执行」。差异在于：是否把某些环节做成了**专用原语/护栏**。

---

## 1. 用自然语言拉取（clone）/ 操作 GitHub 项目

### x-code-cli
- **没有** `github` / `clone` / `repo` 专用命令。内置命令仅 `browser / doctor / goal / mcp / plugin / skill` 等（`packages/cli/src/ui/commands/`）。
- `/review [PR号]`（README:229）本质是**一个 skill 提示词**（markdown 模板），且明确要求本机装好 `gh`——即引导模型用 shell 调 `gh`/`git`，并非内置能力。
- **不内置 GitHub MCP**；MCP 只能用户手动配置（`packages/cli/src/ui/commands/mcp.ts`）。
- clone 走通用 `shell` 工具（`packages/core/src/tools/shell.ts`），由 LLM 推理生成 `git clone` 并经权限检查执行。
- 生态亮点：插件 manifest 字节级兼容 Claude Code，**可直接装 Claude/Codex 生态插件**，marketplace 一键发现。

### MiMo-Code
- **有真正的 GitHub 命令原语**（OpenCode 系）：
  - `github install` / `github run`（`packages/opencode/src/cli/cmd/github.ts`）：写 `.github/workflows/opencode.yml`、安装 `opencode-agent` App，用 `@octokit/rest`+`@octokit/graphql` 拉取 PR/Issue、checkout 分支、`createComment`/`createPR`——**端到端的 GitHub Action 自动化闭环**。
  - `pr` 命令（`packages/opencode/src/cli/cmd/pr.ts`）：用 **gh CLI**（`gh pr checkout`/`gh pr view`）拉取 PR 分支、处理 fork remote、import session。
- bash 工具提示词（`bash.txt:98`）明确写："**Use the gh command via the Bash tool for ALL GitHub-related tasks**"——把 gh 作为 GitHub 操作的标准路径深度集成进 agent 行为。
- 但**"把某个仓库 clone 下来"仍没有专用命令**，同样靠 LLM 调 shell 执行 `git clone`。

### 对比小结
| | x-code-cli | MiMo-Code |
| --- | --- | --- |
| 专用 clone 命令 | ❌ | ❌ |
| PR / Issue / CI 自动化 | 仅 skill（需 gh） | ✅ 真·github/pr 命令（Octokit + gh） |
| 自然语言 clone 完成度 | shell+LLM | shell+LLM（旗鼓相当） |
| GitHub 生态丰富度 | 插件市场兼容 Claude 生态 | 原生 GitHub Action 闭环 |

> **判定**：字面意义的"clone 一个仓库"，两者**旗鼓相当**（都靠 shell）。但 MiMo-Code 在**广义 GitHub 操作（PR/Issue/CI）**上明显更强——它有专用命令原语，而 x-code-cli 的 GitHub 能力基本等于"装好 gh 让模型自己敲命令"。**本项 MiMo-Code 略胜。**

---

## 2. 跑项目（运行 / 构建 / 启动 dev server）

### x-code-cli —— 真正的后台进程管理
- 前台 `shell`：默认超时 **30 秒**（可调）。
- **后台 shell**（`packages/core/src/tools/background-shell.ts`）：`shell({ runInBackground: true })` 用 `execa` detached 生成，**`BG_MAX_MS = 30 * 60 * 1000`（30 分钟）** 才作为失控兜底；`buffer:false` 用 1MB 环形缓冲（避免 noisy dev server 触发 SIGTERM）。
- 配套 `shellOutput`（移动游标轮询新输出）与 `killShell`（终止）两个工具，模型可"起服务 → 继续干活 → 回头看日志 → 关掉"。
- 流式 `tool-execution.ts` 经 `onShellOutput` 实时回传（50ms 节流），`foldShellErrorNoise` 收敛错误噪声，超 30k 截断提示。
- **不足**：grep 全 core 无 `package.json`/`dev server`/端口检测代码——**不自动识别项目类型或探测端口**，靠模型自己判断启动命令。

### MiMo-Code —— 长时间运行会被杀
- bash 工具（`packages/opencode/src/tool/bash.ts`）：`DEFAULT_TIMEOUT = 2 * 60 * 1000` = **120 秒**；超时即 `handle.kill({ forceKillAfter: "3 seconds" })`（line 618-622）。
- 输出超 `Truncate.MAX_BYTES/LINES` 写文件 + head/tail 错误模式检测（line 681-701）。
- `interactive: true` 走 `BashInteractive.request` 把终端交给用户（line 775）——这**不是后台管理**，是把控制权交给人。
- **没有后台进程管理**：起一个 dev server 会在 120 秒被强杀；只能靠 interactive 或手动加大 timeout，**无法"在后台常驻服务并继续对话"**。
- 项目识别同样靠 LLM：compose 的 `runVerify` 只加载 `compose:verify` skill，让 agent 读 `AGENTS.md`/`package.json` 找 build/test 命令，**无硬编码"类型→命令"映射**。

### 对比小结
| | x-code-cli | MiMo-Code |
| --- | --- | --- |
| 后台运行 dev server | ✅ runInBackground，最长 30 分钟，环形缓冲 | ❌ 无，120 秒超时强杀 |
| 边跑边对话 | ✅ shellOutput 轮询 + killShell | ⚠️ 仅 interactive（交还终端） |
| 流式 / 噪声收敛 | ✅ | ✅ |
| 项目类型 / 端口自动探测 | ❌ | ❌ |

> **判定**：**x-code-cli 明显更强，且是决定性差距**。MiMo 的 bash 连"后台常驻一个 dev server"都做不到（120 秒被杀）。对于"跑项目"这一项，x-code-cli 完胜。

---

## 3. 修错误（自动修复循环）

### x-code-cli —— 多验证器阶梯 + 多层护栏
- 持续目标循环 `runner.ts` 的 `while` 持续轮转：工作 agent 调 `updateGoal(complete)` → `verifier.ts` 验证，失败则回填失败 prompt 继续修（`runner.ts:133`）。
- **验证器阶梯**（4 种）：`file`（路径/包含）、`shell`（退出码===0）、`subagent`（返回 `{ok,findings,requiredFixes}` JSON）、**始终追加 `AUTOMATIC_SEMANTIC_VERIFIER` 语义子 agent（120s 防作弊）**；可选用户确认门。
- **多层 loop-guard**：`maxTurns`、`tokenBudget`、`verificationFailureFingerprint` 失败指纹去重；blocker 用 **bigram 相似度 ≥ 0.4** 判定"同一障碍"，重复 ≥ 3 次转 `blocked`；重复失败驱动 `prompts.ts` **升级策略**（换不同修复思路）。
- **普通 agent loop 无命令自动重试**：`executeShell` 仅把退出码错误文本回传模型，靠 LLM 自我纠正；仅上下文溢出压缩时返回 `{kind:'retry'}` 重跑该轮。

### MiMo-Code —— 独立"冷"judge + compose TDD 闭环
- `/goal` 用**独立 judge 模型**（`session/goal.ts` + `prompt.ts` 的 `goalGate`）：`evaluate` 以 `temperature:0`、`generateObject` **只读 transcript**（含工具调用/结果），返回 `Verdict{ok,impossible,reason}`——它不干活，对主 agent 的"乐观"保持冷（`session/prompt.ts:144-219`）。
- 防过早停止：`goalGate` 每次主循环欲停前调用；不满足则把 judge 的 `reason` 注入 synthetic user turn 重进；`bumpReact` 计数，`MAX_GOAL_REACT=12` 封顶；**juden 出错 fail-open 允许停止**（防卡死）。
- **compose workflow 结构化修复**（`workflow/builtin/compose.js`）：
  - TDD 外循环 `MAX_TDD_ATTEMPTS=3`：implement → runVerify → runDebug；
  - Review 后 fix 循环 `MAX_REVIEW_FIX_ATTEMPTS=2`；
  - **"Iron Law"（铁律）**：无真实验证证据不得声称完成；topo-sort 分批、并行 worktree、runIntegrate 合并。
- **普通 agent loop 命令无自动重试**：bash 工具不重试命令错误；provider 层有 transient 错误 reactive retry，但非命令错误。

### 对比小结
| | x-code-cli | MiMo-Code |
| --- | --- | --- |
| 验证机制 | 4 级验证器阶梯 + 语义子 agent | 独立冷 judge 模型（temperature 0，只读 transcript） |
| 防过早乐观停止 | 验证失败才继续 | judge 防乐观 + fail-open 防卡死 |
| 结构化修复 | `/goal` 通用循环 | compose TDD(3) + review-fix(2) + 铁律 |
| 防卡死护栏 | 指纹去重 + bigram blocker ≥0.4→blocked + 升级策略 | MAX_GOAL_REACT=12 + fail-open |
| 普通命令自动重试 | ❌ | ❌ |

> **判定**：**旗鼓相当，MiMo 略胜一筹**。
> - MiMo 的**独立冷 judge** 是更优雅的"防乐观停止"设计，compose 的 **TDD + 铁律** 让"有真凭实据才算完成"被强制约束，适合定义清晰的修复任务。
> - x-code-cli 的**多层护栏**（失败指纹去重 + bigram 相似度判定同障碍 + 思路升级）在"防止原地打转"上更细腻。
> - 差别主要在风格：MiMo 偏"结构化、有纪律"（对明确任务更稳）；x-code 偏"通用循环 + 强护栏"（对模糊任务更抗造）。整体 MiMo 在自主长程修复上设计更成熟。

---

## 4. 综合评分

| 能力 | x-code-cli | MiMo-Code | 胜方 |
| --- | --- | --- | --- |
| 拉取 GitHub 项目（clone+操作） | 通用 shell + skill | 通用 shell + **真·GitHub/PR 命令** | **MiMo-Code**（略） |
| 跑项目（运行/构建/dev server） | **后台 shell 30 分钟 + 环形缓冲** | 120 秒超时被杀、无后台管理 | **x-code-cli**（明显） |
| 修错误（自动修复循环） | 验证器阶梯 + 多层护栏 | 冷 judge + compose TDD + 铁律 | **MiMo-Code**（略） |
| 端到端跑通"拉→跑→修" | ✅ 三步都能完成 | ⚠️ 卡在"跑项目" | **x-code-cli** |

### 一句话结论
- 如果你是 **"把 GitHub 上的某个项目拉下来、让它跑起来、顺便把报错修掉"** 这种**端到端实操场景**：选 **x-code-cli**——它唯一能后台常驻 dev server，三步一气呵成。
- 如果你要做 **PR/CI 自动化**，或追求 **"有纪律的自主长程修复"（TDD + 验证铁律 + 冷 judge）**：选 **MiMo-Code**——它的 GitHub 原语和 compose 工作流更成熟。
- 单纯比"修错误的内功"，两者都在**生产级**；MiMo 的 judge/铁律设计更亮眼，x-code 的 loop-guard 更抗卡死——**平手偏 MiMo**。

### 共同短板（两者都没做好）
1. **没有"自然语言 clone 专用命令"**，clone 都依赖 LLM 调 shell，URL 识别/分支选择/依赖安装全靠模型临场发挥。
2. **没有项目类型 / dev server / 端口自动探测**，启动命令全靠模型读 `package.json`/`README` 推断。
3. **普通 agent loop 的命令级错误都不自动重试**，都依赖 LLM 自我纠正（重试边界只存在于 goal/compose 这种"任务模式"里）。

> 注：以上均基于两个仓库 `main` 分支源码（x-code-cli 基于 Claude Code 系 SDK，MiMo-Code 基于 OpenCode fork）的实读结论；两者都在快速迭代，具体能力请以实际版本为准。
