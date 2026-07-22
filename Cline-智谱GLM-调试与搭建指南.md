# Cline 驱动智谱 GLM 调试与搭建指南

> 目标：让 Cline 这个插件（coding agent）能接上智谱 GLM-4-Flash 模型，用自然语言写 Java、自动编译并运行。同时把调试过程中遇到的真实错误和坑全部记录下来，方便你手动复现。
>
> 适用读者：技术一般、命令不熟，想照着一步步操作的人。

## 背景与结论

**Cline** 是一个类似 AI 程序员的 VS Code 插件（coding agent）。**智谱 GLM-4-Flash** 是智谱 AI 的轻量模型，速度快、价格低，但它是“弱模型”，调用工具时容易犯小错误。

当 Cline 用 GLM-4-Flash 编辑已经存在的文件时，模型经常**忘记填写 `old_text` 参数**（编辑已有文件必须告诉它原来的内容是什么）。Cline 原代码遇到这种情况直接 `throw`（抛错），结果模型看不懂，反复提交同样的错误调用，最终空转卡死、任务 `[abort]`。

本次修复：把**抛错**改成**返回一段可自愈的提示文本**（里面包含当前文件内容），让模型自己纠正。修好后，端到端跑通：自然语言 → 生成 `Calculator.java` → `javac` 编译 → `java` 运行 → 输出结果。

最终发布：`https://github.com/liliangxing/cline/releases/tag/v0.0.1-debug`

---

## 整体流程图

![Cline 智谱调试全流程](images/cline-zhipu/01-flow.png)

---

## 第一部分：环境准备（跟着做即可）

### 1.1 需要的工具

| 工具 | 作用 | 怎么安装 |
|------|------|----------|
| `git` | 从 GitHub 下载代码 | 一般都自带，没有的话 `apt install git` |
| `bun` | Cline 项目用 Bun 运行/构建 | `curl -fsSL https://bun.sh/install \| bash` |
| `node` / `npx` | 打包 vsix 需要 | `apt install nodejs npm` 或官网安装 |
| `gh` (GitHub CLI) | 发布 Release 用 | 见 https://cli.github.com/ |
| Java JDK | 编译运行 Java 示例 | `apt install default-jdk` |

> **为什么用 bun？** Cline 的源码用的是 Bun 的 workspace 和 runtime，不是 npm。用 `npm install` 可能跑不通，所以必须装 bun。

### 1.2 设置 Bun 环境

```bash
# 安装 Bun（第一次安装时）
curl -fsSL https://bun.sh/install | bash

# 安装完后，把 bun 加到当前 shell 环境
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

# 验证
bun --version
# 预期看到类似 1.3.14
```

> **避坑**：每次新开终端，都要重新执行 `export BUN_INSTALL...` 和 `export PATH...`，否则命令会提示 `bun: command not found`。可以把它写进 `~/.bashrc` 里，以后就不用重复输入了。

---

## 第二部分：下载代码

### 2.1 从 GitHub fork 仓库

如果你只想看效果，可以直接克隆我 fork 的仓库（里面已经有修复了）：

```bash
# 进入你的工作目录（这里用 /workspace/forks，你可以换成自己的）
mkdir -p /workspace/forks
cd /workspace/forks

# 克隆仓库
git clone https://github.com/liliangxing/cline.git
cd cline
```

### 2.2 查看当前分支和提交

```bash
git branch --show-current   # 看当前分支，应该是 main
git log --oneline -5         # 看最近 5 条提交记录
```

你会看到类似：

```
0101fcb fix(editor): 非破坏性回灌——编辑已存在文件缺 old_text 时返回文件内容与纠正指令，而非抛错中断（防止弱模型空转）
c564045 chore(cli): includes version numbers in hub status output (#12358)
...
```

> **说明**：第一条 `0101fcb` 就是修复提交。如果你要从零开始修改，可以退回到它前面的版本，把抛错改回来，再重新测试。这里我们不回退，直接基于已修复的代码继续。

---

## 第三部分：安装依赖

### 3.1 执行 bun install

```bash
cd /workspace/forks/cline
bun install
```

这一步会下载所有依赖包，可能要几分钟。成功后你会看到：

```
+ @biomejs/biome@2.4.5
+ @types/bun@1.3.14
...
4887 packages installed [33.23s]
```

> **避坑**：如果网络慢，可能会失败。可以重试一次，或者换手机热点。Cline 依赖很多，耐心等。

### 3.2 检查项目结构

```bash
ls -la
ls apps/cli/
ls sdk/packages/core/src/extensions/tools/executors/
```

重点关注这几个目录：
- `apps/cli/`：命令行入口，打包 vsix 在这里
- `sdk/packages/core/src/extensions/tools/executors/editor.ts`：修复文件所在
- `apps/cli/dist/`：构建后自动生成的文件

---

## 第四部分：查看和理解修复（重点）

### 4.1 打开修复文件

```bash
# 用系统自带的 cat 或 less 查看
less sdk/packages/core/src/extensions/tools/executors/editor.ts
```

找到大约第 231 行，你会看到：

```ts
if (input.old_text == null) {
    // Non-destructive, self-correcting feedback instead of a hard throw.
    const current = await fs.readFile(filePath, { encoding });
    return (
        "EDIT FAILED: parameter `old_text` is required to replace text in an " +
        "existing file, but it was not provided.\n" +
        "Fix by doing ONE of:\n" +
        "1) Provide `old_text` as the EXACT, verbatim substring to replace " +
        "(copy it precisely from the current file below) together with `new_text`.\n" +
        "2) Provide `insert_line` to insert `new_text` at a specific line.\n" +
        "3) To rewrite the whole file, read it first, then either call this " +
        "tool on a non-existent path with `new_text`, or overwrite via the shell.\n\n" +
        `Current contents of ${filePath}:\n\n${current}`
    );
}
```

### 4.2 修复前后对比

![修复前后对比](images/cline-zhipu/02-fix-diff.png)

#### 修复前（原代码）

```ts
if (input.old_text == null) {
    throw new Error(
        "Parameter `old_text` is required when editing an existing file without `insert_line`",
    );
}
```

**为什么会出问题？**
- 模型提交了一个编辑请求，但忘了写 `old_text`。
- 程序直接 `throw new Error`，工具执行失败。
- Cline 把错误信息给模型看，但模型看不懂，再次提交同样缺少 `old_text` 的调用。
- 循环往复，直到达到错误上限，任务被 `[abort]`。

#### 修复后

- 不抛错、不修改文件，只是**返回一段提示文本**。
- 这段文本里包含：**失败原因** + **三种正确做法** + **当前文件内容**。
- 模型看到当前文件内容后，下次调用就能填对 `old_text`。
- 整个循环继续推进，最终 `[task complete]`。

> **大白话**：原来的代码像是一个暴躁老师，学生答错一题就摔卷子；修改后变成耐心老师，把正确答案和卷子一起还给学生，让学生自己改。

---

## 第五部分：验证修复（单元测试）

### 5.1 直接跑测试脚本

我在仓库里放了一个独立测试脚本 `editor_fix_test.ts`，不需要配复杂环境，直接跑：

```bash
cd /workspace/forks/cline
bun editor_fix_test.ts
```

### 5.2 预期输出

```
THREW: false
RESULT_CONTAINS_EDIT_FAILED: true
RESULT_CONTAINS_FILE_CONTENT: true
FILE_UNCHANGED_(non-destructive): true
--- result (head) ---
EDIT FAILED: parameter `old_text` is required to replace text in an existing file, but it was not provided.
Fix by doing ONE of:
1) Provide `old_text` as the EXACT, verbatim substring to replace ...
...
```

### 5.3 这四个判断代表什么

| 输出 | 含义 | 为什么重要 |
|------|------|------------|
| `THREW: false` | 没有抛错 | 原代码会抛错，导致循环中断 |
| `RESULT_CONTAINS_EDIT_FAILED: true` | 返回了纠正提示 | 让模型知道该做什么 |
| `RESULT_CONTAINS_FILE_CONTENT: true` | 返回了当前文件内容 | 模型能看到原文，填对 `old_text` |
| `FILE_UNCHANGED_(non-destructive): true` | 文件没被乱改 | 保证安全，不会破坏已有代码 |

> **如果 `THREW: true` 怎么办？** 说明修复没生效，请回到 `editor.ts` 检查第 231 行是否还是 `throw new Error`。

---

## 第六部分：构建项目

### 6.1 执行 build 命令

```bash
cd /workspace/forks/cline
bun run build
```

这个命令实际执行的是：

```bash
bun run clean && bun install && bun run build:sdk && bun -F @cline/cli build
```

意思是：先清理 → 重新安装依赖 → 构建 SDK → 构建 CLI。

### 6.2 构建成功标志

最后几行应该是：

```
@cline/cli build: Exited with code 0
build_exit=0
```

看到 `0` 就是成功。

### 6.3 构建失败常见原因

| 失败现象 | 可能原因 | 解决 |
|----------|----------|------|
| `bun: command not found` | 环境变量没加 | 执行 `export BUN_INSTALL="$HOME/.bun"; export PATH="$BUN_INSTALL/bin:$PATH"` |
| `error: Cannot find module` | 依赖没装好 | 重新跑 `bun install` |
| 某个包 `Exited with code 1` | 代码有语法错误 | 检查你修改的 `editor.ts` 是否有括号不匹配、引号没闭合 |

---

## 第七部分：打包成 vsix（安装文件）

### 7.1 进入 CLI 目录

```bash
cd /workspace/forks/cline/apps/cli
```

### 7.2 用 npx 打包

```bash
npx -y @vscode/vsce package --no-dependencies
```

> **为什么用 `npx -y @vscode/vsce`？** 因为 `vsce` 不一定装在你的环境里。我第一次用 `vsce package` 直接报错：`sh: 1: vsce: not found`。`npx -y @vscode/vsce` 会临时下载最新版 `vsce` 并执行，不用提前安装。
>
> `--no-dependencies` 表示不要把 `node_modules` 也打进包，否则文件太大。

### 7.3 成功后的输出

```
 DONE  Packaged: cline-debug-3.0.44.vsix (1740 files, 5.93 MB)
```

> **注意**：实际文件名可能叫 `cline-3.0.44.vsix` 或 `cline-debug-3.0.44.vsix`，取决于 `apps/cli/package.json` 里的 `name`。我们发布时也可以改文件名，但包里的版本是 3.0.44。

### 7.4 验证包里确实包含修复

```bash
# 列出包里的文件
unzip -l cline-debug-3.0.44.vsix | head

# 检查修复代码是否在包里
unzip -p cline-debug-3.0.44.vsix dist/index.js | grep -c "EDIT FAILED"
# 预期输出：1（代表找到了一次）

# 检查旧代码是否还在包里
unzip -p cline-debug-3.0.44.vsix dist/index.js | grep -c "throw new Error"
# 预期输出：0（代表没有抛错逻辑了）
```

> **为什么要检查？** 确认你打包的不是旧代码。有时候你以为改了，但 build 没重新跑，包里还是旧内容。

---

## 第八部分：提交代码并推送

### 8.1 查看修改

```bash
cd /workspace/forks/cline
git status
```

你会看到修改过的文件（比如 `editor.ts`）和未跟踪的测试文件（`editor_fix_test.ts`）。

### 8.2 添加到 git 暂存区

```bash
git add sdk/packages/core/src/extensions/tools/executors/editor.ts
git add editor_fix_test.ts
```

### 8.3 提交

```bash
git commit -m "fix(editor): 弱模型编辑文件缺 old_text 时返回纠正提示而非抛错"
```

### 8.4 推送到 GitHub

如果你用 HTTPS 方式，并且带 Personal Access Token（PAT）：

```bash
git push "https://x-access-token:YOUR_GITHUB_PAT@github.com/liliangxing/cline.git" main
```

> **避坑**：不要直接 `git push origin main`，因为 GitHub 现在基本不允许密码登录，会提示 `invalid credentials`。正确方式是 URL 里带 `x-access-token:<PAT>`。
>
> `YOUR_GITHUB_PAT` 替换成你的 GitHub Personal Access Token（通常以 `ghp_` 开头）。

---

## 第九部分：发布到 GitHub Release

### 9.1 创建 Release（如果还没有）

```bash
export GH_TOKEN="YOUR_GITHUB_PAT"
gh auth login --with-token

gh release create v0.0.1-debug \
  --repo liliangxing/cline \
  --title "Cline 智谱 GLM 修复版" \
  --notes "修复弱模型编辑已有文件时缺 old_text 导致的卡死问题。"
```

### 9.2 上传 vsix

```bash
gh release upload v0.0.1-debug cline-debug-3.0.44.vsix --repo liliangxing/cline
```

### 9.3 如果文件名已存在要替换

GitHub 不允许同一个 Release 里有两个同名文件。如果要上传同名的新文件，先删除旧的：

```bash
gh release delete-asset v0.0.1-debug cline-debug-3.0.44.vsix --repo liliangxing/cline --yes
gh release upload v0.0.1-debug cline-debug-3.0.44.vsix --repo liliangxing/cline
```

---

## 第十部分：用 Cline CLI 驱动智谱 GLM 实跑

### 10.1 设置环境变量

```bash
export ZHIPU_API_KEY="你的智谱 API Key"
```

> API Key 从 https://open.bigmodel.cn/ 注册后获取。它是一个长字符串，复制粘贴即可。

### 10.2 执行 CLI 命令

```bash
cd /workspace/forks/cline
bun apps/cli/dist/index.js \
  "用 Java 写一个计算器类 Calculator，含加减乘除；除数为 0 时返回 NaN" \
  -P openai-compatible \
  -k $ZHIPU_API_KEY \
  -m glm-4-flash-250414 \
  -c plugin-java-demo2 \
  --auto-approve \
  --data-dir ./cline-state \
  --retries 3
```

### 10.3 命令拆解

![CLI 命令拆解](images/cline-zhipu/04-command-anatomy.png)

| 参数 | 含义 |
|------|------|
| `bun apps/cli/dist/index.js` | 运行 Cline CLI |
| `"..."` | 你的自然语言任务 |
| `-P openai-compatible` | 使用 OpenAI 兼容的 provider（智谱就是这种） |
| `-k $ZHIPU_API_KEY` | API Key |
| `-m glm-4-flash-250414` | 模型名称 |
| `-c plugin-java-demo2` | 对话 ID，相当于这次任务的名字 |
| `--auto-approve` | 自动批准工具调用，不需要手动点确认 |
| `--data-dir ./cline-state` | 状态保存目录 |
| `--retries 3` | 出错时重试 3 次 |

### 10.4 预期运行过程

```
[Tool Request] write_to_file
  path: plugin-java-demo2/Calculator.java
...
[command request] Command: javac Calculator.java
...
[command request] Command: java Calculator
[command output] 10 + 5 = 15
...
[command output] 10 / 0 = 0
...
[task complete]
```

> **注意**：这个模型是弱模型，它可能在“除数为 0 时返回 NaN”这个业务逻辑上实现得不太准确。我实际跑出来是返回 0，但这是模型理解问题，不是 Cline 工具问题。重要的是：**它没有卡死，任务完整走完了**。

---

## 第十一部分：验证产物

### 11.1 查看生成的文件

```bash
ls -la plugin-java-demo2/
```

你会看到：

```
Calculator.java
Calculator.class
```

### 11.2 手动运行

```bash
cd plugin-java-demo2
javac Calculator.java
java Calculator
```

如果看到输出类似：

```
10 + 5 = 15
10 - 5 = 5
10 * 5 = 50
10 / 5 = 2
10 / 0 = 0
```

就说明闭环成功了。

### 11.3 真实的避坑：类名可能带路径

实际生成的 `Calculator.java` 第一行可能是：

```java
public class workspace.forks.cline.plugin-java-demo2.Calculator {
```

这会导致 `javac` 报错，因为类名里不能有“.”，而且类名必须和文件名一致。

**正确做法**：手动把它改成：

```java
public class Calculator {
```

然后再跑：

```bash
javac Calculator.java
java Calculator
```

---

## 第十二部分：调试排查命令速查表

![调试工具箱](images/cline-zhipu/05-debug-toolkit.png)

### 12.1 定位修复文件

```bash
grep -n "old_text" sdk/packages/core/src/extensions/tools/executors/editor.ts
```

看到第 231 行附近有 `if (input.old_text == null)` 就对了。

### 12.2 确认修复是否生效

```bash
grep -c "EDIT FAILED" sdk/packages/core/src/extensions/tools/executors/editor.ts
# 预期：1

grep -c "throw new Error" sdk/packages/core/src/extensions/tools/executors/editor.ts
# 预期：0
```

### 12.3 检查构建日志

```bash
# 如果用了脚本构建
tail -50 /workspace/forks/cline_build.log

# 关键看这几行
# build_exit=0  -> 成功
# vsix_exit=0   -> 打包成功
# vsix_exit=127 -> vsce 命令没找到
```

### 12.4 检查 vsix 里是否包含修复

```bash
unzip -p cline-debug-3.0.44.vsix dist/index.js | grep -c "EDIT FAILED"
# 预期：1
```

### 12.5 检查网络请求（进阶）

如果模型完全没反应，可以用 `curl` 直接测试智谱端点是否通：

```bash
curl -X POST https://open.bigmodel.cn/api/paas/v4/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ZHIPU_API_KEY" \
  -d '{
    "model": "glm-4-flash-250414",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

如果返回类似 `{choices: [...]}`，说明 API Key 和端点都 OK。如果返回 `401`，说明 Key 错了。如果返回 `404`，说明端点错了（见避坑清单）。

---

## 第十三部分：避坑清单（必须看）

![避坑清单](images/cline-zhipu/03-pitfalls.png)

### 坑 1：vsce 命令找不到

```
sh: 1: vsce: not found
```

**原因**：没有全局安装 `vsce`。

**解决**：

```bash
npx -y @vscode/vsce package --no-dependencies
```

### 坑 2：Java 类名带路径

```java
public class workspace.forks.cline.plugin-java-demo2.Calculator {
```

**原因**：弱模型把当前工作目录路径当成类名写了。

**解决**：手动改成 `public class Calculator {`。

### 坑 3：端点用错

```
https://open.bigmodel.cn/api/compat
```

这个端点会返回 `{"code":500,"msg":"404 NOT_FOUND","success":false}`，不是真正的智谱模型后端。

**正确端点**：

```
https://open.bigmodel.cn/api/paas/v4
```

### 坑 4：Release 上传同名文件冲突

```
422 Validation Failed
```

**原因**：同一个 Release 里已经有同名 vsix。

**解决**：先删除旧资产，再上传新资产。

```bash
gh release delete-asset v0.0.1-debug cline-debug-3.0.44.vsix --repo liliangxing/cline --yes
gh release upload v0.0.1-debug cline-debug-3.0.44.vsix --repo liliangxing/cline
```

### 坑 5：git push 认证失败

```
remote: Invalid username or password.
```

**原因**：GitHub 不再接受普通密码，需要用 Personal Access Token。

**解决**：

```bash
git push "https://x-access-token:YOUR_GITHUB_PAT@github.com/liliangxing/cline.git" main
```

---

## 第十四部分：从 GitHub Release 下载安装

### 14.1 下载 vsix

打开浏览器访问：

```
https://github.com/liliangxing/cline/releases/tag/v0.0.1-debug
```

下载 `cline-debug-3.0.44.vsix`。

### 14.2 安装到 VS Code

1. 打开 VS Code
2. 左侧点击 Extensions（四个方块图标）
3. 右上角三个点 `...` → `Install from VSIX...`
4. 选择下载的 `.vsix` 文件

### 14.3 配置 Cline 使用智谱

1. 安装后打开 Cline 面板
2. 在 Provider 选择 `OpenAI Compatible`
3. 填写：
   - Base URL：`https://open.bigmodel.cn/api/paas/v4`
   - API Key：你的智谱 API Key
   - Model：`glm-4-flash-250414`

---

## 第十五部分：总结

| 步骤 | 关键命令 | 成功标志 |
|------|----------|----------|
| 克隆代码 | `git clone https://github.com/liliangxing/cline.git` | 目录 `cline/` 出现 |
| 安装依赖 | `bun install` | `4887 packages installed` |
| 查看修复 | `grep -n "old_text" editor.ts` | 第 231 行返回纠正提示 |
| 跑单元测试 | `bun editor_fix_test.ts` | `THREW: false` |
| 构建 | `bun run build` | `build_exit=0` |
| 打包 | `npx -y @vscode/vsce package --no-dependencies` | 生成 `.vsix` |
| 提交 | `git commit` / `git push` | GitHub 提交记录更新 |
| 发布 | `gh release upload` | Release 页面出现 vsix |
| 实跑 | `bun apps/cli/dist/index.js ...` | `[task complete]` |
| 验证 | `javac && java` | 看到正确输出 |

整个过程最核心的一点就是：**不要把弱模型的错误变成致命错误，而是把纠正信息回灌给模型，让它自己修复**。这是 Cline 能接上 GLM-4-Flash 的关键。

---

## 附录：完整命令速查

```bash
# 1. 环境
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
export ZHIPU_API_KEY="你的智谱Key"

# 2. 下载
git clone https://github.com/liliangxing/cline.git
cd cline

# 3. 依赖
bun install

# 4. 测试修复
bun editor_fix_test.ts

# 5. 构建
bun run build

# 6. 打包
cd apps/cli
npx -y @vscode/vsce package --no-dependencies

# 7. 验证包内修复
unzip -p cline-debug-3.0.44.vsix dist/index.js | grep -c "EDIT FAILED"

# 8. 提交（示例）
cd ../..
git add .
git commit -m "fix(editor): 非破坏性回灌修复弱模型缺 old_text"
git push "https://x-access-token:YOUR_GITHUB_PAT@github.com/liliangxing/cline.git" main

# 9. 发布
gh release upload v0.0.1-debug apps/cli/cline-debug-3.0.44.vsix --repo liliangxing/cline

# 10. 实跑
bun apps/cli/dist/index.js \
  "用 Java 写 Calculator 类，含加减乘除" \
  -P openai-compatible -k $ZHIPU_API_KEY \
  -m glm-4-flash-250414 -c plugin-java-demo2 \
  --auto-approve --data-dir ./cline-state --retries 3

# 11. 验证
cd plugin-java-demo2
sed -i 's/public class .*.Calculator/public class Calculator/' Calculator.java
javac Calculator.java
java Calculator
```

---

> 版本：2026-07-18
> 基于 Cline fork `liliangxing/cline` commit `0101fcb` 整理。
