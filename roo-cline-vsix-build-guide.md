# Roo-Cline VSIX 从零构建指南（Windows 10）

> **适用人群**：对命令行不熟悉的技术人员
> **最后更新时间**：2026-07-22
> **构建环境**：Windows 10 专业版，64 位

---

## 目录

1. [准备工作](#1-准备工作)
2. [安装 Node.js（必装）](#2-安装-nodejs必装)
3. [下载项目源码](#3-下载项目源码)
4. [安装项目依赖](#4-安装项目依赖)
5. [构建 VSIX 包](#5-构建-vsix-包)
6. [常见错误与避坑指南](#6-常见错误与避坑指南)
7. [调试辅助命令](#7-调试辅助命令)
8. [附录：命令速查表](#8-附录命令速查表)

---

## 1. 准备工作

### 1.1 你需要什么

| 项目 | 说明 |
|------|------|
| 一台 Windows 10 电脑 | 64 位系统 |
| 稳定的网络 | 需要下载文件（约 500MB） |
| 至少 10GB 空闲磁盘 | 项目解压后约 1.5GB |
| GitHub 账户 | 用于提交代码（可选） |

### 1.2 了解你要做什么

简单来说，你要把 Roo-Cline 这个 VS Code 插件的**源代码**打包成一个 `.vsix` 文件。这个文件可以直接在 VS Code 中安装使用。

整个流程是：
```
源代码 → 安装依赖工具 → 下载依赖包 → 编译打包 → .vsix 文件
```

---

## 2. 安装 Node.js（必装）

### 2.1 为什么需要 Node.js？

Roo-Cline 是用 TypeScript 写的，Node.js 就是它的"运行时"。可以这样理解：
- **Node.js** = 翻译官，负责把 TypeScript 代码翻译成电脑能懂的语言
- **npm/pnpm** = 快递员，负责下载项目需要的各种"零件"（依赖包）

### 2.2 下载 Node.js

> **⚠️ 重要**：Roo-Cline 要求 **Node.js 20.19.2** 版本（查看项目根目录 `package.json` 第 4 行）
> **不要装错版本！** 装错了后面会报错。

**方法一：华为云镜像下载（国内推荐，速度快）**

1. 打开命令行（按 `Win + R`，输入 `cmd`，回车）
2. 执行以下命令：

```batch
:: 创建工具目录
mkdir C:\tools\nodejs

:: 进入目录
cd /d C:\tools\nodejs

:: 从华为云下载 Node.js 20.19.2（--insecure 是跳过 SSL 证书检查，国内网络常有这个问题）
curl --insecure -o node-v20.19.2-win-x64.zip https://repo.huaweicloud.com/nodejs/v20.19.2/node-v20.19.2-win-x64.zip

:: 等待下载完成（约 50MB，看网速 1-5 分钟）
```

如果华为云下载慢，可以换阿里云：
```batch
curl --insecure -o node-v20.19.2-win-x64.zip https://npm.taobao.org/mirrors/node/v20.19.2/node-v20.19.2-win-x64.zip
```

**方法二：官网下载（海外网络推荐）**

打开浏览器访问：https://nodejs.org/dist/v20.19.2/node-v20.19.2-win-x64.zip

### 2.3 解压安装

解压后放到 `C:\tools\nodejs\node-v20.19.2-win-x64`

```
C:\tools\nodejs\
    └── node-v20.19.2-win-x64\
        ├── node.exe         ← Node.js 本体
        ├── npm              ← 包管理器
        ├── npx              ← 包运行器
        ├── pnpm             ← 更快的包管理器（新版 Node.js 自带）
        └── ...其他文件
```

### 2.4 配置环境变量（关键步骤）

> **为什么**：你需要在任何目录下都能直接运行 `node` 命令，而不是每次都跑到安装目录去。环境变量就是告诉电脑"node.exe 放在哪个文件夹"。

1. 按 `Win + X` → 选择"系统"
2. 点击"高级系统设置"
3. 点击"环境变量"
4. 在"系统变量"中找到 `Path`，双击编辑
5. 点击"新建"，添加：`C:\tools\nodejs\node-v20.19.2-win-x64`
6. 点击"确定"保存所有窗口

**验证是否安装成功**：

重新打开一个命令行窗口，执行：
```batch
node --version
```

你应该看到：
```
v20.19.2
```

再检查 npm 和 pnpm：
```batch
npm --version
pnpm --version
```

正常输出：
```
10.8.2
10.8.1
```

> **❌ 如果报错 `'node' 不是内部或外部命令`**：
> - 说明环境变量没配置对
> - 重新检查 `Path` 里是否添加了正确的路径
> - 注意是路径到文件夹（含 `node.exe` 的文件夹），不是到 `node.exe` 本身
> - 改完后**必须重新打开命令行窗口**才能生效

---

## 3. 下载项目源码

### 3.1 克隆仓库

```batch
:: 进入工作目录（没有的话先创建）
cd /d C:\temp

:: 克隆 Roo-Code 项目
git clone https://github.com/liliangxing/Roo-Code.git

:: 进入项目目录
cd C:\temp\Roo-Code

:: 查看项目结构（确认下载成功）
dir
```

你应该能看到类似这样的文件和文件夹：
```
package.json     ← 项目配置文件（最重要的！）
pnpm-lock.yaml   ← 依赖锁定文件（保证大家装的版本一样）
src/             ← 源代码
webview-ui/      ← 界面代码
apps/            ← 其他应用
...
```

### 3.2 切换到正确分支（如果需要）

```batch
:: 查看当前分支
git branch

:: 如果你改过代码，查看修改状态
git status
```

---

## 4. 安装项目依赖

### 4.1 什么是"依赖"？

项目就像一辆汽车：
- **源代码** = 汽车的设计图纸
- **依赖包** = 发动机、轮胎、方向盘等零件

安装依赖就是**把所有需要的零件下载到本地**。

### 4.2 关于 npm 镜像（国内用户必看）

> **为什么用镜像**：npm 官方仓库在国外，国内下载非常慢（可能几小时）。镜像就是国内网站的"缓存"，下载速度能快 10 倍。

**⚠️ 重点避坑**：不同镜像有不同的问题，以下是实测结果：

| 镜像 | 速度 | 问题 |
|------|------|------|
| 官方（默认） | ❌ 慢 | 但**最稳定**，没有缺包问题 |
| 阿里云 `npmmirror.com` | ✅ 快 | 缺少 `node-ipc@12.0.0` 这个包 |
| 华为云 `huaweicloud.com` | ✅ 快 | 3 个二进制包下载失败（ECONNRESET） |
| 腾讯云 `tencent.com` | ✅ 快 | 未完整测试 |

**最终推荐方案**：先用官方仓库安装，它会自动缓存已下载的包。第一次慢点，但省心。

### 4.3 配置 npm 镜像（可选）

如果你还是想用镜像试试，可以创建 `.npmrc` 文件：

```batch
:: 创建 .npmrc 文件（在项目根目录 C:\temp\Roo-Code）
echo registry=https://registry.npmmirror.com > .npmrc
```

> **❌ 避坑**：如果 `.npmrc` 文件里写 `registry=`（等号后面是空的），会报错 `ERR_INVALID_URL`
> **✅ 解决方法**：要么写完整地址，要么直接删掉 `.npmrc` 文件

### 4.4 执行安装（最关键的一步）

```batch
:: 进入项目目录
cd /d C:\temp\Roo-Code

:: 运行安装命令
pnpm install --frozen-lockfile
```

**各参数含义**：
- `pnpm`：比 npm 更快的包管理器（Node.js 20+ 自带）
- `install`：安装所有依赖
- `--frozen-lockfile`：严格按照 `pnpm-lock.yaml` 文件安装，不修改锁定文件

**安装过程**：
```
Progress: resolved 2656, reused 2638, downloaded 18, done  ← 这个提示说明安装成功
...
dependencies:                    ← 项目依赖
+ ... 一堆包名
devDependencies:                 ← 开发工具依赖  
+ ... 一堆包名

Done in 4m 24.4s                 ← 安装完成时间
```

> **⏱ 耗时参考**：首次安装约 5-15 分钟，第二次以后因为有缓存只需几秒

---

## 5. 构建 VSIX 包

### 5.1 清理之前的构建文件

```batch
:: 进入项目目录
cd /d C:\temp\Roo-Code

:: 清理
pnpm clean
```

> **为什么需要清理**：就像做饭前要先洗锅。如果之前编译过，需要清掉旧的文件，确保新打包的是最新代码。

### 5.2 打包 VSIX

```batch
:: 打包命令
pnpm vsix
```

**构建过程**（约 3 分钟）：
```
roo-cline:build        ← 编译 TypeScript 代码
roo-cline:esbuild      ← 打包优化
webview-ui:build       ← 编译网页界面
...
roo-cline:vsix         ← 最终打包
  DONE  Packaged: ..\bin\roo-cline-3.53.0.vsix (1740 files, 29.41 MB)
```

看到 `DONE` 就说明成功了！

### 5.3 VSIX 文件在哪？

```
C:\temp\Roo-Code\bin\roo-cline-3.53.0.vsix
```

**文件信息**：
- 大小：29.41 MB
- 包含：1740 个文件
- 版本：3.53.0

### 5.4 在 VS Code 中安装 VSIX

1. 打开 VS Code
2. 按 `Ctrl + Shift + P` 打开命令面板
3. 输入并选择：`Extensions: Install from VSIX...`
4. 选择 `C:\temp\Roo-Code\bin\roo-cline-3.53.0.vsix`
5. 安装完成后，重启 VS Code

---

## 6. 常见错误与避坑指南

### 错误 1：`'node' 不是内部或外部命令`

**原因**：Node.js 没装或环境变量没配置

**解决**：
```batch
:: 检查 Node.js 安装路径
dir C:\tools\nodejs\node-v20.19.2-win-x64\node.exe

:: 如果文件存在，说明是环境变量问题
:: 按 2.4 节重新配置环境变量
```

### 错误 2：`ERR_PNPM_FETCH_404` 找不到包

**错误信息**：
```
ERR_PNPM_FETCH_404 https://registry.npmmirror.com/node-ipc/-/node-ipc-12.0.0.tgz
```

**原因**：阿里云镜像缺少这个包

**解决**：
```batch
:: 方法一：删掉 .npmrc 使用官方仓库
del .npmrc

:: 方法二：换其他镜像
echo registry=https://repo.huaweicloud.com/repository/npm/ > .npmrc
```

### 错误 3：`ECONNRESET` 连接被重置

**错误信息**：
```
Error: ERR_PNPM_FETCH_ECONNRESET … RequestError: connect ECONNRESET
```

**原因**：网络连接被中断（防火墙/代理/不稳定）

**解决**：
```batch
:: 清空 pnpm 缓存
pnpm store prune

:: 删除 .npmrc 使用官方仓库（最稳定）
del .npmrc

:: 重新安装
pnpm install --frozen-lockfile
```

### 错误 4：`ERR_INVALID_URL`

**错误信息**：
```
ERR_PNPM_INVALID_URL registry=/
```

**原因**：`.npmrc` 文件里写了 `registry=`（等号后面是空的）

**解决**：
```batch
:: 查看 .npmrc 内容
type .npmrc

:: 如果内容是 "registry="，直接删掉
del .npmrc
```

### 错误 5：`curl: (35) SSL 证书错误`

**错误信息**：
```
curl: (35) schannel: next InitializeSecurityContext failed: CRYPT_E_REVOCATION_OFFLINE
```

**原因**：Windows 的 SSL 证书检查失败（国内网络常见）

**解决**：在 curl 命令后加 `--insecure` 参数
```batch
curl --insecure -o 文件名.zip https://...
```

### 错误 6：`git push` 失败 - `Failed to connect to github.com`

**错误信息**：
```
fatal: unable to access 'https://github.com/...': Failed to connect to github.com:443
```

**原因**：当前网络环境无法访问 GitHub（公司防火墙/GFW）

**解决**：
```batch
:: 方法一：检查是否有代理
git config --global http.proxy
git config --global https.proxy

:: 如果有代理，设置
git config --global http.proxy http://你的代理地址:端口
git config --global https.proxy http://你的代理地址:端口

:: 方法二：换台电脑提交
:: 把整个 C:\temp\Roo-Code 文件夹拷贝到能访问 GitHub 的电脑上，再运行 git push

:: 方法三：用 Gitee（国内 GitHub 替代）
:: 先在 gitee.com 创建仓库，然后：
git remote add gitee https://gitee.com/你的用户名/Roo-Code.git
git push gitee master
```

---

## 7. 调试辅助命令

以下命令在你遇到问题时非常有用，可以帮你快速定位问题：

### 7.1 查看当前状态

```batch
:: 查看 Node.js 版本（确认版本是否正确）
node --version

:: 查看 npm 版本
npm --version

:: 查看 pnpm 版本
pnpm --version

:: 查看当前目录
cd

:: 列出当前目录文件
dir

:: 查看项目 package.json（了解项目信息）
type package.json

:: 查看环境变量 Path（确认 Node.js 路径是否在里面）
echo %PATH%

:: 查看 npm 配置
npm config list
```

### 7.2 网络诊断

```batch
:: 测试能不能连上 GitHub（看 DNS 能否解析）
ping github.com

:: 查看 GitHub 的真实 IP 地址
nslookup github.com

:: 测试网络是否通（如果能 ping 通但浏览器打不开，说明被防火墙拦截了）
ping 20.205.243.166

:: 测试 curl 能否下载文件
curl --insecure -I https://github.com
```

### 7.3 pnpm 相关

```batch
:: 查看 pnpm 缓存目录
pnpm store path

:: 查看缓存中已下载的包
pnpm store status

:: 清除 pnpm 缓存（如果遇到下载错误可以试试）
pnpm store prune

:: 查看已安装的包
pnpm ls --depth=0

:: 查看 pnpm 配置
pnpm config list
```

### 7.4 Git 相关

```batch
:: 查看当前分支
git branch

:: 查看提交历史
git log --oneline -10

:: 查看远程仓库地址
git remote -v

:: 查看代码修改状态
git status

:: 查看具体改了哪些内容
git diff

:: 查看某个 commit 的详细修改
git show 3b96211
```

### 7.5 VSIX 构建相关

```batch
:: 只编译代码（不打包）
cd /d C:\temp\Roo-Code
pnpm run build

:: 查看构建输出目录
dir C:\temp\Roo-Code\bin

:: 查看 VSIX 文件大小
dir C:\temp\Roo-Code\bin\roo-cline-3.53.0.vsix

:: 如果构建失败，查看详细错误
pnpm vsix --verbose
```

### 7.6 项目文件快速参考

```batch
:: 查看项目依赖清单（看项目用了哪些包）
type C:\temp\Roo-Code\package.json

:: 查看 VS Code 插件配置（了解插件功能）
type C:\temp\Roo-Code\src\package.json

:: 查看 Node.js 版本要求
findstr "node" C:\temp\Roo-Code\package.json

:: 查看构建脚本（了解打包流程）
findstr "vsix" C:\temp\Roo-Code\package.json
```

---

## 8. 附录：命令速查表

### 8.1 快速安装流程

如果你已经准备好，按顺序执行以下命令即可：

```batch
:: ===== 第 1 步：安装 Node.js =====
:: 下载（选择一种方式）
curl --insecure -o C:\tools\nodejs\node-v20.19.2-win-x64.zip https://repo.huaweicloud.com/nodejs/v20.19.2/node-v20.19.2-win-x64.zip

:: 解压（用鼠标右键解压到 C:\tools\nodejs\）

:: 配置环境变量 Path 添加：C:\tools\nodejs\node-v20.19.2-win-x64
:: 重新打开命令行窗口

:: 验证安装
node --version   &&   npm --version   &&   pnpm --version

:: ===== 第 2 步：下载源码 =====
cd /d C:\temp
git clone https://github.com/liliangxing/Roo-Code.git
cd C:\temp\Roo-Code

:: ===== 第 3 步：安装依赖 =====
:: （如果遇到网络问题，就删掉 .npmrc 使用官方源）
del .npmrc 2>nul
pnpm install --frozen-lockfile

:: ===== 第 4 步：打包 VSIX =====
pnpm clean
pnpm vsix

:: ===== 第 5 步：查看结果 =====
dir C:\temp\Roo-Code\bin\roo-cline-3.53.0.vsix
```

### 8.2 常见问题快速解决

| 问题 | 一句话解决 |
|------|-----------|
| `'node' 不是内部命令` | 配置环境变量 Path |
| 下载慢 | 删掉 `.npmrc` 或用华为云镜像 |
| 404 找不到包 | 镜像缺包，删掉 `.npmrc` 用官方源 |
| ECONNRESET | 网络不稳定，`pnpm store prune` 后重试 |
| 连接 GitHub 失败 | 公司网络屏蔽，换网络或用 Gitee |

### 8.3 相关文件路径

| 文件/目录 | 说明 |
|-----------|------|
| `C:\tools\nodejs\node-v20.19.2-win-x64` | Node.js 安装目录 |
| `C:\temp\Roo-Code` | 项目源码目录 |
| `C:\temp\Roo-Code\package.json` | 项目配置文件 |
| `C:\temp\Roo-Code\.npmrc` | npm 镜像配置（可以删） |
| `C:\temp\Roo-Code\pnpm-lock.yaml` | 依赖锁定文件 |
| `C:\temp\Roo-Code\bin\roo-cline-3.53.0.vsix` | 最终打包结果 |

---

> **最后提示**：如果按照文档操作还是遇到问题，请把错误信息截图发给我，我来帮你排查。
>
> 祝你构建顺利！🎉
