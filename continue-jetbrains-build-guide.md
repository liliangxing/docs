# Continue JetBrains 插件离线构建完全指南

> 本指南记录从 fork 仓库、拉取代码、调试构建链、到产出离线 IDEA 插件的完整过程。每个步骤都附带**避坑提示**和**为什么这么做**的说明，适合对命令行不太熟悉的技术人员按步骤操作。

---

## 目录

1. [准备工作](#1-准备工作)
2. [Fork 仓库并拉取代码](#2-fork-仓库并拉取代码)
3. [智谱 GLM API 自然语言写 Java](#3-智谱-glm-api-自然语言写-java)
4. [构建链环境准备](#4-构建链环境准备)
5. [构建本地 packages](#5-构建本地-packages)
6. [构建 GUI 和 prepackage](#6-构建-gui-和-prepackage)
7. [构建 continue-binary（核心难点）](#7-构建-continue-binary核心难点)
8. [Gradle 插件打包](#8-gradle-插件打包)
9. [提交代码并发布 Release](#9-提交代码并发布-release)
10. [附录：完整命令速查表](#10-附录完整命令速查表)

---

## 1. 准备工作

### 1.1 你需要什么

- **Linux 环境**（Ubuntu 22.04 最佳）
- **GitHub Token**：`ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`（用于 fork、clone、push、release）
- **智谱 API Key**：`d7640538xxxxxxxxxxxxxxxxxxxxxxxxxxxx`（用于自然语言写 Java）
- **网络**：能访问 GitHub、npm registry、JetBrains 缓存服务器
- **磁盘空间**：至少 5GB（代码 + 依赖 + 构建产物）
- **内存**：至少 4GB（GUI 构建需要大内存）

### 1.2 为什么需要这些

- **GitHub Token**：`gh` CLI 和 `git clone` 需要认证才能访问私有仓库和发布 release
- **智谱 Key**：GLM-4-Flash 模型是免费/低价的，能用来生成和修复 Java 代码
- **大内存**：GUI 构建（webpack/vite）会打包 4MB 的 JS，Node 默认内存不够会 OOM
- **大磁盘**：IntelliJ Platform SDK 下载约 1GB，binary 打包后 92MB，加上中间产物约 3GB

---

## 2. Fork 仓库并拉取代码

### 2.1 验证 fork 是否已存在

```bash
export GH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
gh api repos/liliangxing/continue --jq \
    '"仓库: " + .full_name + "\n是否 fork: " + (.fork|tostring) \
     + "\n父仓库: " + (.parent.full_name // "N/A")'
```

**预期输出**：
```
仓库: liliangxing/continue
是否 fork: true
父仓库: continuedev/continue
```

**为什么先验证**：
> 如果 fork 已存在，直接 clone 即可；如果不存在，需要执行 `gh repo fork continuedev/continue`。本案例中 fork 已存在（由之前会话创建），所以跳过 fork 步骤。

### 2.2 从 fork 完整克隆代码

```bash
cd /workspace
rm -rf continue 2>/dev/null

# 用 token 嵌入 URL 的方式 clone（避免 gh CLI 的 TLS 问题）
git clone "https://x-access-token:${GH_TOKEN}@github.com/liliangxing/continue.git" continue
```

**预期输出**：
```
Cloning into 'continue'...
Updating files: 100% (3057/3057), done.
```

**避坑**：不要用 `gh repo clone` 或 `--depth=1`
> - `gh repo clone` 在某些网络环境下会报 `gnutls_handshake() failed`
> - `--depth=1` 浅克隆只有最新提交，后续 rebase、查看历史、unshallow 都很麻烦，直接完整 clone 最省心

### 2.3 验证克隆完整性

```bash
cd /workspace/continue

# 检查提交总数（应 > 21000）
git rev-list --count HEAD
# 输出: 21570

# 检查是否浅克隆
git rev-parse --is-shallow-repository
# 输出: false（false = 完整，不是浅克隆）

# 检查是否包含上游最新提交
git remote add upstream https://github.com/continuedev/continue.git
git fetch upstream refs/heads/main:refs/remotes/upstream/main
git merge-base --is-ancestor d0a3c0b62 HEAD && echo "✓ 含上游最新"

# 检查本地是否落后上游
git rev-list --count HEAD..upstream/main
# 输出: 0（0 = 没有落后）
```

**为什么验证这些**：
> 确保你拿到的代码是「上游最新 + fork 的修改」，而不是一个过时的快照。`d0a3c0b62` 是上游 `continuedev/continue` 的最新提交，如果本地不包含它，说明 fork 没同步。

---

## 3. 智谱 GLM API 自然语言写 Java

### 3.1 测试 API Key 是否可用

```bash
curl -sS https://open.bigmodel.cn/api/paas/v4/chat/completions \
    -H "Authorization: Bearer d7640538xxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
    -H "Content-Type: application/json" \
    -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"只回复 PONG"}]}'
```

**预期输出**：
```json
{"choices":[{"finish_reason":"stop","index":0,
"message":{"content":"PONG","role":"assistant"}}],
"usage":{"completion_tokens":4,"prompt_tokens":9,"total_tokens":13}}
```

**避坑：模型选择**
> - `glm-4.5` → 报「余额不足」（1113 错误）
> - `glm-4-flash` → ✅ 免费可用
> - `glm-4-air`/`glm-4` → 报余额不足
> - 所以必须用 `glm-4-flash`

### 3.2 使用智谱 Java Agent 脚本

脚本位置：`/workspace/zhipu-java-agent/zhipu-java-agent.sh`

```bash
cd /workspace/zhipu-java-agent
./zhipu-java-agent.sh "用 Java 写一个统计字符串里每个单词出现次数的程序, 按频率排序"
```

**运行流程**：
1. **生成**：调用 GLM-4-Flash 生成 Java 代码
2. **编译**：用 `javac` 编译
3. **修复**：如果编译失败，把错误信息回传给模型，让模型修复，最多 3 轮
4. **运行**：编译成功后执行 `java` 运行

**预期输出**：
```
==================== 智谱 Java Agent ====================
[1/4] 生成 Java 代码...
✓ 生成文件: WordCount.java  (主类: WordCount)
[2/4] 编译...
✓ 编译成功
[4/4] 运行...
world: 3
hello: 2
java: 1
==================== 完成 ✓ ====================
```

### 3.3 自动修复能力验证

故意写一个带编译错误的文件，测试修复循环：

```bash
# 创建错误文件
cat > /workspace/zhipu-java-agent/zhipu_java_work/Broken.java <<'EOF'
import java.util.*;
public class Broken {
    public static void main(String[] args) {
        List<String> list = new ArrayList<>();
        list.add("a");
        // 错误1: sizee 拼写错误
        System.out.println("size = " + list.sizee());
        // 错误2: JSONObject 未导入
        JSONObject obj = new JSONObject();
        System.out.println(obj);
    }
}
EOF

# 编译（会失败）
javac Broken.java
# 输出: 2 errors (sizee 和 JSONObject)

# 用 fix-test.sh 自动修复
./fix-test.sh
```

**预期结果**：第 1 轮修复成功，输出 `size = 2`

**为什么能修复**：
> 脚本把「源代码 + 编译错误信息」一起传给模型，模型根据错误提示修正代码。`sanitize_imports` 函数还会把模型误插到方法体里的 `import` 语句提到文件顶部（GLM-4-Flash 的常见弱点）。

---

## 4. 构建链环境准备

### 4.1 安装 JDK 17

```bash
export SDKMAN_DIR="/root/.sdkman"
source "$SDKMAN_DIR/bin/sdkman-init.sh"
sdk install java 17.0.13-tem
```

**为什么必须 JDK 17**：
> `extensions/intellij/gradle.properties` 里写死了 `org.gradle.java.installations.paths`，且 `build.gradle.kts` 里 `kotlin { jvmToolchain(17) }`。用 JDK 20 或更高版本会导致 gradle 找不到匹配的 JDK，编译失败。

### 4.2 修复 npm registry（避坑）

```bash
# 检查当前 registry
cat ~/.npmrc
# 输出: registry=https://mirrors.tencent.com/npm/

# 问题：腾讯镜像对某些包返回 404（如 npm 自身）
# 解决：切回官方 registry
npm config set registry https://registry.npmjs.org/
```

**为什么避坑**：
> `packages/llm-info` 的依赖里有一个 `npm` 包（用于 semantic-release），腾讯镜像对这个包返回 `404 Not Found`。这不是你的代码问题，是镜像不完整。切回官方 registry 即可解决。

### 4.3 修复 gradle 初始化脚本（避坑）

```bash
# 检查当前 init.gradle
cat /root/.gradle/init.gradle
# 输出里有: mavelCentral()  ← 拼写错误！

# 修复：重写为正确的仓库配置
cat > /root/.gradle/init.gradle <<'EOF'
allprojects {
    repositories {
        mavenCentral()
        maven { url 'https://cache-redirector.jetbrains.com/intellij-dependencies' }
        maven { url 'https://cache-redirector.jetbrains.com/intellij-plugin-service' }
    }
}
EOF
```

**为什么避坑**：
> `mavelCentral()` 拼写错误导致 gradle 初始化脚本编译失败，整个 build 还没开始就挂了。JetBrains 缓存服务器比 Maven Central 快，适合国内网络。

### 4.4 修复 gradle.properties JDK 路径

```bash
cd /workspace/continue/extensions/intellij

# 原内容写死了 /usr/lib/jvm/java-17-openjdk-amd64，沙箱里没有这个路径
sed -i \
    's|org.gradle.java.installations.paths=.*|org.gradle.java.installations.paths=/root/.sdkman/candidates/java/17.0.13-tem|' \
    gradle.properties
```

**为什么**：
> 不同机器 JDK 安装位置不同。sdkman 把 JDK 装到 `/root/.sdkman/candidates/java/17.0.13-tem`，gradle 需要知道这个位置才能找到正确的 JDK。

---

## 5. 构建本地 packages

### 5.1 为什么必须先构建 packages

continue 项目有 7 个本地子包（`config-types`、`fetch`、`config-yaml`、`llm-info`、`openai-adapters`、`continue-sdk`、`terminal-security`），它们互相依赖。binary 的 esbuild bundle 会 `import` 这些包（如 `@continuedev/openai-adapters`），如果子包没构建，esbuild 会报 `Could not resolve` 错误。

### 5.2 执行构建

```bash
cd /workspace/continue
node ./scripts/build-packages.js
```

**构建顺序**（脚本自动处理）：
1. **Phase 1**：`config-types`、`terminal-security`（无本地依赖）
2. **Phase 2**：`fetch`、`config-yaml`、`llm-info`（依赖 config-types）
3. **Phase 3**：`openai-adapters`、`continue-sdk`（依赖前面的包）

**预期输出**：
```
🎉 All packages built successfully!
```

**避坑**：如果某个 package 的 `npm install` 失败，检查 registry 是否切回官方（见 4.2）。

---

## 6. 构建 GUI 和 prepackage

### 6.1 构建 GUI

```bash
cd /workspace/continue/gui
NODE_OPTIONS="--max-old-space-size=4096" npm run build
```

**为什么加 `NODE_OPTIONS`**：
> GUI 是一个 React 应用，vite 打包后 JS 约 4MB。Node 默认堆内存约 1.4GB，打包过程中会 OOM。`--max-old-space-size=4096` 把内存限制提到 4GB，避免崩溃。

**产物位置**：`gui/dist/`（不是 `gui/build/`）
- `dist/assets/index.js` — webview 主 JS
- `dist/assets/index.css` — webview 样式
- `dist/index.html` — webview 入口

### 6.2 执行 prepackage

```bash
cd /workspace/continue/extensions/vscode
npm run prepackage
```

**prepackage 做什么**：
1. 把 `gui/dist/` 拷贝到 `extensions/intellij/src/main/resources/webview/`
2. 把 `gui/dist/` 拷贝到 `extensions/vscode/gui/`
3. 下载/拷贝 `@lancedb`、ripgrep、sqlite3 等 native 依赖

**避坑**：
> 必须先 build GUI，否则 prepackage 会报 `gui build did not produce index.js`。prepackage 脚本会 `chdir` 到 `gui` 目录检查 `dist/assets/index.js` 是否存在。

---

## 7. 构建 continue-binary（核心难点）

### 7.1 什么是 continue-binary

continue-binary 是一个**单文件可执行程序**，包含：
- Node.js 运行时（约 46MB 压缩后）
- continue 全部 TypeScript 代码（esbuild bundle 后约 25MB）
- 运行时通过 `require` 加载 native 模块（`@lancedb`、`sqlite3`、`ripgrep`）

它是插件与 AI 核心交互的桥梁，IDE 插件通过调用这个 binary 实现代码补全、对话等功能。

### 7.2 第一次失败：pkg 5.8.1 不支持 node: 协议

```bash
cd /workspace/continue/binary
npx pkg --no-bytecode --public-packages "*" --public \
    --compress GZip pkgJson/linux-x64 --out-path bin/linux-x64
```

**错误输出**：
```
> Error! Cannot read file, ENOENT
  node:sqlite
```

**为什么失败**：
> `pkg 5.8.1` 是废弃版本，它把 `node:sqlite` 当成文件路径去解析，而不是 Node.js 内置模块。实际上 continue 代码用的是 `sqlite3` npm 包，不会调用 `node:sqlite`，但 Sequelize 库在 bundle 里有一个动态 require 映射表包含了 `"node:sqlite": () => require("node:sqlite")`，pkg 5.8.1 解析这个映射时就报错了。

### 7.3 解决：用 @yao-pkg/pkg 替换

```bash
cd /workspace/continue/binary

# 1. 卸载旧 pkg
npm uninstall pkg

# 2. 安装社区 fork
npm install --save-dev @yao-pkg/pkg

# 3. 验证版本
npx pkg --version
# 输出: 6.21.0

# 4. 修改 target: node18 -> node22
# @yao-pkg/pkg-fetch 3.6.4 不再提供 node18/20 的 baseline，只提供 node22/24/26
sed -i 's/"node18-linux-x64"/"node22-linux-x64"/' \
    pkgJson/linux-x64/package.json
```

**为什么用 @yao-pkg/pkg**：
> `pkg` 原作者已停止维护，`@yao-pkg/pkg` 是社区 fork，持续更新，支持 Node 22/24/26，正确处理 `node:` 协议前缀。

### 7.4 第二次失败：baseline 下载超时

```bash
npx pkg ... pkgJson/linux-x64 --out-path bin/linux-x64
```

pkg 6.21.0 需要从 GitHub 下载 Node 22 baseline（约 74MB），网络慢会超时。

**解决：手动下载 baseline 到缓存**

```bash
# 1. 查 expected-shas.json 找到 node22 对应的精确版本
jq 'to_entries[] | select(.key | test("v22.*linux-x64"))' \
    node_modules/@yao-pkg/pkg-fetch/lib-es5/expected-shas.json
# 输出: "node-v22.23.1-linux-x64"

# 2. 手动下载到 pkg 缓存目录
mkdir -p ~/.pkg-cache/v3.4
curl -sSL --fail \
    -o ~/.pkg-cache/v3.4/fetched-v22.23.1-linux-x64 \
    "https://github.com/yao-pkg/pkg-fetch/releases/download/v3.6/node-v22.23.1-linux-x64"

# 3. 验证下载成功
file ~/.pkg-cache/v3.4/fetched-v22.23.1-linux-x64
# 输出: ELF 64-bit LSB executable
```

**为什么手动下载**：
> pkg 的自动下载从 GitHub releases 拉取，国内网络经常超时（默认 120 秒不够）。手动下载后 pkg 会检测到缓存存在，跳过下载直接打包。

**缓存路径规则**：
```
~/.pkg-cache/v3.4/fetched-<nodeVersion>-<platform>-<arch>
# 例如: ~/.pkg-cache/v3.4/fetched-v22.23.1-linux-x64
```

### 7.5 打包成功

```bash
cd /workspace/continue/binary
npx pkg --no-bytecode --public-packages "*" --public \
    --compress GZip pkgJson/linux-x64 --out-path bin/linux-x64
```

**预期输出**：
```
> pkg@6.21.0
> Fetching base Node.js binaries to PKG_CACHE_PATH
(使用已缓存的 baseline)
```

**产物**：
```
bin/linux-x64/
├── continue-binary    (92MB, ELF 可执行文件)
├── index.node         (59MB, @lancedb 向量数据库)
├── rg                 (6.5MB, ripgrep)
├── build/
│   └── Release/
│       └── node_sqlite3.node  (2.2MB, sqlite native binding)
└── package.json       (空文件, 让 bindings 库找到正确路径)
```

**验证 binary 是真实 ELF**：
```bash
file bin/linux-x64/continue-binary
# 输出: ELF 64-bit LSB executable, x86-64
```

---

## 8. Gradle 插件打包

### 8.1 执行 buildPlugin

```bash
cd /workspace/continue/extensions/intellij
export JAVA_HOME="/root/.sdkman/candidates/java/17.0.13-tem"
export PATH="$JAVA_HOME/bin:$PATH"

# 清理旧产物
rm -rf build/distributions

# 构建插件（跳过验证和测试，节省时间和避免额外依赖）
./gradlew buildPlugin -x verifyPlugin -x test \
    --no-daemon --console=plain
```

**预期输出**：
```
> Task :prepareSandbox
> Task :buildPlugin
BUILD SUCCESSFUL in 5m 41s
14 actionable tasks: 14 executed
```

**参数说明**：
- `-x verifyPlugin`：跳过插件结构验证（需要额外下载 IDE 版本验证，耗时）
- `-x test`：跳过单元测试（沙箱里没有完整 IDE 环境，测试会失败）
- `--no-daemon`：不启动 gradle daemon（沙箱环境重启后 daemon 会失效）
- `--console=plain`：纯文本输出，方便查看日志

### 8.2 验证 zip 内容

```bash
ls -la build/distributions/
# 输出: -rw-r--r-- 79576896 continue-intellij-extension-1.0.68.zip

unzip -l build/distributions/continue-intellij-extension-1.0.68.zip
```

**关键文件**：
| 文件 | 大小 | 说明 |
|---|---|---|
| `lib/continue-intellij-extension-1.0.68.jar` | 11MB | 插件主 jar |
| `core/linux-x64/continue-binary` | 92MB | **真实 ELF 可执行文件** |
| `core/linux-x64/index.node` | 59MB | @lancedb 向量数据库 |
| `core/linux-x64/rg` | 6.5MB | ripgrep 代码搜索 |
| `core/linux-x64/build/Release/node_sqlite3.node` | 2.2MB | sqlite native binding |

**zip 从 11MB → 76MB 的原因**：
> 之前用占位脚本（276 字节）时 zip 只有 11MB。替换为真实 binary（92MB）后，zip 膨胀到 76MB。这是正常的，因为 binary 包含了完整的 Node.js 运行时 + continue 代码。

---

## 9. 提交代码并发布 Release

### 9.1 配置 git

```bash
cd /workspace/continue
git config user.email "liliangxing@users.noreply.github.com"
git config user.name "liliangxing"

# 用 token 嵌入 URL（避免 push 时提示输入用户名密码）
git remote set-url origin \
    "https://x-access-token:${GH_TOKEN}@github.com/liliangxing/continue.git"
```

### 9.2 提交修改

```bash
# 提交 binary 构建链修复
git add binary/package.json binary/package-lock.json \
    binary/pkgJson/linux-x64/package.json
git commit -m "fix(binary): migrate pkg 5.8.1 -> @yao-pkg/pkg 6.21, node18 -> node22

pkg 5.8.1 不支持 node: 协议动态 require (Sequelize 的 node:sqlite 映射),
导致 continue-binary 打包失败。改用社区 fork @yao-pkg/pkg 6.21.0,
baseline 升级到 Node 22.23.1 (内置 node:sqlite 实验支持)。

实测产出真实 ELF 可执行文件 (92MB), 含 Node 22 runtime + continue 代码。"
```

### 9.3 推送到 fork

```bash
# 避坑：必须用完整 refspec
git push origin refs/heads/main:refs/heads/main
```

**避坑**：
> `git push origin main` 会报 `error: dst refspec main matches more than one`，因为仓库里同时有一个 `main` 分支和一个 `main` tag。用 `refs/heads/main:refs/heads/main` 明确指定推送分支。

### 9.4 创建 Release 并上传插件

```bash
export GH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 创建 release
gh release create v1.0.68-jetbrains \
    --repo liliangxing/continue \
    --title "Continue JetBrains Plugin v1.0.68 (Offline Install)" \
    --target main

# 上传离线插件 zip
gh release upload v1.0.68-jetbrains \
    --repo liliangxing/continue \
    /workspace/continue-intellij-extension-1.0.68.zip
```

**验证 release**：
```bash
gh release view v1.0.68-jetbrains --repo liliangxing/continue \
    --json url,assets
```

**预期输出**：
```
https://github.com/liliangxing/continue/releases/tag/v1.0.68-jetbrains
  asset: continue-intellij-extension-1.0.68.zip (79576896 bytes)
```

---

## 10. 附录：完整命令速查表

### 环境准备
```bash
# JDK 17
export SDKMAN_DIR="/root/.sdkman"
source "$SDKMAN_DIR/bin/sdkman-init.sh"
sdk install java 17.0.13-tem
export JAVA_HOME="/root/.sdkman/candidates/java/17.0.13-tem"

# npm registry
npm config set registry https://registry.npmjs.org/

# gradle init
cat > /root/.gradle/init.gradle <<'EOF'
allprojects {
    repositories {
        mavenCentral()
        maven { url 'https://cache-redirector.jetbrains.com/intellij-dependencies' }
    }
}
EOF
```

### 完整构建流程
```bash
cd /workspace/continue

# 1. 构建本地 packages
node ./scripts/build-packages.js

# 2. 构建 GUI
cd gui && NODE_OPTIONS="--max-old-space-size=4096" npm run build

# 3. prepackage
cd ../extensions/vscode && npm run prepackage

# 4. 构建 binary
cd ../../binary
npm install --save-dev @yao-pkg/pkg
sed -i 's/"node18-linux-x64"/"node22-linux-x64"/' pkgJson/linux-x64/package.json
# (手动下载 baseline 到 ~/.pkg-cache/v3.4/ 如果需要)
npx pkg --no-bytecode --public-packages "*" --public \
    --compress GZip pkgJson/linux-x64 --out-path bin/linux-x64

# 5. 打包插件
cd ../extensions/intellij
./gradlew buildPlugin -x verifyPlugin -x test --no-daemon --console=plain

# 6. 产物在 build/distributions/continue-intellij-extension-1.0.68.zip
```

### 避坑清单

| 问题 | 现象 | 解决 |
|---|---|---|
| 腾讯 npm 镜像 | `404 Not Found` 某些包 | `npm config set registry https://registry.npmjs.org/` |
| gradle init 拼写 | `mavelCentral()` 编译失败 | 重写 `/root/.gradle/init.gradle` |
| JDK 路径错误 | gradle 找不到 JDK 17 | 修改 `gradle.properties` 的 `java.installations.paths` |
| pkg 5.8.1 | `node:sqlite ENOENT` | 换 `@yao-pkg/pkg 6.21.0` |
| baseline 下载超时 | pkg 卡住 10 分钟无输出 | 手动下载到 `~/.pkg-cache/v3.4/` |
| GUI 内存不足 | `JavaScript heap out of memory` | `NODE_OPTIONS="--max-old-space-size=4096"` |
| git push 失败 | `matches more than one` | 用 `refs/heads/main:refs/heads/main` |
| 浅克隆问题 | 历史不完整，rebase 失败 | 完整 clone，不要用 `--depth=1` |

---

> **文档版本**：v1.0  
> **生成时间**：2026-07-18  
> **适用仓库**：https://github.com/liliangxing/continue  
> **上游仓库**：https://github.com/continuedev/continue
