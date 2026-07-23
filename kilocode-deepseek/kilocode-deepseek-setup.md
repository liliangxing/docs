# Kilo Code + DeepSeek V4 Flash 搭建指南

> 本文档面向不熟悉命令行的技术人员，用大白话详细说明每一步操作。

---

## 目录

1. [前置准备](#1-前置准备)
2. [Fork 仓库](#2-fork-仓库)
3. [下载代码](#3-下载代码)
4. [配置 DeepSeek](#4-配置-deepseek)
5. [验证 API](#5-验证-api)
6. [编译打包](#6-编译打包)
7. [发布 Release](#7-发布-release)
8. [常见问题与避坑](#8-常见问题与避坑)

---

## 1. 前置准备

### 1.1 需要安装的工具

| 工具 | 用途 | 安装命令 |
|------|------|----------|
| Git | 代码管理 | `apt-get install git` 或 `brew install git` |
| Node.js | 运行 JavaScript 代码 | 推荐 v20.20.0（项目要求） |
| pnpm | 包管理器 | `npm install -g pnpm@9` |
| GitHub CLI | 与 GitHub 交互 | `apt-get install gh` 或 `brew install gh` |

### 1.2 检查工具是否安装

```bash
# 检查 Node.js 版本
node --version
# 应该显示 v20.x.x 或更高

# 检查 pnpm
pnpm --version
# 应该显示 9.x.x

# 检查 git
git --version

# 检查 gh CLI
gh --version
```

### 1.3 登录 GitHub CLI

```bash
# 用你的 GitHub token 登录
echo "你的github_token" | gh auth login --with-token
```

> ⚠️ **避坑**：token 需要有 `repo` 权限，否则无法推送代码。

---

## 2. Fork 仓库

### 2.1 什么是 Fork？

Fork 就是把别人的仓库复制一份到你自己的账号下，这样你就可以自由修改了。

### 2.2 执行 Fork

```bash
# 用 GitHub API fork 仓库
curl -X POST \
  -H "Authorization: token 你的github_token" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/Kilo-Org/kilocode-legacy/forks
```

### 2.3 验证 Fork 成功

```bash
# 检查你的仓库列表
gh api repos/你的用户名/kilocode-legacy --jq '.full_name'
# 应该显示: 你的用户名/kilocode-legacy
```

> ⚠️ **避坑**：Fork 后默认是 private 的，如果需要 public 要在 GitHub 设置里改。

---

## 3. 下载代码

### 3.1 为什么不用 git clone？

因为网络问题，`git clone` 可能会失败或很慢。我们使用 GitHub API 逐文件下载，更稳定。

### 3.2 下载仓库文件树

```bash
# 获取仓库的所有文件列表
curl -s \
  -H "Authorization: token 你的github_token" \
  "https://api.github.com/repos/你的用户名/kilocode-legacy/git/trees/main?recursive=1" \
  > /tmp/repo-tree.json
```

### 3.3 创建下载脚本

创建一个 Python 脚本来下载所有文件：

```python
#!/usr/bin/env python3
"""下载 GitHub 仓库的所有文件"""
import json, os, urllib.request, base64

TOKEN = "你的github_token"
OWNER = "你的用户名"
REPO = "kilocode-legacy"
OUTPUT = "./kilocode-src"

# 读取文件树
with open('/tmp/repo-tree.json') as f:
    data = json.load(f)

blobs = [item for item in data['tree'] if item['type'] == 'blob']
print(f"总文件数: {len(blobs)}")

success = 0
for i, item in enumerate(blobs):
    path = item['path']
    dest = os.path.join(OUTPUT, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    # 通过 API 获取文件内容
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            content = base64.b64decode(data['content'])
            with open(dest, 'wb') as f:
                f.write(content)
        success += 1
    except Exception as e:
        print(f"失败: {path}: {e}")
    
    if (i + 1) % 50 == 0:
        print(f"进度: {i+1}/{len(blobs)}")

print(f"\n完成! 成功: {success}/{len(blobs)}")
```

### 3.4 运行下载

```bash
python3 download_repo.py
```

> ⚠️ **避坑**：
> - 下载可能需要 10-30 分钟，取决于网络
> - 如果中断了，重新运行脚本会跳过已下载的文件
> - 不要下载 `node_modules` 目录（太大且可以重新安装）

---

## 4. 配置 DeepSeek

### 4.1 修改默认配置

找到文件 `kilocode-src/src/core/config/ProviderSettingsManager.ts`，搜索 `defaultProviderProfiles`。

**修改前：**
```typescript
default: {
    id: this.defaultConfigId,
    apiProvider: "kilocode",
    kilocodeModel: "minimax/minimax-m2.1:free",
},
```

**修改后：**
```typescript
default: {
    id: this.defaultConfigId,
    apiProvider: "openai",
    openAiBaseUrl: "https://api.deepseek.com",
    openAiApiKey: "你的DeepSeek_API_Key",
    openAiModelId: "deepseek-v4-flash",
},
```

### 4.2 为什么要这样改？

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `apiProvider` | `"openai"` | 使用 OpenAI 兼容协议 |
| `openAiBaseUrl` | `"https://api.deepseek.com"` | DeepSeek API 地址 |
| `openAiApiKey` | 你的 API Key | 从 deepseek.com 获取 |
| `openAiModelId` | `"deepseek-v4-flash"` | 模型名称 |

> ⚠️ **避坑**：
> - `apiProvider` 必须是 `"openai"` 而不是 `"deepseek"`，因为 DeepSeek 使用 OpenAI 兼容协议
> - `openAiBaseUrl` 不要加 `/v1` 后缀，SDK 会自动加
> - `openAiModelId` 必须是 DeepSeek 官方支持的模型名

---

## 5. 验证 API

### 5.1 用 curl 测试

```bash
# 测试 DeepSeek API 是否可用
curl -s -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 你的API_Key" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"你好"}],"max_tokens":50}'
```

### 5.2 预期结果

**成功：**
```json
{
  "id": "xxx",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "你好！..."
    }
  }]
}
```

**失败：**
```json
{
  "error": {
    "message": "Authentication Fails",
    "code": "invalid_request_error"
  }
}
```

### 5.3 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `Authentication Fails` | API Key 无效 | 检查 Key 是否正确，或重新生成 |
| `404 Not Found` | 模型名错误 | 使用 `deepseek-v4-flash` 或 `deepseek-chat` |
| `429 Too Many Requests` | 请求太频繁 | 等 30 秒后重试 |
| 连接超时 | 网络问题 | 检查网络，或换网络环境 |

> ⚠️ **重要避坑**：
> - **不要短时间内发送太多请求**，否则会被临时封禁
> - 如果测试失败，**等待 30 秒**再重试
> - 用变量存储 key，不要直接写在命令里：
>   ```bash
>   KEY="你的key"
>   curl ... -H "Authorization: Bearer $KEY" ...
>   ```

---

## 6. 编译打包

### 6.1 安装依赖

```bash
cd kilocode-src

# 创建 .npmrc 加速下载
cat > .npmrc << 'EOF'
registry=https://registry.npmjs.org/
network-timeout=600000
fetch-retries=5
EOF

# 安装依赖（可能需要 5-15 分钟）
pnpm install --no-frozen-lockfile
```

### 6.2 安装全局工具

```bash
# 安装 turbo 和 vsce（编译和打包工具）
npm install -g turbo @vscode/vsce
```

### 6.3 编译扩展

```bash
# 进入 src 目录
cd src

# 编译（使用 esbuild）
node esbuild.mjs --production
```

### 6.4 打包成 .vsix

```bash
# 打包成 VS Code 扩展文件
vsce package --no-dependencies --out ../bin
```

### 6.5 验证产物

```bash
# 检查生成的 .vsix 文件
ls -lh ../bin/*.vsix
# 应该看到类似 kilo-code-5.16.2.vsix 的文件
```

> ⚠️ **避坑**：
> - 如果 `pnpm install` 失败，尝试 `npm install -g pnpm@9` 更新 pnpm
> - 如果编译报错缺少 `del-cli` 等工具，执行 `npm install -g del-cli rimraf`
> - 编译过程可能需要 5-10 分钟

---

## 7. 发布 Release

### 7.1 提交代码

```bash
cd kilocode-src

# 初始化 git（如果还没有）
git init
git add -A
git commit -m "配置 DeepSeek V4 Flash 作为默认 provider"

# 添加远程仓库
git remote add origin https://你的用户名:你的token@github.com/你的用户名/kilocode-legacy.git

# 推送（如果网络不好，用 GitHub API 推送，见下文）
git push origin main
```

### 7.2 用 GitHub API 推送（如果 git push 失败）

```bash
# 创建 blob
BLOB_SHA=$(curl -s -X POST \
  -H "Authorization: token 你的token" \
  -H "Content-Type: application/json" \
  "https://api.github.com/repos/你的用户名/kilocode-legacy/git/blobs" \
  -d '{"content":"文件内容","encoding":"base64"}' | jq -r '.sha')

# ... (详细步骤见完整脚本)
```

### 7.3 创建 Release

```bash
# 用 gh CLI 创建 release
gh release create v5.16.2-deepseek \
  --title "DeepSeek V4 Flash 预配置版" \
  --notes "内置 DeepSeek V4 Flash 配置" \
  ./bin/kilo-code-5.16.2.vsix
```

### 7.4 上传文件到 Release

```bash
# 上传 .vsix 文件
gh release upload v5.16.2-deepseek ./bin/kilo-code-5.16.2.vsix
```

---

## 8. 常见问题与避坑

### 8.1 网络问题

**问题**：`git clone` 或 `pnpm install` 失败

**解决**：
```bash
# 设置 npm 镜像
npm config set registry https://registry.npmmirror.com

# 或者用代理
export https_proxy=http://你的代理地址:端口
```

### 8.2 API Key 问题

**问题**：`curl` 测试时有时成功有时失败

**原因**：DeepSeek 有速率限制，短时间内请求太多次会被临时封禁。

**解决**：
- 等待 30 秒后重试
- 用变量存储 key，避免 shell 特殊字符问题
- 不要连续快速发送多个请求

### 8.3 编译错误

**问题**：`pnpm install` 报 `ELIFECYCLE` 错误

**解决**：
```bash
# 禁用 husky（git hooks 工具）
# 编辑 package.json，把 "prepare": "husky" 改为 "prepare": "echo skip"
```

### 8.4 模型名错误

**问题**：`404 Not Found` 或模型不可用

**解决**：
- 使用 `deepseek-v4-flash`（推荐，免费）
- 或 `deepseek-chat`（旧版，即将下线）
- 不要使用 `deepseek-reasoner`（已废弃）

### 8.5 验证脚本

创建一个测试脚本 `test_api.sh`：

```bash
#!/bin/bash
# DeepSeek API 测试脚本

KEY="你的API_Key"
URL="https://api.deepseek.com/v1/chat/completions"

echo "测试 DeepSeek API..."
curl -s -w "\nHTTP_CODE: %{http_code}\n" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"你好，用Python写一个Hello World"}],"max_tokens":100}'
```

```bash
# 运行测试
chmod +x test_api.sh
./test_api.sh
```

---

## 附录：完整命令清单

```bash
# 1. Fork
curl -X POST -H "Authorization: token TOKEN" \
  https://api.github.com/repos/Kilo-Org/kilocode-legacy/forks

# 2. 下载代码（运行 Python 脚本）
python3 download_repo.py

# 3. 修改配置
# 编辑 src/core/config/ProviderSettingsManager.ts

# 4. 验证 API
KEY="你的key"
curl -s -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"你好"}],"max_tokens":50}'

# 5. 安装依赖
cd kilocode-src
pnpm install --no-frozen-lockfile

# 6. 编译打包
cd src
node esbuild.mjs --production
vsce package --no-dependencies --out ../bin

# 7. 发布
gh release create v1.0.0 --title "DeepSeek版" --notes "说明" ../bin/*.vsix
```

---

## 总结

1. **Fork** → 复制仓库到你账号
2. **下载** → 用 API 下载代码（比 git clone 稳定）
3. **配置** → 修改默认 provider 为 DeepSeek
4. **验证** → 用 curl 测试 API
5. **编译** → pnpm install + esbuild + vsce
6. **发布** → 创建 GitHub Release 并上传 .vsix

> 💡 **提示**：如果遇到任何问题，先检查网络连接，然后等待 30 秒后重试。大多数问题都是暂时的网络或速率限制问题。
