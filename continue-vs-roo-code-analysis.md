# Continue vs Roo-Code：附件投喂 + 自动改文件 + 编译验证能力深度对比分析

> **场景**：投喂多个 Java 文件 + XML 配置 + 需求文档（PDF/doc），让模型理解现有代码逻辑，再根据新需求自动生成/修改文件并编译验证，无需手动复制粘贴。
>
> **前提**：两个插件调用同一个模型（DeepSeek V3，即 `deepseek-chat`）。
>
> **分析方法**：基于源码逐行分析，非推测。所有结论附带源码文件路径和行号。

---

## 目录

1. [结论先行](#1-结论先行)
2. [附件处理能力（决定性差异）](#2-附件处理能力决定性差异)
3. [让模型了解现有代码逻辑](#3-让模型了解现有代码逻辑)
4. [工具调用机制对比](#4-工具调用机制对比)
5. [Agent 循环深度剖析](#5-agent-循环深度剖析)
6. [文件操作与 Diff 策略](#6-文件操作与-diff-策略)
7. [命令执行与编译验证](#7-命令执行与编译验证)
8. [自动修复循环机制](#8-自动修复循环机制)
9. [上下文窗口管理](#9-上下文窗口管理)
10. [Auto-approve 无人值守能力](#10-auto-approve-无人值守能力)
11. [DeepSeek V3 兼容性](#11-deepseek-v3-兼容性)
12. [实操建议](#12-实操建议)
13. [附录：关键源码文件索引](#13-附录关键源码文件索引)

---

## 1. 结论先行

**Roo-Code 完胜，且是唯一能完整满足你需求的插件。**

| 能力维度 | Continue | Roo-Code | 胜者 |
|---|---|---|---|
| **读取 PDF 附件** | ❌ 不支持 | ✅ 内置 `pdf-parse` | **Roo-Code** |
| **读取 DOCX 附件** | ❌ 不支持 | ✅ 内置 `mammoth` | **Roo-Code** |
| **模型自主探索项目** | ⚠️ 实验性 | ✅ `list_files`+`search_files`+`codebase_search` | **Roo-Code** |
| **创建新文件** | ✅ `create_new_file` | ✅ `write_to_file`（含创建父目录） | 平手 |
| **修改文件策略** | 4 种工具 | 7 种工具（含 `apply_patch` 增删改） | **Roo-Code** |
| **删除文件** | ⚠️ 只能靠终端 rm | ✅ `apply_patch` 原生支持 | **Roo-Code** |
| **流式 diff 应用** | ✅ 边生成边应用 | ❌ 一次性应用 | **Continue** |
| **执行编译命令** | ✅ `run_terminal_command` | ✅ `execute_command`（含退出码+大输出持久化） | 平手 |
| **编译失败自动修复** | ⚠️ 靠模型自主判断 | ✅ 多层重试机制 | **Roo-Code** |
| **Auto-approve** | ⚠️ 逐个确认 | ✅ 精细配置（只读/写入/命令/白名单） | **Roo-Code** |
| **上下文压缩** | ✅ 增量摘要 | ✅ 非破坏性压缩+可配阈值+回退 | 平手 |
| **DeepSeek V3** | ✅ 白名单支持 | ✅ Handler 直接启用 | 平手 |

**核心差异**：Continue **无法读取 PDF/DOCX 附件**，这是你场景的硬伤——需求文档是 PDF 或 doc，Continue 根本无法解析。Roo-Code 的 `read_file` 工具内置 `pdf-parse` 和 `mammoth`，模型可以自己读取。

---

## 2. 附件处理能力（决定性差异）

这是两个插件最大的分歧点，也是你场景的关键。

### Continue：不支持 PDF/DOCX

源码证据：

**PDF 被显式忽略** — `/workspace/continue/core/indexing/ignore.ts` 第 107 行：
```typescript
// *.pdf 在索引忽略列表中
```

**无任何二进制文档解析库** — 全项目搜索 `pdf-parse`、`pdfjs`、`mammoth`、`docx` 均无匹配。`FileContextProvider`（`core/context/providers/FileContextProvider.ts`）使用 `extras.ide.readFile` 读取文件，对 PDF 二进制文件只能得到乱码。

**意味着**：你用 Continue 时，@file 一个 PDF 需求文档，模型拿到的是乱码。你必须手动把 PDF 内容复制粘贴到对话框。

### Roo-Code：原生支持 PDF/DOCX/XLSX/IPYNB

源码证据 — `/workspace/Roo-Code/src/integrations/misc/extract-text.ts` 第 11-44 行：

```typescript
import pdf from "pdf-parse/lib/pdf-parse"
import mammoth from "mammoth"

async function extractTextFromPDF(filePath: string): Promise<string> {
    const dataBuffer = await fs.readFile(filePath)
    const data = await pdf(dataBuffer)
    return addLineNumbers(data.text)  // 加行号，方便模型引用
}

async function extractTextFromDOCX(filePath: string): Promise<string> {
    const result = await mammoth.extractRawText({ path: filePath })
    return addLineNumbers(result.value)
}

const SUPPORTED_BINARY_FORMATS = {
    ".pdf": extractTextFromPDF,
    ".docx": extractTextFromDOCX,
    ".ipynb": extractTextFromIPYNB,
    ".xlsx": extractTextFromXLSX,
} as const
```

`read_file` 工具（`src/core/tools/ReadFileTool.ts` 第 198 行）检测到二进制文件时，自动调用 `extractTextFromFile` 提取文本，还会 `addLineNumbers` 加上行号。

**意味着**：把需求文档 PDF 放在项目目录里，告诉 Roo-Code "读取 requirements.pdf 了解需求"，模型会自己调用 `read_file` 工具解析。完全不需要手动复制粘贴。

---

## 3. 让模型了解现有代码逻辑

你的场景需要模型理解大量 Java 文件和 XML 配置。

### Continue 的方式

Continue 有 30 个 Context Provider（`core/context/providers/index.ts` 第 43-74 行），主要靠用户主动 @mention：

| Provider | 功能 | 状态 |
|---|---|---|
| `@file` | 手动逐个添加文件 | 稳定 |
| `@tree` | 文件树结构 | 稳定 |
| `@repo-map` | 仓库地图（含函数签名） | **实验性** |
| `@codebase` | 语义搜索 | 稳定 |

Agent 模式下的工具（`core/tools/builtIn.ts`）：

| 工具 | 功能 | 状态 |
|---|---|---|
| `ls` | 列出目录 | 稳定 |
| `grep_search` | 正则搜索（ripgrep） | 稳定 |
| `file_glob_search` | 文件名 glob 搜索 | 稳定 |
| `view_repo_map` | 仓库地图 | **实验性** |
| `view_subdirectory` | 子目录 | **实验性** |

**问题**：Continue 不会自动把项目结构喂给模型，`view_repo_map` 还是实验性功能。

### Roo-Code 的方式

Roo-Code 的 agent 循环中，模型可以自主调用以下工具（`packages/types/src/tool.ts` 第 24-49 行）：

| 工具 | 功能 | 源码 |
|---|---|---|
| `list_files` | 递归列出目录（上限 200 个文件） | `src/core/tools/ListFilesTool.ts` |
| `search_files` | ripgrep 正则搜索（如搜 `@RequestMapping` 找所有接口） | `src/core/tools/SearchFilesTool.ts` |
| `read_file` | 读取具体文件，支持 offset/limit 分段读取大文件 | `src/core/tools/ReadFileTool.ts` |
| `codebase_search` | 基于向量数据库的语义搜索 | `src/core/tools/CodebaseSearchTool.ts` |

**关键优势**：
- Roo-Code 的系统提示词会引导模型先 `list_files` 了解结构，再 `read_file` 读关键文件
- 每轮循环自动附带 environment details（当前打开文件、工作目录、终端状态等）
- `read_file` 支持 `indentation` 模式（基于代码缩进层次提取语义块）和 `slice` 模式（按行范围读取）

---

## 4. 工具调用机制对比

### Continue：双模式工具调用

Continue 同时支持两种工具调用机制（`gui/src/redux/thunks/streamNormalInput.ts` 第 113-119 行）：

```typescript
const useNativeTools = state.config.config.experimental?.onlyUseSystemMessageTools
    ? false
    : modelSupportsNativeTools(selectedChatModel);
const systemToolsFramework = !useNativeTools
    ? new SystemMessageToolCodeblocksFramework()
    : undefined;
```

**机制一：Native Tool Calling** — 对支持 function calling 的模型，使用 OpenAI 标准 `tools` 参数

**机制二：System Message Tools** — 对不支持的模型，将工具定义注入 system message，从文本输出中解析 ```` ```tool ... ``` ```` 代码块（`core/tools/systemMessageTools/interceptSystemToolCalls.ts` 第 24-119 行）

**内置工具列表**（`core/tools/builtIn.ts` 第 1-24 行）：

| 工具名 | 功能 | 只读 |
|---|---|---|
| `read_file` | 读取文件 | 是 |
| `read_file_range` | 读取指定行范围 | 是 |
| `edit_existing_file` | 编辑现有文件（diff方式） | 否 |
| `single_find_and_replace` | 单次查找替换 | 否 |
| `multi_edit` | 多次查找替换 | 否 |
| `create_new_file` | 创建新文件 | 否 |
| `run_terminal_command` | 执行终端命令 | 否 |
| `grep_search` | 正则搜索 | 是 |
| `file_glob_search` | 文件名搜索 | 是 |
| `search_web` | 网页搜索 | 是 |
| `ls` | 列出目录 | 是 |
| `view_repo_map` | 仓库地图（实验性） | 是 |
| `fetch_url_content` | 获取 URL 内容 | 是 |
| `codebase` | 代码库语义搜索 | 是 |

### Roo-Code：纯 Native Tool Calling

Roo-Code **只支持 native tool calling**，已完全废弃 XML 工具调用（`src/core/tools/BaseTool.ts` 第 143-148 行）：

```typescript
if (paramsText.includes("<") && paramsText.includes(">")) {
    throw new Error(
        "XML tool calls are no longer supported. Use native tool calling (nativeArgs) instead.",
    )
}
```

**内置工具列表**（`packages/types/src/tool.ts` 第 24-49 行），共 24 个：

```
execute_command, read_file, read_command_output, write_to_file,
apply_diff, edit, search_and_replace, search_replace, edit_file,
apply_patch, search_files, list_files, use_mcp_tool,
access_mcp_resource, ask_followup_question, attempt_completion,
switch_mode, new_task, codebase_search, update_todo_list,
run_slash_command, skill, generate_image, custom_tool
```

**5 个内置模式**（`packages/types/src/mode.ts` 第 168-227 行）决定可用工具集：

| 模式 | 工具组 | 说明 |
|---|---|---|
| `code` | read + edit + command + mcp | 全能编码模式 |
| `architect` | read + edit(仅.md) + mcp | 规划设计 |
| `ask` | read + mcp | 只读问答 |
| `debug` | read + edit + command + mcp | 调试模式 |
| `orchestrator` | 仅 always-available | 编排器，通过 new_task 委托 |

---

## 5. Agent 循环深度剖析

### Continue 的 Agent 循环

#### GUI 端：Redux thunk 递归调用

核心链路（`gui/src/redux/thunks/`）：

```
streamResponseThunk (入口)
  └─> streamNormalInput (流式获取 LLM 响应)
        ├─> 检测 toolCalls（从 Redux state 提取）
        ├─> callToolById (执行工具)
        └─> streamResponseAfterToolCall (工具完成后)
              └─> streamNormalInput({ depth: depth + 1 }) (递归！)
```

**深度限制** — `streamNormalInput.ts` 第 82-89 行：
```typescript
if (process.env.NODE_ENV === "test" && depth > 50) {
    throw new Error(`Max stream depth of ${50} reached in test`);
}
```
⚠️ **深度限制 50 仅在测试环境生效**，生产环境无硬性轮次限制，靠模型的 `attempt_completion` 或无 tool call 输出自然终止。

**并行工具处理** — `streamResponseAfterToolCall.ts` 第 17-35 行：
```typescript
function areAllToolsDoneStreaming(assistantMessage, ...): boolean {
    // 只有当所有 tool calls 都完成后才递归
}
```

#### CLI 端：while(true) 循环

`extensions/cli/src/stream/streamChatResponse.ts` 第 443 行：

```typescript
while (true) {
    const { content, toolCalls, shouldContinue, usage } =
        await processStreamingResponse({...});
    // 处理 tool calls...
    if (!shouldContinue && !shouldAutoContinue) {
        break;  // 退出条件：无工具调用且不需要自动续接
    }
}
```

`shouldContinue` = `validToolCalls.length > 0`（第 416 行），即有工具调用时继续循环。

### Roo-Code 的 Agent 循环

#### 栈式递归（非函数递归）

`src/core/task/Task.ts` 第 2461-2472 行：

```typescript
public async recursivelyMakeClineRequests(userContent, includeFileDetails) {
    interface StackItem {
        userContent: Anthropic.Messages.ContentBlockParam[]
        includeFileDetails: boolean
        retryAttempt?: number
    }
    const stack: StackItem[] = [{ userContent, includeFileDetails, retryAttempt: 0 }]

    while (stack.length > 0) {
        const currentItem = stack.pop()
        // 构建 API 请求 → 流式调用 → presentAssistantMessage 执行工具
        // 工具结果推入栈继续循环
        if (this.userMessageContent.length > 0) {
            stack.push({ userContent: [...this.userMessageContent], ... })
        }
    }
}
```

#### 流式提前执行工具（Roo-Code 独特设计）

Roo-Code 在流式响应**还在传输时**就开始执行已完成的 tool_use 块：

```typescript
// Task.ts 第 2853-2855 行 (tool_call_start 时)
this.assistantMessageContent.push(partialToolUse)
this.userMessageContentReady = false
presentAssistantMessage(this)  // 立即尝试执行
```

`presentAssistantMessage`（`src/core/assistant-message/presentAssistantMessage.ts`）使用锁机制防止并发（第 64-70 行）：
```typescript
if (cline.presentAssistantMessageLocked) {
    cline.presentAssistantMessageHasPendingUpdates = true
    return
}
cline.presentAssistantMessageLocked = true
```

如果当前块还是 partial，则不执行（第 913 行 `!block.partial` 判断），等待下一次调用。

#### didAlreadyUseTool 中断流

当第一个工具执行后，中断剩余流式输出（`presentAssistantMessage.ts` 第 277-279 行）：
```typescript
case "text": {
    if (cline.didRejectTool || cline.didAlreadyUseTool) {
        break  // 跳过后续文本块
    }
```

这相当于"消费"掉剩余的流式内容，直接进入下一轮——**一次只执行一个工具**，避免并行工具冲突。

### 循环机制对比

| 特性 | Continue | Roo-Code |
|---|---|---|
| **循环方式** | GUI: thunk 递归；CLI: while(true) | 显式栈结构 |
| **深度限制** | 50（仅测试环境） | 无硬性限制，靠 consecutiveMistakeCount |
| **流式执行工具** | 否（等流结束） | ✅ 是（边传输边执行） |
| **并行工具** | ✅ 支持同时多个只读工具 | ❌ 一次一个（didAlreadyUseTool 中断） |
| **工具执行时机** | 流结束后统一执行 | 流中遇到完整的 tool_use 立即执行 |

---

## 6. 文件操作与 Diff 策略

### 文件操作工具对比

| 操作 | Continue 工具 | Roo-Code 工具 |
|---|---|---|
| 创建新文件 | `create_new_file` | `write_to_file`（含创建父目录） |
| 整文件覆盖 | `create_new_file`（已存在则报错） | `write_to_file`（直接覆盖） |
| 局部修改 | `edit_existing_file`, `single_find_and_replace`, `multi_edit` | `apply_diff`, `edit`, `search_replace`, `edit_file` |
| 删除文件 | ❌ 无专用工具（靠 `run_terminal_command` rm） | ✅ `apply_patch`（`*** Delete File: ***`，调用 `fs.unlink`） |
| 删除目录 | ❌ | ❌（需通过 `execute_command` 执行 `rm -rf`） |

### Continue 的 Diff 策略

#### 流式 diff — `core/edit/streamDiffLines.ts` 第 159-189 行

```typescript
const completion = recursiveStream(llm, abortController, type, prompt, prediction);
let lines = streamLines(completion);       // token 流 → 行流
lines = filterEnglishLinesAtStart(lines);  // 过滤开头英文解释
lines = filterCodeBlockLines(lines);       // 过滤代码块标记
lines = stopAtLines(lines, () => {});
let diffLines = streamDiff(oldLines, lines); // Myers diff 生成 DiffLine
for await (const diffLine of diffLines) {
    yield diffLine;  // 逐行 yield
}
```

**特点**：纯流式管道，边生成边输出 diff，用户可以实时看到变更。

#### Lazy Apply（AST-based）— `core/edit/lazy/deterministic.ts`

模型可以用 `// ... existing code ...` 代替不需要修改的代码段：

```typescript
const LAZY_COMMENT_REGEX = /\.{3}\s*(.+?)\s*\.{3}/;
const REMOVAL_PERCENTAGE_THRESHOLD = 0.3;  // 超过 30% 行被删除则拒绝
```

流程：tree-sitter 解析 AST → `findLazyBlockReplacements` 匹配 lazy block → `reconstructNewFile` 替换为旧代码 → Myers diff 生成 DiffLine

#### 查找替换 — `core/edit/searchAndReplace/performReplace.ts` 第 85-117 行

匹配策略按优先级链式尝试：
1. `exactMatch` — 精确匹配
2. `trimmedMatch` — trim 后匹配
3. `caseInsensitiveMatch` — 大小写不敏感
4. `whitespaceIgnoredMatch` — 忽略所有空白后匹配

### Roo-Code 的 Diff 策略

#### MultiSearchReplaceDiffStrategy — `src/core/diff/strategies/multi-search-replace.ts`

目前唯一的 diff 策略（`DiffStrategy` 接口定义在 `src/shared/tools.ts` 第 362-385 行）：

```typescript
export class MultiSearchReplaceDiffStrategy implements DiffStrategy {
    private fuzzyThreshold: number   // 默认 1.0（精确匹配）
    private bufferLines: number      // 默认 40
    getName(): string { return "MultiSearchReplace" }
}
```

格式使用类似 git merge conflict 的标记：
```
<<<<<<< SEARCH
:start_line:5
-------
[搜索内容]
=======
[替换内容]
>>>>>>> REPLACE
```

#### 模糊匹配算法 — `multi-search-replace.ts` 第 11-73 行

```typescript
function getSimilarity(original: string, search: string): number {
    const normalizedOriginal = normalizeString(original);
    const normalizedSearch = normalizeString(search);
    if (normalizedOriginal === normalizedSearch) return 1;
    const dist = distance(normalizedOriginal, normalizedSearch);  // Levenshtein
    return 1 - dist / Math.max(normalizedOriginal.length, normalizedSearch.length);
}
```

**Middle-out 搜索**（第 37-73 行）：从中间向两边扩展搜索，在 `bufferLines`（40行）范围内找最高相似度的匹配。

匹配流程：
1. 先尝试 `startLine` 指定位置的精确匹配
2. 不满足 `fuzzyThreshold` 时，在 40 行范围内做 middle-out fuzzy search
3. 仍不匹配则激进地去掉行号后重新搜索
4. 匹配成功后替换，记录 `delta` 调整后续 diff 的行号

### Diff 策略对比

| 特性 | Continue | Roo-Code |
|---|---|---|
| **流式 diff** | ✅ 边生成边应用 | ❌ 一次性应用 |
| **Lazy apply** | ✅ AST-based（tree-sitter） | ❌ 无 |
| **Unified diff** | ✅ `applyUnifiedDiff` | ❌ |
| **模糊匹配** | 多策略链（4级） | Levenshtein + middle-out |
| **策略可插拔** | ❌ 各策略独立 | ✅ `DiffStrategy` 接口（但仅 1 个实现） |

---

## 7. 命令执行与编译验证

### Continue：`run_terminal_command`

源码：`core/tools/implementations/runTerminalCommand.ts` 第 109-569 行

- 用 `child_process.spawn` 执行
- 支持前台（`waitForCompletion: true`，默认 2 分钟超时）/后台执行
- 流式输出（`onPartialOutput` 回调）
- 通过 `@continuedev/terminal-security` 包评估命令安全性
- 默认策略：`allowedWithPermission`（需用户批准）

### Roo-Code：`execute_command`

源码：`src/core/tools/ExecuteCommandTool.ts`

工具 schema（`src/core/prompts/tools/native-tools/execute_command.ts`）：
```typescript
parameters: {
    command: { type: "string", description: "Shell command to execute" },
    cwd: { type: ["string", "null"], description: "Optional working directory" },
    timeout: { type: ["number", "null"], description: "Timeout in seconds" },
}
```

**执行后返回给模型**（`ExecuteCommandTool.ts` 第 469-505 行）：
```typescript
return [
    false,
    `Command executed in terminal within working directory '${currentWorkingDir}'. ${exitStatus}\nOutput:\n${result}`,
]
```

其中 `exitStatus` 包含退出码（第 490-496 行）：
```typescript
if (exitDetails.exitCode !== 0) {
    exitStatus += "Command execution was not successful, inspect the cause and adjust as needed.\n"
}
exitStatus += `Exit code: ${exitDetails.exitCode}`
```

**大输出处理**：通过 `OutputInterceptor` 持久化到磁盘，返回 artifact ID，模型可用 `read_command_output` 工具分页读取或搜索。

### 对比

| 特性 | Continue | Roo-Code |
|---|---|---|
| 执行方式 | `child_process.spawn` | 集成终端 / `execa` |
| 退出码反馈 | ✅ | ✅（明确告知模型是否失败） |
| 大输出处理 | 流式截断 | 持久化到磁盘 + `read_command_output` 分页 |
| 安全评估 | `@continuedev/terminal-security` | `allowedCommands`/`deniedCommands` 白名单 |

---

## 8. 自动修复循环机制

你的核心需求：**编译成功，保证引用没错**。

### Continue：靠模型自主判断

Continue **没有专门的编译验证循环机制**。搜索 `compile.*verify`、`auto.*compile`、`build.*loop` 等关键词均无匹配。

Agent 循环中 LLM 可以自主地：
1. 调用 `run_terminal_command` 执行编译
2. 读取编译错误输出
3. 调用 `edit_existing_file` 或 `multi_edit` 修复
4. 再次编译验证

但这不是硬编码的机制，完全依赖 LLM 的判断力。系统消息中没有强制性的编译验证指令。

### Roo-Code：多层自动重试

源码：`src/core/task/Task.ts`

#### 1. consecutiveMistakeCount（连续错误计数）

第 2483-2501 行：
```typescript
if (this.consecutiveMistakeLimit > 0 && this.consecutiveMistakeCount >= this.consecutiveMistakeLimit) {
    const { response, text, images } = await this.ask(
        "mistake_limit_reached",
        t("common:errors.mistake_limit_guidance"),
    )
    this.consecutiveMistakeCount = 0  // 重置
}
```

工具执行失败时计数递增，达到上限时暂停询问用户。用户可提供反馈让模型调整。

#### 2. 指数退避重试

第 3166-3197 行：
```typescript
if (stateForBackoff?.autoApprovalEnabled) {
    await this.backoffAndAnnounce(currentItem.retryAttempt ?? 0, error)
    stack.push({
        userContent: currentUserContent,
        retryAttempt: (currentItem.retryAttempt ?? 0) + 1,
    })
    continue
}
```

`backoffAndAnnounce`（第 4268-4327 行）：基础延迟 5 秒，`2^retryAttempt` 增长，上限 `MAX_EXPONENTIAL_BACKOFF_SECONDS`，处理 429 限流的 RetryInfo。

#### 3. 空响应重试

第 3524-3613 行：模型返回空消息时，前 2 次静默重试（grace retry），之后才报错。

#### 4. noToolsUsed 推进

第 3485-3500 行：
```typescript
// 模型不使用工具时，推送提示消息推动模型继续工作
nextUserContent = [{ type: "text", text: formatResponse.noToolsUsed() }]
```

#### 5. ToolRepetitionDetector

`src/core/tools/ToolRepetitionDetector.ts`：防止模型陷入重复调用同一工具的死循环。

### 对比

| 特性 | Continue | Roo-Code |
|---|---|---|
| 编译失败自动修复 | ⚠️ 靠模型自主判断 | ✅ 多层机制保障 |
| 连续错误计数 | ❌ | ✅ consecutiveMistakeCount |
| 指数退避重试 | ❌ | ✅ 5s × 2^n |
| 空响应重试 | ❌ | ✅ 前 2 次静默重试 |
| 死循环检测 | ❌ | ✅ ToolRepetitionDetector |
| 无工具推进 | ❌ | ✅ noToolsUsed |

---

## 9. 上下文窗口管理

### Continue：增量摘要

源码：`core/util/conversationCompaction.ts` + CLI 端 `extensions/cli/src/compaction.ts`

**触发阈值**（`compaction.ts` 第 19-20 行）：
```typescript
export const AUTO_COMPACT_BUFFER_CAP = 15_000;
export const AUTO_COMPACT_BUFFER_RATIO = 0.8;
```

触发条件：`inputTokens >= contextLimit - maxTokens - buffer`，其中 `buffer = min(maxTokens, 0.2*(contextLimit-maxTokens), 15000)`。

**摘要生成**（`conversationCompaction.ts` 第 85-96 行）：
```typescript
const compactionPrompt = {
    role: "user",
    content: "Create a comprehensive summary of this conversation that captures all essential information..."
};
const response = await currentModel.chat([...messages, compactionPrompt], ...);
```

**特点**：
- 增量摘要：只压缩上次摘要之后的消息（第 41-49 行）
- 为孤立 toolCall 插入 `"Tool cancelled"` tool 消息（第 54-74 行）
- 摘要写入消息的 `conversationSummary` 字段，不删除原始消息

三处触发点（`streamChatResponse.compactionHelpers.ts`）：
1. Pre-API compaction（每次 API 请求前）
2. Post-tool validation（工具执行后强制压缩）
3. Normal auto-compaction（80% 阈值触发）

### Roo-Code：非破坏性压缩 + 可配阈值

源码：`src/core/context-management/index.ts` + `src/core/condense/index.ts`

**触发阈值**（`context-management/index.ts` 第 24、157-192 行）：
```typescript
export const TOKEN_BUFFER_PERCENTAGE = 0.1

export function willManageContext({...}): boolean {
    const allowedTokens = contextWindow * (1 - TOKEN_BUFFER_PERCENTAGE) - reservedTokens
    const contextPercent = (100 * prevContextTokens) / contextWindow
    return contextPercent >= effectiveThreshold || prevContextTokens > allowedTokens
}
```

阈值可配（`condense/index.ts` 第 109-110 行）：
```typescript
export const MIN_CONDENSE_THRESHOLD = 5
export const MAX_CONDENSE_THRESHOLD = 100
```

**tool_use/tool_result 转文本**（`condense/index.ts` 第 19-59 行）：
```typescript
export function toolUseToText(block): string {
    // [Tool Use: write_to_file]\npath: Xxx.java\ncontent: ...
    return `[Tool Use: ${block.name}]\n${input}`
}

export function toolResultToText(block): string {
    // [Tool Result]\n文件已创建...
    return `[Tool Result${errorSuffix}]\n${contentText}`
}
```

转换原因：某些 provider 要求 tool blocks 存在时必须传 `tools` 参数，转为文本后可以不带 tools 参数发送摘要请求。

**非破坏性存储**（`condense/index.ts` 第 451-480 行）：
```typescript
const summaryMessage: ApiMessage = {
    role: "user",
    content: summaryContent,
    isSummary: true,
    condenseId,
}
// 原始消息打 condenseParent 标记保留，不删除
const newMessages = messages.map((msg) => {
    if (!msg.condenseParent) return { ...msg, condenseParent: condenseId }
    return msg
})
newMessages.push(summaryMessage)
```

`getEffectiveApiHistory` 发送给 API 时过滤掉带 `condenseParent` 的消息，只保留 summary 之后的消息。原始消息保留在存储中，支持 rewind 回溯。

**额外保留**：
- `injectSyntheticToolResults`（第 132 行）：为孤立 tool_use 注入合成 tool_result
- `extractCommandBlocks`（第 185 行）：提取 `<command>` 块跨压缩保留
- `generateFoldedFileContext`：保留已读文件的折叠代码上下文

### 对比

| 特性 | Continue | Roo-Code |
|---|---|---|
| 触发阈值 | 固定公式（buffer 上限 15000） | 可配百分比（5-100%） |
| 摘要生成 | 用当前模型 chat 生成 | 用 apiHandler.createMessage 流式生成 |
| tool_use 处理 | 插入 "Tool cancelled" | 转为文本 `[Tool Use: name]` |
| 存储方式 | 摘要写入消息字段 | 独立 summary 消息 + 原始消息标记保留 |
| 非破坏性 | 原始消息保留 | ✅ 完全非破坏，支持 rewind |
| 回退机制 | 压缩失败 throw error | 回退到 sliding window truncation |
| 额外保留 | 无 | command blocks + folded file context |

---

## 10. Auto-approve 无人值守能力

你的场景需要"不用我再复制粘贴，直接修改"——工具执行最好不需要逐个手动确认。

### Continue 的权限系统

每个工具有 `defaultToolPolicy`：`allowedWithoutPermission` 或 `allowedWithPermission`。`run_terminal_command` 有额外的 `evaluateTerminalCommandSecurity` 安全评估。

**但**没有全局的 auto-approve 配置面板，更像是一次性批准。

### Roo-Code 的 auto-approve 系统

源码：`src/core/auto-approval/index.ts`

`Task.ask()` 方法（`Task.ts` 第 1219 行）在每个工具执行前调用 `checkAutoApproval()`（第 1321 行）：

```typescript
const approval = await checkAutoApproval({ state, ask: type, text, isProtected })
if (approval.decision === "approve") {
    this.approveAsk()  // 自动批准
} else if (approval.decision === "deny") {
    this.denyAsk()
}
```

**精细配置项**（`auto-approval/index.ts` 第 17-35 行）：

| 配置项 | 作用 |
|---|---|
| `autoApprovalEnabled` | 总开关 |
| `alwaysAllowReadOnly` | 自动批准 read_file/list_files/search_files |
| `alwaysAllowReadOnlyOutsideWorkspace` | 允许只读操作访问工作区外 |
| `alwaysAllowWrite` | 自动批准文件写入 |
| `alwaysAllowWriteOutsideWorkspace` | 允许写操作访问工作区外 |
| `alwaysAllowWriteProtected` | 允许写受保护文件 |
| `alwaysAllowExecute` | 自动批准命令执行 |
| `allowedCommands` | 命令白名单（前缀匹配，如 `javac *`、`java *`） |
| `deniedCommands` | 命令黑名单 |
| `alwaysAllowMcp` | 自动批准 MCP 工具 |
| `alwaysAllowModeSwitch` | 自动批准模式切换 |
| `alwaysAllowSubtasks` | 自动批准子任务 |
| `alwaysAllowFollowupQuestions` | 自动批准追问（带超时） |

**命令执行的精细控制**（`auto-approval/index.ts` 第 114-130 行）：即使 `alwaysAllowExecute` 开启，仍检查 `allowedCommands`/`deniedCommands`，返回 `auto_approve`/`auto_deny`/`ask`。

**启用 auto-approve 后的流式失败自动重试**（`Task.ts` 第 3174 行）：若启用则自动指数退避重试，无需用户介入。

---

## 11. DeepSeek V3 兼容性

两者都支持 DeepSeek V3 的 native tool calling。

### Continue

`/workspace/continue/core/llm/toolSupport.ts` 第 256-269 行：

```typescript
deepseek: (model) => {
    const lower = model.toLowerCase();
    if (
        lower === "deepseek-reasoner" ||
        lower === "deepseek-chat" ||
        lower.startsWith("deepseek-coder")
    ) {
        return true;
    }
    return false;
},
```

`Deepseek.ts` 继承自 OpenAI，默认走 OpenAI 的 tool calling 流程。

### Roo-Code

`/workspace/Roo-Code/src/api/providers/deepseek.ts` 第 79-81 行：

```typescript
tools: this.convertToolsForOpenAI(metadata?.tools),
tool_choice: metadata?.tool_choice,
parallel_tool_calls: metadata?.parallelToolCalls ?? true,  // 默认开启并行工具
```

模型配置（`packages/types/src/providers/deepseek.ts`）：

| 模型 | contextWindow | supportsImages | 说明 |
|---|---|---|---|
| `deepseek-chat` | 128,000 | false | V3.2 非思考模式，支持 tool calls |
| `deepseek-reasoner` | 128,000 | false | V3.2 思考模式，支持 tool calls |

**注意**：两个插件都标注 DeepSeek `supportsImages: false`，不能用 DeepSeek 处理图片附件（但 PDF/DOCX 文本提取不受影响）。

---

## 12. 实操建议

### 用 Roo-Code 的完整工作流

1. **准备项目目录**：把所有 Java 文件、XML 配置、需求文档 PDF 放在同一个目录

2. **配置 DeepSeek V3**：
   - Provider 选 DeepSeek
   - Model 选 `deepseek-chat`
   - 上下文窗口 128K，足够容纳多个 Java 文件 + XML + 需求文档

3. **开启 Auto-approve**：
   ```
   alwaysAllowReadOnly = true        # 让模型自由读文件
   alwaysAllowWrite = true           # 让模型自由改文件
   alwaysAllowExecute = true         # 让模型自由执行编译命令
   allowedCommands = ["javac *", "java *", "mvn *", "gradle *"]  # 限制只允许编译相关命令
   ```

4. **发送需求**（示例提示词）：
   ```
   请先 list_files 了解项目结构，然后 read_file 读取需求文档 requirements.pdf。
   阅读后，理解现有的 Java 接口逻辑和 XML 配置，根据需求文档实现新功能。
   完成后用 javac 编译验证，如有错误自动修复，直到编译通过。
   ```

5. **Roo-Code 自主执行链**：
   ```
   list_files → 了解项目骨架
   read_file requirements.pdf → 自动提取 PDF 文本（pdf-parse）
   read_file XxxController.java → 读取相关 Java 文件
   read_file XxxMapper.xml → 读取 XML 配置
   write_to_file / apply_diff → 创建新文件或修改现有文件
   execute_command "javac ..." → 编译验证
   ↓ 编译失败
   读取错误输出 → edit 修复 → 再编译（自动循环）
   ↓ 编译通过
   attempt_completion → 任务完成
   ```

### Continue 能做到什么程度

如果你坚持用 Continue：
- 需求文档 PDF **必须手动复制粘贴**到对话框（Continue 无法解析 PDF）
- Java 文件和 XML 可以 @file 逐个添加，或让模型用 `grep_search` 搜索
- 编译可以用 `run_terminal_command`，但每次执行需要手动批准
- 编译失败后的修复循环靠模型自主判断，没有 Roo-Code 的多层重试机制稳健

**一句话**：Continue 能做，但体验差很多——PDF 附件是硬伤，auto-approve 也不够精细。

---

## 13. 附录：关键源码文件索引

### Continue

| 能力 | 源码位置 |
|---|---|
| 工具定义枚举 | `core/tools/builtIn.ts` 第 1-24 行 |
| 工具注册 | `core/tools/index.ts` 第 6-51 行 |
| 工具调用入口 | `core/tools/callTool.ts` 第 235-280 行 |
| DeepSeek 工具支持 | `core/llm/toolSupport.ts` 第 256-269 行 |
| PDF 索引忽略 | `core/indexing/ignore.ts` 第 107 行 |
| Agent 循环（GUI） | `gui/src/redux/thunks/streamNormalInput.ts` 第 72-398 行 |
| Agent 循环（CLI） | `extensions/cli/src/stream/streamChatResponse.ts` 第 443 行 |
| 工具结果递归 | `gui/src/redux/thunks/streamResponseAfterToolCall.ts` 第 56-84 行 |
| 深度限制 | `gui/src/redux/thunks/streamNormalInput.ts` 第 82-89 行 |
| 流式 diff | `core/edit/streamDiffLines.ts` 第 159-189 行 |
| Lazy Apply | `core/edit/lazy/deterministic.ts` |
| Unified diff | `core/edit/lazy/unifiedDiffApply.ts` 第 43-93 行 |
| 查找替换 | `core/edit/searchAndReplace/performReplace.ts` 第 85-117 行 |
| 上下文压缩 | `core/util/conversationCompaction.ts` |
| 压缩阈值（CLI） | `extensions/cli/src/compaction.ts` 第 19-20 行 |
| System Message Tools | `core/tools/systemMessageTools/interceptSystemToolCalls.ts` 第 24-119 行 |
| 30 个 Context Provider | `core/context/providers/index.ts` 第 43-74 行 |

### Roo-Code

| 能力 | 源码位置 |
|---|---|
| 工具名称枚举 | `packages/types/src/tool.ts` 第 24-49 行 |
| 工具执行入口 | `src/core/assistant-message/presentAssistantMessage.ts` 第 651 行 |
| 工具分发锁机制 | `src/core/assistant-message/presentAssistantMessage.ts` 第 64-70 行 |
| Agent 循环（栈式） | `src/core/task/Task.ts` `recursivelyMakeClineRequests()` 第 2461 行 |
| 流式提前执行工具 | `src/core/task/Task.ts` 第 2853-2855 行 |
| didAlreadyUseTool 中断 | `src/core/assistant-message/presentAssistantMessage.ts` 第 277-279 行 |
| PDF/DOCX 文本提取 | `src/integrations/misc/extract-text.ts` 第 11-44 行 |
| Auto-approve 系统 | `src/core/auto-approval/index.ts` |
| Auto-approve 检查 | `src/core/task/Task.ts` 第 1219、1321 行 |
| 上下文管理 | `src/core/context-management/index.ts` |
| 上下文压缩 | `src/core/condense/index.ts` |
| 压缩阈值配置 | `src/core/condense/index.ts` 第 109-110 行 |
| tool_use 转文本 | `src/core/condense/index.ts` 第 19-59 行 |
| 非破坏性压缩存储 | `src/core/condense/index.ts` 第 451-480 行 |
| DeepSeek Handler | `src/api/providers/deepseek.ts` 第 79-81 行 |
| DeepSeek 模型配置 | `packages/types/src/providers/deepseek.ts` 第 11-35 行 |
| 文件写入工具 | `src/core/tools/WriteToFileTool.ts` |
| 命令执行工具 | `src/core/tools/ExecuteCommandTool.ts` |
| 命令输出反馈 | `src/core/tools/ExecuteCommandTool.ts` 第 469-505 行 |
| 大输出持久化 | `src/core/tools/ReadCommandOutputTool.ts` |
| consecutiveMistakeCount | `src/core/task/Task.ts` 第 2483-2501 行 |
| 指数退避重试 | `src/core/task/Task.ts` 第 3166-3197、4268-4327 行 |
| 空响应重试 | `src/core/task/Task.ts` 第 3524-3613 行 |
| noToolsUsed 推进 | `src/core/task/Task.ts` 第 3485-3500 行 |
| 死循环检测 | `src/core/tools/ToolRepetitionDetector.ts` |
| Diff 策略接口 | `src/shared/tools.ts` 第 362-385 行 |
| MultiSearchReplace 策略 | `src/core/diff/strategies/multi-search-replace.ts` |
| 模糊匹配算法 | `src/core/diff/strategies/multi-search-replace.ts` 第 11-73 行 |
| 5 个内置模式 | `packages/types/src/mode.ts` 第 168-227 行 |
| 工具分组配置 | `src/shared/tools.ts` 第 296-314 行 |
| XML 工具调用废弃 | `src/core/tools/BaseTool.ts` 第 143-148 行 |
| list_files 工具 | `src/core/tools/ListFilesTool.ts` |
| search_files 工具 | `src/core/tools/SearchFilesTool.ts` |
| codebase_search 工具 | `src/core/tools/CodebaseSearchTool.ts` |
| apply_patch（含删除） | `src/core/tools/ApplyPatchTool.ts` 第 26、235-288 行 |

---

*文档版本: v2.0 | 生成时间: 2026-07-18 | 基于源码逐行分析，非推测*
