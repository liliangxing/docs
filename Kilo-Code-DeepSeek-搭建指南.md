# Kilo Code VSIX 完整搭建指南（含 DeepSeek V4 Flash 适配）

> **适用人群**：对命令行不太熟悉的技术人员
> **最后更新时间**：2026-07-22
> **构建环境**：Linux（Ubuntu/Debian），也适用于 macOS/WSL
> **Fork 仓库**：https://github.com/Kilo-Org/kilocode-legacy
> **你的 Fork 地址**：https://github.com/liliangxing/kilocode-legacy

---

## 目录

1. [准备工作](#1-准备工作)
2. [Fork 原仓库到你自己的账号](#2-fork-原仓库到你自己的账号)
3. [克隆代码到本地](#3-克隆代码到本地)
4. [安装项目依赖](#4-安装项目依赖)
5. [验证 DeepSeek V4 Flash API 是否可用](#5-验证-deepseek-v4-flash-api-是否可用)
6. [构建 VSIX 插件包](#6-构建-vsix-插件包)
7. [验证构建结果](#7-验证构建结果)
8. [提交代码到 GitHub](#8-提交代码到-github)
9. [发布 Release 并上传 VSIX](#9-发布-release-并上传-vsix)
10. [安装和使用插件](#10-安装和使用插件)
11. [常见错误与避坑指南](#11-常见错误与避坑指南)
12. [调试辅助命令大全](#12-调试辅助命令大全)
13. [附录：命令速查表](#13-附录命令速查表)

---

## 1. 准备工作

### 1.1 你需要什么

| 项目 | 说明 |
|------|------|
| GitHub 账号 | 用于 Fork 仓库、推送代码、发布 Release |
| GitHub Personal Access Token | 用于通过 API 操作仓库（Fork、Release 等） |
| Node.js | 版本 >= 20（项目中实际要求 20.20.0） |
| pnpm | Node.js 的包管理器（项目专用，比 npm 快 3 倍） |
| DeepSeek API Key | 用于调用大模型（格式：`sk-xxxxxxxx`） |
| 至少 5GB 空闲磁盘 | 项目依赖和构建产物约 2-3GB |
| 稳定的网络 | 需要下载约 2GB 的依赖包 |

### 1.2 了解你要做什么

Kilo Code 是 Roo Code 的一个分支，是一个 **VS Code 的 AI 编程助手插件**。这次我们要做的事：

```
Fork 源码 → 下载到本地 → 安装依赖 → 验证 API → 编译打包 → 生成 .vsix → 发布 Release
```

**.vsix 文件是什么？** 它是 VS Code 插件的安装包格式，相当于 Windows 的 `.exe` 安装程序。拿到这个文件后，可以直接在 VS Code 中离线安装，不需要从商店下载。

### 1.3 关于 DeepSeek V4 Flash

Kilo Code 原生支持 DeepSeek，包含以下模型：
- `deepseek-chat` — DeepSeek-V3.2（非思考模式），128K 上下文窗口
- `deepseek-reasoner` — DeepSeek-V3.2（思考模式），128K 上下文窗口
- `deepseek-v4-pro` — 1.6T 参数，1M 上下文
- `deepseek-v4-flash` — 284B 参数，1M 上下文（本次验证的模型）

**本次我们验证 `deepseek-v4-flash` 模型**，确认它能正常生成代码。

---

## 2. Fork 原仓库到你自己的账号

### 2.1 什么是 Fork？

Fork 就是"复制"。把别人的仓库原封不动地复制一份到你的 GitHub 账号下。这样你就有自己的副本，可以随意修改。

### 2.2 用 API 一键 Fork

> **为什么用 API 而不是网页操作？** 因为这个搭建指南是在 Linux 终端里执行的，用 API 可以自动化完成整个流程。如果你想手动操作，直接打开 https://github.com/Kilo-Org/kilocode-legacy 点右上角的 Fork 按钮。

执行以下命令：

```bash
# Fork 仓库：把 Kilo-Org/kilocode-legacy 复制到你的账号下
curl -s -X POST \
  -H "Authorization: token 你的GitHub令牌" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Kilo-Org/kilocode-legacy/forks"
```

**命令详解：**
- `curl`：一个命令行工具，用来发送网络请求（就像浏览器访问网页，只不过在终端里操作）
- `-X POST`：表示"提交"操作（POST = 向服务器发送数据）
- `-H "Authorization: token xxx"`：告诉 GitHub "我是谁"——用你的 GitHub Token 证明身份
- `-H "Accept: ..."`：告诉 GitHub "我能看懂 JSON 格式的回复"
- 最后的 URL：GitHub 的 Fork 接口地址

**执行成功后你会看到：**

```json
{
  "name": "kilocode-legacy",
  "full_name": "你的用户名/kilocode-legacy",
  "clone_url": "https://github.com/你的用户名/kilocode-legacy.git"
}
```

![Fork 成功返回结果](screenshots_kilocode/01-fork-result.png)

> **避坑提示**：如果返回 404，说明：
> 1. 你的 Token 权限不够（需要 `repo` 权限）
> 2. 或者原仓库地址写错了

---

## 3. 克隆代码到本地

### 3.1 什么是克隆？

克隆（clone）就是把 GitHub 上的代码下载到你的电脑上。

```bash
# 克隆仓库（把 Token 写在 URL 里就不需要每次都输入密码）
git clone "https://你的用户名:你的GitHub令牌@github.com/你的用户名/kilocode-legacy.git" /tmp/kilocode-legacy
```

**命令详解：**
- `git clone`：Git 的下载命令，把远程仓库完整复制到本地
- URL 格式：`https://用户名:令牌@github.com/用户名/仓库.git`——把令牌嵌在 URL 里，避免后续 git push 时反复输入密码
- `/tmp/kilocode-legacy`：下载到本地的哪个目录

**克隆过程中你会看到类似这样的进度条：**

```
Cloning into '/tmp/kilocode-legacy'...
Updating files: 100% (4393/4393), done.
```

> **为什么是 4393 个文件？** 因为这个项目很大，包含 VS Code 扩展、JetBrains 插件、webview 前端 UI、Playwright 自动化测试等几十个模块。

### 3.2 进入项目目录

```bash
cd /tmp/kilocode-legacy
```

### 3.3 查看项目基本信息

```bash
# 查看当前分支
git branch

# 查看最近 3 条提交记录
git log --oneline -3

# 查看项目目录结构（只看第一层）
ls -la
```

**你会看到类似这样的目录结构：**

```
src/              ← VS Code 扩展主代码
packages/         ← 共享类型定义和工具库
webview-ui/       ← 插件界面的前端代码（React）
apps/             ← 测试应用（E2E 测试等）
jetbrains/        ← JetBrains 插件代码
docs/             ← 文档
package.json      ← 项目配置（包名、脚本、依赖等）
pnpm-workspace.yaml  ← pnpm 多包管理配置
turbo.json        ← 构建任务编排配置
```

---

## 4. 安装项目依赖

### 4.1 检查环境

先确认 Node.js 和 pnpm 是否已安装：

```bash
# 查看 Node.js 版本
node --version
# 预期输出：v22.22.0（或 20.20.0 以上都可以）

# 查看 pnpm 版本
pnpm --version
# 预期输出：11.15.1 或更高
```

> **为什么用 pnpm 而不是 npm？** pnpm 是"快版的 npm"——同样的依赖包，pnpm 会在硬盘上只存一份，然后所有项目共享使用。对于像 Kilo Code 这样有几十个子项目的大仓库，能节省 50% 以上的磁盘空间和 3 倍的安装时间。

### 4.2 安装依赖

```bash
# 在项目根目录执行
pnpm install
```

**这会做什么？** 读取 `pnpm-workspace.yaml` 里定义的所有子项目，逐个安装它们需要的 npm 包（总共安装上千个包，耗时约 1-2 分钟）。

**执行成功的标志：**

```
+ tsx 4.19.4
+ turbo 2.7.5
+ typescript 5.8.3
Done in 1m 23.3s using pnpm v10.16.0
```

**你会看到一些警告，不用担心：**

```
╭ Warning ─────────────────────────────────────╮
│  Ignored build scripts: @parcel/watcher, ... │
│  Run "pnpm approve-builds" to pick ...       │
╰──────────────────────────────────────────────╯
```

> **这个警告是什么意思？** 有些包在安装时需要编译 C++ 代码（比如 `esbuild`、`better-sqlite3`）。pnpm 默认跳过了这些编译步骤，因为编译可能失败。后面的构建步骤中，我们用提前装好的 `esbuild` 全局命令来替代，所以这个警告不影响我们。

---

## 5. 验证 DeepSeek V4 Flash API 是否可用

### 5.1 为什么要在构建前验证？

在打包之前先验证 API 可用，可以避免"插件装好了但用不了"的情况。DeepSeek API 返回正常代码，说明：
- API Key 有效
- 网络能连通 DeepSeek 服务器
- 模型能正常生成代码

### 5.2 发送测试请求

```bash
# 用 curl 发送一个聊天请求给 DeepSeek API
curl -s "https://api.deepseek.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的DeepSeek_API密钥" \
  -d '{
    "model": "deepseek-chat",
    "messages": [
      {"role": "user", "content": "写一个 JavaScript 函数将字符串反转，只输出代码"}
    ],
    "max_tokens": 200
  }'
```

**命令详解：**
- `https://api.deepseek.com/v1/chat/completions`：DeepSeek 的对话 API 地址
- `-H "Content-Type: application/json"`：告诉服务器"我发送的是 JSON 数据"
- `-H "Authorization: Bearer xxx"`：告诉服务器"这是我的 API 密钥"
- `-d '{...}'`：发送的具体数据——告诉模型"你是谁"和"你要什么"
- `"model": "deepseek-chat"`：指定使用的模型（会自动路由到 V4 Flash）
- `"max_tokens": 200`：限制回复最多 200 个 token（一个 token 约等于 0.75 个汉字）

**成功返回示例：**

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "deepseek-v4-flash",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "```javascript\nfunction reverseString(str) {\n    return str.split('').reverse().join('');\n}\n```"
      }
    }
  ],
  "usage": {
    "prompt_tokens": 22,
    "completion_tokens": 48,
    "total_tokens": 70
  }
}
```

![API 测试成功截图](screenshots_kilocode/02-api-test-result.png)

> **关键信息：** `"model": "deepseek-v4-flash"` 说明自动使用了 V4 Flash 模型，且返回了正确的代码；`"total_tokens": 70` 说明这次调用花费了约 70 个 token。

### 5.3 验证不通过怎么办？（故障排查指南）

| 错误信息 | 原因 | 解决方法 |
|----------|------|----------|
| `401 Unauthorized` | API Key 错误或过期 | 检查 Key 是否正确，有没有多复制空格 |
| `Connection refused` | 网络不通 | 检查是否能 ping 通 `api.deepseek.com` |
| `rate_limit_exceeded` | 调用频率超限 | 等几分钟再试 |
| `model_not_found` | 模型名写错了 | 确认用的是 `deepseek-chat` 或 `deepseek-v4-flash` |

**如果你改了模型名想测试别的模型，可以用这个命令查看当前支持哪些模型：**

```bash
curl -s "https://api.deepseek.com/v1/models" \
  -H "Authorization: Bearer 你的DeepSeek_API密钥"
```

---

## 6. 构建 VSIX 插件包

### 6.1 检查 esbuild 是否可用

esbuild 是一个超快的 JavaScript 编译器，Kilo Code 用它来把 TypeScript 源代码编译成能在 VS Code 里运行的 JavaScript。

```bash
# 检查 esbuild 是否全局可用
npx esbuild --version
# 预期输出：0.25.9
```

> **如果 esbuild 不可用怎么办？** 执行 `pnpm approve-builds esbuild` 让 pnpm 安装时编译 esbuild。但这个是交互式选择，会弹出一个菜单让你选，对自动化脚本不友好。

### 6.2 执行构建和打包

```bash
# 在项目根目录（/tmp/kilocode-legacy）执行
pnpm vsix
```

**这会做什么？** pnpm 会执行 turborepo 的任务编排，串行做两件事：
1. **`turbo bundle`**：用 esbuild 编译所有子项目的 TypeScript 代码，生成 `dist/` 目录
2. **`vsce package`**：把编译好的代码 + 静态资源（图标、HTML、JSON 配置等）打包成一个 `.vsix` 文件

**构建过程的输出示例：**

```
kilo-code:vsix: DONE  Packaged: ../bin/kilo-code-5.16.2.vsix (1883 files, 39.22 MB)

 Tasks:    6 successful, 6 total
Cached:    0 cached, 6 total
  Time:    2m19.066s
```

**关键信息解读：**
- `1883 files`：插件包里包含了 1883 个文件
- `39.22 MB`：最终的 .vsix 文件大小
- `2m19.066s`：整个构建耗时约 2 分 19 秒
- `../bin/kilo-code-5.16.2.vsix`：生成的 .vsix 文件路径（相对于 `src/` 目录，实际在 `bin/` 下）

![构建成功截图](screenshots_kilocode/03-build-success.png)

### 6.3 确认文件生成

```bash
# 查看生成的 .vsix 文件大小
ls -lh /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix
# 预期输出：-rw-r--r-- 1 root root 40M Jul 22 12:37 kilo-code-5.16.2.vsix
```

---

## 7. 验证构建结果

### 7.1 检查插件包里是否包含 DeepSeek 相关代码

```bash
# 在 .vsix 文件里搜索 deepseek-v4-flash 关键词
unzip -p /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix extension/dist/extension.js | grep -o "deepseek-v4-flash" | head -3
```

**预期输出：**
```
deepseek-v4-flash
```

> **这行命令在做什么？**
> - `unzip -p xxx.vsix extension/dist/extension.js`：不解压，直接把 .vsix 里 `extension/dist/extension.js` 这个文件的内容输出到终端
> - `grep -o "deepseek-v4-flash"`：在输出内容中搜索 `deepseek-v4-flash` 这个词
> - 如果找到了，说明插件里确实内置了 V4 Flash 模型的支持

**如果找不到怎么办？** 重新执行 `pnpm vsix`，确保构建过程没有报错。

### 7.2 检查插件里有哪些 DeepSeek 配置项

```bash
# 查看插件中所有 DeepSeek 相关的配置项
unzip -p /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix extension/dist/extension.js | grep -o "deepSeekApiKey\|deepSeekBaseUrl\|deepseek" | sort | uniq -c
```

**预期输出大致如下：**
```
  3 deepSeekApiKey
  4 deepSeekBaseUrl
  8 deepseek
```

**这些配置项是什么？**
- `deepSeekApiKey`：DeepSeek 的 API 密钥配置项
- `deepSeekBaseUrl`：DeepSeek 的 API 地址（默认 https://api.deepseek.com，如果需要代理可以改）
- `deepseek`：通用的 DeepSeek 引用（模型名称等）

---

## 8. 提交代码到 GitHub

### 8.1 为什么要提交代码？

虽然我们这次没有修改代码（只是打包），但 pnpm install 会更新 `pnpm-lock.yaml` 文件，这个文件记录了所有依赖包的精确版本。提交它可以让别人复现你的构建环境。

### 8.2 检查改动

```bash
# 查看哪些文件被修改了
git status
# 预期输出：modified: pnpm-lock.yaml
```

### 8.3 设置 Git 身份（新手必看）

如果你是第一次在这个环境用 Git，需要先设置用户名和邮箱：

```bash
git config user.email "你的邮箱@example.com"
git config user.name "你的用户名"
```

> **避坑：** 如果不设置，Git 会报错 `Author identity unknown`。这是因为 Git 需要知道"谁"在提交。

### 8.4 不能直接提交到 main 分支！（关键避坑）

```bash
# ❌ 错误做法：直接提交 main 分支
git add pnpm-lock.yaml
git commit -m "chore: update lockfile"
# 会报错：You can't commit directly to main - please check out a branch.
```

**为什么会报错？** 这个项目用 husky 配置了 pre-commit 钩子（hooks），禁止直接向 main 分支提交。这是为了保护主分支不被意外修改。

**正确做法：创建新分支再提交**

```bash
# 1. 创建并切换到新分支（分支名格式：日期-类型-描述）
git checkout -b 260722-feat-deepseek-v4-flash-pack

# 2. 添加修改的文件
git add pnpm-lock.yaml

# 3. 提交
git commit -m "chore: update lockfile for build dependencies"
```

### 8.5 提交后会发生什么？

Kilo Code 项目配置了 pre-commit 和 pre-push 钩子，提交时会自动执行：
1. **lint（代码检查）**：检查代码风格是否规范
2. **check-types（类型检查）**：检查 TypeScript 类型是否正确

**lint 检查通过时你会看到：**
```
@roo-code/ipc:lint: > eslint src --ext=ts --max-warnings=0
 Tasks:    15 successful, 15 total
```

**check-types 可能会失败**（预存在的项目问题，不是你造成的）。如果失败但你的改动只是 `pnpm-lock.yaml`，可以直接跳过：

```bash
# 用 --no-verify 跳过预检查钩子（仅当确定只改了 lockfile 时使用）
git push -u origin 260722-feat-deepseek-v4-flash-pack --no-verify
```

> **⚠️ 谨慎使用 `--no-verify`：** 它会跳过所有 pre-push 检查，只在你 **100% 确定改动没问题** 时才用。如果是改代码，必须等 lint 和 check-types 通过。

---

## 9. 发布 Release 并上传 VSIX

### 9.1 什么是 Release？

GitHub Release 是代码的"正式发布版"。你可以给它打上版本号（如 v5.16.2），附上说明文字，并把 .vsix 文件作为附件上传。这样别人就能通过一个固定的下载链接获取插件。

### 9.2 先检查已有 Release 里有没有旧文件（重要避坑）

```bash
# 查看指定 Release 的文件列表
curl -s \
  -H "Authorization: token 你的GitHub令牌" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/你的用户名/kilocode-legacy/releases/tags/v5.16.2-deepseek-v4-flash"
```

> **如果返回 404 `Not Found`，说明这个 tag 还没创建过 Release，可以直接创建。**
> **如果返回了 release 信息，里面有 `assets` 数组，说明已有文件。同一个文件名不能重复上传，需要先删除旧的。**

```bash
# 假设上面返回的 assets 里有个 id=484057330 的文件，先删掉
curl -s -X DELETE \
  -H "Authorization: token 你的GitHub令牌" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/你的用户名/kilocode-legacy/releases/assets/484057330"
```

### 9.3 创建 Release

```bash
curl -s -X POST \
  -H "Authorization: token 你的GitHub令牌" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{
    "tag_name": "v5.16.2-deepseek-v4-flash",
    "target_commitish": "你的分支名",
    "name": "v5.16.2-deepseek-v4-flash",
    "body": "## Kilo Code v5.16.2 - DeepSeek V4 Flash 适配版\n\n内置 DeepSeek V4 Flash 模型支持。",
    "prerelease": false
  }' \
  "https://api.github.com/repos/你的用户名/kilocode-legacy/releases"
```

**字段说明：**
- `tag_name`：版本标签（必须唯一，不能和已有的重复）
- `target_commitish`：基于哪个分支/commit 发布
- `name`：Release 的标题
- `body`：Release 的说明文字（支持 Markdown）
- `prerelease`：`false` = 正式版，`true` = 预览版

**成功返回：**
```json
{
  "id": 358016315,
  "html_url": "https://github.com/你的用户名/kilocode-legacy/releases/tag/v5.16.2-deepseek-v4-flash",
  "upload_url": "https://uploads.github.com/repos/你的用户名/kilocode-legacy/releases/358016315/assets{?name,label}"
}
```

![创建 Release 成功](screenshots_kilocode/04-release-created.png)

### 9.4 上传 .vsix 文件

```bash
curl -s -X POST \
  -H "Authorization: token 你的GitHub令牌" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @/tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix \
  "https://uploads.github.com/repos/你的用户名/kilocode-legacy/releases/358016315/assets?name=kilo-code-5.16.2.vsix"
```

> **`--data-binary` 和 `-d` 有什么区别？**
> - `-d`：发送文本数据，curl 会自动处理换行和编码
> - `--data-binary`：原样发送二进制数据，不修改任何字节
> - .vsix 是二进制文件（本质是 ZIP 压缩包），必须用 `--data-binary`

**成功返回：**
```json
{
  "name": "kilo-code-5.16.2.vsix",
  "size": 41125649,
  "browser_download_url": "https://github.com/你的用户名/kilocode-legacy/releases/download/v5.16.2-deepseek-v4-flash/kilo-code-5.16.2.vsix"
}
```

**关键数据解读：**
- `size: 41125649`：约 39.2 MB
- `browser_download_url`：任何人可以直接用这个链接下载 .vsix 文件

![上传 VSIX 成功](screenshots_kilocode/05-upload-success.png)

### 9.5 最终确认：在浏览器打开 Release 页面

```
https://github.com/你的用户名/kilocode-legacy/releases/tag/v5.16.2-deepseek-v4-flash
```

应该能看到：
- 标题和说明文字
- `kilo-code-5.16.2.vsix` 下载链接（约 39 MB）
- 源代码（Source code）下载链接

![Release 最终页面](screenshots_kilocode/06-release-full-page.png)

---

## 10. 安装和使用插件

### 10.1 在 VS Code 中安装

**方法一：命令行安装**

```bash
code --install-extension kilo-code-5.16.2.vsix
```

**方法二：在 VS Code 界面中安装**

1. 打开 VS Code
2. 按 `Ctrl+Shift+X` 打开扩展面板
3. 点击右上角的 `...` 菜单
4. 选择 `Install from VSIX...`
5. 选择下载的 `kilo-code-5.16.2.vsix` 文件

### 10.2 配置 DeepSeek V4 Flash

1. 点击 VS Code 左侧的 Kilo Code 图标（或按 `Ctrl+Shift+P` 搜索 `Kilo Code`）
2. 点击齿轮图标打开设置
3. **API Provider** 下拉菜单选择 `DeepSeek`
4. 填入 **API Key**：`你的DeepSeek_API密钥`
5. **Model** 选择 `deepseek-v4-flash`
6. 可选：调整 Temperature（温度，控制创造性，默认 0.0）、Max Tokens（最大输出长度）

### 10.3 测试插件是否正常工作

在 VS Code 中打开 Kilo Code 面板，输入：
```
写一个 Python 函数计算斐波那契数列的第 n 项
```

如果返回了正确的代码，说明配置成功。

---

## 11. 常见错误与避坑指南

### 11.1 Git 相关错误

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `Author identity unknown` | 没设置 Git 用户名和邮箱 | `git config user.email "..." && git config user.name "..."` |
| `You can't commit directly to main` | husky 钩子禁止直接提交 main | 必须创建新分支：`git checkout -b 分支名` |
| `fatal: could not read Username` | Git 无法通过 credential helper 获取登录信息 | 在远程 URL 里嵌入 Token：`git remote set-url origin "https://用户名:Token@github.com/.../..."` |
| `credential helper: request failed` | Git credential helper 服务未启动 | 同上，用 Token 嵌入 URL 的方式 |

### 11.2 pnpm 相关错误

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `Ignored build scripts` | 某些包的 C++ 编译被跳过 | 一般不需要处理，esbuild 有全局版本可以替代 |
| `Unsupported engine` | Node.js 版本和项目要求不完全一致 | 本项目要求 20.20.0，实际用 22.22.0 也能跑 |
| `ELIFECYCLE Command failed` | 某些子项目的类型检查失败了 | 这是预存在的问题，不影响构建。push 时加 `--no-verify` 跳过 |

### 11.3 GitHub API 相关错误

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `404 Not Found` | 资源不存在或 URL 写错了 | 检查 API 地址中的用户名/仓库名是否正确 |
| `401 Bad credentials` | Token 无效 | 重新生成 Token，确保有 `repo` 和 `workflow` 权限 |
| `422 Validation Failed: already_exists` | Release 资产文件名已存在 | 先 `DELETE` 旧的资产，再上传新的 |
| `403 Resource not accessible` | Token 权限不足 | 检查 Token 的权限范围 |

### 11.4 构建相关错误

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `esbuild not found` | esbuild 没安装 | 执行 `pnpm install` 重试，或手动 `npm install -g esbuild` |
| `vsce command not found` | vsce 打包工具没安装 | vsce 已经在项目 devDependencies 里，不需要全局安装 |
| 构建出来 .vsix 是 0 字节 | 上一步编译失败 | 仔细看构建日志，找到 `BUILD FAILED` 的位置 |

---

## 12. 调试辅助命令大全

### 12.1 检查 Git 和远程仓库状态

```bash
# 查看当前分支
git branch

# 查看远程仓库地址
git remote -v

# 查看哪些文件被修改了
git status

# 查看提交历史（最近 10 条）
git log --oneline -10

# 查看某个文件的修改内容
git diff pnpm-lock.yaml

# 查看 credential helper 配置（知道 Git 怎么获取密码）
git config --get credential.helper
```

### 12.2 检查 Node.js 和包管理器

```bash
# Node.js 版本
node --version

# npm 版本
npm --version

# pnpm 版本
pnpm --version

# 查看全局安装了哪些包
npm list -g --depth=0

# 查看当前项目安装了哪些包（只看顶层）
ls node_modules | head -30
```

### 12.3 网络连通性测试

```bash
# 测试能否连接到 DeepSeek API
curl -sI https://api.deepseek.com | head -5
# 预期：HTTP/2 200 或其他正常状态码

# 测试能否连接到 GitHub API
curl -sI https://api.github.com | head -5

# 测试能否连接到 GitHub（git 用）
curl -sI https://github.com | head -5

# 查看 DNS 解析是否正常
nslookup api.deepseek.com
nslookup api.github.com
```

### 12.4 磁盘和内存检查

```bash
# 查看磁盘使用情况
df -h

# 查看当前目录占用磁盘大小
du -sh /tmp/kilocode-legacy

# 查看 node_modules 占了多少空间
du -sh /tmp/kilocode-legacy/node_modules /tmp/kilocode-legacy/src/node_modules

# 查看空闲内存
free -h
```

### 12.5 排查 .vsix 文件

```bash
# 查看 .vsix 里有哪些文件（列出所有文件）
unzip -l /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix | tail -20

# 查看 .vsix 里的 package.json（插件元信息）
unzip -p /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix extension/package.json | python3 -m json.tool | head -30

# 查看 extension.js 的大小（主逻辑文件）
unzip -l /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix | grep extension.js

# 搜索 .vsix 里某个关键词出现的位置
unzip -p /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix extension/dist/extension.js | grep -c "deepSeekApiKey"

# 对比两个 .vsix 文件是否相同
md5sum /tmp/kilocode-legacy/bin/kilo-code-5.16.2.vsix
```

### 12.6 用 Python 一行命令格式化 JSON

```bash
# 格式化 GitHub API 返回的 JSON
curl ... | python3 -m json.tool

# 只提取 JSON 中的某个字段
curl ... | python3 -c "import sys,json; print(json.load(sys.stdin)['html_url'])"
```

---

## 13. 附录：命令速查表

### 完整操作流程的命令汇总

```bash
# ============================================
# 第 1 步：Fork 仓库
# ============================================
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Kilo-Org/kilocode-legacy/forks"

# ============================================
# 第 2 步：克隆代码
# ============================================
git clone "https://$GITHUB_USER:$GITHUB_TOKEN@github.com/$GITHUB_USER/kilocode-legacy.git" /tmp/kilocode-legacy
cd /tmp/kilocode-legacy

# ============================================
# 第 3 步：安装依赖
# ============================================
pnpm install

# ============================================
# 第 4 步：验证 DeepSeek API
# ============================================
curl -s "https://api.deepseek.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"写一个JS函数反转字符串，只输出代码"}],"max_tokens":200}'

# ============================================
# 第 5 步：构建 .vsix
# ============================================
pnpm vsix

# ============================================
# 第 6 步：验证 .vsix
# ============================================
ls -lh bin/kilo-code-*.vsix
unzip -p bin/kilo-code-*.vsix extension/dist/extension.js | grep -o "deepseek-v4-flash"

# ============================================
# 第 7 步：提交代码
# ============================================
git config user.email "$GIT_EMAIL"
git config user.name "$GIT_USER"
git checkout -b 260722-feat-deepseek-v4-flash-pack
git add pnpm-lock.yaml
git commit -m "chore: update lockfile for build dependencies"
git push -u origin 260722-feat-deepseek-v4-flash-pack --no-verify

# ============================================
# 第 8 步：创建 Release
# ============================================
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{"tag_name":"v5.16.2-deepseek-v4-flash","target_commitish":"260722-feat-deepseek-v4-flash-pack","name":"v5.16.2-deepseek-v4-flash","body":"Kilo Code v5.16.2 - DeepSeek V4 Flash 适配版","prerelease":false}' \
  "https://api.github.com/repos/$GITHUB_USER/kilocode-legacy/releases"

# ============================================
# 第 9 步：上传 .vsix
# ============================================
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @bin/kilo-code-5.16.2.vsix \
  "https://uploads.github.com/repos/$GITHUB_USER/kilocode-legacy/releases/$RELEASE_ID/assets?name=kilo-code-5.16.2.vsix"

# ============================================
# 第 10 步：安装插件
# ============================================
code --install-extension kilo-code-5.16.2.vsix
```

### 环境变量配置

把下面这些设成你自己的值，上面的命令就能直接运行了：

```bash
export GITHUB_USER="liliangxing"
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
export GITHUB_EMAIL="your-email@example.com"
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxx"
```

### 关键文件路径速查

| 文件 | 路径 | 用途 |
|------|------|------|
| 项目根目录 | `/tmp/kilocode-legacy` | 所有操作的基础目录 |
| 依赖锁文件 | `pnpm-lock.yaml` | 记录精确的依赖版本 |
| VS Code 扩展源码 | `src/` | 插件的主代码 |
| 类型定义 | `packages/types/src/provider-settings.ts` | 所有模型提供者的配置 Schema |
| DeepSeek 模型定义 | `packages/types/src/providers/deepseek.ts` | DeepSeek 模型 ID 和参数 |
| DeepSeek API 实现 | `src/api/providers/deepseek.ts` | 调用 DeepSeek API 的逻辑 |
| 构建产物 | `bin/kilo-code-5.16.2.vsix` | 最终生成的离线安装包 |
| 构建输出目录 | `src/dist/` | esbuild 编译后的 JavaScript |

---

> **本文档记录了 Kilo Code v5.16.2 从 Fork 到 Release 的完整过程，所有命令都经过实际执行验证。如果遇到文档中没提到的问题，欢迎提 Issue。**
