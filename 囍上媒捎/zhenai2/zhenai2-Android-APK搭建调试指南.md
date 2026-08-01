# 珍爱2（zhenai2）Android APK 搭建·调试·发布完整指南

> 本文档记录「珍爱2」（zhenai2）复刻项目从零搭建编译环境、定位启动闪退、修复代码、生成 APK、通过 GitHub Actions 自动编译并上传 GitHub Release 的全过程。
>
> 文档面向**命令行不太熟悉**的读者。所有命令都附带「大白话解释」和「为什么要这样做」。成功步骤标记为 ✅ 照着做就行，失败步骤标记为 ⚠️ 避坑提醒。关键命令附带命令输出样例（等同截图效果），方便你对照检查。

---

## 目录

- [一、项目是什么](#一项目是什么)
- [二、工具与 MCP / Skill / 模块方法说明](#二工具与-mcp--skill--模块方法说明)
- [三、环境准备（搭建编译环境）](#三环境准备搭建编译环境)
- [四、定位闪退根因（调试过程）](#四定位闪退根因调试过程)
- [五、代码修复（启动链路改造）](#五代码修复启动链路改造)
- [六、本地编译 APK（成功步骤）](#六本地编译-apk成功步骤)
- [七、APK 验证（确认产物正确）](#七apk-验证确认产物正确)
- [八、GitHub Actions 自动化构建（从零到发布）](#八github-actions-自动化构建从零到发布)
- [九、避坑总结（速查表）](#九避坑总结速查表)
- [附录：完整命令速查表](#附录完整命令速查表)

---

## 一、项目是什么

**珍爱2（zhenai2）** 是一个「珍爱网」Android 客户端的复刻项目。它的目标是：根据官方 APK 逆向出来的信息，用 Kotlin + Android 原生技术栈重新实现一个可编译、可安装的 App。

**技术栈一览（先混个眼熟）：**

| 技术 | 作用（大白话） | 版本 |
|------|--------------|------|
| Kotlin | 编程语言，写 App 逻辑 | 1.9.24 |
| Android Gradle Plugin (AGP) | 把代码打包成 APK 的「总指挥」 | 8.5.2 |
| Gradle | 自动化构建工具，AGP 靠它跑起来 | 8.7 |
| JDK 17 | Java 运行环境，Gradle 和 AGP 都要它 | 17.0.20 |
| Android SDK 34 | 编译 APK 所需的官方组件 | platform 34 / build-tools 34.0.0 |
| ARouter | 页面跳转路由框架（App 内 A→B 页怎么走） | 1.5.2 |
| KSP (Kotlin Symbol Processing) | Kotlin 的注解处理器（Glide 图片库用） | 1.9.24-1.0.20 |
| kapt (Kotlin Annotation Processing) | Kotlin 的旧版注解处理器（ARouter 1.5.2 必须用这个） | 随 Kotlin 1.9.24 |

**项目结构（13 个模块）：**

```
zhenai2/
├── app/              # App 主壳（入口、Manifest、启动页、主页）
├── lib-common/       # 公共库（常量、账号管理、日志工具 FileLog、ARouter API）
├── lib-network/      # 网络库（Retrofit + OkHttp 封装）
├── module-login/     # 登录模块
├── module-home/      # 首页推荐模块
├── module-mine/      # 我的模块
├── module-live/      # 直播模块
├── module-chat/      # 聊天模块
├── module-cert/      # 认证模块
├── module-moment/    # 动态模块
├── module-pay/       # 支付模块
├── module-emotion/   # 情感模块
├── module-web/       # 网页模块
└── .github/workflows/ # GitHub Actions 自动化脚本
    └── build-apk.yml  # APK 自动构建 + 上传 Release 的工作流
```

**每个模块的职责**：App 启动后先加载 `app` 壳，壳通过 ARouter 路由按需加载各个业务模块的页面。这样拆分的好处是「模块之间互不依赖，各自独立编译」。

**模块依赖关系图（理解这个对避坑很重要）：**

```
app (主壳，依赖所有模块)
 ├── lib-network (依赖 lib-common)
 ├── module-login (依赖 lib-common)
 ├── module-home (依赖 lib-common)
 ├── module-mine (依赖 lib-common)
 └── 其他 feature modules (都依赖 lib-common)

lib-common (被所有模块依赖，放公共工具和 ARouter API)
```

> ⚠️ **关键理解**：`lib-common` 使用 `api` 声明依赖（而不是 `implementation`），意味着依赖会传递给下游模块。所以 `app` 模块间接拥有 `arouter-api`。但注解处理器 (`kapt`) 的传递是另一回事——**`kapt` 依赖不会自动传递**，每个模块需要自己声明。

---

## 二、工具与 MCP / Skill / 模块方法说明

> 本节是重点。下面列出整个过程中**用到的工具、MCP 接口、Skill 技能、AI 模块方法**，逐一说明是什么、原理是什么、什么时候用。

### 2.1 我（AI 助手）使用的模块方法

AI 助手不只是「会聊天」，它能调用一系列内置工具来操作你的电脑（读文件、写文件、跑命令）。这些工具就是「模块方法」。本次用到的有：

| 方法名 | 作用（大白话） | 原理说明 | 本次使用场景 |
|--------|--------------|---------|-------------|
| `read` | 读取文件内容 | 把文件按行读出来给 AI 看。就像你用记事本打开文件。每次最多读 200 行，大文件分段读，省内存 | 查看构建日志、源代码文件 |
| `glob` | 按文件名找文件 | 用通配符（如 `**/*.kt`）模糊匹配文件名，返回文件路径列表。相当于 Windows 搜索框 | 搜索项目中所有 kotlin 文件 |
| `grep` | 在文件内容里搜关键字 | 全文正则搜索。比如搜「@Route」就能找出所有路由注解。比逐文件打开快得多 | 查找特定类的引用、错误关键字 |
| `write` | 写入/新建文件 | 整个文件内容一次性写入。用于新建文件 | 创建新脚本、配置文件 |
| `edit` | 精确替换文件某段 | 找到文件中一段「唯一文本」，替换成新内容。比 write 更精准，只改该改的地方 | 修改已有文件的部分内容 |
| `bash` | 执行 shell 命令 | 直接在你的终端里跑命令（curl、unzip、gradle、git 等）。所有命令执行都走它 | 编译、git 操作、API 调用 |
| `background_terminal_create` | 后台执行长命令 | 像 gradle 编译这种要跑几十分钟的命令，放后台跑，不阻塞对话；日志写到文件里 | 长时间编译任务 |
| `background_terminal_kill` | 停止后台任务 | 后台跑太久或卡住了，用终端 ID 结束它 | 取消失败的任务 |
| `todowrite` | 维护任务清单 | 把大任务拆成多步，标记进行中/完成，防止漏步骤 | 跟踪修复进度 |
| `question` | 向你提问 | 有歧义或需要你确认时，弹选项让用户选 | 确认操作意图 |
| `task` | 派发子任务给子 AI | 复杂调研交给子代理并行做，子代理有独立上下文，做完把结果汇总回来 | 并行搜索代码、测试 |

### 2.2 MCP（Model Context Protocol）工具

MCP 是「让 AI 连接外部服务的标准化接口」。本次可用的 MCP 工具及原理：

| MCP 工具 | 作用 | 原理 | 本次使用 |
|---------|------|------|---------|
| `resolve-library-id` | 把库名解析成 Context7 标准 ID | 把库名（如 React）映射成标准标识，后续查询文档用 | 未使用 |
| `query-docs` | 查开源库在线文档 | 用标准 ID 从 Context7 拉取官方文档和代码示例 | 未使用 |
| `websearch_search` | 原始网页搜索 | 返回网页链接列表。适合找最新资讯、验证官网地址 | 未使用（本地编译任务） |
| `websearch_aisearch` | 联网综合问答 | 基于多个网页来源生成总结回答 | 未使用 |

> **本项目实际用到哪些？** 本次 zhenai2 是「本地代码编译 + GitHub Actions」任务，主要用到了**模块方法**（read/grep/edit/bash 等）和 **GitHub CLI (gh)**。MCP 文档查询类工具在本项目中没有触发。

### 2.3 Skill（技能）

Skill 是「针对特定任务的成套流程脚本」，加载后 AI 按流程执行。本项目环境中可用的：

| Skill | 用途 | 本次是否用到 |
|-------|------|------------|
| `deploy-website` | 部署并本地预览 Web 项目 | 未用 |
| `publish-website` | 把 Web 项目发布成线上托管应用 | 未用（用 GitHub Release 代替） |
| `pdf` | PDF 文件处理 | 未用 |
| `pptx` | PPT 演示文稿处理 | 未用 |
| `docx` | Word 文档处理 | 未用 |
| `xlsx` | Excel 表格处理 | 未用 |
| `skill-creator` | 创建新技能 | 未用 |
| `paw-browser` | 浏览器自动化 | 未用 |

> **原理说明**：Skill 本质上是一份「带步骤说明和参考脚本的说明书」。AI 判断任务匹配某个 skill 时，通过 `skill` 工具把说明书注入对话上下文，然后按里面的流程一步步执行。本项目的编译和发布走的是**命令行 + GitHub API** 而非特定的 skill。

### 2.4 GitHub CLI（gh）— 最重要的发布工具

`gh` 是 GitHub 官方命令行工具，用于操作仓库、Releases、PR 等。在自动化构建中非常关键：

```bash
# ===== gh 常用命令速查 =====

# 登录（用 Personal Access Token）
echo "<你的token>" | gh auth login --with-token

# 让 git 使用 gh 的凭据（解决 git push 反复要密码）
gh auth setup-git

# 创建 Release 并附带 APK 文件
gh release create v1.1.0 "/路径/app-debug.apk"

# 查看 Release 列表
gh release list

# ===== GitHub API 直接调用（本项目大量使用）=====

# 获取文件内容（返回 base64 编码）
gh api repos/liliangxing/zhenai2/contents/path/to/file?ref=branch -q '.content' | base64 -d

# 获取文件 SHA（更新文件用）
gh api repos/liliangxing/zhenai2/contents/path/to/file?ref=branch -q '.sha'

# 更新文件（PUT 方式，一次性 push 不经过 git commit）
gh api repos/liliangxing/zhenai2/contents/path/to/file --method PUT \
  --field message="提交说明" \
  --field content="$(base64 -w0 /tmp/newfile)" \
  --field sha="旧文件SHA" \
  --field branch="分支名"

# 查看 Actions 运行状态
gh api "repos/liliangxing/zhenai2/actions/runs?per_page=3" \
  --jq '.workflow_runs[] | {id, status, conclusion, head_sha: .head_sha[0:8]}'

# 查看某个运行的任务列表
gh run view <run_id> --repo liliangxing/zhenai2

# 查看失败任务的日志
gh run view <run_id> --repo liliangxing/zhenai2 --log-failed

# 查看完整日志
gh run view <run_id> --repo liliangxing/zhenai2 --log

# 列出仓库所有 Releases
gh api repos/liliangxing/zhenai2/releases --jq '.[] | {tag_name, name, id}'

# 查看 Release 详情（含资产列表）
gh api repos/liliangxing/zhenai2/releases/<release_id> \
  --jq '{tag, name, assets: [.assets[]? | {name, size, browser_download_url}]}'
```

**原理**：`gh auth login` 把 token 存到 `~/.config/gh/hosts.yml`；`gh auth setup-git` 会修改 git 的凭据配置，让 `git push` 自动用这个 token。

**为什么本项目用 GitHub API 而不是 git push？** GitHub Actions 环境里 git push 有时会触发不必要的 webhook 循环，而直接用 API 更新文件更可控、更快（不需要 clone 整个仓库）。

### 2.5 GitHub Actions 工作流核心 YAML 语法速查

```yaml
name: Build APK           # 工作流名称

on:                       # 触发条件
  push:
    tags: ['v*']          # tag 匹配 v* 时触发
    branches: ['v0.1.0-fixed']  # 特定分支 push 时触发
  workflow_dispatch:       # 允许手动触发

permissions:               # 整个工作流的权限
  contents: write          # 可读写仓库内容（创建 Release 必须）

jobs:
  build:
    runs-on: ubuntu-latest  # 运行环境
    permissions:            # 单 job 的权限
      contents: write       # 创建 Release 需要写权限
    steps:                  # 执行步骤（按顺序）
      - name: 步骤名
        uses: xxx@v1        # 用现成的 action
        run: |              # 跑 shell 命令
          echo "hello"
        env:                # 环境变量
          KEY: value
        if: success()       # 条件：上一步成功才执行
```

**关键参数说明：**
- `permissions: contents: write` — 如果不加这个，`softprops/action-gh-release@v2` 会报 `Resource not accessible by integration` 错误！这在「八、GitHub Actions 自动化构建」里会详细说。
- `tag_name` — Release 关联的 tag。如果 tag 不存在会自动创建。
- `softprops/action-gh-release@v2` — 把文件上传到 GitHub Release 的现成 action，比自己调 API 方便。

---

## 三、环境准备（搭建编译环境）

> 目标：让电脑具备「把 Kotlin 代码编译成 APK」的全部工具。顺序：JDK → Gradle → Android SDK → 项目配置。

### 3.1 安装 JDK 17

**为什么**：AGP 8.5.2 和 Gradle 8.7 都要求 Java 17。没有它，后面一切免谈。

```bash
# 1) 用系统包管理器安装 OpenJDK 17（Ubuntu/Debian）
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk

# 2) 验证安装成功（应显示 17.x）
java -version

# 期望输出（等同截图）：
# openjdk version "17.0.20" 2026-07-21
# OpenJDK Runtime Environment (build 17.0.20+8-1-deb12u1-Debian)
# OpenJDK 64-Bit Server VM
```

**安装到哪里了？** 通常装在 `/usr/lib/jvm/java-17-openjdk-amd64`。这个路径后面设 `JAVA_HOME` 要用，先记住它。

### 3.2 安装 Gradle 8.7

**为什么**：Gradle 是构建执行器。AGP 是插件，必须挂在 Gradle 上跑。版本必须 8.7（AGP 8.5.2 兼容的 Gradle 版本）。

```bash
# 1) 下载 Gradle 8.7 发行版（zip 约 135MB）
cd /opt
curl -L -o gradle-8.7-bin.zip "https://services.gradle.org/distributions/gradle-8.7-bin.zip"

# 2) 解压
unzip gradle-8.7-bin.zip      # 解压出 /opt/gradle-8.7

# 3) 验证
/opt/gradle-8.7/bin/gradle --version
# 期望输出（等同截图）：
# Gradle 8.7
# JVM: 17.0.20 (Debian 17.0.20+8-1-deb12u1-Debian)
```

> **⚠️ 避坑提醒 1：`./gradlew` 第一次跑会自动去 services.gradle.org 下载 Gradle，沙箱里会报 `Connection refused`。** 这是网络不通导致。**解决办法：直接用 `/opt/gradle-8.7/bin/gradle` 命令，跳过 gradlew 自动下载。**（gradlew 是「项目自带的小启动器」，本质还是去下载 Gradle 再调用；既然我们已经手动装了 Gradle，直接调用即可。）

### 3.3 安装 Android SDK（platform-34 + build-tools 34.0.0）

**为什么**：编译 APK 需要两个 SDK 组件——`platforms/android-34`（提供 android.jar 编译库）和 `build-tools/34.0.0`（提供 aapt2 等打包工具）。

#### 3.3.1 下载 build-tools 34.0.0

> **避坑提醒 2：国内直连 dl.google.com 很慢，强烈建议用腾讯云镜像。**

```bash
mkdir -p /opt/android-sdk/build-tools
cd /opt/android-sdk

# 下载（腾讯云镜像，速度快）
curl --http1.1 -sL -o build-tools.zip \
  "https://mirrors.cloud.tencent.com/AndroidSDK/build-tools_r34-linux.zip"

unzip -q build-tools.zip
ls        # 看到 android-14 之类的目录
mv android-14 build-tools/34.0.0
```

#### 3.3.2 下载 platform-34

```bash
cd /opt/android-sdk
curl --http1.1 -sL --max-time 300 -o platform.zip \
  "https://mirrors.cloud.tencent.com/AndroidSDK/platform-34-ext7_r03.zip"

unzip -q platform.zip
mkdir -p platforms
mv android-34 platforms/
```

### 3.4 配置项目 `local.properties`

**为什么**：Gradle 需要知道 SDK 装在哪。项目根目录的 `local.properties` 就是干这个的（**不要**提交到 git，已加入 .gitignore）。

```bash
echo "sdk.dir=/opt/android-sdk" > /workspace/local.properties
```

### 3.5 项目网络仓库配置（settings.gradle.kts）

**为什么**：编译时要下载 AGP、Kotlin 插件、第三方库。这些依赖从哪下载？在 `settings.gradle.kts` 里配置仓库地址。

**最终有效配置（GitHub Actions 环境）：**

```kotlin
pluginManagement {
    repositories {
        google()         # Google 官方仓库（AGP 在这里）
        mavenCentral()   # Maven 中央仓库
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://jitpack.io") }  // 第三方自定义库
    }
}
```

> **避坑提醒**：不要加阿里云镜像（`maven.aliyun.com`）在 GitHub Actions 里。原因：阿里云镜像在 GitHub Actions 网络环境下经常超时或不可达，反而导致插件下载失败。Google 官方和 Maven Central 在 GitHub Actions 的 ubuntu-runner 上是可达的。

---

## 四、定位闪退根因（调试过程）

> 这一节是**最值钱的部分**——它展示了「App 一打开就闪退」是怎么一步步查出来的。

### 4.1 现象

用户报告：安装 APK 后**打开就闪退**，没有任何界面。

### 4.2 第一步：按 Android App 启动顺序梳理排查路径

```
系统创建进程
   ↓
① Application.attachBaseContext()   ← MultiDex 在这里
   ↓
② 系统实例化 Manifest 里注册的所有 ContentProvider
   ↓                          ← ⚠️ 这一步最先执行，比 Application.onCreate 还早！
③ Application.onCreate()           ← CrashHandler 在这里才安装
   ↓
④ 启动 Activity（SplashActivity）onCreate()
   ↓
⑤ ARouter 路由跳转 → MainActivity / LoginActivity
```

### 4.3 第二步：查 Manifest（用 aapt2 解析 APK）

```bash
# 用 aapt2 解出 APK 里的 AndroidManifest.xml 并转成可读文本
/opt/android-sdk/build-tools/34.0.0/aapt2 dump xmltree \
  --file AndroidManifest.xml app-debug.apk > /tmp/manifest.txt

# 统计四大组件数量
grep -c "E: activity" /tmp/manifest.txt     # Activity 数量
grep -c "E: provider" /tmp/manifest.txt     # Provider 数量
```

**排查结果：** Activity 322 个、Provider 17 个——绝大多数是第三方 SDK 的类。

**结论**：闪退根因是 **Manifest 声明了源码中不存在的第三方组件类（尤其是 Provider），系统在 Application.onCreate 之前实例化它们时抛 ClassNotFoundException**。这个崩溃发生在 CrashHandler 安装之前，所以无日志可查。

### 4.4 验证命令（确认哪些类确实不存在）

```bash
# 在项目源码目录搜不存在的第三方包
grep -rn "com.netease.nimlib" /workspace/app/src/ 2>/dev/null
grep -rn "com.getui" /workspace/app/src/ 2>/dev/null
# 无输出 = 类不存在 = 确认闪退根因
```

---

## 五、代码修复（启动链路改造）

> 修复思路：**精简 Manifest**——只注册源码中真实存在的组件。这是比「补齐缺失依赖」更小的修复方案。

### 5.1 重写精简版 AndroidManifest.xml

**保留**：根级权限、uses-feature、application 属性、uses-library、meta-data。
**只注册实际存在的组件**：
- `SplashActivity`（含 LAUNCHER 启动入口）
- `MainActivity`
- `LoginActivity`
- `FileProvider`（androidx 提供的文件分享 Provider）

### 5.2 修复 SplashActivity：使用 lifecycleScope 异步检查登录态

**为什么**：原 SplashActivity 只调用 super.onCreate 然后打日志，没有 setContentView 也没有导航——这就是用户感知「白屏卡死（闪退）」的原因。

```kotlin
class SplashActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 不走 setContentView，仅利用主题背景做启动画面
        lifecycleScope.launch {
            checkLoginAndRoute()
        }
    }

    private suspend fun checkLoginAndRoute() {
        if (AccountManager.isLogin) {
            routeToMain(); finish(); return
        }
        try {
            val resp = NetworkClient.apiService.checkLogin()
            if (resp.data?.isLogin == true) routeToMain() else routeToLogin()
        } catch (e: Exception) {
            routeToLogin()  // 网络异常默认进登录页
        }
        finish()
    }
}
```

### 5.3 新增统一日志工具 FileLog（重点设计）

**为什么**：之前发现「启动早期闪退无日志可查」。解决办法是做一个**比 CrashHandler 更早、能覆盖所有模块的日志工具**。

**放在哪个模块？** `lib-common`（公共库）。**为什么？** 因为 login/home/mine 等所有业务模块都依赖 lib-common，放这里所有模块都能调用。如果放 app 壳，业务模块依赖 app 会形成循环依赖。

### 5.4 重写 CrashHandler：基于 FileLog

```kotlin
class CrashHandler private constructor() : Thread.UncaughtExceptionHandler {
    fun install(ctx: Context) {
        FileLog.init(ctx.applicationContext)
        Thread.setDefaultUncaughtExceptionHandler(this)
    }

    override fun uncaughtException(t: Thread, e: Throwable) {
        try { /* 写日志到 /sdcard/douyinguanjia/Log/zhenai2.log */ } catch (_: Throwable) {}
        Process.killProcess(Process.myPid())
        System.exit(10)
    }
}
```

**原理**：`Thread.setDefaultUncaughtExceptionHandler` 是 Java 提供的「全局未捕获异常钩子」。任何线程抛出没人处理的异常，系统都会回调它。我们在这里记录堆栈，然后主动结束进程。

---

## 六、本地编译 APK（成功步骤）

### 6.1 关键环境变量

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/opt/android-sdk
```

### 6.2 首次尝试：用 gradlew → 失败

```bash
cd /workspace
./gradlew :app:assembleDebug
```

**结果（避坑）**：`Connection refused`。gradlew 尝试去下载 Gradle 被网络拦截。

### 6.3 第二次尝试：用本地 Gradle → 又失败（插件解析不了）

```bash
/opt/gradle-8.7/bin/gradle :app:assembleDebug --no-daemon
```

**报错：** `Plugin [id: 'com.android.application', version: '8.5.2'] was not found`

### 6.4 排查代理问题（经典错误定位过程）

```bash
# ① 检查 gradle.properties 里的代理配置
cat gradle.properties
# 看到：systemProp.http.proxyHost=127.0.0.1:18080

# ② 检查 18080 端口到底有没有进程在监听
ss -tlnp | grep 18080
# ⚠️ 结果：没有输出！说明根本没有服务监听 18080

# ③ 结论：JVM 每次请求都去连 18080 但被拒 → 插件下载失败
```

### 6.5 修复：移除错误的代理配置

```bash
# 删除这 4 行代理配置
# systemProp.http.proxyHost=127.0.0.1
# systemProp.http.proxyPort=18080
# systemProp.https.proxyHost=127.0.0.1
# systemProp.https.proxyPort=18080
```

> **为什么可以直连？** 沙箱网络实际是「透明代理」——出口流量已被自动代理，不需要应用自己配代理。手动配 18080 反而连到不存在的端口直接失败。

### 6.6 编译成功

```bash
cd /workspace
/opt/gradle-8.7/bin/gradle :app:assembleDebug --no-daemon
```

**结果（等同截图）：**

```
> Task :app:compileDebugKotlin
> Task :app:compileDebugJavaWithJavac
> Task :app:dexBuilderDebug
> Task :app:packageDebug
> Task :app:assembleDebug

BUILD SUCCESSFUL in 8m 54s
```

**产物位置：** `/workspace/app/build/outputs/apk/debug/app-debug.apk` （约 91MB）

### 6.7 后续编译过程中的代码 Bug 修复（汇总）

本地编译成功后，后续用 GitHub Actions 自动编译时遇到了更多代码 Bug，这里先汇总，详细过程见第八节：

| 次序 | 错误类型 | 报错信息 | 根因 | 修复方案 |
|------|---------|---------|------|---------|
| 1 | Kotlin 编译 | `Unresolved reference: network` | AutoLoginManager 在 lib-common，但 import 了 lib-network 的包 | 把 AutoLoginManager 移到 lib-network |
| 2 | Duplicate class | `support-compat:28.0.0 vs androidx.core` | logger:2.2.0 传递拉入旧 support 库 | 移除 logger + exclude support 组 |
| 3 | UnknownPluginException | 插件找不到 | gradle.properties 残留代理配置 | 移除代理配置 |
| 4 | @Route unsupported | Fragment 不支持 @Route | ARouter 1.5.2 不支持 Fragment | 移除 Fragment 上的 @Route |
| 5 | kapt constant | `element value must be a constant expression` | 跨模块 Kotlin 常量不可见 | 用内联字符串替代 RouterPath.XXX |
| 6 | kapt | `Unresolved reference: city` | BasicProfile 没有 city 字段 | 删除这行代码 |
| 7 | launch extension | `Unresolved reference: launch` | BaseViewModel 缺少 launch 扩展函数 | 添加扩展函数 |
| 8 | **kapt processor crash** | `getTypeElement(...) returns null` | **ARouter 1.5.2 注解处理器在 app 模块（kapt+KSP 共存）时崩溃** | **彻底移除 app 模块的 kapt，改用 Intent 导航** |

> ⚠️ **第 8 条是最重要的坑，也是本次会话重点解决的内容。** 详细分析见下一节。

---

## 七、APK 验证（确认产物正确）

### 7.1 查看包信息、启动入口

```bash
/opt/android-sdk/build-tools/34.0.0/aapt2 dump badging app-debug.apk
```

**关键输出：**
```
package: name='com.zhenai2.android' versionCode='1' versionName='1.0.0'
launchable-activity: name='com.zhenai2.android.ui.splash.SplashActivity'
```

### 7.2 确认组件只剩真实存在的类

```bash
/opt/android-sdk/build-tools/34.0.0/aapt2 dump xmltree \
  --file AndroidManifest.xml app-debug.apk > /tmp/final_manifest.txt

# 列出所有注册的组件类名
grep -oE 'name\(0x01010003\)="[^"]*"' /tmp/final_manifest.txt | sort -u
```

应只剩：`SplashActivity`, `MainActivity`, `LoginActivity`, `FileProvider`（androidx 自带）。

### 7.3 确认 ARouter 路由表生成

编译日志中应看到：
```
Note: ARouter::Compiler >>> Found activity route: com.zhenai2.login.LoginActivity <<<
```

---

## 八、GitHub Actions 自动化构建（从零到发布）

> 本节是**核心新增内容**——记录如何用 GitHub Actions 让代码提交后自动编译 APK 并上传到 Release。

### 8.1 创建 workflow 文件

**路径：** `.github/workflows/build-apk.yml`

```yaml
name: Build APK

on:
  push:
    branches: ['v0.1.0-fixed']  # 这个分支 push 就触发
  workflow_dispatch:            # 也允许手动触发

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      - uses: android-actions/setup-android@v3
      # ... 后续步骤
```

### 8.2 处理 Gradle 发行版下载（GitHub Actions 环境）

**问题**：GitHub Actions 环境里 `gradlew` 自动下载 Gradle 超慢或失败。

**解决步骤：**

```bash
# 第一步：手动安装 Gradle 8.7
GRADLE_DEST="/opt/gradle-8.7"
GRADLE_ZIP="/tmp/gradle-8.7-bin.zip"

# 从多个镜像尝试下载
mirrors=(
  "https://services.gradle.org/distributions/gradle-8.7-bin.zip"
  "https://downloads.gradle.org/distributions/gradle-8.7-bin.zip"
  "https://mirrors.cloud.tencent.com/gradle/gradle-8.7-bin.zip"
  "https://mirrors.aliyun.com/macports/distfiles/gradle/gradle-8.7-bin.zip"
)
for mirror in "${mirrors[@]}"; do
  if curl -sL --max-time 120 "$mirror" -o "$GRADLE_ZIP" && [ -s "$GRADLE_ZIP" ]; then
    unzip -t "$GRADLE_ZIP" >/dev/null 2>&1 && break
  fi
done

sudo mkdir -p /opt
sudo unzip -q "$GRADLE_ZIP" -d /opt/
echo "$GRADLE_DEST/bin" >> $GITHUB_PATH

# 第二步：安装 Android platform-34
$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platforms;android-34"

# 第三步：编译
gradle :app:assembleDebug --no-daemon --stacktrace
```

**验证 APK 产物的正确命令（避坑重点！）：**

```yaml
- name: Find APK
  id: find-apk
  run: |
    # ✅ 正确写法：只在 build 输出目录找
    APK=$(find app/build/outputs/apk/debug -name "*.apk" 2>/dev/null | head -1)
    echo "apk=$APK" >> $GITHUB_OUTPUT
```

> **⚠️ 避坑提醒：如果写成 `find . -name "*.apk"` 会找到仓库里原有的原始 APK 文件（如 `原apk及原始反编译/珍爱网官方原版APK-v9.29.5.apk`），导致上传错误的文件。一定要限定路径为 `app/build/outputs/apk/debug/`。**

### 8.3 上传到 GitHub Release

```yaml
- name: Upload APK to release
  if: success()
  uses: softprops/action-gh-release@v2
  with:
    tag_name: v0.1.1-fixed
    name: "v0.1.1-fixed (Auto-build with crash fixes)"
    files: ${{ steps.find-apk.outputs.apk }}
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 8.4 调试过程：第一个 Bug — Gradle 发行版下载失败

**现象**：构建报错 `Could not resolve com.android.tools.build:gradle:8.5.2`。

**排查**：
1. 检查 `gradle.properties` → 发现残留的 `127.0.0.1:18080` 代理配置
2. 测试 `curl -sL "https://mirrors.cloud.tencent.com/..."` → 镜像可达
3. **结论**：JVM 的 `systemProp.http.proxyHost` 拦截了所有请求到不存在的端口

**修复**：从 `gradle.properties` 删除代理配置。

### 8.5 调试过程：第二个 Bug — ARouter kapt 处理器崩溃（本次最复杂的坑）

#### 8.5.1 现象

```
> Task :app:kaptDebugKotlin FAILED
error: ARouter::Compiler An exception is encountered, 
[Cannot invoke "javax.lang.model.element.TypeElement.asType()" 
because the return value of "javax.lang.model.util.Elements.getTypeElement(...)" is null]
```

#### 8.5.2 分析错误

**定位过程：**

```bash
# 查看完整错误日志
gh run view <run_id> --repo liliangxing/zhenai2 --log 2>&1 | grep -B2 -A10 "ARouter::Compiler"
```

**错误栈关键信息：**
```
at com.alibaba.android.arouter.compiler.processor.RouteProcessor.parseRoutes(RouteProcessor.java:135)
```

**白话解释**：ARouter 注解处理器在解析 `@Route` 注解时，调用 `Elements.getTypeElement("android.app.Activity")` 试图获取 Activity 类的定义。但这个方法返回了 **null**（null = 找不到），而代码接着对它调用 `.asType()`，就报了 NullPointerException。

#### 8.5.3 为什么会这样？（根因分析）

ARouter 编译器初始化时需要拿到「Activity」「Fragment」「Service」等关键类的 TypeMirror，以便：
- 判断 `@Route` 标注的类是不是 Activity/Fragment
- 生成路由表时记录这些类的类型信息

**调用链**：`Elements.getTypeElement()` → 在编译器的搜索路径里找 `android.app.Activity` → 找不到 → 返回 null

**为什么找不到？** 这涉及到 kapt stub 生成机制：
1. kapt 要把 Kotlin 代码先转成 Java Stub（给注解处理器看）
2. 当 app 模块**同时使用 KSP (Glide) 和 kapt (ARouter)** 时，KSP 先运行生成了一部分 Stub
3. kapt 自己在生成 ARouter 需要的 Stub 时，因为 Groovy/KSP 已经创建过的上下文冲突或 classpath 不完整，导致找不到 `android.app.Activity` 的 Stub
4. `getTypeElement("android.app.Activity")` 在这个不完整的上下文里返回 null

#### 8.5.4 第一次修复尝试：加 --add-opens（失败）

**尝试**：以为是 Java 17 模块系统限制，在 `gradle.properties` 和 `build.gradle.kts` 都加了 JVM 参数：

```properties
# gradle.properties
org.gradle.jvmargs=-Xmx4096m --add-opens=java.base/java.lang=ALL-UNNAMED ...
```

```kotlin
// app/build.gradle.kts
kapt {
    javacOptions {
        option("--add-opens", "java.base/java.lang=ALL-UNNAMED")
    }
}
```

**结果**：同样的错误。**说明根因不是 Java 模块系统限制**。

#### 8.5.5 第二次修复尝试：root build.gradle.kts 统一配置（失败）

**尝试**：在根项目 `build.gradle.kts` 里统一给所有子模块注入 kapt 参数：

```kotlin
subprojects {
    plugins.withId("com.android.application") {
        // 配置 kapt 参数 ...
    }
}
```

**结果**：失败，同样错误。

#### 8.5.6 最终解决方案：彻底移除 app 模块的 kapt

**根本思路**：既然 ARouter kapt 处理器在 app 模块（KSP+kapt 共存环境）下无法正常工作，就别在 app 模块用 kapt 了。用更简单的方式实现同样的功能。

**修改 1：`app/build.gradle.kts` — 移除 kapt 和 ARouter 编译器依赖**

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.google.devtools.ksp")     // 保留 KSP（Glide 需要）
    id("org.jetbrains.kotlin.plugin.parcelize")
    // ❌ 删除 id("org.jetbrains.kotlin.kapt")  ← 关键！
}

dependencies {
    implementation(project(":lib-common"))
    implementation(project(":lib-network"))
    // ❌ 删除 kapt("com.alibaba:arouter-compiler:1.5.2") ← 关键！
}
```

**修改 2：`SplashActivity.kt` — 移除 @Route，改用 Intent 导航**

```kotlin
// ❌ 删除 @Route(path = "/app/splash")
class SplashActivity : AppCompatActivity() {
    
    private fun startMainActivity() {
        // ✅ 显式 Intent 导航
        startActivity(Intent(this, MainActivity::class.java))
    }
    
    private fun startLoginActivity() {
        // ✅ 登录页路由仍通过 ARouter（feature module 的 kapt 是正常的）
        ARouter.getInstance().build("/login/login").navigation(this)
    }
}
```

**修改 3：`MainActivity.kt` — 移除 @Route**

```kotlin
// ❌ 删除 @Route(path = "/app/main")
class MainActivity : AppCompatActivity() { ... }
```

**为什么这样能工作？**
- SplashActivity → MainActivity：用 Intent 直接启动，不需要 ARouter
- SplashActivity → LoginActivity：LoginActivity 的 `@Route` 注解在 module-login 模块编译，那个模块只有 kapt 没有 KSP，所以 ARouter 处理器能正常工作
- 最终效果：运行时 ARouter loadRouteMap() 会加载所有正常生成的路由（来自各 feature module），app 模块自己的两个 Activity 不走 ARouter

**运行逻辑验证（用命令确认）：**

```bash
# 查看运行时 ARouter 会加载哪些路由类
# 各 feature module 编译后会生成：
ls module-login/build/generated/source/kapt/debug/com/alibaba/android/arouter/routes/
# ARouter$$Group$$login.java  ← 这个文件里有 LoginActivity 的路由
# ARouter$$Providers$$login.java
# ARouter$$Root$$login.java
```

### 8.6 调试过程：权限问题（第二个大坑）

#### 8.6.1 现象

```
⚠️ Unexpected error fetching GitHub release for tag refs/heads/v0.1.0-fixed:
HttpError: Resource not accessible by integration
```

**白话**：GitHub API 返回「这个 token 没权限这么做」。

#### 8.6.2 原因

GitHub Actions 的 `GITHUB_TOKEN` 默认只有 **读** 权限。而 `softprops/action-gh-release@v2` 要创建/更新 Release，需要 **写** 权限。

#### 8.6.3 修复：在 workflow 文件里加 permissions

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write     # ← 加这行！创建 Release 需要写 contents
    steps:
      # ...
```

> **⚠️ 避坑提醒：** 这个权限必须写在 **job 级别**（或 workflow 级别），不能是 env 变量。

### 8.7 调试过程：APK 路径找到了错误文件

#### 8.7.1 现象

上传的 APK 文件名是 `珍爱网官方原版APK-v9.29.5.apk` 而不是编译出来的 `app-debug.apk`。

#### 8.7.2 原因

原始 workflow 用 `find . -name "*.apk"` 在整个仓库找 APK，而仓库里本来就有一个 `原apk及原始反编译/珍爱网官方原版APK-v9.29.5.apk`（之前提交的反编译素材）。

#### 8.7.3 修复

```bash
# ❌ 错误写法
APK=$(find . -name "*.apk" 2>/dev/null | head -1)

# ✅ 正确写法：只在 build 输出目录找
APK=$(find app/build/outputs/apk/debug -name "*.apk" 2>/dev/null | head -1)
```

### 8.8 最终成功的 workflow 文件

完整内容见 `.github/workflows/build-apk.yml`，核心结构：

```yaml
name: Build APK

on:
  push:
    tags: ['v*']
    branches: ['v0.1.0-fixed']
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4:
        with: { java-version: '17', distribution: 'temurin' }
      - uses: android-actions/setup-android@v3
      
      # 1. 手动下载 Gradle 8.7（处理 gh-actions 网络问题）
      - name: Install Gradle wrapper distribution
        run: |
          mirrors=(...多镜像 fallback...)
          for mirror in "${mirrors[@]}"; do curl ... && break; done
      
      # 2. 安装 platform-34
      - name: Install Android platforms;34
        run: sdkmanager "platforms;android-34"
      
      # 3. 编译
      - name: Build Debug APK
        run: gradle :app:assembleDebug --no-daemon --stacktrace
      
      # 4. 找 APK（限定路径！）
      - name: Find APK
        run: APK=$(find app/build/outputs/apk/debug -name "*.apk" | head -1)
      
      # 5. 上传
      - name: Upload APK to release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v0.1.1-fixed
          files: ${{ steps.find-apk.outputs.apk }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 8.9 查看构建结果

```bash
# 查看最新构建状态
gh api "repos/liliangxing/zhenai2/actions/runs?per_page=1" \
  --jq '.workflow_runs[0] | {id, status, conclusion}'

# 查看构建日志（只看错误）
gh run view <run_id> --repo liliangxing/zhenai2 --log-failed

# 构建成功后查看 Release 资产
gh api repos/liliangxing/zhenai2/releases \
  --jq '.[] | select(.tag_name == "v0.1.1-fixed") | {tag, assets: [.assets[]?.name]}'

# 查看 APK 文件大小
gh api repos/liliangxing/zhenai2/releases/<id> \
  --jq '.assets[] | {name, size, browser_download_url}'
```

### 8.10 最终结果

```
构建 ID:  30709765894
状态:     success
Release:  https://github.com/liliangxing/zhenai2/releases/tag/v0.1.1-fixed
APK:      app-debug.apk (约 91MB)
下载:     https://github.com/liliangxing/zhenai2/releases/download/v0.1.1-fixed/app-debug.apk
```

---

## 九、避坑总结（速查表）

| # | 坑 | 现象 | 解决 |
|---|----|------|------|
| 1 | `./gradlew` 自动下载 Gradle 被拒 | `Connection refused` | 直接用 `/opt/gradle-8.7/bin/gradle` |
| 2 | 国内下载 SDK 慢/卡死 | 下载停滞 | 用腾讯云镜像 `mirrors.cloud.tencent.com/AndroidSDK/` |
| 3 | SDK zip 顶层目录名不对 | 解压出来叫 `android-14` | 先 `ls` 看再 `mv` 改名 |
| 4 | platform 文件名带后缀 | 找不到 `platform-34.zip` | 用 `platform-34-ext7_r03.zip` |
| 5 | gradle.properties 错误代理 | 插件 `was not found` | 移除 `127.0.0.1:18080` 代理配置 |
| 6 | Manifest 声明不存在的类 | 启动即闪退且无日志 | 精简 Manifest 只留真实组件 |
| 7 | MainActivity 缺 @Route | 跳主页失败 | 补 `@Route(path = "...")` 或改用 Intent |
| 8 | ARouter navigation() 返回 null | 强转 NPE 闪退 | 用 `as? Fragment ?: Fragment()` 兜底 |
| 9 | SplashActivity finish() 过早 | 无法跳转 | finish() 移入路由方法内部 |
| 10 | settings.gradle.kts 用阿里云镜像 | GitHub Actions 超时 | 移除阿里云，用 google() + mavenCentral() |
| 11 | gradle.properties 残留代理 | 沙箱里所有网络被拦 | 删掉 sandbox 的 `systemProp.http.proxyHost` |
| 12 | Kotlin 跨模块常量不可见 | `must be a constant expression` | 用内联字符串替代 RouterPath 常量 |
| 13 | Fragment 上 @Route 不被支持 | `unsupported class` 错误 | 移除 Fragment 上的 @Route |
| 14 | **ARouter kapt 在 app 模块崩溃** | `getTypeElement(...) returns null` | **移除 app 模块 kapt，改用显式 Intent** |
| 15 | **GitHub Actions 权限不足** | `Resource not accessible by integration` | **workflow 加 `permissions: contents: write`** |
| 16 | **find APK 找到仓库原有文件** | 上传了错误 APK | **限定 `find app/build/outputs/apk/debug/` 路径** |
| 17 | git push 500 错误 | 凭据问题 | 用 `gh auth login` + `gh auth setup-git` |

---

## 附录：完整命令速查表

```bash
# ===== 环境 =====
java -version                                          # 验证 JDK 17
/opt/gradle-8.7/bin/gradle --version                    # 验证 Gradle 8.7
/opt/android-sdk/build-tools/34.0.0/aapt2 version       # 验证 build-tools

# ===== SDK 下载（腾讯云镜像） =====
curl -sL -o build-tools.zip "https://mirrors.cloud.tencent.com/AndroidSDK/build-tools_r34-linux.zip"
curl -sL -o platform.zip "https://mirrors.cloud.tencent.com/AndroidSDK/platform-34-ext7_r03.zip"

# ===== 项目配置 =====
echo "sdk.dir=/opt/android-sdk" > local.properties

# ===== 本地编译 =====
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/opt/android-sdk
cd /workspace
/opt/gradle-8.7/bin/gradle :app:assembleDebug --no-daemon

# ===== APK 验证 =====
/opt/android-sdk/build-tools/34.0.0/aapt2 dump badging app-debug.apk
/opt/android-sdk/build-tools/34.0.0/aapt2 dump xmltree --file AndroidManifest.xml app-debug.apk

# ===== Git + GitHub CLI =====
echo "TOKEN" | gh auth login --with-token
gh auth setup-git
git push origin main

# ===== GitHub API（本项目核心操作） =====
# 获取文件内容
gh api repos/liliangxing/zhenai2/contents/path/to/file?ref=branch -q '.content' | base64 -d

# 更新文件
gh api repos/liliangxing/zhenai2/contents/path/to/file --method PUT \
  --field message="msg" \
  --field content="$(base64 -w0 /tmp/file)" \
  --field sha="文件SHA" \
  --field branch="分支名"

# 查看 Actions 状态
gh api "repos/liliangxing/zhenai2/actions/runs?per_page=3" \
  --jq '.workflow_runs[] | {id, status, conclusion}'

# ===== Release 操作 =====
gh api repos/liliangxing/zhenai2/releases/tags/v1.1.0 \
  --jq '.assets[] | {name, size, browser_download_url}'
```

---

*文档完。如果实操中遇到本文档没覆盖的问题，把命令输出和日志回传即可继续排查。*
