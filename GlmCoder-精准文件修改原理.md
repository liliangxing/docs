# GlmCoder 精准文件修改原理

本文档详细剖析 GlmCoder 如何通过 LLM + 工具链实现精准的代码文件修改。整个流程涵盖项目索引、上下文压缩、文件读取、唯一性匹配、路径安全和编译验证六个关键阶段。

---

## 一、架构总览

GlmCoder 是一个 Spring Boot + Spring AI + Thymeleaf 的 Java 编码 Agent，核心思想是让 LLM 通过 **结构化工具调用（Tool Calling）** 来精准修改代码文件。

```
用户请求 -> CodingAgent(构建Prompt) -> LLM(生成tool_calls)
    -> readFile(带行号读取) -> LLM(分析，生成editFile参数)
    -> editFile(oldText/newText唯一匹配) -> compileCheckJava(编译验证)
    -> 反馈给用户
```

---

## 二、第一阶段：项目索引与结构分析

**代码位置：** `IndexService.java:13-30`、`CodeStructureIndex.java:37-106`

### 2.1 触发时机

每次用户发起请求时，`CodingAgent.execute()` 第一件事就是调用 `indexService.indexProject(projectPath)` 对整个项目进行索引。

### 2.2 实现原理

1. **遍历 Java 源文件**：`Files.walk()` 递归扫描项目目录，过滤出所有 `.java` 文件，排除 `test/` 和 `target/` 目录
2. **JavaParser 解析**：使用 `com.github.javaparser.JavaParser`，设置 `JAVA_17` 语言级别，逐文件解析 AST（抽象语法树）
3. **提取结构信息**：
   - 包名（`getPackageDeclaration()`）
   - import 列表（`getImports()`）
   - 每个类/接口的名称、是否为接口、字段列表
   - 每个方法的签名（`返回值 类名.方法名(参数类型列表)`）、参数、方法体、行号
4. **构建索引**：将结果存入 `ConcurrentHashMap`：
   - `classIndex`：全限定类名 -> ClassInfo（字段、方法）
   - `methodIndex`：`类名#方法名` -> MethodInfo（签名、参数、行号、方法体）
5. **生成文本摘要**：`getClassSummary()` 将所有类结构拼成一个人类可读的文本，格式为：

### 2.3 索引在 Prompt 中的作用

`getClassSummary()` 的输出会被写入 LLM 的 System Prompt 中的 "项目代码结构" 部分。这让 LLM 在生成工具调用之前，就能理解项目的类结构、方法定义、字段组成，从而知道"改动哪个文件的哪个方法"。

---

## 三、第二阶段：上下文压缩与 Token 管理

**代码位置：** `ContextCompressor.java`

LLM 的上下文窗口有限，GlmCoder 实现了 **两级压缩策略** 来管理上下文：

### 3.1 L1：代码结构摘要截断

`compress()` 方法（第41-72行）：

1. 将代码结构摘要按 "类:" 分段
2. 逐段添加，同时估算 token 数（`text.length() / 3`）
3. 达到 `MAX_TOKENS / 2 = 4000` 时停止
4. 相关文件和聊天历史也会按 token 预算添加

### 3.2 L1：工具结果截断

`l1TruncateToolResult()` 方法（第97-125行）：

1. 超过 **500 行**或 **2000 字符** 的工具返回结果会被截断
2. 保留前 500 行，标注省略的行数
3. 最多截断到 **6000 字符**（2000 x 3），防止超大文件内容撑爆上下文

### 3.3 L2：对话历史摘要

`checkAndCompressConversation()` 方法（第127-138行）：

1. 当对话轮次超过 **20 轮** 时触发
2. 取前 **10 轮** 消息，将每条消息截断到 200 字符
3. 生成 "会话摘要" 写入项目的 `MEMORY.md` 文件
4. 后续请求中 `CodingAgent` 会读取 `MEMORY.md` 作为项目上下文

---

## 四、第三阶段：LLM System Prompt 注入

**代码位置：** `CodingAgent.java:58-83`

`execute()` 方法构建一个结构化的 System Prompt，关键部分：

### 4.1 Prompt 结构

```
## 项目ID
projectId: xxxxxxxx

## 项目信息
当前日期、项目根目录、CLAUDE.md/MEMORY.md 内容

## 工具使用规范
1. 修改文件前先 readFile 确认当前内容
2. editFile 的 oldText 必须与原文完全一致（含缩进），且必须唯一匹配
3. 如果 editFile 返回"不唯一"错误，扩大 oldText 范围重新尝试
4. 如果 editFile 返回"未找到"错误，用 readFile 重新读取后再试
5. 创建/修改后调用 compileCheckJava 验证编译
6. 编译失败时根据错误日志自动修复
7. 一次只修改与当前任务直接相关的代码

## 项目代码结构
(IndexService 生成的类/方法总览)

## 对话历史上下文
(如果有 conversationId)

## 用户请求
(用户的实际问题)
```

### 4.2 关键设计点

- **强制 readFile 先读**：规则 1 明确要求先读取再修改，确保 LLM 拿到的 oldText 是实时内容
- **唯一性检查自修复**：规则 3-4 告诉 LLM 如何应对匹配失败——扩大上下文或重新读取
- **编译验证闭环**：规则 5-6 构成"改->编->修"的自动修复循环
- **工具可用性**：所有 `@Tool` 注解的方法都通过 Spring AI 的工具注册机制暴露给 LLM

---

## 五、第四阶段：文件修改核心机制

**代码位置：** `ModificationTools.java:28-72`

这是整个系统最核心的部分。LLM 调用 `editFile(filePath, oldText, newText, projectId)` 来修改文件。

### 5.1 完整流程图

```
editFile() 被调用
  |
  v
Step 1: 路径安全检查 -----> 不通过 -> 返回错误
  |
  v
Step 2: 保护文件检查 -----> 受保护 -> 返回错误
  |
  v
Step 3: 读取文件完整内容
  |
  v
Step 4: 精确匹配 oldText
  |
  v
Step 5: 唯一性检查 (checkUniqueMatch)
  |
  +-- 完全匹配且唯一 -> 获取匹配位置 idx
  |
  +-- 精确不匹配 -> 尝试空格规范化再匹配
  |                 |
  |                 +-- 规范化后匹配 -> 返回规范化版本建议
  |                 |
  |                 +-- 仍不匹配 -> 返回 "未找到 oldText"
  |
  +-- 匹配但不唯一 -> 返回所有匹配位置（前5个）
  |
  v
Step 6: 执行替换
  content = content[0:idx] + newText + content[idx+len(oldText):]
  |
  v
Step 7: 记录 Patch -> PatchApprovalService.submitPatch()
  |
  v
Step 8: 写入文件 -> Files.writeString(target, modified)
  |
  v
Step 9: 返回成功
```

### 5.2 Step 1-2：安全保障

**代码位置：** `ModificationTools.java:35-44`

```java
Path root = projectManager.getProjectPath(projectId);
Path target = root.resolve(filePath).normalize();

if (!pathValidator.isAllowed(target, root)) {
    return "错误: 不允许修改该文件";
}
if (pathValidator.isProtectedFile(target.getFileName().toString())) {
    return "错误: 该文件受保护，不允许修改";
}
```

1. **ProjectManager.getProjectPath()** 将 projectId 映射到实际项目根目录（`ConcurrentHashMap`）
2. **PathValidator.isAllowed()** 三层层防护：
   - 路径规范化后检查是否以项目根目录为前缀（防 `../` 路径穿越）
   - 文件名不能是受保护文件（`pom.xml`、`application.properties` 等）
   - 路径不能经过受保护目录（`.git`、`target`、`build`、`node_modules`、`.idea`）

### 5.3 Step 3-5：唯一性匹配算法（核心）

**代码位置：** `ModificationTools.java:145-190`

这是 `checkUniqueMatch()` 方法的实现，是整个精准修改的关键：

```java
static MatchCheckResult checkUniqueMatch(String content, String oldText) {
```

#### 5.3.1 精确匹配检查

先用 `content.contains(oldText)` 检查 oldText 是否存在于文件内容中。

#### 5.3.2 不匹配时的规范化回退

如果精确匹配失败，调用 `normalizeWhitespace(oldText)` 进行规范化：
- 将 `\r\n` 统一为 `\n`
- 将制表符 `\t` 替换为空格
- 多个连续空格合并为一个空格
- 每行首尾空格去除
- 整体 trim

然后用规范化后的文本再次匹配。如果匹配成功，返回错误信息，**建议 LLM 使用规范化后的版本重试**：

```
错误: oldText 未精确匹配。尝试以下规范化版本（请用此版本重试editFile）:
` ` `
规范化后的文本
` ` `
```

#### 5.3.3 不唯一时的上下文定位

从位置 0 开始，用 `indexOf(oldText, searchFrom)` 循环查找所有匹配位置：

- 记录第一个匹配位置 `firstIdx`（用于实际替换）
- 对前 5 个匹配位置，计算行号并提取前后 40 字符的上下文
- 如果超过 5 个，标注 "... 及其他 N 处匹配"

返回错误信息：

```
错误: oldText 在文件中出现了 N 次，不唯一。
请提供更长的上下文来唯一标识要替换的位置。所有匹配位置:
  位置 1 (行 15): ...前文...匹配文本...后文...
  位置 2 (行 42): ...前文...匹配文本...后文...
```

**关键设计**：返回每个匹配位置的行号和上下文，让 LLM 知道"哪里重复了"，从而扩大 oldText 的范围（包含更多前后文）实现唯一匹配。

#### 5.3.4 为什么这种机制精准？

这个设计的核心在于：**让 LLM 自己确定替换位置，程序只做校验**。

- LLM 通过 `readFile`（带行号）看到文件内容
- LLM 自己摘取要替换的片段作为 `oldText`
- `editFile` 的 `checkUniqueMatch` 强制要求 oldText **精确匹配** 且 **在文件中唯一**

如果 LLM 摘的片段不够精准（不唯一）或摘错了（不匹配），`checkUniqueMatch` 会返回详细的错误信息（所有匹配位置 + 上下文），LLM 利用这些信息调整 oldText 后重试。这个"试错-反馈-调整"闭环确保了修改的精准性。

### 5.4 Step 6-8：执行替换与记录

**代码位置：** `ModificationTools.java:54-68`

```java
int idx = result.matchIndex;
String modified = content.substring(0, idx) + newText + content.substring(idx + oldText.length());

PatchEntry patch = new PatchEntry();
patch.setFilePath(filePath);
patch.setOperation("edit");
patch.setOriginalCode(oldText);
patch.setModifiedCode(newText);
patchApprovalService.submitPatch(patch);

Files.writeString(target, modified);
```

- 使用 `substring` 拼接实现精确替换，O(n) 时间复杂度
- 每次修改都记录到 `PatchApprovalService`（操作审计）
- `Files.writeString` 原子写入整个文件内容

---

## 六、第五阶段：编译验证闭环

**代码位置：** `BuildTools.java:99-104`

### 6.1 CompileCheckJava

```java
@Tool(name = "compileCheckJava", description = "在指定目录执行 Maven 编译检查")
public String compileCheckJava(@ToolParam String projectDir) {
    return executeProcess(new File(dir), List.of("mvn", "compile", "-q"), 120);
}
```

LLM 在修改文件后会调用此工具，执行 `mvn compile -q`：
- 超时限制 120 秒
- 输出截断到 500 行
- 返回 exit code + 编译输出

### 6.2 自动修复循环

CodingAgent 的 Prompt 规则 6：

> 编译失败时，根据错误日志定位问题自动修复

这就构成了"修改 -> 编译 -> 失败 -> 定位错误行 -> 再次 editFile -> 编译"的自动修复循环，直到编译通过。

### 6.3 危险命令拦截

`executeBash` 在执行前会检查命令是否包含危险模式（`rm -rf`、`DROP TABLE`、`shutdown` 等 20+ 种），直接拒绝执行。

---

## 七、完整工具集一览

| 工具名 | 功能 | 所属类 |
|--------|------|--------|
| `readFile` | 读取文件完整内容（带行号） | CodeUnderstandingTools |
| `searchCode` | 按关键词搜索类名或方法名 | CodeUnderstandingTools |
| `getClassStructure` | 获取类的完整结构 | CodeUnderstandingTools |
| `listFiles` | 列出目录内容 | FileTools |
| `searchFiles` | glob 模式搜索文件 | FileTools |
| `getDependencies` | 分析文件 import 依赖 | FileTools |
| `editFile` | 精准修改文件（oldText/newText 匹配） | ModificationTools |
| `createFile` | 创建新文件 | ModificationTools |
| `generateDiff` | 生成文件修改 diff | ModificationTools |
| `compileCheckJava` | Maven 编译检查 | BuildTools |
| `runTests` | 运行测试 | BuildTools |
| `executeBash` | 执行安全 Shell 命令 | BuildTools |

---

## 八、完整修改时序图

```
用户发起请求
    |
    v
AgentController.chat()
    |-- 自动创建 Conversation
    |
    v
CodingAgent.execute()
    |-- 1. IndexService.indexProject()       -- 解析 Java AST，构建类/方法索引
    |-- 2. IndexService.getClassSummary()     -- 生成代码结构文本摘要
    |-- 3. ContextCompressor.compress()       -- L1 截断摘要，控制 token 预算
    |-- 4. ConversationService (L2 压缩)       -- 超过 20 轮对话则写入 MEMORY.md
    |-- 5. 读取 CLAUDE.md / MEMORY.md         -- 项目约定和记忆
    |-- 6. 构建 System Prompt                -- 拼接结构摘要 + 工具规范 + 用户请求
    |
    v
ChatClient.call()  -->  LLM 处理
    |-- LLM 分析代码结构，决定调用哪些工具
    |-- LLM 调用 readFile(filePath)            -- 读取目标文件（带行号）
    |-- 拿到带行号的文件内容
    |-- LLM 摘取要替换的代码片段作为 oldText
    |-- LLM 调用 editFile(filePath, oldText, newText)
    |       |-- PathValidator 安全检查
    |       |-- checkUniqueMatch:
    |       |     |-- 不匹配 -> 返回规范化建议
    |       |     |-- 不唯一 -> 返回所有位置+上下文
    |       |     |-- 唯一匹配 -> 执行替换
    |       |-- PatchApprovalService.submitPatch()
    |       |-- Files.writeString()
    |-- LLM 调用 compileCheckJava()
    |       |-- 编译通过 -> 完成
    |       |-- 编译失败 -> 分析错误日志 -> 再次 editFile -> 重新编译
    |-- 循环直到编译通过或达到 10 次迭代上限
    |
    v
返回结果给用户
ConversationService.saveMessage()  -- 保存对话记录
```

---

## 九、关键设计原则

### 9.1 防御式编程

每一步都有安全检查和错误处理：
- **路径安全**：PathValidator 防止路径穿越
- **文件安全**：保护配置文件不被修改
- **命令安全**：BuildTools 拦截危险 shell 命令
- **唯一性校验**：避免误改同名代码

### 9.2 LLM 驱动 + 程序校验

- LLM 负责 "理解和决定改什么"
- 程序负责 "校验和执行修改"
- 两者通过结构化的错误反馈形成闭环

### 9.3 渐进式上下文管理

- L1 截断：token 预算内尽可能多地保留代码结构
- L2 摘要：长对话自动摘要写入 MEMORY.md
- 对话记忆：SQLite 持久化，搜索复用

### 9.4 可观测性

- 每次修改记录 Patch（operation, originalCode, modifiedCode）
- 编译结果带 exit code 和完整输出
- 所有操作有日志记录

---

## 十、核心代码文件索引

| 文件 | 行数 | 职责 |
|------|------|------|
| `agent/CodingAgent.java` | 231 | Agent 主控，Prompt 构建，迭代执行 |
| `tools/ModificationTools.java` | 226 | 文件精准修改 + 唯一性匹配算法 |
| `tools/BuildTools.java` | 146 | 编译检查 + 测试 + 安全执行 |
| `tools/CodeUnderstandingTools.java` | 120+ | 文件读取 + 代码搜索 + 类结构查询 |
| `tools/FileTools.java` | 120+ | 文件列表 + glob 搜索 + 依赖分析 |
| `context/ContextCompressor.java` | 207 | L1 截断 + L2 对话摘要 |
| `index/CodeStructureIndex.java` | 200 | JavaParser AST 解析 + 类/方法索引 |
| `index/IndexService.java` | 30+ | 索引构建入口 |
| `security/PathValidator.java` | 70+ | 路径安全 + 保护文件检查 |
| `security/PatchApprovalService.java` | 40+ | 修改记录审计 |
| `project/ProjectManager.java` | 51 | projectId 到项目路径映射 |
