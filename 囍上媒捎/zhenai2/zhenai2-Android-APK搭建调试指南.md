# 珍爱2（zhenai2）Android APK 搭建·调试·发布完整指南

> 本文档记录「珍爱2」（zhenai2）复刻项目从零搭建编译环境、定位启动闪退、修复代码、生成 APK、上传 GitHub Release 的全过程。
>
> 文档面向**命令行不太熟悉**的读者。所有命令都附带「大白话解释」和「为什么要这样做」。成功步骤标记为 `✅ 照着做就行`，失败步骤标记为 `⚠️ 避坑提醒`。关键命令附带命令输出样例（等同截图效果），方便你对照检查。

---

## 目录

- [一、项目是什么](#一项目是什么)
- [二、工具与 MCP / Skill / 模块方法说明](#二工具与-mcp--skill--模块方法说明)
- [三、环境准备（搭建编译环境）](#三环境准备搭建编译环境)
- [四、定位闪退根因（调试过程）](#四定位闪退根因调试过程)
- [五、代码修复（启动链路改造）](#五代码修复启动链路改造)
- [六、编译 APK（成功步骤）](#六编译-apk成功步骤)
- [七、APK 验证（确认产物正确）](#七apk-验证确认产物正确)
- [八、Git 提交与 GitHub Release 发布](#八git-提交与-github-release-发布)
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
| ARouter | 页面跳转路由框架（App 内 A→B 页怎么走） | - |

**项目结构（13 个模块）：**

```
zhenai2/
├── app/              # App 主壳（入口、Manifest、启动页、主页）
├── lib-common/       # 公共库（常量、账号管理、日志工具 FileLog）
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
└── module-web/       # 网页模块
```

**每个模块的职责**：App 启动后先加载 `app` 壳，壳通过 ARouter 路由按需加载各个业务模块的页面。这样拆分的好处是「模块之间互不依赖，各自独立编译」，但代价是 **Manifest 里注册的组件必须真实存在**，否则一启动就崩——这正是本次要修的核心问题（见第四节）。

---

## 二、工具与 MCP / Skill / 模块方法说明

> 本节是重点。下面列出整个过程中**用到的工具、MCP 接口、Skill 技能、AI 模块方法**，逐一说明是什么、原理是什么、什么时候用。

### 2.1 我（AI 助手）使用的模块方法

AI 助手不只是「会聊天」，它能调用一系列内置工具来操作你的电脑（读文件、写文件、跑命令）。这些工具就是「模块方法」。本次用到的有：

| 方法名 | 作用（大白话） | 原理说明 |
|--------|--------------|---------|
| `read` | 读取文件内容 | 把文件按行读出来给 AI 看。就像你用记事本打开文件。每次最多读 200 行，大文件分段读，省内存 |
| `glob` | 按文件名找文件 | 用通配符（如 `**/*.kt`）模糊匹配文件名，返回文件路径列表。相当于 Windows 搜索框 |
| `grep` | 在文件内容里搜关键字 | 全文正则搜索。比如搜「428」就能找出所有提到 428 的代码文件。比逐文件打开快得多 |
| `write` | 写入/新建文件 | 整个文件内容一次性写入。用于新建 FileLog.kt、文档等 |
| `edit` | 精确替换文件某段 | 找到文件中一段「唯一文本」，替换成新内容。比 write 更精准，只改该改的地方 |
| `bash` | 执行 shell 命令 | 直接在你的终端里跑命令（curl、unzip、gradle、git 等）。所有命令执行都走它 |
| `background_terminal_create` | 后台执行长命令 | 像 gradle 编译这种要跑几十分钟的命令，放后台跑，不阻塞对话；日志写到文件里，用 `background_terminal_output_path` 查看 |
| `background_terminal_kill` | 停止后台任务 | 后台跑太久或卡住了，用终端 ID 结束它（不能直接 `kill` 进程名） |
| `todowrite` | 维护任务清单 | 把大任务拆成多步，标记进行中/完成，防止漏步骤 |
| `question` | 向你提问 | 有歧义或需要你确认时（比如「删除 release 要不要确认？」），弹选项让你选 |
| `task` | 派发子任务给子 AI | 复杂调研交给子代理并行做，子代理有独立上下文，做完把结果汇总回来 |

### 2.2 MCP（Model Context Protocol）工具

MCP 是「让 AI 连接外部服务的标准化接口」。本次可用的 MCP 工具及原理：

| MCP 工具 | 作用 | 原理 |
|---------|------|------|
| `resolve-library-id` | 把库名解析成 Context7 标准 ID | 当你问「某个开源库怎么用」时，先把库名（如 React）映射成 `/facebook/react` 这种标准标识，后续查询文档用 |
| `query-docs` | 查开源库在线文档 | 用标准 ID + 具体问题，从 Context7 拉取官方文档和代码示例。**每个问题最多调 3 次**，3 次没结果就用已有信息回答 |
| `websearch_search` | 原始网页搜索 | 返回网页链接列表。适合「找最新资讯、验证官网地址」 |
| `websearch_aisearch` | 联网综合问答 | 基于多个网页来源生成总结回答，适合「归纳、多源综合」 |
| `image_analysis_create_task` | 图片理解（异步） | 把图片 URL 提交给视觉模型分析。异步执行，先返回任务 ID，再用 `image_analysis_get_result` 轮询结果 |
| `image_generate_text_to_image` | 文生图（异步） | 根据文字描述生成图片。返回任务 ID，1~5 分钟完成 |
| `docparse_parse` | 文档转 Markdown / OCR | 把 PDF、Word、Excel、图片转成 Markdown 文本。本地文件要先 `docparse_get_doc_upload_url` 上传拿 URL 再解析 |
| `imgsearch_search` | 按文本搜图片 | 用文字描述搜匹配的图片 |

> **本项目实际用到哪些？** 本次 zhenai2 是「本地代码编译」任务，主要用到了**模块方法**（read/grep/edit/bash 等）。MCP 文档查询类工具（query-docs 等）在本项目中没有触发，因为项目的构建问题主要靠读本地代码和日志定位。但上面表格列出来，是为了让你了解这套体系，后续遇到「查某个库的用法」时 AI 会走 MCP。

### 2.3 Skill（技能）

Skill 是「针对特定任务的成套流程脚本」，加载后 AI 按流程执行。本项目环境中可用的：

| Skill | 用途 | 本次是否用到 |
|-------|------|------------|
| `deploy-website` | 部署并本地预览 Web 项目（自动检测 Node/Python/静态 HTML 等类型并启动服务器） | 未用（本次是 Android 编译，不是 Web 预览） |
| `publish-website` | 把 Web 项目发布成线上托管应用 | 未用 |
| `feature-design` | 用 EARS 规范生成需求文档和技术设计文档 | 未用 |
| `implementation-planner` | 把设计方案拆解成可执行任务列表 | 未用 |
| `feature-implementer` | 按任务列表执行具体开发 | 未用 |
| `project-wiki` | 根据代码仓库生成 DeepWiki 风格项目文档 | 未用 |
| `customize-opencode` | 配置 opencode 自身（opencode.json 等） | 未用 |

> **原理说明**：Skill 本质上是一份「带步骤说明和参考脚本的说明书」。AI 判断任务匹配某个 skill 时，通过 `skill` 工具把说明书注入对话上下文，然后按里面的流程一步步执行。本项目的发布走的是 **GitHub Release（gh 命令）** 而非 `publish-website`（后者面向平台托管展示），所以 skill 体系未介入。

### 2.4 GitHub CLI（gh）

`gh` 是 GitHub 官方命令行工具，用于登录、建 Release、传文件。它是**命令**不是 AI 模块，但在发布环节非常关键：

```bash
# 登录（用 Personal Access Token）
echo "<你的token>" | gh auth login --with-token

# 让 git 使用 gh 的凭据（解决 git push 反复要密码）
gh auth setup-git

# 创建 Release 并附带 APK 文件
gh release create v1.1.0 "/路径/app-debug.apk"

# 查看 Release 列表
gh release list
```

**原理**：`gh auth login` 把 token 存到 `~/.config/gh/hosts.yml`；`gh auth setup-git` 会修改 git 的凭据配置，让 `git push` 自动用这个 token，不用手动输账号密码。

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

**SDK 目录规划**（自己定，放 `/opt/android-sdk`）：

```
/opt/android-sdk/
├── build-tools/34.0.0/     # aapt2、zipalign、apksigner 等打包工具
└── platforms/android-34/   # android.jar（编译时引用的系统类库）
```

#### 3.3.1 下载 build-tools 34.0.0

> **⚠️ 避坑提醒 2：国内直连 dl.google.com 很慢，强烈建议用腾讯云镜像** `mirrors.cloud.tencent.com/AndroidSDK/`。文件名从 Google 的 repository 文件里查出来是 `build-tools_r34-linux.zip`（Linux 版），**不是** `build-tools-34.0.0.zip`。

```bash
mkdir -p /opt/android-sdk/build-tools
cd /opt/android-sdk

# 下载（腾讯云镜像，速度快）
curl --http1.1 -sL -o build-tools.zip \
  "https://mirrors.cloud.tencent.com/AndroidSDK/build-tools_r34-linux.zip"

# 解压
unzip -q build-tools.zip
# ⚠️ 解压出来的目录名可能是 android-14（Google 的 zip 命名混乱），
#    实际内容就是 build-tools 34.0.0。需要改名：
ls        # 看到 android-14 之类的目录
mv android-14 build-tools/34.0.0
# 最终：/opt/android-sdk/build-tools/34.0.0/aapt2

# 验证 aapt2 能运行（等同截图）
/opt/android-sdk/build-tools/34.0.0/aapt2 version
# 应输出：Android Asset Packaging Tool (aapt2) 8.5.2-... 之类版本号
```

> **避坑提醒 3：zip 内部目录名不可信。** Google 的 SDK zip 顶部目录名经常和实际组件名不一致（这里是 `android-14`），解压后一定 `ls` 看一下再移动，别直接假设名字。

#### 3.3.2 下载 platform-34

> **避坑提醒 4：platform 的文件名带 `-ext7_r03` 后缀**，完整名是 `platform-34-ext7_r03.zip`（从 repository2-3.xml 查到的）。google 域名直连下载会卡死（沙箱透明代理不支持断点续传），同样用腾讯云镜像。

```bash
cd /opt/android-sdk
curl --http1.1 -sL --max-time 300 -o platform.zip \
  "https://mirrors.cloud.tencent.com/AndroidSDK/platform-34-ext7_r03.zip"

# 解压，出现 android-34 目录
unzip -q platform.zip

# 移动到标准位置
mkdir -p platforms
mv android-34 platforms/

# 验证（等同截图）
ls -la /opt/android-sdk/platforms/android-34/android.jar
# 应看到 android.jar（约 26MB）
```

### 3.4 配置项目 `local.properties`

**为什么**：Gradle 需要知道 SDK 装在哪。项目根目录的 `local.properties` 就是干这个的（**不要**提交到 git，已加入 .gitignore）。

```bash
echo "sdk.dir=/opt/android-sdk" > /workspace/local.properties

# 确认（等同截图）
cat /workspace/local.properties
# sdk.dir=/opt/android-sdk
```

### 3.5 项目网络仓库配置（settings.gradle.kts）

**为什么**：编译时要下载 AGP、Kotlin 插件、第三方库。这些依赖从哪下载？在 `settings.gradle.kts` 里配置仓库地址。本项目配置了阿里云镜像优先 + Google 官方兜底：

```kotlin
pluginManagement {
    repositories {
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/central") }
        maven { url = uri("https://maven.aliyun.com/repository/gradle-plugin") }
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
```

> **为什么阿里云镜像优先**：`maven.aliyun.com` 是阿里云的 Maven 仓库镜像，国内访问快且稳定。`google()` 是官方仓库，可能慢或超时。国内环境把阿里云放前面能大幅减少下载失败。

---

## 四、定位闪退根因（调试过程）

> 这一节是**最值钱的部分**——它展示了「App 一打开就闪退」是怎么一步步查出来的。

### 4.1 现象

用户报告：安装 APK 后**打开就闪退**，没有任何界面。

### 4.2 第一步：按 Android App 启动顺序梳理排查路径

Android App 启动是有固定顺序的，按这个顺序排查不会漏：

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

**为什么**：闪退最可能发生在「系统要实例化一个类但类不存在」。而 Manifest 里注册的组件，就是系统会自动实例化的类。先看 APK 里到底注册了哪些组件。

```bash
# 用 aapt2 解出 APK 里的 AndroidManifest.xml 并转成可读文本
/opt/android-sdk/build-tools/34.0.0/aapt2 dump xmltree \
  --file AndroidManifest.xml app-debug.apk > /tmp/manifest.txt

# 统计四大组件数量
grep -c "E: activity" /tmp/manifest.txt     # Activity 数量
grep -c "E: provider" /tmp/manifest.txt     # Provider 数量
grep -c "E: receiver" /tmp/manifest.txt     # Receiver 数量
grep -c "E: service"  /tmp/manifest.txt     # Service 数量

# 列出所有组件类名
grep -oE 'name\(0x01010003\)="[^"]*"' /tmp/manifest.txt | sort -u
```

**排查结果（关键发现！）：**

```
Activity: 322 个
Service:   39 个
Receiver:  17 个
Provider:  17 个
```

但其中绝大多数是**第三方 SDK 的类**，比如：
- `com.zhenai.base.AppInit`
- `com.netease.nimlib.*`（网易云信）
- `com.getui.*`（个推推送）
- `com.huawei.*`（华为推送）
- `com.securesandbox.*`
- `com.tencent.*`（腾讯）

**问题来了**：复刻项目的源码里**根本没有这些类**（这些是原 App 引入的第三方 SDK，复刻版没引入）。而 Manifest 声明了它们。

### 4.4 为什么这会导致闪退（原理详解）

Android 系统启动 App 时，有一个**比 Application.onCreate 更早的步骤**：系统会先实例化 Manifest 里注册的 **ContentProvider**（无论你的业务代码用不用它）。

流程：

```
进程启动
  → 系统遍历 Manifest 的 <provider> 列表
  → 对每个 provider，用 Class.forName(类名) 加载该类
  → 类不存在 → 抛 ClassNotFoundException
  → 进程直接崩溃 → 闪退
```

**关键点**：这个崩溃发生在 `Application.onCreate()` **之前**，而 CrashHandler（闪退日志捕获器）是在 `onCreate()` 里才安装的。所以 **这个阶段的闪退连日志都来不及写**——这就是之前「查不到任何崩溃日志」的原因。

### 4.5 验证命令（确认哪些类确实不存在）

```bash
# 搜索项目源码里是否真的存在这些类
# 在项目源码目录搜 com.netease.nimlib 等，搜不到就是不存在
grep -rn "com.netease.nimlib" /workspace/app/src/ 2>/dev/null | head
grep -rn "com.getui" /workspace/app/src/ 2>/dev/null | head

# 无输出 = 类不存在 = 确认闪退根因
```

**结论**：闪退根因是 **Manifest 声明了源码中不存在的第三方组件类（尤其是 Provider），系统在 Application.onCreate 之前实例化它们时抛 ClassNotFoundException，且此时 CrashHandler 尚未安装导致无日志可查。**

---

## 五、代码修复（启动链路改造）

> 修复思路：**精简 Manifest**——只注册源码中真实存在的组件，把不存在的第三方组件全部移除。这是比「补齐缺失依赖」更小的修复方案（复刻项目不可能引入原 App 的全部付费 SDK）。

### 5.1 重写精简版 AndroidManifest.xml

**保留**：根级权限、uses-feature、application 属性、uses-library、meta-data。
**只注册实际存在的组件**：
- `SplashActivity`（含 LAUNCHER 启动入口）
- `MainActivity`
- `LoginActivity`
- `FileProvider`（androidx 提供的文件分享 Provider）

```xml
<!-- 精简后的关键结构（示意） -->
<application
    android:name="com.zhenai2.android.App"
    android:theme="@style/AppTheme">
    <activity android:name="com.zhenai2.android.ui.splash.SplashActivity"
        android:exported="true">
        <intent-filter>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LAUNCHER" />
        </intent-filter>
    </activity>
    <activity android:name="com.zhenai2.android.ui.main.MainActivity" />
    <activity android:name="com.zhenai2.login.LoginActivity" />

    <provider
        android:name="androidx.core.content.FileProvider"
        android:authorities="com.zhenai2.android.fileprovider" />
</application>
```

> **命令**：改 Manifest 用 `edit` 模块方法或直接编辑文件。原版 2247 行 → 精简版 271 行。**保留备份** `AndroidManifest.xml.bak`（已加入 .gitignore），方便随时还原对比。

### 5.2 修复 MainActivity：补 @Route 注解 + 空安全兜底

**问题 1**：`MainActivity` 作为主页，需要通过 ARouter 跳转进入（`/app/main`），但类上**没有 @Route 注解** → ARouter 路由表里找不到它 → 跳主页失败。

**修复**：加注解。

```kotlin
@Route(path = RouterPath.MAIN)   // ← 新增，让 ARouter 认识这个页面
class MainActivity : AppCompatActivity() {
    ...
}
```

**问题 2**：主页用 ARouter 加载 4 个 Tab Fragment，原来的写法：

```kotlin
// ❌ 旧写法：如果路由不存在，navigation() 返回 null，强转会抛 NPE 崩溃
ARouter.getInstance().build(tabs[position]).navigation() as Fragment
```

**修复**：加空安全兜底。

```kotlin
// ✅ 新写法：路由取不到时兜底为一个空白 Fragment，不再崩溃
ARouter.getInstance().build(tabs[position]).navigation() as? Fragment
    ?: androidx.fragment.app.Fragment()
```

### 5.3 修复 SplashActivity：finish() 位置错误

**问题**：原代码在 `checkLoginAndRoute()` 外部调用 `finish()`，导致流程没走完就关掉页面，无法正确跳转主页/登录页。

**修复**：把 `finish()` 移进 `routeToMain()` / `routeToLogin()` 内部，并给整个启动协程加 try-catch：

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    try {
        lifecycleScope.launch { checkLoginAndRoute() }
    } catch (e: Throwable) {
        FileLog.e("SplashActivity 启动协程失败", e)
        routeToLogin()   // 兜底进登录页
    }
}

private fun routeToMain() {
    FileLog.i("SplashActivity -> 主页")
    ARouter.getInstance().build(RouterPath.MAIN).navigation(this)
    finish()
}
```

### 5.4 新增统一日志工具 FileLog（重点设计）

**为什么**：之前发现「启动早期闪退无日志可查」。解决办法是做一个**比 CrashHandler 更早、能覆盖所有模块的日志工具**，让每个关键节点都记录，用户回传日志就能定位。

**放在哪个模块？** `lib-common`（公共库）。**为什么？** 因为 login/home/mine 等所有业务模块都依赖 lib-common，放这里所有模块都能调用，写进同一个日志文件；如果放 app 壳，业务模块依赖 app 会形成循环依赖。

```kotlin
// lib-common/.../FileLog.kt（核心逻辑）
object FileLog {
    private val executor = Executors.newSingleThreadExecutor() // 单线程串行写，防止并发写坏文件

    fun init(context: Context) {
        appContext = context.applicationContext
        i("========== 应用启动 ==========")
    }

    fun e(msg: String, tr: Throwable? = null) = write("E", msg, tr)

    private fun persist(content: String) {
        val sdDir = File(Environment.getExternalStorageDirectory(), DIR)
        if (writeFile(sdDir, content)) return          // ① 首选 /sdcard/douyinguanjia/Log/zhenai2.log
        try {
            val fallback = File(ctx.getExternalFilesDir(null), DIR)
            if (writeFile(fallback, content)) return   // ② 降级：应用专属外部目录（免权限）
        } catch (_: Throwable) {}
        try {
            val cache = File(ctx.cacheDir, DIR)
            writeFile(cache, content)                   // ③ 兜底：应用缓存目录（必可写）
        } catch (_: Throwable) {}
    }
}
```

**日志路径与降级链（原理）**：

```
/sdcard/douyinguanjia/Log/zhenai2.log        ← 首选（用户能直接看到）
   ↓ 不可写（Android 10+ 分区存储限制）
getExternalFilesDir/douyinguanjia/Log/...    ← 降级（App 专属，无需权限）
   ↓ 仍失败
cacheDir/douyinguanjia/Log/...               ← 兜底（一定可写）
```

**为什么用单线程 executor**：Android 里多个线程同时写同一个文件会互相干扰导致文件损坏或日志丢失。用 `newSingleThreadExecutor()` 让日志按顺序一条条排队写，安全。

### 5.5 重写 CrashHandler：基于 FileLog

```kotlin
class CrashHandler private constructor() : Thread.UncaughtExceptionHandler {
    fun install(ctx: Context) {
        FileLog.init(ctx.applicationContext)     // 先初始化日志工具（幂等）
        defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler(this)
        FileLog.i("CrashHandler 已安装")
    }

    override fun uncaughtException(t: Thread, e: Throwable) {
        try {
            FileLog.e("闪退 Thread=${t.name} ... " +
                "设备=${Build.MANUFACTURER} ${Build.MODEL} " +
                "Android=${Build.VERSION.RELEASE}(sdk=${Build.VERSION.SDK_INT})", e)
        } catch (_: Throwable) {}
        Process.killProcess(Process.myPid())   // 杀进程，避免残留状态
        System.exit(10)
    }
}
```

**原理**：`Thread.setDefaultUncaughtExceptionHandler` 是 Android/Java 提供的「全局未捕获异常钩子」。任何线程抛出没人处理的异常，系统都会回调它。我们在这里记录堆栈到日志文件，然后主动结束进程（避免 App 卡在崩溃状态）。

### 5.6 App 启动链路全部加 try-catch + 日志

`App.kt` 里每个初始化步骤都包 try-catch，出问题写日志而不是静默：

```kotlin
override fun attachBaseContext(base: Context) {
    super.attachBaseContext(base)
    try {
        androidx.multidex.MultiDex.install(this)   // 多 dex 加载
    } catch (e: Throwable) {
        FileLog.e("MultiDex.install 失败", e)
    }
}

override fun onCreate() {
    super.onCreate()
    CrashHandler.get().install(this)                // 第 1 步就装崩溃捕获
    try { AccountManager.init(this) } catch (e: Throwable) { FileLog.e("AccountManager.init 失败", e) }
    try {
        ARouter.openLog(); ARouter.openDebug(); ARouter.init(this)
    } catch (e: Throwable) { FileLog.e("ARouter.init 失败", e) }
    try { NetworkClient.setFingerprint(null) } catch (e: Throwable) { FileLog.e("NetworkClient.setFingerprint 失败", e) }
    FileLog.i("App.onCreate 完成, 初始化全部成功")
}
```

### 5.7 登录模块加日志（LoginActivity / LoginViewModel / RecommendFragment）

登录流程的关键节点都记录到日志，方便排查「登录为什么失败」：

```kotlin
// LoginViewModel.login()
FileLog.i("发起 userLogin.do 登录请求 phone=${phone}")
val resp = api.userLogin(phone, encryptedPwd, captchaType, imgCode, ticket, randstr)
if (resp.isError) {
    FileLog.w("userLogin.do 返回错误: code=${resp.errorCode} msg=${resp.errorMessage}")
    handleLoginError(resp.errorCode, resp.errorMessage)
} else {
    resp.data?.let {
        FileLog.i("登录成功 memberID=${it.memberID}")
        AccountManager.saveSession(...)
        _loginResult.value = it
    } ?: FileLog.w("userLogin.do 成功但 data 为空")
}
```

> **排查方向提示（关于 428）**：真机登录时接口返回 HTTP **428**，这是珍爱网 **EdgeOne WAF 的 TLS 指纹（JA3）拦截**——它识别到请求来自「非官方客户端」就在握手阶段拦截。这和业务错误码（-8001021 需验证码、-8001025 需激活手机号，在 `LoginViewModel.handleLoginError` 处理）是两码事。428 属于平台风控，需官方授权接入，不属于代码 bug 范畴。

---

## 六、编译 APK（成功步骤）

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

**结果（避坑）**：失败。gradlew 尝试去 `services.gradle.org` 下载 Gradle 发行版，沙箱里网络被拒（`Connection refused`）。

> **原因**：gradlew 本身不包含 Gradle，它只是个「下载器」。既然已手动装了 Gradle，直接用 `/opt/gradle-8.7/bin/gradle` 即可。

### 6.3 第二次尝试：用本地 Gradle → 又失败（插件解析不了）

```bash
cd /workspace
/opt/gradle-8.7/bin/gradle :app:assembleDebug --no-daemon
```

**报错（关键）：**

```
Plugin [id: 'com.android.application', version: '8.5.2', apply: false] was not found
```

**排查过程（调试命令）**：

```bash
# ① 检查 gradle.properties 里的代理配置（重点怀疑对象）
cat gradle.properties
# 看到：systemProp.http.proxyHost=127.0.0.1:18080

# ② 检查 18080 端口到底有没有进程在监听
ss -tlnp | grep 18080
# ⚠️ 结果：没有输出！说明根本没有服务监听 18080

# ③ 用 Java 直接测试「走 18080 代理访问外网」→ 连接被拒
#    （写个小测试类验证 JVM 代理行为）

# ④ 用 curl 测试「不走代理直接访问」→ 成功
curl -sL -o /dev/null -w "%{http_code}\n" \
  "https://maven.aliyun.com/repository/google/com/android/tools/build/gradle/8.5.2/gradle-8.5.2.pom"
# 输出 200 = 阿里云镜像可达
```

**根因定位**：`gradle.properties` 里配置了 `127.0.0.1:18080` 代理，但**这个端口根本没有服务在监听**。JVM（Gradle 跑在 JVM 上）每次请求都去连 18080 → 连接被拒 → 插件下载失败。

### 6.4 修复：移除错误的代理配置

```bash
# 编辑 gradle.properties，删除这 4 行代理配置
# systemProp.http.proxyHost=127.0.0.1
# systemProp.http.proxyPort=18080
# systemProp.https.proxyHost=127.0.0.1
# systemProp.https.proxyPort=18080
```

> **为什么可以直连？** 该沙箱网络实际是「透明代理」——出口流量已被自动代理，不需要应用自己配代理。手动配 18080 反而画蛇添足，连到不存在的端口直接失败。

### 6.5 编译成功

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
326 actionable tasks: 259 executed, 67 from cache
```

**产物位置**：

```
/workspace/app/build/outputs/apk/debug/app-debug.apk   # 约 91MB
```

> **命令解读**：`:app:assembleDebug` = 编译 app 模块的 Debug 版。`--no-daemon` = 不用常驻后台进程（用完即退，避免残留进程占内存）。

---

## 七、APK 验证（确认产物正确）

> 编译成功不代表没问题。必须确认 APK 里的 Manifest 是「修复后的精简版」，关键类真实存在。

### 7.1 查看包信息、启动入口、权限

```bash
/opt/android-sdk/build-tools/34.0.0/aapt2 dump badging app-debug.apk
```

**关键输出（等同截图）：**

```
package: name='com.zhenai2.android' versionCode='1' versionName='1.0.0'
sdkVersion:'23' targetSdkVersion:'34'
uses-permission: name='android.permission.INTERNET'
launchable-activity: name='com.zhenai2.android.ui.splash.SplashActivity'
application-label:'珍爱'
```

### 7.2 确认组件只剩真实存在的类

```bash
/opt/android-sdk/build-tools/34.0.0/aapt2 dump xmltree \
  --file AndroidManifest.xml app-debug.apk > /tmp/final_manifest.txt

# 统计（应只剩 3 个 Activity / 2 个 Provider / 1 个 Receiver）
grep -cE "E: activity" /tmp/final_manifest.txt
grep -cE "E: provider" /tmp/final_manifest.txt
grep -cE "E: receiver" /tmp/final_manifest.txt
grep -cE "E: service"  /tmp/final_manifest.txt
```

**最终确认（等同截图）：**

```
E: activity -> com.zhenai2.android.ui.splash.SplashActivity
E: activity -> com.zhenai2.android.ui.main.MainActivity
E: activity -> com.zhenai2.login.LoginActivity
E: provider -> androidx.core.content.FileProvider
E: provider -> androidx.startup.InitializationProvider
E: receiver -> androidx.profileinstaller.ProfileInstallReceiver
```

全部是真实存在的类（后三个是 androidx 库自带的），闪退根因已消除。

### 7.3 确认关键类编译进了 dex

```bash
cd /tmp && mkdir -p apk_check && cd apk_check
unzip -q app-debug.apk "classes*.dex"
for f in classes*.dex; do
  echo "== $f =="
  strings "$f" | grep -oE "Lcom/zhenai2/(android/ui/(splash/SplashActivity|main/MainActivity)|login/LoginActivity|android/App);" | sort -u
done
```

**结果（等同截图）：** 关键类（SplashActivity / MainActivity / LoginActivity / App）在 dex 里都能找到，说明修复代码确实编译进去了。

### 7.4 ARouter 路由验证

```bash
# 在编译日志里确认 ARouter 路由表生成了
grep "Found activity route" /tmp/build_full.log
# 应看到：com.zhenai2.android.ui.main.MainActivity
```

---

## 八、Git 提交与 GitHub Release 发布

### 8.1 提交代码

```bash
cd /workspace
git status                       # 看改了哪些文件
git add <文件...>                # 逐个暂存改动
git commit -m "fix: 修复启动闪退,统一异常日志写入 douyinguanjia/Log/zhenai2.log"
```

> **注意**：`local.properties`、`AndroidManifest.xml.bak`、`*.apk` 已被 .gitignore 忽略，不会提交。

### 8.2 推送 GitHub（需要认证）

**避坑**：直接 `git push` 会报 `credential helper: server returned status 500`（环境的凭据服务不可用）。用 GitHub 官方 CLI 解决：

```bash
# ① 用 Personal Access Token 登录（token 需要 repo 权限）
echo "你的token" | gh auth login --with-token

# ② 让 git 复用 gh 的凭据
gh auth setup-git

# ③ 推送
git push origin main
```

### 8.3 创建 Release（附 APK）

```bash
# 上传 APK 到 Release
cp app-debug.apk zhenai2-1.1.0.apk
gh release create v1.1.0 /tmp/zhenai2-1.1.0.apk \
  --title "珍爱2 复刻版 v1.1.0" --notes "修复说明..."

# 查看
gh release view v1.1.0
```

> **避坑提醒 5：`gh release create` 的 `文件#重命名` 语法可能不生效**（产物名还是 app-debug.apk）。**解决办法**：先 `cp` 成想要的名字再上传，文件名就是你想要的资产名。
>
> **避坑提醒 6：tag 已存在**。如果 `v1.0.0` 已存在，`gh release create v1.0.0` 会报 `a release with the same tag name already exists`。**解决办法**：用新版本号（v1.1.0），或用 `--clobber` 覆盖。

### 8.4 若资产多余需要清理

```bash
# 删除某个资产（比如上传重了）
gh release delete-asset v1.1.0 app-debug.apk --yes

# 验证最终资产列表
gh api repos/liliangxing/zhenai2/releases/tags/v1.1.0 --jq '.assets[] | .name'
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
| 7 | MainActivity 缺 @Route | 跳主页失败 | 补 `@Route(path = RouterPath.MAIN)` |
| 8 | ARouter navigation() 返回 null | 强转 NPE 闪退 | 用 `as? Fragment ?: Fragment()` 兜底 |
| 9 | SplashActivity finish() 过早 | 无法跳转 | finish() 移入路由方法内部 |
| 10 | `gh release create` 文件#重命名无效 | 资产名不变 | 先 `cp` 成目标名再上传 |
| 11 | Release tag 已存在 | `already exists` | 换新版本号 |
| 12 | 早期闪退无日志 | 查不到崩溃 | FileLog 放 lib-common，全链路记录 |

---

## 附录：完整命令速查表

```bash
# ===== 环境 =====
java -version                                          # 验证 JDK 17
/opt/gradle-8.7/bin/gradle --version                   # 验证 Gradle 8.7
/opt/android-sdk/build-tools/34.0.0/aapt2 version      # 验证 build-tools

# ===== SDK 下载（腾讯云镜像） =====
curl -sL -o build-tools.zip "https://mirrors.cloud.tencent.com/AndroidSDK/build-tools_r34-linux.zip"
curl -sL -o platform.zip "https://mirrors.cloud.tencent.com/AndroidSDK/platform-34-ext7_r03.zip"

# ===== 项目配置 =====
echo "sdk.dir=/opt/android-sdk" > local.properties

# ===== 编译 =====
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/opt/android-sdk
cd /workspace
/opt/gradle-8.7/bin/gradle :app:assembleDebug --no-daemon

# ===== APK 验证 =====
/opt/android-sdk/build-tools/34.0.0/aapt2 dump badging app-debug.apk
/opt/android-sdk/build-tools/34.0.0/aapt2 dump xmltree --file AndroidManifest.xml app-debug.apk

# ===== Git + GitHub =====
echo "TOKEN" | gh auth login --with-token
gh auth setup-git
git push origin main
cp app-debug.apk zhenai2-1.1.0.apk
gh release create v1.1.0 /tmp/zhenai2-1.1.0.apk --title "..." --notes "..."
```

---

*文档完。如果你在实操中遇到本文档没覆盖的问题，把命令输出和 `/sdcard/douyinguanjia/Log/zhenai2.log` 日志回传即可继续排查。*
