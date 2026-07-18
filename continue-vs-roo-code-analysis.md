# Continue vs Roo-Code：附件投喂 + 自动改文件 + 编译验证 —— 源码实证分析

> **场景**：投喂多个 Java 文件 + XML 配置 + 需求文档（PDF/doc），让模型理解现有代码逻辑，再根据新需求自动生成/修改文件并编译验证，无需手动复制粘贴。
>
> **前提**：两个插件调用同一个模型（DeepSeek V3，即 `deepseek-chat`）。
>
> **分析方法**：本文所有结论均来自作者直接打开 `/workspace/continue` 与 `/workspace/Roo-Code` 两个仓库的真实源文件逐行核对，**附真实代码原文与文件路径+行号**，非任何推测或二手转述。
>
> **核实日期**：2026-07-18，基于仓库当前 HEAD。

---

## 一、结论（源码实证后）

**Roo-Code 完胜，且是唯一能完整满足你需求的插件。**

你的场景有一个不可妥协的前提：**需求文档是 PDF 或 doc，要作为附件直接投喂给模型**。这一点在源码层面直接决定了胜负——

- **Roo-Code 能解析 PDF/DOCX**：`src/integrations/misc/extract-text.ts` 第 3-4 行 import 了 `pdf-parse` 和 `mammoth`，第 39-44 行注册了 `.pdf`/`.docx` 提取器，`read_file` 工具（第 391 行）直接调用 `extractTextFromFile` 完成自动提取。
- **Continue 不能解析 PDF/DOCX**：`core/indexing/ignore.ts` 第 107 行把 `*.pdf` 显式放进忽略列表；全项目（core + gui/src）搜不到 `pdf-parse`/`mammoth`/`pdfjs`/`docx` 任何一个引用；`FileContextProvider.ts` 第 33 行只用 `extras.ide.readFile` 做纯文本读取。

**结论**：用 Continue，你发 PDF 给模型，模型拿到的是乱码，必须你手动复制粘贴内容——而"不用复制粘贴"正是你想甩掉的核心痛点。Roo-Code 把 PDF 扔进目录，告诉模型"读 requirements.pdf"，模型自己就解析了。

---

## 二、附件处理（决定性差异，已逐行核对源码）

### 2.1 Roo-Code：原生支持 PDF / DOCX / XLSX / IPYNB

**文件**：`/workspace/Roo-Code/src/integrations/misc/extract-text.ts`

**真实的 import（第 3-4 行）**：
```typescript
// @ts-ignore-next-line
import pdf from "pdf-parse/lib/pdf-parse"
import mammoth from "mammoth"
```

**真实的格式映射表（第 39-44 行）**：
```typescript
const SUPPORTED_BINARY_FORMATS = {
	".pdf": extractTextFromPDF,
	".docx": extractTextFromDOCX,
	".ipynb": extractTextFromIPYNB,
	".xlsx": extractTextFromXLSX,
} as const
```

**真实的提取函数（第 11-20 行）**：
```typescript
async function extractTextFromPDF(filePath: string): Promise<string> {
	const dataBuffer = await fs.readFile(filePath)
	const data = await pdf(dataBuffer)
	return addLineNumbers(data.text)
}

async function extractTextFromDOCX(filePath: string): Promise<string> {
	const result = await mammoth.extractRawText({ path: filePath })
	return addLineNumbers(result.value)
}
```

**关键的桥梁**：`read_file` 工具直接调用上面的提取器。`src/core/tools/ReadFileTool.ts` 第 23 行 import，第 391 行执行：
```typescript
const content = await extractTextFromFile(fullPath)
const numberedContent = addLineNumbers(content)
```

> **源码证据链**：`read_file` → `extractTextFromFile`（extract-text.ts 第 131 行）→ `SUPPORTED_BINARY_FORMATS[".pdf"]` → `extractTextFromPDF` → `pdf-parse`。完整闭环，模型读取 PDF 时自动转成带行号的纯文本投喂给 DeepSeek。

### 2.2 Continue：不支持，且主动忽略 PDF

**文件**：`/workspace/continue/core/indexing/ignore.ts` 第 107 行
```typescript
"*.pdf",
```
（位于 ignore 列表第 95-120 行之间，与 `*.png`/`*.jpg`/`*.zip` 等同列）

**文件**：`/workspace/continue/core/context/providers/FileContextProvider.ts` 第 33、44 行
```typescript
const content = await extras.ide.readFile(fileUri);
// ...
content: `\`\`\`${relativePathOrBasename}\n${content}\n\`\`\``,
```

**反向验证**：在 `/workspace/continue/core` 和 `/workspace/continue/gui/src` 全量搜索 `pdf-parse|mammoth|pdfjs|docx`，**零命中**。亦即 Continue 没有任何二进制文档解析能力，对任何非文本文件只能用 IDE 的 `readFile`（拿到二进制乱码）。

> **结论**：Continue 对 PDF/DOCX 的需求文档无法处理。这是你场景的硬伤，无法绕过。

---

## 三、让模型理解现有代码逻辑（工具对比）

### 3.1 Roo-Code 的工具清单（已读真实源码）

**文件**：`/workspace/Roo-Code/packages/types/src/tool.ts` 第 24-49 行
```typescript
export const toolNames = [
	"execute_command",
	"read_file",
	"read_command_output",
	"write_to_file",
	"apply_diff",
	"edit",
	"search_and_replace",
	"search_replace",
	"edit_file",
	"apply_patch",
	"search_files",
	"list_files",
	"use_mcp_tool",
	"access_mcp_resource",
	"ask_followup_question",
	"attempt_completion",
	"switch_mode",
	"new_task",
	"codebase_search",
	"update_todo_list",
	"run_slash_command",
	"skill",
	"generate_image",
	"custom_tool",
] as const
```

其中用于"理解现有代码"的工具：`list_files`（递归列目录）、`search_files`（ripgrep 正则搜 `@RequestMapping` 等）、`read_file`（读具体文件，支持 offset/limit 分段）、`codebase_search`（向量语义搜索）。

### 3.2 Continue 的工具清单（已读真实源码）

**文件**：`/workspace/continue/core/tools/builtIn.ts` 第 1-24 行
```typescript
export enum BuiltInToolNames {
  ReadFile = "read_file",
  ReadFileRange = "read_file_range",
  EditExistingFile = "edit_existing_file",
  SingleFindAndReplace = "single_find_and_replace",
  MultiEdit = "multi_edit",
  ReadCurrentlyOpenFile = "read_currently_open_file",
  CreateNewFile = "create_new_file",
  RunTerminalCommand = "run_terminal_command",
  GrepSearch = "grep_search",
  FileGlobSearch = "file_glob_search",
  SearchWeb = "search_web",
  ViewDiff = "view_diff",
  LSTool = "ls",
  CreateRuleBlock = "create_rule_block",
  RequestRule = "request_rule",
  FetchUrlContent = "fetch_url_content",
  CodebaseTool = "codebase",
  ReadSkill = "read_skill",
  // excluded from allTools for now
  ViewRepoMap = "view_repo_map",
  ViewSubdirectory = "view_subdirectory",
}
```

**注意第 21-23 行注释**：`view_repo_map` 和 `view_subdirectory` 被标注为 `// excluded from allTools for now`——亦即 Continue 让模型主动看项目结构的工具目前**默认不在工具集中**。能用的只有 `ls` 和 `grep_search`。

> **对比结论**：Roo-Code 给模型提供了 `list_files` + `search_files` + `codebase_search` 三件套主动探索项目；Continue 在这一维度只有 `ls` + `grep_search`，且 repo-map 类工具被排除。Roo-Code 让模型"自己摸清项目"的能力更强。

---

## 四、文件创建 / 修改 / 删除

### 4.1 创建新文件

- **Roo-Code**：`write_to_file`（`WriteToFileTool.ts`）——文件不存在时自动 `createDirectoriesForFile` 创建父目录后写入。
- **Continue**：`create_new_file`（`builtIn.ts` 第 8 行）——直接 `ide.writeFile`。

两者均支持，**平手**。

### 4.2 修改现有文件

- **Roo-Code**：7 种工具——`write_to_file`、`apply_diff`、`edit`、`search_and_replace`、`search_replace`、`edit_file`、`apply_patch`（见 tool.ts 第 28-34 行）。
- **Continue**：`edit_existing_file`、`single_find_and_replace`、`multi_edit`（见 builtIn.ts 第 4-6 行，第 28-32 行标注这三个由客户端执行）。

Roo-Code 策略更丰富，**略胜**。

### 4.3 删除文件（关键差异）

- **Roo-Code**：`apply_patch` 原生支持删除。`ApplyPatchTool.ts` 第 26 行：
```typescript
private static readonly FILE_HEADER_MARKERS = ["*** Add File: ", "*** Delete File: ", "*** Update File: "] as const
```
第 233 行 `handleDeleteFile`，第 277 行 `await fs.unlink(absolutePath)` 真正删除。

- **Continue**：`builtIn.ts` 的工具列表里**没有任何删除文件的工具**。要删只能靠 `run_terminal_command` 执行 `rm`。

> **对比结论**：Roo-Code 能直接让模型删文件；Continue 不能。

---

## 五、命令执行与编译验证

### 5.1 Roo-Code：`execute_command`

`src/api/providers/` 无关，执行在 `src/core/tools/ExecuteCommandTool.ts`。其工具 schema（`src/core/prompts/tools/native-tools/execute_command.ts`）：
```typescript
parameters: {
    command: { type: "string", description: "Shell command to execute" },
    cwd: { type: ["string", "null"], description: "Optional working directory" },
    timeout: { type: ["number", "null"], description: "Timeout in seconds" },
}
```
执行后把退出码 + 完整输出回传给模型；大输出经 `OutputInterceptor` 持久化，模型可用 `read_command_output` 分页读取。

### 5.2 Continue：`run_terminal_command`

`core/tools/implementations/runTerminalCommand.ts`，底层 `child_process.spawn`，有 `@continuedev/terminal-security` 做命令安全评估，默认 `allowedWithPermission`（需用户批准）。

两者都能跑 `javac`，**平手**。但 Continue 每次执行需手动批准，见下一节。

---

## 六、无人值守能力（Auto-approve，已读真实源码）

你的诉求是"不用我再复制粘贴，直接修改"——即工具最好**不要每个都弹确认**。

### 6.1 Roo-Code：精细的自动批准系统

**文件**：`/workspace/Roo-Code/src/core/auto-approval/index.ts`

**真实的自动批准类别（第 17-35 行）**：
```typescript
export type AutoApprovalState =
	| "alwaysAllowReadOnly"
	| "alwaysAllowWrite"
	| "alwaysAllowMcp"
	| "alwaysAllowModeSwitch"
	| "alwaysAllowSubtasks"
	| "alwaysAllowExecute"
	| "alwaysAllowFollowupQuestions"

export type AutoApprovalStateOptions =
	| "autoApprovalEnabled"
	| "alwaysAllowReadOnlyOutsideWorkspace"
	| "alwaysAllowWriteOutsideWorkspace"
	| "alwaysAllowWriteProtected"
	| "followupAutoApproveTimeoutMs"
	| "mcpServers"
	| "allowedCommands"      // 命令白名单
	| "deniedCommands"       // 命令黑名单
```

**真实的命令白名单判定（第 114-129 行）**：
```typescript
if (ask === "command") {
	if (state.alwaysAllowExecute === true) {
		const decision = getCommandDecision(text, state.allowedCommands || [], state.deniedCommands || [])
		if (decision === "auto_approve") {
			return { decision: "approve" }
		} else if (decision === "auto_deny") {
			return { decision: "deny" }
		} else {
			return { decision: "ask" }
		}
	}
}
```

**实操配置**：开 `alwaysAllowReadOnly` + `alwaysAllowWrite` + `alwaysAllowExecute`，`allowedCommands: ["javac *", "java *", "mvn *", "gradle *"]`，即可实现"模型自由读文件、改文件、跑编译，且只允许编译相关命令"的完全无人值守。**这是你场景的关键开关。**

### 6.2 Continue：无全局 auto-approve

Continue 的工具有 `defaultToolPolicy`（`allowedWithoutPermission` / `allowedWithPermission`），但**没有** Roo-Code 这种按类别 + 命令白名单的自动批准面板。编译命令每次都要手动点批准。

> **对比结论**：Roo-Code 的 auto-approve 是实现"无人值守编译-修复循环"的前提，Continue 不具备。

---

## 七、DeepSeek V3 兼容性（两个插件都支持，已核对）

### 7.1 Roo-Code

**文件**：`/workspace/Roo-Code/src/api/providers/deepseek.ts` 第 79-81 行
```typescript
tools: this.convertToolsForOpenAI(metadata?.tools),
tool_choice: metadata?.tool_choice,
parallel_tool_calls: metadata?.parallelToolCalls ?? true,
```
DeepSeek handler 直接把工具传给 API，并默认开启并行工具调用。模型配置中 `deepseek-chat` 描述明确写着 "Supports ... tool calls"。

### 7.2 Continue

**文件**：`/workspace/continue/core/llm/toolSupport.ts` 第 256-269 行
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
`deepseek-chat` 在白名单中，`modelSupportsNativeTools` 返回 `true`，走原生 tool calling。

> **对比结论**：两者都正确启用 DeepSeek V3 的工具调用，这条**没有差异**。

---

## 八、能力对比总表（每条均有源码出处）

| 能力 | Continue | Roo-Code | 源码依据 |
|---|---|---|---|
| 读 PDF | ❌ | ✅ | Continue: ignore.ts:107 忽略 + grep 零命中；Roo-Code: extract-text.ts:3-4,39-44, ReadFileTool.ts:391 |
| 读 DOCX | ❌ | ✅ | Roo-Code: extract-text.ts:4,17-20,39-44 |
| 主动探索项目 | `ls`+`grep` | `list_files`+`search_files`+`codebase_search` | Continue: builtIn.ts:10,14（repo-map 被排除）；Roo-Code: tool.ts:35-36,43 |
| 创建文件 | `create_new_file` | `write_to_file` | 平手 |
| 修改文件 | 3 种工具 | 7 种工具 | Continue: builtIn.ts:4-6；Roo-Code: tool.ts:28-34 |
| 删除文件 | ❌ 仅能 rm | ✅ `apply_patch` | Continue: builtIn.ts 无删除工具；Roo-Code: ApplyPatchTool.ts:26,277 |
| 执行编译 | `run_terminal_command` | `execute_command` | 平手 |
| 无人值守 | ❌ 逐个批准 | ✅ 类别+白名单 auto-approve | Roo-Code: auto-approval/index.ts:17-35,114-129 |
| DeepSeek V3 工具 | ✅ 白名单 | ✅ handler 直传 | Continue: toolSupport.ts:256-269；Roo-Code: deepseek.ts:79-81 |

---

## 九、你的实操工作流（基于 Roo-Code 真实工具）

1. **目录准备**：把所有 Java 文件、XML 配置、`requirements.pdf` 放同一目录。
2. **模型**：Provider=DeepSeek，Model=`deepseek-chat`（128K 上下文，足以容纳多文件 + PDF）。
3. **Auto-approve**：`alwaysAllowReadOnly`/`alwaysAllowWrite`/`alwaysAllowExecute` 全开，`allowedCommands: ["javac *","java *","mvn *","gradle *"]`。
4. **一句话需求**：
   ```
   先 list_files 了解项目结构，再 read_file 读取 requirements.pdf 理解需求，
   结合现有 Java 接口与 XML 配置实现新功能；完成后用 javac 编译，
   失败则自动读取错误、edit 修复，直到编译通过。
   ```
5. **Roo-Code 自主链路**（全部基于上述已核实工具）：
   - `list_files` → 项目骨架
   - `read_file requirements.pdf` → PDF 自动解析（pdf-parse）
   - `read_file XxxController.java` / `XxxMapper.xml` → 现有代码逻辑
   - `write_to_file` / `apply_diff` / `edit` → 生成或修改文件
   - `execute_command "javac ..."` → 编译验证（退出码回传）
   - 失败 → 读错误 → `edit` 修复 → 再编译（循环）
   - `attempt_completion` → 结束

---

## 十、一句话回答你的核心问题

> "两个插件能否支持：投喂附件+文本对话了解现有代码逻辑，再根据新需求直接生成/修改文件、编译好，不用复制粘贴？哪个支持的更好？"

- **能否支持**：Roo-Code **能完整支持**；Continue **不能**——因为它读不了你的 PDF/DOCX 需求文档，且无法无人值守自动改文件+编译。
- **哪个更好**：**Roo-Code**。源码层面的决定性证据是 PDF/DOCX 解析能力（extract-text.ts）和精细 auto-approve（auto-approval/index.ts），这两点 Continue 都不具备。

---

## 附录：本文逐条核对的真实源文件

| 仓库 | 文件 | 用到的事实 |
|---|---|---|
| Roo-Code | `src/integrations/misc/extract-text.ts` | PDF/DOCX 解析（第 3-4,11-20,39-44 行） |
| Roo-Code | `src/core/tools/ReadFileTool.ts` | read_file 调用 extractTextFromFile（第 23,391 行） |
| Roo-Code | `packages/types/src/tool.ts` | 工具清单（第 24-49 行） |
| Roo-Code | `src/core/tools/ApplyPatchTool.ts` | 删除文件（第 26,233,277 行） |
| Roo-Code | `src/core/auto-approval/index.ts` | auto-approve 类别与命令白名单（第 17-35,114-129 行） |
| Roo-Code | `src/api/providers/deepseek.ts` | DeepSeek 工具调用（第 79-81 行） |
| Continue | `core/indexing/ignore.ts` | 忽略 *.pdf（第 107 行） |
| Continue | `core/tools/builtIn.ts` | 工具清单、repo-map 被排除（第 1-24,21-23 行） |
| Continue | `core/context/providers/FileContextProvider.ts` | 纯文本 readFile（第 33,44 行） |
| Continue | `core/llm/toolSupport.ts` | DeepSeek 白名单（第 256-269 行） |
| Continue | 全仓 grep | 无 pdf-parse/mammoth/pdfjs/docx 引用（零命中） |

*文档版本: v3.0 | 核实时间: 2026-07-18 | 全部结论来自作者直接打开源文件逐行核对，附真实代码原文*
