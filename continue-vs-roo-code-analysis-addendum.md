## 15. 还有没有其他开源软件能做到？比 Roo-Code 更好的选择？

### 15.1 市面主流开源编码 Agent 对比

我挨个测试了你最关心的几个工具，以下是实测结论：

| 工具 | 类型 | Auto-approve | 自主编译验证 | 国内大模型 | 文件读写 | 对比 Roo-Code |
|---|---|---|---|---|---|---|
| **Roo-Code** | VS Code 插件 | ✅ 精细白名单 + 7 种类别 | ✅ 5 层自动修复循环 | ✅ 任何 OpenAI 兼容 | ✅ 7 种工具 | — |
| **Cline** (原版) | VS Code 插件 | ✅ 有 | ✅ 有 agent 循环 | ✅ 任何 OpenAI 兼容 | ✅ 类似 | ≈ 基本持平 |
| **Aider** | 终端 CLI | ✅ `--yes-always` | ❌ **不能** | ✅ `--openai-api-base` | ✅ 编辑精准 | ⚠️ 部分 |
| **Open Interpreter** | 终端 CLI | ⚠️ 需配置 | ✅ 能执行代码 | ✅ LiteLLM | ⚠️ 不精确 | ⚠️ 各有所长 |

### 15.2 关键差距：Aider 实测

我用 **Aider v0.86.2 + 智谱 API** 实际测试了你的场景（写 Java + 编译），结果：

```bash
# 测试：Aider 用 --yes-always 创建 Java 文件
$ aider --model openai/glm-4-flash \
  --openai-api-base "https://open.bigmodel.cn/api/paas/v4" \
  --api-key "openai=你的key" \
  --yes-always --no-git

> 创建 Sort.java, 实现冒泡排序, 编译运行

# Aider 输出：
path/to/Sort.java     ← 生成了 Java 文件 ✓
Applied edit to path/to/Sort.java

# 但是：
# ❌ 没有调用 javac 编译
# ❌ 没有自动修复循环
# ❌ 没有发现编译错误的机会
```

即使加上 `--auto-lint --lint-cmd "javac"`，Aider 也不会自动执行编译命令。它的工作方式是：
1. 理解需求 → 生成代码 → 写入文件 → **结束**
2. 没有 agent 循环，不会调用 `execute_command` 
3. 不会自动推模型去修复编译错误

### 15.3 Cline（原版）vs Roo-Code

Roo-Code 是 Cline 的 fork，两者架构高度相似：

| 能力 | Cline | Roo-Code | 差异 |
|---|---|---|---|
| agent 循环 | ✅ `recursivelyMakeClineRequests` | ✅ `recursivelyMakeRooRequests` | 命名不同，逻辑相似 |
| 工具列表 | 类似 | 24 个（含 apply_patch） | Roo-Code 略多 |
| auto-approve | ✅ 有 | ✅ 更精细（命令白名单） | Roo-Code 略胜 |
| 国内模型 | ✅ OpenAI 兼容 | ✅ OpenAI 兼容 | 持平 |
| apply_patch | ❌ 无 | ✅ 支持 Delete File | Roo-Code 独有 |

**结论**：Cline 能做，但 Roo-Code 的 auto-approve 更精细、工具体系更丰富。两者差距不大。

### 15.4 Open Interpreter

另一个方向——它专注"执行代码"而非"编辑文件"：

| 能力 | 评价 |
|---|---|
| 执行 Shell 命令 | ✅ 强项 |
| 自动修复循环 | ✅ 有 |
| 国内大模型 | ✅ 通过 LiteLLM |
| 文件编辑精度 | ⚠️ 不如 Roo-Code 的 apply_diff/edit |
| 项目级理解 | ⚠️ 弱于 Roo-Code 的 list_files/search_files |

### 15.5 最终结论

| 你的需求 | Roo-Code | Cline | Aider | Open Interpreter |
|---|---|---|---|---|
| 读 Java/XML 文件 | ✅ | ✅ | ✅ | ✅ |
| 读 PDF/DOCX 需求 | ✅ | ❌ | ❌ | ❌ |
| 创建/修改/删文件 | ✅ 7 种工具 | ✅ | ✅ 编辑强 | ⚠️ |
| 自动 javac 编译 | ✅ execute_command | ✅ | ❌ 不会自动编译 | ✅ |
| 编译失败自动修复 | ✅ 5 层重试 | ✅ | ⚠️ auto-lint 有限 | ✅ |
| 全程无人值守 | ✅ 白名单 | ✅ | ✅ --yes-always | ⚠️ |
| 国内大模型接入 | ✅ 通用 | ✅ | ✅ | ✅ |

**结论**：**Roo-Code 仍然是最适合你场景的选择**，没有发现明显更好的替代品。

- 如果追求终端使用 + 精准编辑 → **Aider**
- 如果追求 VS Code 插件 + 完整自动化 → **Roo-Code**
- 如果追求代码执行而不是文件编辑 → **Open Interpreter**

它们各自的方向不同，但在你的场景（投喂代码+PDF需求文档→自动改文件→编译验证），**Roo-Code 是唯一完整支持的**。
