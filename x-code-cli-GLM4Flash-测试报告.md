# x-code-cli + GLM-4-Flash 工具调用测试报告

## 测试环境

| 项目 | 详情 |
|------|------|
| 源代码 | https://github.com/liliangxing/x-code-cli（commit `HEAD`） |
| 分支 | main |
| 构建方式 | `pnpm install && pnpm build`（tsc + esbuild） |
| 运行方式 | `node packages/cli/dist/cli.js`（`xc` 命令） |
| LLM | 智谱 GLM-4-Flash-250414 |
| 模型 ID | `zhipu:glm-4-flash-250414` |
| 模式 | `-p`（非交互 print 模式）+ `-t`（trust 跳过确认） |

## 已验证的能力

### 写文件工具

write 工具**完全正常**。

```bash
xc -m zhipu:glm-4-flash-250414 -p -t "Create /tmp/xc-test2/calc.py with a Python function that adds two numbers"
```

结果：

```python
def add(a, b):
    return a + b

if __name__ == "__main__":
    print(add(1, 2))
```

### 编译运行

bash 工具**完全正常**。

```bash
xc -m zhipu:glm-4-flash-250414 -p -t "Create /tmp/BubbleSort.java with bubble sort, compile and run"
```

结果：
- write 工具成功写入 `BubbleSort.java`（冒泡排序完整实现）
- bash 工具尝试调用 `javac` / `java`（环境无 JDK，但工具调用本身正确）

### Python 语法错误修复

**能修复**。提供明确的文件路径 + 具体错误描述时效果最好。

```bash
xc -p -t "Fix all errors in /tmp/broken2.py: 'retrun' → 'return', 'prumes' → 'primes', missing colon..."
```

修复合计：`retrun` typo × 2、`prumes` typo、`for x in numbers` 缺冒号 — **4/4 全部修复**。

### 写文件 + 运行 + 修复 全流程

**部分工作**。以下提示词方式最稳定：

```bash
xc -p -t "Write code to /tmp/test.py. Run python3 /tmp/test.py. Fix errors, re-run."
```

文件被创建，工具调用触发，但模型在迭代修复时偶尔**只说不动**（描述"我来检查一下"但不执行工具）。

## 未通过 / 表现不稳定的场景

### C++ 错误修复

GLM-4-Flash **能调用 write 工具编辑文件，但生成的修复代码质量差**，会引入新错误：

- `bool swapped` → `bool swapped; = false`（破坏性修改）
- `break` → `break; = false`（破坏性修改）

### 复杂迭代排错

模型有时陷入**"描述-不执行"**循环：反复输出"Let me check the file"、"It seems there's an issue"，但不实际调用 read/write/bash 工具。在 `--max-turns` 达到上限后终止。

## 根因分析

| 问题 | 原因 |
|------|------|
| 工具调用**可以正常触发** | AI SDK + Zhipu provider 通道正常 |
| 模型"只说不动" | GLM-4-Flash 在 `-p` 模式下对复杂任务倾向于文本描述而非工具调用 |
| C++ 修复质量差 | GLM-4-Flash 对 C++ 语法理解较弱 |
| Python 修复合计率高 | Python 是 GLM-4-Flash 的强项 |

## 推荐实践

在 Windows 上使用 x-code-cli + GLM-4-Flash 时：

1. **明确描述所需操作**（写文件路径、编译命令、期望结果）
2. **分步执行**：先写、再编、最后运行，不要一步到位
3. **交互模式优先**：`xc`（不带 `-p`）能更充分利用 TUI 的 tool call 反馈，排错能力更强
4. **Python 最稳定**：需自动修复时优先用 Python
5. **C++/Java 建议用更强模型**：如 GLM-4-Plus 或 GLM-5

## 在 Windows 上复现

```powershell
# 1. 配置 API Key
set ZHIPU_API_KEY=your-key-here

# 2. 设置 xc 的 home 目录和项目目录
set X_CODE_HOME=%USERPROFILE%\.x-code
set X_CODE_PROJECT_DIR=%USERPROFILE%\xc-test

# 3. 测试写文件
xc -m zhipu:glm-4-flash-250414 -p -t "Create C:\Users\xxx\xc-test\hello.py that prints Hello World"

# 4. 测试修复错误
# 先手动创建一个有语法错误的文件，然后：
xc -m zhipu:glm-4-flash-250414 -p -t "Fix syntax errors in C:\Users\xxx\xc-test\broken.py. Run python"
```

## Linux 调试记录（本次）

```bash
# 构建
cd /workspace/x-code-cli
pnpm install && pnpm build

# 运行（使用 built dist）
export ZHIPU_API_KEY="your-key"
export X_CODE_HOME=/tmp/x-code-test
export X_CODE_PROJECT_DIR=/tmp/xc-test
node packages/cli/dist/cli.js -m zhipu:glm-4-flash-250414 -p -t "prompt here"
```
