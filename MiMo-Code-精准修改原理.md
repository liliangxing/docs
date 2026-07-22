# MiMo-Code 精准文件修改原理

本文档详细剖析 MiMo-Code（小米终端 AI 编程助手）如何通过 LLM + 工具链实现精准的代码文件修改。重点是 `edit` 工具的精确字符串替换机制、`apply_patch` 的自定义补丁语言、以及完整的模糊匹配回退链。

---

## 一、架构总览

MiMo-Code 提供 **三种文件修改工具**，根据模型类型自动选用：

```
用户请求 -> Session.prompt() -> System Prompt 注入 -> LLM 调用
    -> 工具选择 (按模型类型):
        GPT 模型 (非 gpt-4, 非 oss): apply_patch (自定义补丁语言)
        其他所有模型:             edit (old_string/new_string 精确替换)
                                  write (全文件覆写)
```

`registry.ts:355-358` 中的选择逻辑：

```typescript
const usePatch =
  input.modelID.includes("gpt-") &&
  !input.modelID.includes("oss") &&
  !input.modelID.includes("gpt-4")
if (tool.id === ApplyPatchTool.id) return usePatch
if (tool.id === EditTool.id || tool.id === WriteTool.id) return !usePatch
```

| 工具 | 文件 | 机制 | 使用模型 |
|------|------|------|----------|
| `edit` | `tool/edit.ts` (752行) | `old_string` 精确查找替换 | 大部分模型（Claude、MiMo、DeepSeek等） |
| `write` | `tool/write.ts` (88行) | 全文件覆写 | 所有模型（创建新文件或大改时） |
| `apply_patch` | `tool/apply_patch.ts` (308行) | 自定义补丁语言格式 | GPT 模型（非 gpt-4/oss） |

此外还有两个辅助工具：
- `multiedit.ts` (54行)：对同一文件批量执行多个 edit，原子性操作
- `notebook-edit.ts` (225行)：专门处理 `.ipynb` Jupyter 文件的单元格替换/插入/删除

---

## 二、第一阶段：前置安全校验

所有文件修改操作都经过三道安全检查：

### 2.1 read-state 校验 -- 强制先读再改

**代码位置：** `tool/read-state.ts`

```typescript
assertFileRead(ctx, filePath)
```

- 扫描当前会话的历史消息，查找是否有过 `read` 工具的成功调用
- 如果 LLM 没有先读取文件就直接 edit/write，抛出 `RecoverableError`
- LLM 看到这个错误后会调用 `read` 工具重新读取文件，然后重试

### 2.2 external-directory 校验 -- 防越权

**代码位置：** `tool/external-directory.ts`

- `assertWriteAllowed()`：检查目标路径是否在项目工作区或允许的外部目录内
- 防止 LLM 修改系统文件、配置目录等非授权路径
- 对 memory tree 路径放宽限制（检查点写入器需要非交互式访问）

### 2.3 权限确认

- `askEditUnlessMemory()`：对普通文件弹出权限确认对话框
- memory tree 路径跳过确认（非交互式场景）
- 外部目录操作需要额外权限

---

## 三、edit 工具核心机制（752行）

**代码位置：** `tool/edit.ts`

### 3.1 输入参数

```typescript
{
  file_path: string,    // 绝对路径
  old_string: string,   // 要替换的原文本
  new_string: string,   // 替换后的新文本
  replace_all: boolean  // 是否全局替换
}
```

### 3.2 完整执行流程

```
edit() 被调用
  |
  v
Step 1: 参数校验
  |-- file_path 不能为空
  |-- old_string !== new_string
  |-- 解析相对路径 (基于 SessionCwd)
  |
  v
Step 2: 安全校验
  |-- assertWriteAllowed() -- 路径权限检查
  |-- assertFileRead()     -- 强制先读文件
  |
  v
Step 3: 获取文件级信号量锁
  |-- 防止多个 edit 并发修改同一文件
  |
  v
Step 4: old_string === "" 分支
  |-- 创建新文件: fs.writeWithDirs(target, new_string)
  |
  v
Step 5: 读取当前文件内容
  |-- 检测行尾符 (\r\n 或 \n)
  |-- 统一规范化为 \n
  |
  v
Step 6: 调用 replace() 函数 (核心)
  |
  v
Step 7: 生成 unified diff
  |-- createTwoFilesPatch(original, modified)
  |-- trimDiff() -- 裁剪公共前导缩进
  |
  v
Step 8: 权限确认
  |-- ctx.ask({ permission: "edit" })
  |
  v
Step 9: 写入文件
  |-- 恢复原始行尾符
  |-- fs.writeWithDirs(target, modified)
  |-- 重新读取确认写入成功
  |
  v
Step 10: 发布事件
  |-- File.Event.Edited
  |-- FileWatcher.Event.Updated
  |
  v
Step 11: LSP 诊断
  |-- 报告文件的 LSP 诊断结果
  |-- 返回 diff + 诊断信息
```

### 3.3 replace() 函数 -- 精确替换核心

**代码位置：** `tool/edit.ts:657-714`

```typescript
export function replace(content, oldString, newString, replaceAll = false) {
  // 默认模式：精确严格匹配
  if (!Flag.MIMOCODE_ENABLE_FUZZY_EDIT) {
    // Step 1: 查找匹配
    const firstIndex = content.indexOf(oldString)
    if (firstIndex === -1) {
      throw buildNotFoundError(content, oldString)  // "文件中未找到"
    }

    // Step 2: replace_all 全局替换
    if (replaceAll) return content.replaceAll(oldString, newString)

    // Step 3: 唯一性检查
    const matches = content.split(oldString).length - 1
    if (matches > 1) {
      throw Error("old_string 出现了 N 次，不唯一。请提供更多上下文。")
    }

    // Step 4: 执行替换
    return content.substring(0, firstIndex) +
           newString +
           content.substring(firstIndex + oldString.length)
  }
  // Fuzzy 模式... (可选开启)
}
```

**默认行为（`MIMOCODE_ENABLE_FUZZY_EDIT` 关闭时）：**

1. **精确匹配**：`content.indexOf(oldString)` 严格查找
2. **找不到时**：调用 `findClosestMatch()` 在所有模糊匹配器中寻找最接近的匹配，作为错误提示返回给 LLM
3. **找到多个时**：抛出错误 "不唯一，请提供更多上下文"
4. **替换执行**：`substring` 拼接，O(n) 时间复杂度

### 3.4 buildNotFoundError -- 智能错误反馈

**代码位置：** `tool/edit.ts:720-751`

当 `old_string` 在文件中找不到时，不简单地返回"未找到"，而是：

1. 遍历所有 9 个模糊匹配器（见下方）
2. 每个匹配器尝试在文件中查找最相似的文本
3. 返回最接近的匹配（截断到 2000 字符）
4. LLM 看到错误后可以用返回的"最接近匹配"作为新的 `old_string` 重试

---

## 四、模糊匹配链（可选，FLAG 控制）

`MIMOCODE_ENABLE_FUZZY_EDIT` 标志开启时，edit 工具按以下优先级依次尝试 **9 种匹配器**：

### 4.1 匹配器链

| 序号 | 匹配器 | 策略 | 适用场景 |
|------|--------|------|----------|
| 1 | `SimpleReplacer` | 精确字符串匹配 | 首选，100% 精确 |
| 2 | `LineTrimmedReplacer` | 每行去除首尾空格后匹配 | LLM 添加了多余空格 |
| 3 | `BlockAnchorReplacer` | 首尾行作为锚点，中间行用 Levenshtein 距离匹配 | 多行代码块有细微差异 |
| 4 | `WhitespaceNormalizedReplacer` | 所有空白字符统一为单空格 | tab vs space，多余空格 |
| 5 | `IndentationFlexibleReplacer` | 剥离公共前导缩进后匹配 | 缩进宽度不一致 |
| 6 | `EscapeNormalizedReplacer` | 反转义 `\n` `\t` `\r` | LLM 输出含转义字符 |
| 7 | `MultiOccurrenceReplacer` | 返回所有精确出现位置 | 配合 replace_all 使用 |
| 8 | `TrimmedBoundaryReplacer` | 裁剪首尾空白字符 | old_string 两端多余空格 |
| 9 | `ContextAwareReplacer` | 首尾行锚点 + 50% 中间行匹配阈值 | 代码重构后部分内容变化 |

### 4.2 BlockAnchorReplacer 详解（最关键的回退策略）

**代码位置：** `tool/edit.ts` 中 `BlockAnchorReplacer`

这是模糊匹配链中最智能的匹配器。原理：

1. 将 `old_string` 拆分为行数组
2. **第一行**和**最后一行**作为"锚点"，必须在文件中精确找到
3. 中间行使用 **Levenshtein 编辑距离** 计算相似度
4. 相似度 = `1 - (编辑距离 / max(旧行长度, 新行长度))`
5. 匹配策略：
   - 单个候选：阈值 0.0（接受任何匹配）
   - 多个候选：阈值 0.3（需要高于 30% 的相似度）

**这意味着什么？** 当 LLM 引用的代码与文件内容略有差异时（比如变量名微调、多了空行），BlockAnchorReplacer 通过首尾行定位目标块，再通过 Levenshtein 距离容忍中间行的差异。

### 4.3 ContextAwareReplacer

与 BlockAnchorReplacer 类似，但中间行的匹配要求更高：
- 要求至少 **50%** 的中间行匹配
- 适用于代码块整体结构未变但部分行被修改的场景

---

## 五、apply_patch 工具 -- 自定义补丁语言

**代码位置：** `tool/apply_patch.ts` (308行) + `patch/index.ts`

GPT 模型不擅长使用 `old_string`/`new_string` 模式，MiMo-Code 设计了一套自定义补丁语法。

### 5.1 补丁格式

```
*** Begin Patch
*** Update File: src/foo.ts
@@ 第X行附近的上下文行
 保持的行
-删除的行
+新增的行
*** End of File
*** End Patch
```

### 5.2 支持的操作

| 操作 | 标记 | 说明 |
|------|------|------|
| 新增文件 | `*** Add File: <path>` | 后续 `+` 行组成新文件内容 |
| 删除文件 | `*** Delete File: <path>` | 直接删除 |
| 更新文件 | `*** Update File: <path>` | 包含 `@@` 定位块 |
| 文件移动 | `*** Move to: <path>` | 配合 Update File 使用 |

### 5.3 seekSequence -- 多遍行定位算法

**代码位置：** `patch/index.ts`

定位块（`@@` 后的上下文行）与文件的匹配经过 **4 遍查找**：

```
第 1 遍: 完全精确匹配          (context === file[i])
第 2 遍: 右剥离空格匹配        (context.rstrip === file[i].rstrip)
第 3 遍: 两端剥离空格匹配      (context.trim === file[i].trim)
第 4 遍: Unicode 规范化匹配    (全角标点 -> 半角标点)
```

每遍找不到才进入下一遍，确保在 LLM 引入空白差异或全角标点时仍能定位。

### 5.4 computeReplacements + applyReplacements

1. `computeReplacements()`：遍历所有块（chunks），调用 `seekSequence()` 定位每块
2. 生成 `[startIdx, oldLen, newLines]` 三元组
3. `applyReplacements()`：**从后向前**应用替换（避免索引偏移）

---

## 六、write 工具 -- 全文件覆写

**代码位置：** `tool/write.ts` (88行)

最简单的修改工具：接收完整文件内容 `content`，直接覆写整个文件。

- 建议 LLM 将大文件分为：先 `write` 创建 → 多个 `edit` 微调
- 生成 unified diff + trimDiff
- 同样经过 assertWriteAllowed + assertFileRead + askEditUnlessMemory

---

## 七、trimDiff 函数 -- 智能差异精简

**代码位置：** `tool/edit.ts:196-230`

LLM 生成的 diff 常因缩进差异产生大量噪音行（只有前导空格不同）。`trimDiff()` 解决此问题：

1. 遍历 diff 中所有内容行（非 `-`/`+` 开头的行）
2. 计算每行的公共前导缩进
3. 移除所有内容行的公共缩进
4. 跳过多余的空行

这样 diff 输出只显示真正的修改内容，而非缩进噪音。

---

## 八、并发控制 -- 文件级信号量锁

**代码位置：** `tool/edit.ts`

```typescript
const semaphore = ctx.get[SessionEditSemaphore]()
semaphore.acquire(filePath)
// ... 执行修改 ...
semaphore.release(filePath)
```

每个文件一个信号量，确保多步修改操作串行执行，防止竞态条件导致文件损坏。

---

## 九、模型自适应工具选择

不同模型的 Coding 能力不同，MiMo-Code 据此提供不同的工具：

| 模型分组 | 默认工具 | 原因 |
|----------|----------|------|
| GPT (非 gpt-4/oss) | apply_patch | GPT 更擅长结构化补丁格式 |
| Claude / MiMo / DeepSeek 等 | edit + write | 这些模型能精确理解 old_string/new_string |
| GPT-4 (含 oss 变体) | edit + write | GPT-4 也能有效使用编辑工具 |

这个选择由 `registry.ts:355-358` 在运行时按模型 ID 动态决定。

---

## 十、multiedit -- 原子批量修改

**代码位置：** `tool/multiedit.ts` (54行)

对同一文件执行多个 `old_string`/`new_string` 替换，所有替换必须全部成功才算成功（原子性）。

```typescript
params: {
  file_path: string,
  edits: [{ old_string: string, new_string: string, replace_all?: boolean }]
}
```

适用于 LLM 需要同时修改同一文件多处位置的场景。

---

## 十一、完整工具调用循环

```
LLM 收到 System Prompt (含工具规范)
   |
   v
LLM 调用 read(file_path) -- 读取文件内容（带行号）
   |
   v
LLM 分析文件内容，确定修改位置
   |
   v
LLM 调用 edit(file_path, old_string, new_string)
   |-- read-state 校验: 是否已读过此文件? 否 -> RecoverableError -> LLM 重读
   |-- path 校验: 是否在允许目录内?
   |-- 信号量锁定文件
   |-- replace() 执行替换:
   |     |-- 精确匹配 -> 成功替换
   |     |-- 找不到 -> findClosestMatch() 返回最接近匹配 -> LLM 调整重试
   |     |-- 不唯一 -> 返回错误 "不唯一" -> LLM 扩大上下文重试
   |-- trimDiff() 生成精简 diff
   |-- 写入文件
   |-- LSP 诊断 -> 如有错误返回给 LLM
   |
   v
LLM 查看结果（diff + 可能编译错误）
   |
   v
需要进一步修改？-> 循环（最多 maxSteps 次）
   |
   v
返回最终结果给用户
```

---

## 十二、与 GlmCoder 的对比

| 特性 | MiMo-Code | GlmCoder |
|------|-----------|----------|
| 修改方式 | old_string/new_string | oldText/newText |
| 模糊匹配 | 9 级匹配链（FLAG 控制） | 仅空格规范化 |
| 模型自适应 | edit vs apply_patch 按模型自动选 | 统一 editFile |
| 前置校验 | read-state 强制先读 | Prompt 中建议先读 |
| 错误反馈 | findClosestMatch 智能提示 | 规范化版本 + 匹配位置列表 |
| 并发控制 | 文件级信号量锁 | 无 |
| Levenshtein | BlockAnchorReplacer | 无 |
| Diff 精简 | trimDiff 裁剪缩进噪音 | 无 |
| 原子批修改 | multiedit | 无 |
| LSP 集成 | 编辑后自动诊断 | 无 (仅 compileCheck) |
| 补丁语言 | apply_patch 自定义格式 | 无 |

---

## 十三、关键代码文件索引

| 文件 | 行数 | 职责 |
|------|------|------|
| `tool/edit.ts` | 752 | edit 工具实现、replace()、trimDiff()、9 个模糊匹配器 |
| `tool/edit.txt` | - | edit 工具描述，注入 System Prompt |
| `tool/write.ts` | 88 | write 工具实现 |
| `tool/apply_patch.ts` | 308 | apply_patch 工具 + patch 解析 |
| `tool/multiedit.ts` | 54 | 原子批量编辑 |
| `tool/notebook-edit.ts` | 225 | Jupyter 文件编辑 |
| `tool/registry.ts` | 358+ | 工具注册、模型适配选择 |
| `patch/index.ts` | - | Patch 解析、seekSequence、replacements 计算 |
| `tool/read-state.ts` | - | assertFileRead 强制先读 |
| `tool/external-directory.ts` | - | assertWriteAllowed + askEditUnlessMemory |
| `session/prompt.ts` | 3730+ | runLoop 工具调用编排 |
| `session/prompt/default.txt` | 172 | 默认 System Prompt |
| `session/prompt/anthropic.txt` | 154 | Anthropic 专用 Prompt |
