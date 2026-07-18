# Roo-Code VSCode 插件离线构建与智谱集成指南

> 本指南记录从克隆 Roo-Code 仓库、调试构建链、打包 VSIX 插件，到通过智谱 GLM-4-Flash 自然语言写 Java、编译、自动修复的完整过程。每个步骤附带**避坑提示**和**为什么这么做**，适合对命令行不太熟悉的技术人员按步骤操作。

---

## 目录

1. [准备工作](#1-准备工作)
2. [克隆仓库](#2-克隆仓库)
3. [项目结构](#3-项目结构)
4. [安装依赖](#4-安装依赖)
5. [构建项目](#5-构建项目)
6. [打包 VSIX](#6-打包-vsix)
7. [智谱 GLM API 集成](#7-智谱-glm-api-集成)
8. [自然语言写 Java + 自动修复](#8-自然语言写-java--自动修复)
9. [提交代码与发布 Release](#9-提交代码与发布-release)
10. [附录：避坑清单](#10-附录避坑清单)

---

## 1. 准备工作

### 1.1 你需要什么

- **Linux 环境**（Ubuntu 22.04 最佳）
- **GitHub Token**：用于 clone、push、release
- **智谱 API Key**：`d7640538...（你的智谱key）`
- **pnpm**：Roo-Code 用 pnpm monorepo，不能用 npm/yarn
- **网络**：能访问 GitHub、npm registry
- **磁盘空间**：至少 3GB
- **内存**：至少 4GB（GUI 构建需要）

### 1.2 为什么需要这些

- **pnpm**：Roo-Code 是 pnpm workspace + turbo 构建，npm 或 yarn 无法正确处理依赖关系
- **智谱 Key**：GLM-4-Flash 是免费/低价模型，通过 OpenAI 兼容端点调用
- **大内存**：Webview UI 构建（webpack/vite）会打包大量 JS，Node 默认内存不够会 OOM

---

## 2. 克隆仓库

```bash
cd /workspace
export GH_TOKEN=ghp_xxx

# 用 token 嵌入 URL 的方式 clone
git clone "https://x-access-token:${GH_TOKEN}@github.com/liliangxing/Roo-Code.git" Roo-Code
```

![克隆仓库](images/roo-code-build/01_clone.png)

验证克隆完整性：
```bash
cd Roo-Code
git rev-list --count HEAD    # 应输出 7073
git rev-parse --is-shallow-repository   # 应输出 false
git log --oneline HEAD -3    # 查看最新 3 个提交
```

**为什么用 token 嵌入 URL**：
> `gh repo clone` 在某些网络环境下会报 `gnutls_handshake() failed`。用 `https://x-access-token:${TOKEN}@github.com/...` 格式最稳定。

---

## 3. 项目结构

Roo-Code 是 **pnpm monorepo**（多包仓库），结构如下：

```
Roo-Code/
├── src/              # VSCode 扩展主目录（插件核心代码）
├── webview-ui/       # Webview UI（React 前端）
├── apps/
│   ├── cli/          # CLI 工具
│   ├── docs/         # 文档站点
│   └── vscode-e2e/   # E2E 测试
├── packages/
│   ├── core/           # 核心逻辑
│   ├── types/          # TypeScript 类型
│   └── ...
├── pnpm-workspace.yaml   # pnpm 工作区配置
├── turbo.json            # turbo 构建配置
└── package.json          # 根 package.json
```

![项目结构](images/roo-code-build/02_structure.png)

**关键文件**：
- `src/package.json`：插件主配置，版本 3.53.0，publisher `RooVeterinaryInc`
- `src/package.json` 里的 `vsix` script：`vsce package --no-dependencies --out ../bin`

---

## 4. 安装依赖

### 4.1 为什么必须用 pnpm

Roo-Code 用 `pnpm-workspace.yaml` 定义多个子包，`turbo.json` 定义构建依赖关系。npm/yarn 不认识这些配置，会装错依赖或版本冲突。

### 4.2 执行安装

```bash
cd /workspace/Roo-Code

# 先确保 npm registry 是官方（腾讯镜像会 404）
npm config set registry https://registry.npmjs.org/

# 安装所有依赖（--no-frozen-lockfile 允许 lockfile 有差异）
pnpm install --no-frozen-lockfile
```

![pnpm install](images/roo-code-build/03_pnpm_install.png)

**预期输出**：
```
Done in 51s using pnpm v10.8.1
```

**避坑：esbuild build scripts 被忽略**
> 安装后会提示 `Ignored build scripts: esbuild, ...`。这是因为 pnpm 安全策略默认不运行 postinstall 脚本。但 esbuild 会按需下载对应平台的 binary，不影响打包。

### 4.3 Node 版本差异

```bash
cat .nvmrc    # 项目要求 v20.19.2
node -v       # 沙箱实际是 v22.13.1
```

![Node 版本](images/roo-code-build/11_node_version.png)

安装时会 warning：
```
WARN  Unsupported engine: wanted: {"node":"20.19.2"} (current: {"node":"v22.13.1"})
```

**为什么不影响**：
> Node 22 兼容 Node 20 的 API，只是 warning。如果遇到 native 模块编译失败，才需要用 nvm 安装 20.19.2。

---

## 5. 构建项目

### 5.1 为什么必须先 build

`pnpm vsix` 打包时会把 `src/dist/` 和 `webview-ui/dist/` 打进 VSIX。这些 dist 目录是 `pnpm build` 生成的，如果没有先 build，打包出来的 VSIX 是空的或缺少关键文件。

### 5.2 执行构建

```bash
cd /workspace/Roo-Code
pnpm build
```

![pnpm build](images/roo-code-build/04_build.png)

**预期输出**：
```
Tasks:    5 successful, 5 total
Time:    1m31.554s
```

**避坑：不要用 `cd src && npm run build`**
> 单独进入 src 目录用 npm 构建会缺少依赖（因为依赖在根目录 node_modules 里通过 pnpm 软链接管理）。必须在根目录执行 `pnpm build`，turbo 会自动处理子包的依赖顺序。

---

## 6. 打包 VSIX

### 6.1 执行打包

```bash
cd /workspace/Roo-Code
pnpm vsix
```

![pnpm vsix](images/roo-code-build/05_vsix.png)

**预期输出**：
```
roo-cline:vsix:  DONE  Packaged: ../bin/roo-cline-3.53.0.vsix
                            (1740 files, 29.41 MB)
```

**产物位置**：`bin/roo-cline-3.53.0.vsix`

### 6.2 VSIX 里包含什么

| 目录 | 大小 | 说明 |
|---|---|---|
| `dist/` | 94.67 MB | 扩展主代码（TypeScript 编译后） |
| `webview-ui/` | 46.81 MB | Webview 前端（React 构建产物） |
| `assets/` | 1.38 MB | 图标、图片等资源 |
| `package.nls.*.json` | ~5 KB x 18 | 多语言翻译文件 |

---

## 7. 智谱 GLM API 集成

### 7.1 测试 API 连通性

```bash
curl -sS https://open.bigmodel.cn/api/paas/v4/chat/completions \
    -H "Authorization: Bearer $ZHIPU_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"只回复 PONG"}]}'
```

![智谱 API 测试](images/roo-code-build/06_zhipu_api.png)

**预期输出**：`{"choices":[{"message":{"content":"PONG"}}]}`

### 7.2 避坑：模型选择

| 模型 | 结果 |
|---|---|
| `glm-4.5` | ❌ 余额不足（1113 错误） |
| `glm-4` | ❌ 余额不足 |
| `glm-4-flash` | ✅ 免费可用 |

**必须用 `glm-4-flash`**，其他模型需要充值。

### 7.3 在 Roo-Code 中配置

1. 打开 Roo-Code 侧边栏
2. 点击设置齿轮 → **API Provider**
3. 选择 **OpenAI Compatible**
4. 填写：
   - **Base URL**：`https://open.bigmodel.cn/api/paas/v4`
   - **API Key**：你的智谱 key
   - **Model ID**：`glm-4-flash`

**为什么选 OpenAI Compatible**：
> 智谱提供了 OpenAI 兼容的 API 端点（`/v1/chat/completions`），Roo-Code 原生支持这个格式，不需要额外适配。

---

## 8. 自然语言写 Java + 自动修复

### 8.1 使用脚本

脚本位置：`roo-zhipu-java-agent.sh` 和 `fix_java.py`

```bash
cd /workspace/Roo-Code
./roo-zhipu-java-agent.sh "用 Java 实现快速排序, main 里排序 {5,2,8,1,9,3,7,4,6}"
```

![智谱 Java Agent - 快速排序](images/roo-code-build/07_agent_quicksort.png)

**运行流程**：
1. **生成**：调用智谱 GLM-4-Flash 生成 Java 代码
2. **编译**：用 `javac` 编译
3. **修复**：如果编译失败，把错误信息回传给模型，最多 3 轮
4. **运行**：编译成功后执行 `java`

**预期输出**：
```
[1/4] 生成 Java 代码...
✓ 生成: QuickSortExample.java
[2/4] 编译...
✓ 编译成功
[4/4] 运行...
[1, 2, 3, 4, 5, 6, 7, 8, 9]
==================== 完成 ✓ ====================
```

### 8.2 自动修复能力验证

故意写一个带编译错误的文件：

```bash
cat > Broken.java <<'EOF'
import java.util.*;
public class Broken {
    public static void main(String[] args) {
        List<String> list = new ArrayList<>();
        list.add("a");
        System.out.println("size = " + list.sizee());  // 错误1: sizee 拼写
        JSONObject obj = new JSONObject();              // 错误2: 未导入
        System.out.println(obj);
    }
}
EOF
```

用 Python 脚本自动修复（避免 bash 转义问题）：

```bash
python3 fix_java.py Broken.java
```

![自动修复编译错误](images/roo-code-build/08_autofix.png)

**预期结果**：第 2 轮修复成功，输出 `size = 2`

**为什么用 Python 脚本**：
> bash 处理 JSON 和控制字符容易出错（`jq parse error: Invalid string: control characters`）。Python 的 `urllib` 和 `json` 库更稳健，能正确处理模型返回的换行和特殊字符。

---

## 9. 提交代码与发布 Release

### 9.1 避坑：husky 阻止直接推 main

Roo-Code 配置了 husky git hooks，阻止直接提交到 main 分支：

```bash
git commit -m "feat: xxx"
# 输出: You can't commit directly to main - please check out a branch.
# husky - pre-commit script failed (code 1)
```

![husky 阻止直接推 main](images/roo-code-build/09_husky_block.png)

**解决**：创建新分支提交

```bash
git checkout -b feat/zhipu-java-agent
git add roo-zhipu-java-agent.sh fix_java.py
git commit -m "feat: 添加智谱 GLM Java agent"
git push origin feat/zhipu-java-agent
```

### 9.2 创建 Release 并上传 VSIX

```bash
export GH_TOKEN=ghp_xxx

# 创建 release
gh release create v3.53.0 \
    --repo liliangxing/Roo-Code \
    --title "Roo-Code VSIX v3.53.0 (Offline Install)" \
    --target main

# 上传 VSIX
gh release upload v3.53.0 \
    --repo liliangxing/Roo-Code \
    bin/roo-cline-3.53.0.vsix
```

![创建 Release 并上传 VSIX](images/roo-code-build/10_release.png)

**验证**：
```bash
gh release view v3.53.0 --repo liliangxing/Roo-Code
# 应显示: roo-cline-3.53.0.vsix (30,836,486 bytes)
```

---

## 10. 附录：避坑清单

| 问题 | 现象 | 解决 |
|---|---|---|
| 用 npm/yarn 安装 | 依赖缺失或版本冲突 | 必须用 `pnpm install` |
| 腾讯 npm 镜像 | 某些包 404 | `npm config set registry https://registry.npmjs.org/` |
| 单独 cd src 构建 | 缺少依赖 | 必须在根目录 `pnpm build` |
| Node 22 vs 20 | `Unsupported engine` warning | 忽略 warning，不影响构建 |
| esbuild scripts 被忽略 | 安装后提示 Ignored build scripts | 不影响，esbuild 会按需下载 |
| glm-4.5 余额不足 | 1113 错误 | 改用 `glm-4-flash` |
| bash jq 解析失败 | `parse error: Invalid string` | 用 Python 脚本 `fix_java.py` |
| husky 阻止 main | `You can't commit directly to main` | 创建新分支提交 |
| git push origin main | `matches more than one` | 用 `refs/heads/main:refs/heads/main` |

---

## 快速命令速查表

```bash
# 1. 克隆
git clone "https://x-access-token:${GH_TOKEN}@github.com/liliangxing/Roo-Code.git"

# 2. 安装
npm config set registry https://registry.npmjs.org/
cd Roo-Code && pnpm install --no-frozen-lockfile

# 3. 构建
pnpm build

# 4. 打包 VSIX
pnpm vsix
# 产物: bin/roo-cline-3.53.0.vsix

# 5. 智谱 Java Agent
./roo-zhipu-java-agent.sh "用 Java 写快速排序"

# 6. 自动修复
python3 fix_java.py Broken.java

# 7. 提交 (新分支)
git checkout -b feat/xxx
git add . && git commit -m "feat: xxx"
git push origin feat/xxx

# 8. Release
gh release create v3.53.0 --repo liliangxing/Roo-Code --target main
gh release upload v3.53.0 --repo liliangxing/Roo-Code bin/roo-cline-3.53.0.vsix
```

---

> **文档版本**：v1.0  
> **生成时间**：2026-07-18  
> **适用仓库**：https://github.com/liliangxing/Roo-Code  
> **Release**：https://github.com/liliangxing/Roo-Code/releases/tag/v3.53.0
