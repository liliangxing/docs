# Aider 编码助手源码分析与 Roo-Code 对比指南

> 本指南记录 Aider AI 编程助手的源码分析、安装调试、自然语言生成 Java 代码测试，以及与 Roo-Code 在代码质量方面的对比。
>
> 适用读者：想了解 Aider 和 Roo-Code 内部工作原理、想自己复现测试的技术人员。
>
> **核实时点**：2026-07-19 | **Aider 版本**：v0.86.2 | **源码仓库**：https://github.com/liliangxing/aider

---

## 目录

1. [Fork 仓库并拉取代码](#1-fork-仓库并拉取代码)
2. [Aider 源码结构分析](#2-aider-源码结构分析)
3. [安装与配置](#3-安装与配置)
4. [Aider 核心能力分析](#4-aider-核心能力分析)
5. [测试：自然语言写 Java + 编译](#5-测试自然语言写-java--编译)
6. [Aider 与 Roo-Code 的架构差异](#6-aider-与-roo-code-的架构差异)
7. [代码质量对比](#7-代码质量对比)
8. [避坑清单](#8-避坑清单)
9. [附录：关键源码文件索引](#9-附录关键源码文件索引)

---

## 1. Fork 仓库并拉取代码

### 1.1 Fork 到自己的 GitHub

```bash
# 用 gh CLI fork 仓库
export GH_TOKEN=ghp_xxx
gh repo fork Aider-AI/aider --clone=false --remote=false
# 输出: https://github.com/你的用户名/aider
```

**为什么 fork**：fork 后你可以修改源码、提交自己的测试代码，不影响原仓库。

### 1.2 从自己的仓库克隆

```bash
cd /workspace
git clone "https://x-access-token:${GH_TOKEN}@github.com/liliangxing/aider.git" aider
```

**为什么用 token 嵌入 URL**：`gh repo clone` 在某些网络环境下会报 `gnutls_handshake() failed`。用 `https://x-access-token:${TOKEN}@github.com/...` 格式最稳定。

### 1.3 验证克隆完整性

```bash
cd aider
git log --oneline -5
# 预期输出: 最近 5 个 commit（Merge pull request #xxx from xxx...）
```

---

## 2. Aider 源码结构分析

### 2.1 整体架构

Aider 是纯 Python 项目，核心目录结构：

```
aider/
├── aider/                     # 核心源码
│   ├── __main__.py           # 入口
│   ├── args.py               # 命令行参数解析（945行）
│   ├── io.py                 # 输入输出 + 确认对话框（含 --yes-always 实现）
│   ├── linter.py             # 代码检查（304行）
│   ├── llm.py                # LLM 配置
│   ├── commands.py           # 内置命令（1712行）
│   ├── diffs.py              # diff 工具
│   ├── coders/               # 编码器（核心！）
│   │   ├── base_coder.py     # 基类（2485行）- 核心逻辑
│   │   ├── editblock_coder.py    # edit block 格式
│   │   ├── wholefile_coder.py    # 整文件格式
│   │   ├── udiff_coder.py        # unified diff 格式
│   │   ├── patch_coder.py        # patch 格式
│   │   ├── search_replace.py     # 搜索替换格式
│   │   └── *.py + prompts/*.py   # 各种格式的提示词
```

### 2.2 关键文件逐行解读

#### (1) `aider/args.py` — 参数配置（第 760 行）

`--yes-always` 是核心参数，自动确认所有对话框：

```python
"--yes-always",  # 第 760 行
```

`--auto-lint` 和 `--auto-test` 控制编辑后自动检查：

```python
"--lint-cmd",    # 第 534 行：自定义 lint 命令
"--auto-lint",   # 第 543 行：编辑后自动运行 lint（默认 True）
"--test-cmd",    # 第 549 行：测试命令
"--auto-test",   # 第 554 行：编辑后自动运行测试（默认 False）
```

#### (2) `aider/io.py` — 确认对话框机制（第 807-925 行）

```python
def confirm_ask(self, question, default="y", explicit_yes_required=False, ...):
    # ...
    if self.yes is True:                            # 第 866 行
        res = "n" if explicit_yes_required else "y"  # 第 867 行
    # self.yes = True 由 --yes-always 设置
```

**重要**：`--yes-always` 会让 `confirm_ask` 自动返回 "y"，但不影响 `explicit_yes_required=True` 的提问（会返回 "n"）。

#### (3) `aider/coders/base_coder.py` — 核心 Agent 循环（第 1599-1623 行）

```python
if edited and self.auto_lint:                        # 第 1599 行
    lint_errors = self.lint_edited(edited)            # 执行 lint
    self.auto_commit(edited, context="Ran the linter")
    if lint_errors:
        ok = self.io.confirm_ask("Attempt to fix lint errors?")  # 第 1604 行
        if ok:
            self.reflected_message = lint_errors      # 喂回给模型修复
            return

shared_output = self.run_shell_commands()             # 第 1609 行

if edited and self.auto_test:                         # 第 1616 行
    test_errors = self.commands.cmd_test(self.test_cmd)
    if test_errors:
        ok = self.io.confirm_ask("Attempt to fix test errors?")
        if ok:
            self.reflected_message = test_errors
            return
```

**Aider 的工作流程**：
1. 模型生成代码 → 应用到文件 → 保存
2. 如果有 lint 错误 → 问用户 → 修复
3. 执行 shell 命令（如果有）
4. 如果有测试错误 → 问用户 → 修复

#### (4) `aider/linter.py` — Lint 机制

```python
class Linter:
    def __init__(self, encoding="utf-8", root=None):
        self.languages = dict(
            python=self.py_lint,         # 只有 Python 有内置 lint
        )
        self.all_lint_cmd = None          # 自定义 lint 命令
```

**问题**：Aider 内置 lint 只支持 Python。Java 需要自定义 `--lint-cmd "javac"`，但 javac 返回的是**编译错误**（exit code ≠ 0 时才有输出），Aider 的 lint 机制只会在 exit code ≠ 0 时把输出喂回给模型。

---

## 3. 安装与配置

### 3.1 pip 安装（推荐）

```bash
pip install aider-chat
# 验证
aider --version
# 输出: aider 0.86.2
```

### 3.2 从源码安装

```bash
cd /workspace/aider
pip install -e .
```

**为什么从源码安装**：可以修改源码、加调试输出，理解内部运行机制。

### 3.3 配置国内大模型

Aider 通过 `--openai-api-base` 支持任何 OpenAI 兼容的 API：

```bash
# 智谱 GLM-4-Flash
export AIDER_OPENAI_API_BASE="https://open.bigmodel.cn/api/paas/v4"
export AIDER_API_KEY="openai=你的智谱key"

# 或命令行传参
aider --model openai/glm-4-flash \
  --openai-api-base "https://open.bigmodel.cn/api/paas/v4" \
  --api-key "openai=你的智谱key"
```

**支持的国内模型**：
- 智谱：`openai/glm-4-flash`（免费）
- 深度求索：`openai/deepseek-chat`
- 通义千问：`openai/qwen-plus`
- 百度文心：需通过千帆平台

---

## 4. Aider 核心能力分析

### 4.1 多种编辑格式

Aider 支持 5 种编辑格式，各有利弊：

| 格式 | 源码文件 | 说明 | 适用场景 |
|---|---|---|---|
| `whole` | `wholefile_coder.py` | 整文件重写 | 小文件、新文件创建 |
| `editblock` | `editblock_coder.py` | 搜索替换块 | 常规修改 |
| `udiff` | `udiff_coder.py` | unified diff | 精细修改 |
| `patch` | `patch_coder.py` | patch 格式 | 跨文件变更 |
| `search_replace` | `search_replace.py` | 搜索替换 | 局部修改 |

对于 glm-4-flash 等较弱模型，默认用 `whole` 格式（整文件重写，不容易搞错缩进）。

对于 GPT-4、Claude 等强模型，用 `udiff` 或 `editblock`（更精准）。

### 4.2 Auto-approve 机制

与 Roo-Code 的对比：

| 特性 | Aider | Roo-Code |
|---|---|---|
| 自动确认编辑 | ✅ `--yes-always` | ✅ `alwaysAllowWrite` |
| 自动确认读文件 | ✅ 默认自动 | ✅ `alwaysAllowReadOnly` |
| 自动确认命令执行 | ❌ 每次问 | ✅ `alwaysAllowExecute` |
| 命令白名单 | ❌ 无 | ✅ `allowedCommands: ["javac *"]` |
| 自动 lint 修复 | ✅ `--auto-lint` + 确认 | ✅ `execute_command` agent 循环 |

### 4.3 项目探索能力

Aider 没有 Roo-Code 的 `list_files` / `search_files` 工具。它通过 `repo-map` 功能了解项目：

```bash
# 启用 repo-map（自动生成项目地图）
--map-refresh auto    # 自动刷新
--map-multiplier 1.0  # 地图大小缩放
```

Repo-map 是用 tree-sitter 解析代码生成的函数/类列表摘要，不是完整文件内容。

### 4.4 错误修复循环

Aider 的修复循环是**线性的**（编辑→lint→修复→结束），不是**迭代的**（Roo-Code 是工具调用→结果反馈→再调用→...）。这意味着：

- Aider 最多修复一轮 lint 错误
- Roo-Code 可以多轮迭代直到编译通过

---

## 5. 测试：自然语言写 Java + 编译

### 5.1 测试项目搭建

**文件**：7 个 Java 文件，308 行，图书馆系统（Book/Member/DataStore/Service）

```
codegen-test/
├── src/
│   ├── model/Book.java         (id, title, author, isbn, publishedYear)
│   ├── model/Member.java       (id, name, email)
│   ├── service/BookService.java     (接口)
│   ├── service/BookServiceImpl.java (实现)
│   ├── service/MemberService.java   (接口)
│   ├── store/DataStore.java         (泛型接口)
│   └── store/impl/InMemoryDataStore.java (HashMap 实现)
```

### 5.2 需求文档

```
为图书馆系统添加借书还书功能:
1. Book.java 加 borrowed + borrowedByMemberId 字段
2. BookService.java 加 borrowBook + returnBook 方法
3. 创建 MemberServiceImpl.java（遵循 DataStore 模式）
4. 实现借还书逻辑（检查书存在、未借出、会员存在）
```

### 5.3 运行 Aider 测试

```bash
cd /workspace/codegen-test

# 先 git 初始化（Aider 依赖 git 做自动提交）
git init && git add -A && git config user.email "test@test.com" && git config user.name "test" && git commit -m "init"

# 运行 Aider
aider --model openai/glm-4-flash \
  --openai-api-base "https://open.bigmodel.cn/api/paas/v4" \
  --api-key "openai=你的智谱key" \
  --yes-always --no-auto-lint \
  --file src/model/Book.java \
  --file src/service/BookService.java \
  --file src/service/impl/BookServiceImpl.java \
  --file src/service/MemberService.java \
  --message "$(cat requirement.txt)"
```

**参数解释**：
- `--yes-always`：自动确认所有编辑，不需要手动按 Y
- `--no-auto-lint`：禁用自动 lint（因为 Java 没有内置 lint）
- `--file`：把文件加入上下文给模型看
- `--message`：需求文档内容

### 5.4 测试结果

| 需求项 | 完成度 | 代码质量 |
|---|---|---|
| Book.java 加字段 | ✅ 完全正确 | 字段 + getter/setter + 构造初始化 |
| BookService.java 加方法 | ✅ 完全正确 | borrowBook + returnBook 接口 |
| MemberServiceImpl.java | ✅ 创建 | 完美遵循 BookServiceImpl 的 DataStore 模式 |
| borrowBook 实现 | ⚠️ 部分 | 检查书存在 ✅，没检查会员 ❌ |
| returnBook 实现 | ✅ 完全正确 | 检查存在 → 归还 → 保存 |
| 编译 | ✅ **通过** | 0 错误 |

**代码亮点**：
- 生成的 `MemberServiceImpl` 完全遵循了 `BookServiceImpl` 的代码风格（构造注入 DataStore）
- `borrowBook` 正确检查了 `book.isBorrowed()` 状态
- `returnBook` 正确重置了 `borrowed` 和 `borrowedByMemberId`

**不足之处**：
- `BookServiceImpl` 没有注入 `MemberService`，`borrowBook` 无法验证会员是否存在
- 原因：需求文档要求注入但模型没做到，属于复杂跨文件依赖理解的短板

---

## 6. Aider 与 Roo-Code 的架构差异

### 6.1 根本区别：编辑驱动 vs 工具调用

| 维度 | Aider | Roo-Code |
|---|---|---|
| **工作方式** | 编辑驱动（对话→生成代码→应用） | 工具驱动（agent 循环→调用工具→反馈） |
| **文件操作** | 直接改文件（diff apply） | 通过工具调用（write_to_file / apply_diff） |
| **命令执行** | 无内置命令执行 `❌` | ✅ `execute_command` 工具 |
| **agent 循环** | 线性：生成→lint→结束 | 迭代：工具→结果→工具→... |
| **模型要求** | 低（只需文本生成和理解） | 高（需 tool calling 能力） |

### 6.2 edit_format 选择对模型的影响

Aider 的编辑格式决定了模型需要的智能水平：

```
whole 格式（glm-4-flash 适用）：模型输出完整文件内容 → Aider 直接写入
   ↓ 模型能力增强
editblock 格式：模型输出搜索替换块 → Aider 解析并应用
   ↓
udiff 格式：模型输出 unified diff → Aider 解析并应用
   ↓
patch 格式：模型输出 patch → Aider 解析并应用（最高精度）
```

Roo-Code 的工具调用要求模型必须支持 function calling（即 `tools` 参数），不支持就完全不能用。Aider 的 whole 格式甚至 GPT-3.5 都能用。

### 6.3 自动修复能力对比

| 能力 | Aider | Roo-Code |
|---|---|---|
| 编译错误修复 | ⚠️ 需 `--lint-cmd "javac"` + `--auto-lint` | ✅ `execute_command` 编译 + agent 循环 |
| 多轮迭代修复 | ❌ 最多 1 轮 | ✅ 5 层重试（consecutiveMistakeCount + 指数退避 + noToolsUsed） |
| 自动推送 | ❌ 等用户确认 | ✅ 模型不用工具时 push noToolsUsed |
| 死循环防护 | ❌ 无 | ✅ ToolRepetitionDetector |

### 6.4 agent 循环对比

**Aider 的循环**（`base_coder.py` 第 1560-1623 行）：
```
模型生成代码 → 应用到文件 → 跑 lint → 问用户是否修复 → 修复 → 结束
```

**Roo-Code 的循环**（`Task.ts` 第 2461 行 `recursivelyMakeClineRequests`）：
```
模型思考 → 调用工具(读文件/写文件/执行命令) → 工具结果回传 → 模型再思考 → ... → attempt_completion
```

---

## 7. 代码质量对比

### 7.1 相同模型（glm-4-flash）下的对比

| 维度 | Aider | Roo-Code（理论上） |
|---|---|---|
| **文件编辑精度** | ✅ 高（whole 格式整文件重写，不会漏行） | ⚠️ 依赖工具调用质量 |
| **跨文件理解** | ✅ 多文件同时上下文，能看到所有关联关系 | ✅ agent 可逐个读文件探索 |
| **业务逻辑完整性** | ⚠️ 可能漏掉跨文件依赖 | ✅ agent 可先探索再改 |
| **编译验证** | ❌ 不会自动编译 | ✅ 可 execute_command 编译 |
| **对弱模型友好度** | ✅ 高（whole 格式不要求 tool calling） | ❌ 低（必须 tool calling） |

### 7.2 代码质量打分

| 类别 | Aider (glm-4-flash) | Roo-Code (glm-4-flash) | Roo-Code (DeepSeek V3) |
|---|---|---|---|
| 语法正确性 | ★★★★★ | ★★（工具调用差） | ★★★★★ |
| 逻辑完整性 | ★★★★☆ | ★★ | ★★★★★ |
| 项目风格一致 | ★★★★★ | ★★ | ★★★★★ |
| 编译验证 | ★☆☆☆☆ | ★★★★ | ★★★★★ |
| **总分** | **★★★★☆** | **★★☆☆☆** | **★★★★★** |

> 注意：Roo-Code 用 glm-4-flash 分数低是因为 glm-4-flash 的工具调用遵从度低（第 14 章已验证），换成 DeepSeek V3 后完全不同

### 7.3 选型建议

| 你的场景 | 推荐工具 | 原因 |
|---|---|---|
| 用国产弱模型（glm-4-flash） | **Aider** | 不需要 tool calling，whole 格式就能工作 |
| 用强模型（DeepSeek V3 / GPT-4） | **Roo-Code** | agent 循环 + 工具调用可自动编译验证 |
| 需要编译错误自动修复 | **Roo-Code** | execute_command + 5 层重试 |
| 不关心编译，只关心改代码 | **Aider** | 编辑精度高，代码风格好 |
| 项目大、文件多、不熟 | **Roo-Code** | 自主探索项目结构 |

---

## 8. 避坑清单

### 避坑 1：Aider 必须配 git

```bash
# ❌ 会出问题
aider --no-git --yes-always ...

# ✅ 正确做法
git init && git add -A && git commit -m "init"
aider --yes-always ...
```

**原因**：Aider 用 git 做自动提交、回退和 diff 展示。`--no-git` 模式下有些功能不正常。

### 避坑 2：Aider 不会自动执行终端命令

```bash
# ❌ Aider 不会自动运行 javac
aider --message "创建 Sort.java, 用 javac 编译"

# ✅ Aider 只能创建/修改文件，编译需要手动
aider --message "创建 Sort.java"
javac Sort.java
```

**原因**：Aider 没有 `execute_command` 工具。它只能生成和编辑文件，不能执行终端命令。

### 避坑 3：Aider 的 --auto-lint 对 Java 无效

```bash
# ❌ 不会自动修复 Java 编译错误
aider --auto-lint --lint-cmd "javac" ...

# ✅ 正确理解：--auto-lint 只在 exit code ≠ 0 时把输出喂回模型
# 但即使喂回去了，Aider 也只修复一轮
```

**原因**：Aider 的 lint 机制是"编辑后跑一次 lint → 有错就修复 → 结束"。不是迭代修复。

### 避坑 4：Aider 非 TTY 模式下可能不工作

```bash
# ❌ 在 Docker 或无终端环境可能看到
Warning: Input is not a terminal (fd=0).

# ✅ 解决方法：加上 --yes-always 和 --no-auto-lint
```

**原因**：Aider 依赖终端交互，非 TTY 模式下确认对话框可能没有效果。

### 避坑 5：旧版 Aider 的 edit 格式不同

```bash
# v0.86+ 默认用 whole 格式（对弱模型友好）
# 旧版可能用 editblock 格式（需要模型输出特定格式的代码块）
```

---

## 9. 附录：关键源码文件索引

| 功能 | 源码位置 | 关键行 |
|---|---|---|
| 参数解析 | `aider/args.py` | 第 760 行：`--yes-always`；第 534 行：`--lint-cmd` |
| 确认对话框 | `aider/io.py` | 第 807 行：`confirm_ask` 函数；第 866 行：`self.yes is True` 自动确认 |
| 核心 agent 循环 | `aider/coders/base_coder.py` | 第 1599 行：auto_lint 逻辑；第 1616 行：auto_test 逻辑 |
| Lint 机制 | `aider/linter.py` | 第 21 行：`class Linter`；第 27 行：仅 Python 内置 |
| LLM 配置 | `aider/llm.py` | 模型加载、编辑格式选择 |
| Edit 格式 | `aider/coders/editblock_coder.py` | 搜索替换块编辑 |
| Whole 格式 | `aider/coders/wholefile_coder.py` | 整文件重写 |
| Udiff 格式 | `aider/coders/udiff_coder.py` | unified diff 编辑 |
| Patch 格式 | `aider/coders/patch_coder.py` | patch 文件编辑 |
| 命令执行 | `aider/commands.py` | shell 命令、git 操作 |

### Roo-Code 关键文件（对比用）

| 功能 | 源码位置 |
|---|---|
| 工具枚举 | `packages/types/src/tool.ts` 第 24-49 行（24 个工具） |
| Agent 循环 | `src/core/task/Task.ts` `recursivelyMakeClineRequests` |
| Auto-approve | `src/core/auto-approval/index.ts` 第 17-35 行 |
| 编译修复推送 | `src/core/prompts/responses.ts` 第 42 行 `noToolsUsed()` |
| PDF/DOCX 解析 | `src/integrations/misc/extract-text.ts` 第 3-44 行 |
| 连续错误计数 | `src/core/task/Task.ts` 第 2483 行 |
| 指数退避重试 | `src/core/task/Task.ts` 第 4268 行 |

---

> **一句话结论**：
> - 用国产弱模型（glm-4-flash）选 **Aider**（不需要 tool calling）
> - 用强模型（DeepSeek V3 / GPT-4）选 **Roo-Code**（agent 循环可自动编译验证）
> - Aider 编辑精度高但不会自动编译；Roo-Code 能自动探索+编译但需要强模型

*文档版本: v1.0 | 生成时间: 2026-07-19 | 基于 Aider v0.86.2 源码分析与实测*
