# Roo Code vs Cline：基于源码的深度能力对比分析

> 问题场景：调用同一个 API 模型（如 DeepSeek-V3），投喂多个 Java 文件 + XML 文件 + PDF/DOCX 需求文档，让插件理解现有代码逻辑后，自动生成/修改文件并编译验证——不复制粘贴、不启动服务，只保证编译通过、引用无误。
>
> 本文所有结论均基于 `/workspace/forks/Roo-Code` 和 `/workspace/forks/cline` 的实际源码验证，每条都附源码文件路径与行号。

---

## 一、直接回答

**两个插件都支持这个需求，但 Roo Code 更好。**

核心原因是三个：PDF/DOCX 解析在核心层（CLI 直接可用）、目录限制更宽松、支持更多文件格式。下面逐项从源码层面展开。

---

## 二、需求拆解

| 环节 | 说明 | 关键能力点 |
|------|------|------------|
| ① 投喂多个 Java 文件 | 让模型了解现有代码逻辑 | 批量读文件、列目录 |
| ② 投喂 XML 文件 | 让模型了解接口/SQL 映射 | read_file 支持任意文本 |
| ③ 投喂 PDF/DOCX 需求文档 | 告诉模型要开发什么 | PDF/DOCX 文本提取 |
| ④ 自动生成/修改文件 | 不用复制粘贴 | write_to_file / apply_diff / apply_patch |
| ⑤ 自动编译验证 | 跑 javac/mvn，保证引用没错 | execute_command / run_commands |

---

## 三、能力对照表（源码验证）

| 能力 | Cline | Roo Code | 胜出 |
|------|-------|----------|------|
| PDF 读取 | ⚠️ 仅 VS Code 层 | ✅ 核心层，CLI 直接可用 | **Roo** |
| DOCX 读取 | ⚠️ 仅 VS Code 层 | ✅ 核心层，CLI 直接可用 | **Roo** |
| 额外格式（IPYNB/XLSX） | ❌ 无 | ✅ 支持 | **Roo** |
| 批量读文件 | ✅ `read_files` | ✅ `read_file`（files 数组） | 平手 |
| 列目录/项目结构 | ✅ `search_codebase` | ✅ `list_files`（递归，上限 200） | 平手 |
| 写文件 | ✅ `apply_patch` + `editor` | ✅ `write_to_file` + `apply_diff` | 平手 |
| 执行命令 | ✅ `run_commands` | ✅ `execute_command`（含 cwd/timeout） | 平手 |
| MCP 支持 | ✅ 完整 | ✅ 完整 | 平手 |
| CLI 自动批准 | ✅ `--auto-approve` / `--mode yolo` | ✅ 默认自动批准（YOLO） | 平手 |
| @mention 加文件 | ✅ VS Code 层 | ✅ VS Code 层 | 平手 |
| 目录限制 | ⚠️ `restrictToCwd` 默认 true | ✅ 无硬限制 | **Roo** |

---

## 四、关键差异详解（三个 Roo 胜出点）

### 4.1 PDF/DOCX 解析：核心层 vs VS Code 层

这是最关键的差异。

#### Cline：PDF/DOCX 只在 VS Code 集成层

Cline 的 PDF/DOCX 解析在 `apps/vscode/src/integrations/misc/extract-text.ts`：

```ts
// apps/vscode/src/integrations/misc/extract-text.ts
import mammoth from "mammoth"           // L6
import pdf from "pdf-parse/lib/pdf-parse" // L9

case ".pdf":   content = await extractTextFromPDF(filePath)  // L51
case ".docx":  content = await extractTextFromDOCX(filePath)  // L54-55
```

但 CLI 用的是 `sdk/packages/core/`，核心层的 `file-read.ts` **不支持 PDF/DOCX**：

```ts
// sdk/packages/core/src/extensions/tools/executors/file-read.ts
// 只支持图片格式：
const IMAGE_MEDIA_TYPES = new Map([
    [".gif", "image/gif"],   // L22
    [".png", "image/png"],    // L23
    [".jpg", "image/jpeg"],   // L24
    [".jpeg", "image/jpeg"],  // L25
    [".webp", "image/webp"],  // L26
])
// 没有任何 PDF/DOCX 处理逻辑
```

> **结论**：Cline 的 CLI 模式下，PDF/DOCX 读不了（除非额外适配 VS Code 层的 extract-text 到 SDK 核心）。

#### Roo Code：PDF/DOCX 在核心层，CLI 和 VS Code 都支持

Roo 的解析在 `src/integrations/misc/extract-text.ts`，属于核心层：

```ts
// src/integrations/misc/extract-text.ts
import pdf from "pdf-parse/lib/pdf-parse"   // L3
import mammoth from "mammoth"                // L4

async function extractTextFromPDF(filePath: string): Promise<string> {
    const dataBuffer = await fs.readFile(filePath)
    const data = await pdf(dataBuffer)
    return addLineNumbers(data.text)          // L11-15
}

async function extractTextFromDOCX(filePath: string): Promise<string> {
    const result = await mammoth.extractRawText({ path: filePath })
    return addLineNumbers(result.value)        // L17-20
}

// 还支持 IPYNB 和 XLSX：
const SUPPORTED_BINARY_FORMATS = {
    ".pdf":  extractTextFromPDF,    // L40
    ".docx": extractTextFromDOCX,   // L41
    ".ipynb": extractTextFromIPYNB, // L42
    ".xlsx":  extractTextFromXLSX,  // L43
} as const
```

`ReadFileTool` 直接调用核心层的 `extractTextFromFile`：

```ts
// src/core/tools/ReadFileTool.ts
import { extractTextFromFile, getSupportedBinaryFormats } from "../../integrations/misc/extract-text"  // L23

const supportedBinaryFormats = getSupportedBinaryFormats()  // L346
const content = await extractTextFromFile(fullPath)          // L391
```

> **结论**：Roo 的 CLI 和 VS Code 都能直接读 PDF/DOCX/IPYNB/XLSX。这是架构层面的优势——解析逻辑在核心层而非 IDE 集成层。

### 4.2 目录限制：硬限制 vs 软提示

#### Cline：`restrictToCwd` 默认开启

```ts
// sdk/packages/core/src/extensions/tools/executors/editor.ts
restrictToCwd?: boolean    // L28  可选参数
restrictToCwd: boolean     // L40  函数参数
if (!restrictToCwd) {      // L46  关闭则放行
    return resolved
}
// 绝对路径越界抛错：
throw new Error("Path must stay within cwd")  // L56-57

restrictToCwd = true       // L208 默认开启
```

`apply-patch.ts` 同样有 `restrictToCwd`（L50, L56, L62）。

> **影响**：如果你的 Java 源码和 XML 文件分散在不同目录（比如源码在 `project/src/`，XML 在 `project/resources/mapper/`），只要在同一个工作目录下就行。但如果文件在工作目录外，会被拒绝。

#### Roo Code：无硬限制

```ts
// src/utils/pathUtils.ts
isPathOutsideWorkspace()  // L9-24  仅检测是否在工作区外

// ListFilesTool.ts L38 / WriteToFileTool.ts L13
// isOutsideWorkspace 只作为提示字段传给审批 UI，不阻断操作
```

CLI 的 YOLO 模式下（默认），所有操作自动批准，无任何拦截。

> **结论**：Roo 对文件位置更宽容，不会因为路径在工作目录外而报错。

### 4.3 额外文件格式

Roo Code 额外支持 `.ipynb`（Jupyter notebook）和 `.xlsx`（Excel）。如果你的需求文档是 Excel 表格（比如接口定义表、字段映射表），Roo 能直接读取，Cline 不能。

---

## 五、两个插件共同支持的能力（平手项）

### 5.1 批量读文件

**Cline** — `read_files` 工具支持数组：
```ts
// sdk/packages/core/src/extensions/tools/definitions.ts L248
name: "read_files"
// 描述："When you already know multiple files you need, read them together in one call"
// 支持 files / file_paths / paths 数组（L271-289）
```

**Roo Code** — `read_file` 支持 files 数组：
```ts
// src/core/tools/ReadFileTool.ts L9
// Legacy format: { files: [{ path: string, lineRanges?: [...] }] }
// L77: this.executeLegacy(params.files, task, callbacks)
```

### 5.2 列目录/了解项目结构

**Cline** — `search_codebase` 工具（`definitions.ts` L345）。
**Roo Code** — `list_files` 工具，可递归，上限 200 个文件（`ListFilesTool.ts` L19-20, L40）。

### 5.3 文件写入/修改

| | Cline | Roo Code |
|--|-------|----------|
| 全新写入 | `apply_patch`（`definitions.ts` L554） | `write_to_file`（`WriteToFileTool.ts` L26-27） |
| 局部修改 | `editor`（`definitions.ts` L603） | `apply_diff`（`ApplyDiffTool.ts` L23-24） |

### 5.4 命令行执行

**Cline** — `run_commands`（`definitions.ts` L417），"Run non-interactive shell commands from the root of the workspace"。
**Roo Code** — `execute_command`（`ExecuteCommandTool.ts` L40-41），含 `command`、`cwd`、`timeout` 参数。

两者都能跑 `javac`、`mvn compile`、`gradle build` 等。

### 5.5 MCP 支持

两者都有完整的 MCP（Model Context Protocol）支持：
- **Cline**：`sdk/packages/core/src/extensions/mcp/` 整目录（client.ts、manager.ts、config-loader.ts 等）
- **Roo Code**：`src/core/tools/UseMcpToolTool.ts` + `src/services/mcp/McpHub.ts`

### 5.6 CLI 自动批准

**Cline**：
```ts
// apps/cli/src/commands/program.ts
"--auto-approve <boolean>"  // L29
"-y, --yolo"                // L96  全自动批准
```

**Roo Code**：
```ts
// apps/cli/src/index.ts L36
.option("-a, --require-approval", "Require manual approval for actions", false)
// 默认 false → nonInteractive=true → 自动批准

// apps/cli/src/commands/cli/run.ts L164
nonInteractive: !effectiveRequireApproval
```

---

## 六、IDE 支持对比

| | Cline | Roo Code |
|--|-------|----------|
| VS Code | ✅ 原生插件 | ✅ 原生插件 |
| IntelliJ IDEA | ❌ 不支持 | ❌ 不支持 |
| CLI（无 IDE） | ✅ `bun apps/cli/dist/index.js` | ✅ `tsx apps/cli/src/index.ts --print` |

两者都是 VS Code 专属插件，源码深度绑定 VS Code Extension API（各 100+ 文件 `import ... from "vscode"`），不支持 IntelliJ IDEA。

RooCodeInc 另有一个产品 **Roomote**（https://github.com/RooCodeInc/Roomote），是云端编码代理，不依赖任何 IDE，通过 Slack/Web 发任务、自动改代码提 PR。但它不是 Roo Code 的 IDEA 版本，是独立产品。

---

## 七、实际操作建议

### 7.1 推荐方案：Roo Code CLI + DeepSeek-V3

```bash
# 1. 准备工作目录，把 Java 源码、XML、需求文档都放进去
mkdir -p my-project/src my-project/xml my-project/docs
# .java 放 src/，.xml 放 xml/，需求文档(.pdf/.docx) 放 docs/

# 2. 用 Roo CLI 跑（headless + 自动批准）
export ZHIPU_API_KEY="你的API Key"  # 或 DeepSeek API Key
node_modules/.bin/tsx apps/cli/src/index.ts --print \
  "先读取 src/ 下所有 Java 文件和 xml/ 下所有 XML 文件，了解现有项目结构和接口逻辑。
   然后读取 docs/需求文档.pdf，按需求文档开发新功能。
   开发完成后用 javac 或 mvn compile 验证编译通过。" \
  --provider openai-compatible --api-key "$ZHIPU_API_KEY" \
  --base-url "https://open.bigmodel.cn/api/paas/v4/" \
  --model deepseek-chat --mode code \
  -w my-project
```

### 7.2 模型选择建议

| 模型 | 适合场景 | 说明 |
|------|----------|------|
| **DeepSeek-V3**（`deepseek-chat`） | ✅ 推荐 | 代码能力强，64K 上下文，两插件都原生支持 |
| GLM-4-Flash | ⚠️ 简单任务 | 弱模型，处理"理解大量文件 + 开发新功能"容易出错 |
| GLM-4-Plus / GLM-4-Air | ✅ 可选 | 比 Flash 强，智谱系中等模型 |

> **提醒**：你说"网页版模型只能生成代码，简单微调就能跑"——说明需求不算特别复杂。插件的优势在于自动化（自动改文件、自动编译、自动修复编译错误），但如果模型能力不够（如 GLM-4-Flash），可能在"理解大量文件 + 做复杂修改"场景下频繁出错、反复修改也编译不过，反而比你手动复制粘贴更慢。建议用 DeepSeek-V3 或更强的模型。

### 7.3 如果用 IDEA 开发

两个插件都不支持 IDEA。可行方案：

| 方案 | 做法 | 优缺点 |
|------|------|--------|
| **Roo Code CLI** | 终端跑，不依赖 IDE | ✅ 完全可用；❌ 没有图形界面 |
| **VS Code + Roo 插件** | 装 VS Code 打开同一项目 | ✅ 功能完整；❌ 要换 IDE |
| **Roomote** | 自托管云端代理，Slack 发任务 | ✅ 自动提 PR；❌ 需要服务器 |

---

## 八、总结

| 维度 | Roo Code | Cline |
|------|----------|-------|
| PDF/DOCX（CLI） | ✅ 核心层支持 | ❌ 仅 VS Code 层 |
| 额外格式 | ✅ IPYNB / XLSX | ❌ 无 |
| 目录限制 | ✅ 无硬限制 | ⚠️ restrictToCwd |
| IDE 支持 | VS Code + CLI | VS Code + CLI |
| 适合场景 | 需要读 PDF/DOCX 需求文档 + CLI 模式 | VS Code 内交互式开发 |

**结论**：对于"投喂 Java + XML + PDF/DOCX 需求文档 → 自动生成/修改文件 + 编译验证"这个场景，**Roo Code 是更好的选择**，核心原因是 PDF/DOCX 解析在核心层、CLI 直接可用，且目录限制更宽松。

---

> 版本：2026-07-18
> 基于 Roo Code `liliangxing/Roo-Code`（分支 `debug-zhipu-java-demo`）和 Cline `liliangxing/cline`（commit `0101fcb`）源码验证。
