# MonkeyCode Android APK 多变体一键构建 搭建指南

> **目标**：基于 MonkeyCode 仓库 commit `1a60b21a` 的 Android WebView 工程，自动生成三个独立 APK——`MonkeyCode.apk`（包名 `com.monkeyCode.ai`）、`Monkey2.apk`（包名 `com.monkeyCode.ai2`）、`Monkey3.apk`（包名 `com.monkeyCode.ai3`），做成一键构建工具，并发布到 GitHub Release。
>
> 本文档用大白话写给"技术一般、对命令不熟悉"的人看。每一步都有完整命令、有"为什么这么做"的解释、有"你应该看到的结果"、有踩坑提醒。照着从上到下复制粘贴就能做出来。

---

## 目录

- [一、这次到底要做成什么事](#一这次到底要做成什么事)
- [二、需要提前准备什么](#二需要提前准备什么)
- [三、大白话背景知识（不懂也能照做）](#三大白话背景知识不懂也能照做)
- [四、第一步：检查电脑里有什么工具](#四第一步检查电脑里有什么工具)
- [五、第二步：把代码仓库下载到本地](#五第二步把代码仓库下载到本地)
- [六、第三步：摸清楚工程结构](#六第三步摸清楚工程结构)
- [七、第四步：安装 Java 17](#七第四步安装-java-17)
- [八、第五步：安装 Android SDK（最容易踩坑的一步）](#八第五步安装-android-sdk最容易踩坑的一步)
- [九、第六步：编写自动化构建工具](#九第六步编写自动化构建工具)
- [十、第七步：一键构建三个 APK](#十第七步一键构建三个-apk)
- [十一、第八步：验证 APK 是否正确](#十一步第八步验证-apk-是否正确)
- [十二、第九步：把工具提交到代码仓库](#十二第九步把工具提交到代码仓库)
- [十三、第十步：发布 APK 到 GitHub Release](#十三第十步发布-apk-到-github-release)
- [十四、排查错误工具箱（遇到问题先来这里）](#十四排查错误工具箱遇到问题先来这里)
- [十五、踩过的坑完整记录](#十五踩过的坑完整记录)
- [十六、常见问题 FAQ](#十六常见问题-faq)
- [十七、本指南用到的工具逐个说明](#十七本指南用到的工具逐个说明)
- [十八、完整命令速查表（从头到尾复制粘贴版）](#十八完整命令速查表从头到尾复制粘贴版)

---

## 一、这次到底要做成什么事

MonkeyCode 是一个 AI 开发平台，有一个 Android 手机 App（APK 文件），本质上是一个 WebView 壳子——打开 App 就是访问 `monkeycode-ai.com/console/` 网页，但额外加了导出消息、捕获 API 等功能。

现在要做的是：**基于这个 App 的源码，"克隆"出两个新 App**，它们功能完全一样，但包名和应用名不同，这样可以在同一台手机上同时安装三个互不冲突的实例：

| APK 文件名 | 包名（package） | 应用名（label） | 说明 |
|-----------|----------------|----------------|------|
| `MonkeyCode.apk` | `com.monkeyCode.ai` | MonkeyCode | 原始版本 |
| `Monkey2.apk` | `com.monkeyCode.ai2` | Monkey2 | 新克隆版本 1 |
| `Monkey3.apk` | `com.monkeyCode.ai3` | Monkey3 | 新克隆版本 2 |

> **为什么包名不同就能同时安装？** Android 系统用"包名"来区分 App。两个 App 包名一样，系统认为它们是同一个，后装的会覆盖先装的。包名不同，系统就当作三个独立 App，可以并排存在。

除此之外，还要做一个**自动化工具**（一键脚本），以后想生成更多变体时跑一条命令就行，不用手动改文件。

---

## 二、需要提前准备什么

| 东西 | 说明 | 怎么检查有没有 |
|------|------|--------------|
| 一台 Linux 电脑/服务器 | 本指南所有命令在 Linux（Ubuntu）下执行。Windows 请装 WSL | `uname -a` |
| root 权限 | 安装软件需要。本环境直接就是 root | `whoami` 输出 `root` |
| git | 下载代码、提交代码用 | `git --version` |
| curl | 下载文件、调用 GitHub API 用 | `curl --version` |
| GitHub Personal Access Token | 有仓库写权限的 token | 自己去 GitHub Settings 生成 |
| 约 500MB 磁盘空间 | Android SDK 和编译产物要用 | `df -h` |
| 能上网 | 要从 Google 下载 Android SDK | `ping -c 1 google.com` |

> **关于 GitHub Token**：去 GitHub → 右上角头像 → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token，勾选 `repo` 权限。生成后是一串 `ghp_` 开头的字符串，后面命令里用 `你的TOKEN` 代替。

---

## 三、大白话背景知识（不懂也能照做）

### 3.1 APK 是什么

APK 就是 Android 手机的"安装包"，类似 Windows 的 `.exe`。你把 `.apk` 文件传到手机上点开就能装。

### 3.2 一个 APK 的"身份证"由什么决定

一个 APK 有三样关键身份信息，改了这三样，系统就认为它是不同的 App：

1. **包名（package）**：写在 `AndroidManifest.xml` 文件里的 `package="com.monkeyCode.ai"`。这是最重要的，Android 系统靠它区分 App。
2. **应用名（label）**：手机桌面上显示的名字，比如"MonkeyCode"。写在两个地方：`AndroidManifest.xml` 的 `android:label` 和 `strings.xml` 的 `app_name`。
3. **Java 包路径**：源代码文件 `MainActivity.java` 第一行 `package com.monkeyCode.ai;`，以及文件所在的文件夹路径 `com/monkeyCode/ai/`。这个要和包名对应。

### 3.3 这个工程怎么编译的（不 Gradle）

大多数 Android 工程用 Gradle 编译，但这个工程特别精简——它用三个底层工具直接编译，不用 Gradle：

| 工具 | 干什么用的 | 大白话比喻 |
|------|-----------|-----------|
| `javac` | 把 `.java` 源码编译成 `.class` 字节码 | 把中文翻译成"半成品" |
| `aapt2` | 处理资源文件（图标、布局、清单等），打成资源包 | 把"配料"装进盒子 |
| `d8` | 把 `.class` 转成 Android 能跑的 `.dex` | 把"半成品"加工成"成品" |
| `apksigner` | 给 APK 签名（不签名装不上） | 给产品盖"合格章" |

流程是：`javac → aapt2 → d8 → 组装 → apksigner → 完成`

### 3.4 为什么需要 Android SDK

上面那些工具（`aapt2`、`d8`、`apksigner`）不是系统自带的，它们是 Android SDK（开发工具包）的一部分。另外编译时还需要一个 `android.jar` 文件——这是 Android 系统的"接口定义库"，告诉编译器"Android 有哪些功能可以用"。

### 3.5 为什么需要 Java 17

原始的 `build.sh` 脚本里写死了 `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64`。虽然源码用 Java 11 语法编译（`-source 11 -target 11`），但运行编译工具需要 Java 17 环境。

---

## 四、第一步：检查电脑里有什么工具

先看看电脑里已经装了什么，心里有个数。

```bash
echo "=== git ===" && git --version
echo "=== java ===" && java -version 2>&1
echo "=== gradle ===" && which gradle && gradle --version 2>&1 | head -5
echo "=== android ===" && echo $ANDROID_HOME
echo "=== sdkmanager ===" && which sdkmanager 2>&1
echo "=== node ===" && node --version 2>&1
echo "=== python ===" && python3 --version 2>&1
```

**你应该看到的结果**（如果你是全新环境）：

```
=== git ===
git version 2.34.1
=== java ===
openjdk version "11.0.31" 2026-04-21
...
=== gradle ===
（空，说明没装——没关系，我们不需要它）
=== android ===
（空，说明没设置——后面会装）
=== sdkmanager ===
（空，说明没装——后面会装）
=== node ===
v22.23.1
=== python ===
Python 3.10.12
```

> **为什么先检查？** 知道缺什么才知道接下来装什么。这里关键发现是：有 git、有 Java 11、有 Python 3，但**没有 Android SDK，也没有 Gradle**。好消息是这个工程不用 Gradle，所以只需要装 Android SDK。

> **避坑**：Java 版本可能不是 17。原始 `build.sh` 要求 Java 17，所以后面要装。别用 Java 11 去跑，`aapt2` 和 `d8` 这些工具需要 Java 17 运行环境。

---

## 五、第二步：把代码仓库下载到本地

### 5.1 用 git clone 下载

```bash
cd /data/user/work
git clone https://你的TOKEN@github.com/liliangxing/MonkeyCode.git
```

> **为什么 URL 里要放 Token？** 因为这是私有操作（需要写权限）。把 token 放在 `https://` 和 `@github.com` 之间，git 就会用这个身份去访问。格式是 `https://TOKEN@github.com/用户名/仓库.git`。

**你应该看到的结果**：

```
Cloning into 'MonkeyCode'...
```

### 5.2 确认下载成功，看看最近的提交

```bash
cd MonkeyCode
git log --oneline -5
```

**你应该看到的结果**：

```
1a60b21a feat(android-apk): FAB 导出按钮显示剩余额度，低额度大字提示
a13a6b9d feat(android-apk): add MonkeyCode Android WebView APK
1231da27 Merge pull request #1012 from ...
b500dfaf fix(frontend): preserve task dialog draft on dismiss
...
```

> **关键**：确认 `1a60b21a` 在最上面（HEAD）。这就是我们要基于的 commit。

### 5.3 查看这个 commit 改了什么

```bash
git show 1a60b21a --stat
```

**你应该看到的结果**：

```
commit 1a60b21a850e4581d8d87ebb845ba8067e2e8985
Author: TRAE Bot <trae-bot@bytedance.com>
Date:   Fri Aug 7 12:49:51 2026 +0000

    feat(android-apk): FAB 导出按钮显示剩余额度，低额度大字提示

 .../main/java/com/monkeyCode/ai/MainActivity.java  | 196 +++++++++++++++++++--
 1 file changed, 181 insertions(+), 15 deletions(-)
```

> **为什么看这个？** 确认这个 commit 改的是 `MainActivity.java`，这是我们后面要处理的核心源文件。

---

## 六、第三步：摸清楚工程结构

### 6.1 找到 Android 工程在哪

```bash
find . -name "MainActivity.java" 2>/dev/null
find . -name "AndroidManifest.xml" 2>/dev/null
find . -name "build.sh" 2>/dev/null
```

**你应该看到的结果**：

```
./mobile/android-apk/app/src/main/java/com/monkeyCode/ai/MainActivity.java
./mobile/android-apk/app/src/main/AndroidManifest.xml
./mobile/android-apk/build.sh
```

> **为什么用 find？** 仓库很大（有前端、后端、桌面端等），Android 工程只是其中一小部分。用 `find` 直接定位关键文件，比一个个文件夹翻快得多。

### 6.2 看 Android 工程的目录结构

```bash
ls -la mobile/android-apk/
ls -la mobile/android-apk/app/src/main/
```

**你应该看到的结果**：

```
mobile/android-apk/ 下有：
  app/        ← 源码目录
  build.sh    ← 原始构建脚本
  .gitignore  ← 忽略规则

app/src/main/ 下有：
  AndroidManifest.xml   ← 清单文件（声明包名等）
  java/                 ← Java 源码
  res/                  ← 资源文件（图标、字符串等）
```

### 6.3 读原始构建脚本

```bash
cat mobile/android-apk/build.sh
```

这是理解整个编译流程的关键。脚本内容如下（加注释解释每一步）：

```bash
#!/bin/bash
set -e

# 设置 Java 17 和 Android SDK 的路径
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/data/user/work/android-sdk
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/build-tools/34.0.0:$ANDROID_HOME/platform-tools:$PATH

# 定义各种路径变量
PROJECT=/data/user/work/MonkeyCode/mobile/android-apk
APP_DIR=$PROJECT/app
BUILD_DIR=$PROJECT/build
# ...（省略部分变量定义）

# 第1步：用 javac 编译 Java 源码 → .class 文件
javac -source 11 -target 11 -classpath $ANDROID_JAR \
    -d $BUILD_DIR/classes \
    $JAVA_SRC/com/monkeyCode/ai/MainActivity.java

# 第2步：用 aapt2 处理资源 → resources.apk
aapt2 compile --dir $RES -o $BUILD_DIR/compiled-res/
aapt2 link -I $ANDROID_JAR --manifest $MANIFEST ...

# 第3步：用 d8 把 .class → .dex
d8 --output $BUILD_DIR/dex --lib $ANDROID_JAR --min-api 24 ...

# 第4步：把 .dex 塞进 resources.apk → unsigned.apk
cp $BUILD_DIR/resources.apk $BUILD_DIR/unsigned.apk
cd $BUILD_DIR
zip -j unsigned.apk dex/classes.dex

# 第5步：生成签名用的密钥
keytool -genkey -keystore $BUILD_DIR/debug.keystore -alias monkeycode ...

# 第6步：签名
apksigner sign --ks $BUILD_DIR/debug.keystore ... \
    --out $BUILD_DIR/MonkeyCode.apk $BUILD_DIR/unsigned.apk

# 第7步：验证签名
apksigner verify --verbose $BUILD_DIR/MonkeyCode.apk

# 第8步：复制到 /workspace
cp $BUILD_DIR/MonkeyCode.apk /workspace/MonkeyCode.apk
```

> **为什么仔细读 build.sh？** 这是整个构建的"配方"。我们要做的自动化工具，本质上就是把这个脚本的逻辑提取出来，加上"改包名、改应用名"的步骤。理解了它，后面的一切都好懂。

### 6.4 读 AndroidManifest.xml（包名在这里）

```bash
cat mobile/android-apk/app/src/main/AndroidManifest.xml
```

**你应该看到的结果**：

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.monkeyCode.ai">                    ← 【包名在这里】

    <uses-permission android:name="android.permission.INTERNET" />
    ...

    <application
        android:icon="@mipmap/ic_launcher"
        android:label="MonkeyCode"                   ← 【应用名在这里】
        ...>
        <activity
            android:name=".MainActivity"
            ...>
        </activity>
    </application>
</manifest>
```

> **关键发现**：要改包名，改 `package="com.monkeyCode.ai"` 这一行；要改应用名，改 `android:label="MonkeyCode"` 这一行。

### 6.5 读 strings.xml（应用名也在这里）

```bash
cat mobile/android-apk/app/src/main/res/values/strings.xml
```

**你应该看到的结果**：

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">MonkeyCode</string>     ← 【应用名也在这里】
</resources>
```

> **为什么应用名在两个地方？** `AndroidManifest.xml` 里的 `android:label` 可以直接写字符串（如 `"MonkeyCode"`），也可以引用资源（如 `@string/app_name`）。这个工程直接写了字符串，但 `strings.xml` 里也有一个 `app_name`。两个都要改才保险。

### 6.6 看 MainActivity.java 的包声明和关键引用

```bash
# 看第一行（包声明）
head -1 mobile/android-apk/app/src/main/java/com/monkeyCode/ai/MainActivity.java

# 搜索所有含 "monkeyCode" 或 "MonkeyCode" 的行
grep -n -i "monkeyCode\|com\.monkeycode" \
    mobile/android-apk/app/src/main/java/com/monkeyCode/ai/MainActivity.java
```

**你应该看到的结果**（关键行）：

```
1:package com.monkeyCode.ai;                                    ← 【包声明】
61:    private static final String SERVER_URL = "https://monkeycode-ai.com";  ← 服务器地址，不能改！
136:        webView.addJavascriptInterface(new MonkeyCodeBridge(), "MonkeyCodeBridge");
688:                    Environment.DIRECTORY_DOWNLOADS + "/MonkeyCode");      ← 【下载目录名】
710:                    "MonkeyCode");                                          ← 【下载目录名】
718:            showToast("已保存到 Download/MonkeyCode/" + filename);          ← 【下载目录名】
820:        subtitle.setText("请检查网络连接后重试\n\nMonkeyCode AI");
831:        private class MonkeyCodeBridge {                                   ← 【内部类名】
```

> **关键发现**：除了包声明，还有几处含 "MonkeyCode" 的字符串：
> - `SERVER_URL`：这是服务器地址 `monkeycode-ai.com`，**绝对不能改**，改了就连不上服务器了
> - 下载目录名（`"/MonkeyCode"`、`"MonkeyCode"`）：改了可以让每个变体存到不同的下载文件夹
> - `MonkeyCodeBridge`、内部类名：这些是代码内部的标识符，不改也不影响功能
>
> **所以我们的策略是**：改包声明、改下载目录名（让每个 App 的导出文件分开存），保留 `SERVER_URL` 不动。

---

## 七、第四步：安装 Java 17

### 7.1 安装

```bash
# 更新软件源
apt-get update -qq

# 安装 Java 17（无界面版，体积小）
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-17-openjdk-headless
```

> **为什么用 `-qq`？** 安静模式，少输出一些日志。`DEBIAN_FRONTEND=noninteractive` 是告诉系统"别弹交互式问题，用默认值"，否则安装过程中可能卡住等你确认。

> **为什么装 `headless` 版？** 服务器上没有图形界面，`headless` 版去掉了 GUI 相关组件，体积更小、安装更快。编译 Android APK 不需要 GUI。

### 7.2 验证安装

```bash
/usr/lib/jvm/java-17-openjdk-amd64/bin/java -version
```

**你应该看到的结果**：

```
openjdk version "17.0.19" 2026-04-21
OpenJDK Runtime Environment (build 17.0.19+10-1-22.04.2-Ubuntu)
OpenJDK 64-Bit Server VM (build 17.0.19+10-1-22.04.2-Ubuntu, mixed mode, sharing)
```

> **为什么用完整路径？** 系统里可能已经有 Java 11，直接敲 `java -version` 可能还是 11。用完整路径能确认 Java 17 确实装好了。后面的构建脚本里会用 `JAVA_HOME` 环境变量指定用哪个 Java。

---

## 八、第五步：安装 Android SDK（最容易踩坑的一步）

这一步分三个部分：命令行工具、build-tools、android 平台。**每个都可能出问题**，请仔细看。

### 8.1 下载 Android 命令行工具（cmdline-tools）

```bash
cd /data/user/work

# 下载命令行工具（约 150MB）
curl -sL -o cmdline-tools.zip \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"

# 确认下载成功
ls -la cmdline-tools.zip
```

**你应该看到的结果**：

```
-rw-r--r-- 1 root root 153607504 Aug  8 01:46 cmdline-tools.zip
```

> 文件大小约 150MB（153607504 字节）。如果大小差很多，说明下载不完整，重新下载。

### 8.2 解压并放到正确位置

```bash
# 创建 SDK 根目录
mkdir -p android-sdk/cmdline-tools

# 解压
unzip -q cmdline-tools.zip -d android-sdk/cmdline-tools

# 【关键】把解压出来的 cmdline-tools 文件夹改名为 latest
mv android-sdk/cmdline-tools/cmdline-tools android-sdk/cmdline-tools/latest

# 验证
ls android-sdk/cmdline-tools/latest/bin/
```

**你应该看到的结果**：

```
apkanalyzer  avdmanager  lint  profgen  resourceshrinker  retrace  screenshot2  sdkmanager
```

> **为什么必须改名为 `latest`？** Android SDK 的目录结构有严格规定：`cmdline-tools/latest/` 下面才能放 `bin/`、`lib/` 等。如果直接用 `cmdline-tools/cmdline-tools/`，`sdkmanager` 会报错说找不到自己的路径。这是 Google 官方文档的要求。

> **避坑**：如果你看到 `sdkmanager` 报错 `SDKMANAGER: command not found` 或 `Error: Could not determine SDK root`，99% 是这个目录结构不对。检查 `android-sdk/cmdline-tools/latest/bin/sdkmanager` 这个文件是否存在。

### 8.3 用 sdkmanager 安装 build-tools 和 platform

```bash
# 设置环境变量（后面所有 SDK 相关命令都要用）
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/data/user/work/android-sdk
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH

# 接受所有许可协议（不接的话安装会被拦住）
yes | sdkmanager --licenses >/dev/null 2>&1

# 安装三个组件
sdkmanager "build-tools;34.0.0" "platforms;android-34" "platform-tools"
```

> **为什么用 `yes |`？** `sdkmanager` 安装时会问你一堆 "Accept? (y/N)" 的问题。`yes` 命令会不断输出 `y`，通过管道 `|` 喂给 `sdkmanager`，相当于自动全部同意。

> **这一步可能很慢**，因为要下载几百 MB 的文件。正常情况下等几分钟就行。

### 8.4 ⚠️ 踩坑：sdkmanager 下载 build-tools 卡住

**实际遇到的问题**：`sdkmanager` 安装 `build-tools;34.0.0` 时卡住不动，等了很久 `build-tools/` 目录还是空的。`platforms;android-34` 和 `platform-tools` 倒是装上了。

**排查方法**：

```bash
# 看 SDK 目录多大（判断有没有在下载）
du -sh /data/user/work/android-sdk

# 看 build-tools 目录有没有内容
ls /data/user/work/android-sdk/build-tools/ 2>/dev/null

# 看 platforms 目录
ls /data/user/work/android-sdk/platforms/ 2>/dev/null
```

**如果 build-tools 目录是空的**，说明卡住了。解决办法是**直接下载 build-tools 压缩包手动安装**：

```bash
cd /data/user/work

# 直接从 Google 下载 build-tools 34 的压缩包（约 60MB）
curl -sL -o build-tools_r34-linux.zip \
    "https://dl.google.com/android/repository/build-tools_r34-linux.zip"

# 确认下载成功
ls -la build-tools_r34-linux.zip
```

**你应该看到的结果**：

```
-rw-r--r-- 1 root root 61224257 Aug  8 01:46 build-tools_r34-linux.zip
```

然后解压到正确位置：

```bash
# 先看看压缩包里面的目录结构
unzip -l build-tools_r34-linux.zip | head -10
```

**你应该看到的结果**：

```
Archive:  build-tools_r34-linux.zip
  Length      Date    Time    Name
---------  ---------- -----   ------
  1069352  2008-01-01 00:00   android-14/NOTICE.txt
  1525352  2008-01-01 00:00   android-14/aapt
  6076216  2008-01-01 00:00   android-14/aapt2
```

> **注意**：压缩包里的顶层目录叫 `android-14`，不是 `34.0.0`。我们需要手动放到 `build-tools/34.0.0/` 目录下。

```bash
# 解压到临时目录
unzip -q build-tools_r34-linux.zip -d bt-tmp

# 顶层目录名是 android-14
TOPDIR=$(ls bt-tmp)
echo "顶层目录: $TOPDIR"    # 应该输出 android-14

# 创建目标目录并复制
mkdir -p android-sdk/build-tools/34.0.0
cp -r bt-tmp/$TOPDIR/* android-sdk/build-tools/34.0.0/

# 清理临时目录
rm -rf bt-tmp

# 验证
ls android-sdk/build-tools/34.0.0/ | head -15
```

**你应该看到的结果**：

```
NOTICE.txt
aapt
aapt2          ← 这个最重要
aidl
apksigner      ← 这个也重要
d8             ← 这个也重要
dexdump
...
zipalign
```

### 8.5 ⚠️ 踩坑：platform android-34 目录为空

**实际遇到的问题**：之前 `sdkmanager` 被中断后，`platforms/android-34/` 目录只有一个 `.installer` 子目录，没有 `android.jar` 文件。

**排查方法**：

```bash
ls -la android-sdk/platforms/android-34/
```

**如果看到只有一个 `.installer` 目录**，说明 platform 没装完。解决办法是**单独再装一次**：

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/data/user/work/android-sdk
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH

yes | sdkmanager "platforms;android-34"
```

**验证 `android.jar` 存在**：

```bash
ls -la android-sdk/platforms/android-34/android.jar
```

**你应该看到的结果**：

```
-rw-r--r-- 1 root root 26361808 Aug  8 01:46 android-sdk/platforms/android-34/android.jar
```

> **为什么 android.jar 这么重要？** 编译时 `javac` 需要它来知道 Android 提供了哪些类（比如 `Activity`、`WebView`、`Bundle` 等）。没有它，编译器会说"找不到 Activity 这个类"。文件大小约 26MB。

### 8.6 最终验证整个工具链

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/data/user/work/android-sdk
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/build-tools/34.0.0:$PATH

echo "=== aapt2 ===" && aapt2 version
echo "=== d8 ===" && d8 --version
echo "=== apksigner ===" && apksigner --version
echo "=== android.jar ===" && ls -la $ANDROID_HOME/platforms/android-34/android.jar
```

**你应该看到的结果**：

```
=== aapt2 ===
Android Asset Packaging Tool (aapt) 2.19-10229193
=== d8 ===
D8 8.2.2-dev ...
=== apksigner ===
0.9
=== android.jar ===
-rw-r--r-- 1 root root 26361808 ... android.jar
```

> 四个工具全部就位，工具链搭建完成！如果任何一个报错，回到对应小节重新安装。

---

## 九、第六步：编写自动化构建工具

这是整个任务的核心——写两个脚本，让"改包名 + 编译 + 签名"变成全自动。

### 9.1 build-variant.sh：单变体构建器

这个脚本的作用是：给它一个包名后缀、一个应用名、一个 APK 文件名，它就自动"克隆"出一个新 APK。

**核心思路**（重要，先理解再看代码）：

1. 把 `app/` 源码**复制一份**到临时目录（不碰原始源码）
2. 在临时副本里用 Python 脚本改四个地方：
   - `AndroidManifest.xml` 里的 `package` 和 `android:label`
   - `strings.xml` 里的 `app_name`
   - `MainActivity.java` 里的 `package` 声明和下载目录名
   - 把 `.java` 文件移动到新的包路径文件夹
3. 用 `javac → aapt2 → d8 → apksigner` 编译签名
4. 把成品 APK 复制到输出目录

> **为什么不直接改原始源码？** 因为要生成三个变体，如果直接改原始源码，生成第二个的时候原始的就被破坏了。每次都从干净的副本开始改，保证可重复。

创建文件 `mobile/android-apk/build-variant.sh`：

```bash
cd /data/user/work/MonkeyCode/mobile/android-apk
```

> 以下是 `build-variant.sh` 的完整内容。你也可以直接在仓库里查看这个文件：
> https://github.com/liliangxing/MonkeyCode/blob/260324.1.22/mobile/android-apk/build-variant.sh

```bash
#!/usr/bin/env bash
#
# build-variant.sh — 用指定包名、应用名、APK名构建一个变体
#
# 用法:
#   ./build-variant.sh <包名后缀> <应用名> <apk文件名>
#
# 例子:
#   ./build-variant.sh ai   MonkeyCode  MonkeyCode.apk
#   ./build-variant.sh ai2  Monkey2     Monkey2.apk
#   ./build-variant.sh ai3  Monkey3     Monkey3.apk
#
set -euo pipefail

# 读取参数：$1=后缀 $2=应用名 $3=apk名
PKG_SUFFIX="${1:?ERROR: 需要包名后缀 (如 ai2)}"
APP_NAME="${2:?ERROR: 需要应用名 (如 Monkey2)}"
APK_NAME="${3:?ERROR: 需要apk名 (如 Monkey2.apk)}"

# 拼出完整包名和包路径
PACKAGE="com.monkeyCode.${PKG_SUFFIX}"
PKG_PATH="com/monkeyCode/${PKG_SUFFIX}"

# 设置工具路径（有默认值，也可用环境变量覆盖）
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export ANDROID_HOME="${ANDROID_HOME:-/data/user/work/android-sdk}"
BT_VERSION="${BT_VERSION:-34.0.0}"
PLATFORM="${PLATFORM:-android-34}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/build-tools/${BT_VERSION}:$ANDROID_HOME/platform-tools:$PATH"
ANDROID_JAR="$ANDROID_HOME/platforms/${PLATFORM}/android.jar"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_APP="$SCRIPT_DIR/app"
WORK_DIR="$SCRIPT_DIR/build/variant-${PKG_SUFFIX}"
STAGE_APP="$WORK_DIR/app"
BUILD_DIR="$WORK_DIR/build"
OUT_DIR="${OUT_DIR:-$SCRIPT_DIR/dist}"
# 第4个参数可以覆盖输出目录
[ "${4:-}" != "" ] && OUT_DIR="$4"

echo "==> 构建变体"
echo "    包名: $PACKAGE"
echo "    应用名: $APP_NAME"
echo "    APK名: $APK_NAME"

# --- 检查工具是否齐全 ---
command -v javac >/dev/null   || { echo "ERROR: 找不到 javac"; exit 1; }
command -v aapt2 >/dev/null   || { echo "ERROR: 找不到 aapt2"; exit 1; }
command -v d8 >/dev/null      || { echo "ERROR: 找不到 d8"; exit 1; }
command -v apksigner >/dev/null || { echo "ERROR: 找不到 apksigner"; exit 1; }
[ -f "$ANDROID_JAR" ]         || { echo "ERROR: 找不到 android.jar"; exit 1; }
[ -d "$SRC_APP" ]             || { echo "ERROR: 找不到 app 源码目录"; exit 1; }

# --- 第0步：复制一份干净的源码到临时目录 ---
echo "--- Step 0: 复制源码 ---"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cp -r "$SRC_APP" "$STAGE_APP"

ASSETS="$STAGE_APP/src/main/assets"
RES="$STAGE_APP/src/main/res"
JAVA_SRC="$STAGE_APP/src/main/java"
MANIFEST="$STAGE_APP/src/main/AndroidManifest.xml"
mkdir -p "$ASSETS"

# --- 第1步：用 Python 改身份信息 ---
echo "--- Step 1: 改身份 ---"
python3 - "$STAGE_APP" "$PACKAGE" "$PKG_PATH" "$APP_NAME" <<'PY'
import os, re, sys
stage, package, pkg_path, app_name = sys.argv[1:5]

# 改 AndroidManifest.xml 的 package 和 label
man = os.path.join(stage, "src/main/AndroidManifest.xml")
s = open(man, encoding="utf-8").read()
s = s.replace('package="com.monkeyCode.ai"', 'package="%s"' % package)
s = s.replace('android:label="MonkeyCode"', 'android:label="%s"' % app_name)
open(man, "w", encoding="utf-8").write(s)

# 改 strings.xml 的 app_name
st = os.path.join(stage, "src/main/res/values/strings.xml")
s = open(st, encoding="utf-8").read()
s = re.sub(r'(<string name="app_name">)[^<]*(</string>)',
           r'\g<1>%s\g<2>' % app_name, s)
open(st, "w", encoding="utf-8").write(s)

# 改 MainActivity.java 的 package 声明和下载目录名
java_dir = os.path.join(stage, "src/main/java/com/monkeyCode/ai")
jf = os.path.join(java_dir, "MainActivity.java")
s = open(jf, encoding="utf-8").read()
s = s.replace("package com.monkeyCode.ai;", "package %s;" % package)
s = s.replace('"/MonkeyCode"', '"/%s"' % app_name)
s = s.replace('"MonkeyCode")', '"%s")' % app_name)
s = s.replace("Download/MonkeyCode/", "Download/%s/" % app_name)
open(jf, "w", encoding="utf-8").write(s)

# 把 .java 文件移到新的包路径文件夹
new_dir = os.path.join(stage, "src/main/java", pkg_path)
os.makedirs(new_dir, exist_ok=True)
os.rename(jf, os.path.join(new_dir, "MainActivity.java"))
try:
    os.rmdir(java_dir)  # 删掉空文件夹
except OSError:
    pass
print("    已改: manifest, strings, java package, 下载目录")
PY

# --- 第2步：编译 Java ---
echo "--- Step 2: 编译 Java ---"
mkdir -p "$BUILD_DIR/classes"
javac -source 11 -target 11 -classpath "$ANDROID_JAR" \
    -d "$BUILD_DIR/classes" \
    "$JAVA_SRC/$PKG_PATH/MainActivity.java"

# --- 第3步：aapt2 处理资源 ---
echo "--- Step 3: aapt2 ---"
mkdir -p "$BUILD_DIR/compiled-res"
aapt2 compile --dir "$RES" -o "$BUILD_DIR/compiled-res/"
aapt2 link \
    -I "$ANDROID_JAR" \
    --manifest "$MANIFEST" \
    -A "$ASSETS" \
    --java "$BUILD_DIR/gen" \
    -o "$BUILD_DIR/resources.apk" \
    --min-sdk-version 24 \
    --target-sdk-version 34 \
    "$BUILD_DIR"/compiled-res/*.flat

# --- 第4步：d8 生成 dex ---
echo "--- Step 4: d8 ---"
mkdir -p "$BUILD_DIR/dex"
find "$BUILD_DIR/classes" -name "*.class" > "$BUILD_DIR/class-list.txt"
d8 \
    --output "$BUILD_DIR/dex" \
    --lib "$ANDROID_JAR" \
    --min-api 24 \
    $(cat "$BUILD_DIR/class-list.txt" | tr '\n' ' ')

# --- 第5步：组装未签名 APK ---
echo "--- Step 5: 组装 APK ---"
cp "$BUILD_DIR/resources.apk" "$BUILD_DIR/unsigned.apk"
( cd "$BUILD_DIR" && zip -j unsigned.apk dex/classes.dex )

# --- 第6步：生成密钥 ---
echo "--- Step 6: 密钥 ---"
rm -f "$BUILD_DIR/debug.keystore"
keytool -genkey \
    -keystore "$BUILD_DIR/debug.keystore" \
    -alias "${APP_NAME,,}" \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android \
    -dname "CN=${APP_NAME}, OU=Dev, O=MonkeyCode AI, L=Beijing, ST=Beijing, C=CN" >/dev/null 2>&1

# --- 第7步：签名 ---
echo "--- Step 7: 签名 ---"
apksigner sign \
    --ks "$BUILD_DIR/debug.keystore" \
    --ks-key-alias "${APP_NAME,,}" \
    --ks-pass pass:android \
    --key-pass pass:android \
    --out "$BUILD_DIR/$APK_NAME" \
    "$BUILD_DIR/unsigned.apk"
apksigner verify --verbose "$BUILD_DIR/$APK_NAME" >/dev/null 2>&1 && echo "    签名验证通过"

# --- 第8步：输出成品 ---
echo "--- Step 8: 收集成品 ---"
mkdir -p "$OUT_DIR"
cp "$BUILD_DIR/$APK_NAME" "$OUT_DIR/$APK_NAME"
echo "==> 完成: $OUT_DIR/$APK_NAME  ($(du -h "$OUT_DIR/$APK_NAME" | cut -f1))"
```

#### 关键设计解释

**为什么用 Python 改文件而不是用 sed？**

`sed` 是命令行文本替换工具，但处理多行、特殊字符、正则时容易出错（比如应用名里有特殊字符就会出问题）。Python 的字符串操作更可靠、更可读，而且大部分 Linux 系统自带 Python 3。

**为什么用 `${APP_NAME,,}` 作为密钥别名？**

`${APP_NAME,,}` 是 Bash 语法，把变量转成小写。比如 `Monkey2` → `monkey2`。Java 的 `keytool` 工具对别名大小写敏感，统一用小写避免混乱。

**为什么每个变体用不同的密钥？**

虽然用同一个密钥也能签出不同包名的 APK，但用不同密钥更干净——如果以后某个变体要单独发布或迁移，不会被密钥绑定。密钥密码统一用 `android`（调试用，不影响功能）。

### 9.2 build-all.sh：一键全量构建

这个脚本就是依次调用 `build-variant.sh` 三次：

```bash
#!/usr/bin/env bash
#
# build-all.sh — 一键构建全部三个变体
#
# 用法:
#   ./build-all.sh [输出目录]
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${1:-$DIR/dist}"
mkdir -p "$OUT_DIR"

echo "###################################################"
echo "# MonkeyCode APK — 一键多变体构建                #"
echo "###################################################"
echo "输出目录: $OUT_DIR"
echo

# 依次构建三个变体
"$DIR/build-variant.sh" ai  MonkeyCode MonkeyCode.apk "$OUT_DIR"
echo
"$DIR/build-variant.sh" ai2 Monkey2    Monkey2.apk    "$OUT_DIR"
echo
"$DIR/build-variant.sh" ai3 Monkey3    Monkey3.apk    "$OUT_DIR"

echo
echo "###################################################"
echo "# 全部构建完成。产物：                           #"
echo "###################################################"
ls -lh "$OUT_DIR"/*.apk
echo
echo "APK 在: $OUT_DIR"
```

### 9.3 给脚本加执行权限

```bash
chmod +x mobile/android-apk/build-variant.sh mobile/android-apk/build-all.sh
```

> **为什么需要 chmod +x？** Linux 里新建的脚本默认没有"执行权限"，直接运行会报 `permission denied`。`chmod +x` 就是给它加上执行权限。

> **⚠️ 避坑**：我实际操作时就踩了这个坑——先创建了脚本文件，然后在一个组合命令里同时跑 `chmod +x` 和构建，结果 `chmod` 那行没执行到（因为前面的命令出错了），构建时报 `permission denied: ./build-variant.sh`。**解决方法就是单独执行一次 `chmod +x`**。

---

## 十、第七步：一键构建三个 APK

### 10.1 先测试构建原始版本

在构建全部三个之前，先单独构建一个原始版本（`MonkeyCode.apk`）验证脚本能跑通：

```bash
cd /data/user/work/MonkeyCode/mobile/android-apk

./build-variant.sh ai MonkeyCode MonkeyCode.apk /data/user/work/test-out
```

**你应该看到的结果**：

```
==> 构建变体
    包名: com.monkeyCode.ai
    应用名: MonkeyCode
    APK名: MonkeyCode.apk
--- Step 0: 复制源码 ---
--- Step 1: 改身份 ---
    已改: manifest, strings, java package, 下载目录
--- Step 2: 编译 Java ---
warning: [options] system modules path not set in conjunction with -source 11
Note: ...MainActivity.java uses or overrides a deprecated API.
1 warning
--- Step 3: aapt2 ---
--- Step 4: d8 ---
--- Step 5: 组装 APK ---
  adding: classes.dex (deflated 56%)
--- Step 6: 密钥 ---
--- Step 7: 签名 ---
    签名验证通过
--- Step 8: 收集成品 ---
==> 完成: /data/user/work/test-out/MonkeyCode.apk  (32K)
```

> **那些 warning 正常吗？** 正常。`system modules path not set` 和 `deprecated API` 都是警告不是错误，不影响编译结果。只要最后看到 `签名验证通过` 和 `完成` 就说明成功了。

> **为什么先测一个？** 先跑通一个再跑全部。如果脚本有 bug，只构建一个能更快定位问题，不用等三个都跑完才发现错误。

### 10.2 一键构建全部三个

确认单个能跑通后，执行一键构建：

```bash
cd /data/user/work/MonkeyCode/mobile/android-apk

./build-all.sh /data/user/work/apks
```

**你应该看到的结果**（节选）：

```
###################################################
# MonkeyCode APK — 一键多变体构建                #
###################################################
输出目录: /data/user/work/apks

==> 构建变体
    包名: com.monkeyCode.ai
    应用名: MonkeyCode
    APK名: MonkeyCode.apk
...
==> 完成: /data/user/work/apks/MonkeyCode.apk  (32K)

==> 构建变体
    包名: com.monkeyCode.ai2
    应用名: Monkey2
    APK名: Monkey2.apk
...
==> 完成: /data/user/work/apks/Monkey2.apk  (32K)

==> 构建变体
    包名: com.monkeyCode.ai3
    应用名: Monkey3
    APK名: Monkey3.apk
...
==> 完成: /data/user/work/apks/Monkey3.apk  (32K)

###################################################
# 全部构建完成。产物：                           #
###################################################
-rw-r--r-- 1 root root 29K ... Monkey2.apk
-rw-r--r-- 1 root root 29K ... Monkey3.apk
-rw-r--r-- 1 root root 29K ... MonkeyCode.apk

APK 在: /data/user/work/apks
```

> 三个 APK 都约 29-32KB，大小接近因为代码完全一样，只是包名和签名不同。

---

## 十一、第八步：验证 APK 是否正确

构建完了不能直接用，要验证包名和应用名是不是真的改对了。

### 11.1 用 aapt2 查看每个 APK 的身份证

```bash
export PATH=/data/user/work/android-sdk/build-tools/34.0.0:$PATH

for apk in MonkeyCode Monkey2 Monkey3; do
    echo "=== $apk.apk ==="
    aapt2 dump badging /data/user/work/apks/$apk.apk 2>/dev/null | grep -E "^package:|application-label:"
    echo
done
```

**你应该看到的结果**：

```
=== MonkeyCode.apk ===
package: name='com.monkeyCode.ai' versionCode='' ...
application-label:'MonkeyCode'

=== Monkey2.apk ===
package: name='com.monkeyCode.ai2' versionCode='' ...
application-label:'Monkey2'

=== Monkey3.apk ===
package: name='com.monkeyCode.ai3' versionCode='' ...
application-label:'Monkey3'
```

> **`aapt2 dump badging` 是什么？** 它可以读出 APK 里的"名片信息"——包名、应用名、版本号、权限列表等。`grep -E "^package:|application-label:"` 只过滤出包名和应用名这两行，方便确认。

> **如果包名或应用名没改对怎么办？** 说明 Python 补丁脚本有问题。回到 9.1 节检查替换逻辑，特别注意 `replace` 的匹配字符串是否和源文件完全一致（大小写、引号都要对上）。

---

## 十二、第九步：把工具提交到代码仓库

构建工具写好了，要提交到 GitHub 仓库，这样别人也能用、以后也有记录。

### 12.1 检查状态

```bash
cd /data/user/work/MonkeyCode

# 看当前在哪个分支
git branch --show-current

# 看有哪些新文件
git status --short mobile/android-apk/

# 确认构建产物被 .gitignore 忽略了（不会被误提交）
git check-ignore mobile/android-apk/build mobile/android-apk/dist
```

**你应该看到的结果**：

```
260324.1.22                          ← 当前分支名
?? mobile/android-apk/build-all.sh   ← 新文件，?? 表示未跟踪
?? mobile/android-apk/build-variant.sh
mobile/android-apk/build             ← 被 .gitignore 忽略了
mobile/android-apk/dist              ← 被 .gitignore 忽略了
```

> **为什么确认 .gitignore？** `build/` 目录里有编译中间产物（`.class`、`.dex`、密钥等），`dist/` 里有成品 APK。这些都不应该提交到代码仓库。`.gitignore` 文件里已经有 `build/` 和 `*.apk` 规则，所以它们会被自动忽略。`git check-ignore` 就是验证某个路径是否被忽略。

### 12.2 确认远程分支信息

```bash
# 看远程仓库的默认分支
git remote show origin | grep "HEAD branch"

# 看当前分支追踪的远程分支
git rev-parse --abbrev-ref --symbolic-full-name @{u}

# 确认当前 HEAD 就是要基于的 commit
git rev-parse HEAD
```

**你应该看到的结果**：

```
  HEAD branch: 260324.1.22
origin/260324.1.22
1a60b21a850e4581d8d87ebb845ba8067e2e8985
```

> **为什么要确认这些？** 确保你提交到正确的分支、推到正确的远程。HEAD 确认是 `1a60b21a`，说明基于正确的 commit。

### 12.3 提交并推送

```bash
cd /data/user/work/MonkeyCode

# 设置提交者信息（如果还没设过）
git config user.email "你的邮箱"
git config user.name "你的名字"

# 暂存新文件
git add mobile/android-apk/build-variant.sh mobile/android-apk/build-all.sh

# 提交
git commit -m "feat(android-apk): one-click multi-variant APK builder (Monkey2/Monkey3)

- build-variant.sh: parameterized builder producing an independent APK per
  (package suffix, app label, apk name). Stages a pristine source copy and
  patches manifest package/label, strings app_name, java package path and
  per-variant download folder, then compiles+d8+signs.
- build-all.sh: one-click build of MonkeyCode (com.monkeyCode.ai),
  Monkey2 (com.monkeyCode.ai2) and Monkey3 (com.monkeyCode.ai3)."

# 推送到远程
git push origin 260324.1.22
```

**你应该看到的结果**：

```
[260324.1.22 93e104a3] feat(android-apk): one-click multi-variant APK builder (Monkey2/Monkey3)
 2 files changed, 219 insertions(+)
 create mode 100755 mobile/android-apk/build-all.sh
 create mode 100755 mobile/android-apk/build-variant.sh
To https://github.com/liliangxing/MonkeyCode.git
   1a60b21a..93e104a3  260324.1.22 -> 260324.1.22
```

> **提交信息为什么用英文？** 这是工程习惯，团队仓库的提交信息一般用英文，方便国际协作者阅读。内容描述了两个脚本各自的功能。

---

## 十三、第十步：发布 APK 到 GitHub Release

### 13.1 查看已有的 Release

```bash
TOKEN="你的TOKEN"

# 查看 v26080701 这个 release 的信息
curl -s -H "Authorization: token $TOKEN" \
    https://api.github.com/repos/liliangxing/MonkeyCode/releases/tags/v26080701 \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Release ID:', d['id'])
print('名称:', d['name'])
print('Tag:', d['tag_name'])
print('已发布:', d['published_at'])
print('现有资产:')
for a in d['assets']:
    print(f'  - {a[\"name\"]} | {a[\"size\"]} bytes | id: {a[\"id\"]}')
"
```

**你应该看到的结果**（发布前）：

```
Release ID: 366754264
名称: MonkeyCode APK v26080701
Tag: v26080701
已发布: 2026-08-07T13:06:51Z
现有资产:
  - MonkeyCode.apk | 29603 bytes | id: 505164558
```

> **Release ID 是什么？** GitHub 给每个 Release 分配一个数字 ID（这里是 `366754264`）。上传文件时要用的就是这个 ID，不是 tag 名。

### 13.2 上传 Monkey2.apk 和 Monkey3.apk

```bash
cd /data/user/work/apks
TOKEN="你的TOKEN"
REL_ID=366754264

# 上传 Monkey2.apk
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/vnd.android.package-archive" \
  --data-binary @"Monkey2.apk" \
  "https://uploads.github.com/repos/liliangxing/MonkeyCode/releases/$REL_ID/assets?name=Monkey2.apk"

# 上传 Monkey3.apk
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/vnd.android.package-archive" \
  --data-binary @"Monkey3.apk" \
  "https://uploads.github.com/repos/liliangxing/MonkeyCode/releases/$REL_ID/assets?name=Monkey3.apk"
```

> **逐行解释**：
> - `-X POST`：用 POST 方法上传
> - `-H "Authorization: token $TOKEN"`：带上身份认证
> - `-H "Content-Type: application/vnd.android.package-archive"`：告诉 GitHub 这是 APK 文件
> - `--data-binary @"Monkey2.apk"`：把文件内容以二进制方式上传（`@` 表示读文件）
> - URL 里的 `?name=Monkey2.apk`：指定上传后在 Release 里显示的文件名

> **避坑**：`Content-Type` 必须设对。如果用默认的 `application/json`，GitHub 可能拒绝或损坏文件。

### 13.3 用脚本方式上传（带结果检查）

更稳妥的方式是用 Python 解析返回结果，确认上传成功：

```bash
cd /data/user/work/apks
TOKEN="你的TOKEN"
REL_ID=366754264

for f in Monkey2.apk Monkey3.apk; do
    echo "=== 上传 $f ==="
    curl -s -X POST \
      -H "Authorization: token $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/vnd.android.package-archive" \
      --data-binary @"$f" \
      "https://uploads.github.com/repos/liliangxing/MonkeyCode/releases/$REL_ID/assets?name=$f" \
      | python3 -c "
import sys,json
d=json.load(sys.stdin)
if 'name' in d:
    print(f'  上传成功: {d[\"name\"]} | {d[\"size\"]} bytes | id: {d[\"id\"]} | 状态: {d[\"state\"]}')
else:
    print(f'  错误: {d}')
"
done
```

**你应该看到的结果**：

```
=== 上传 Monkey2.apk ===
  上传成功: Monkey2.apk | 29601 bytes | id: 505784693 | 状态: uploaded
=== 上传 Monkey3.apk ===
  上传成功: Monkey3.apk | 29601 bytes | id: 505784698 | 状态: uploaded
```

### 13.4 最终确认

```bash
TOKEN="你的TOKEN"

curl -s -H "Authorization: token $TOKEN" \
    https://api.github.com/repos/liliangxing/MonkeyCode/releases/366754264 \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Release:', d['name'], '| tag:', d['tag_name'])
print()
for a in d['assets']:
    print(f'  - {a[\"name\"]} | {a[\"size\"]} bytes')
    print(f'    {a[\"browser_download_url\"]}')
"
```

**你应该看到的结果**：

```
Release: MonkeyCode APK v26080701 | tag: v26080701

  - Monkey2.apk | 29601 bytes
    https://github.com/liliangxing/MonkeyCode/releases/download/v26080701/Monkey2.apk
  - Monkey3.apk | 29601 bytes
    https://github.com/liliangxing/MonkeyCode/releases/download/v26080701/Monkey3.apk
  - MonkeyCode.apk | 29603 bytes
    https://github.com/liliangxing/MonkeyCode/releases/download/v26080701/MonkeyCode.apk
```

三个 APK 都在 Release 里了，任务完成！

---

## 十四、排查错误工具箱（遇到问题先来这里）

### 14.1 工具找不到

```bash
# 检查某个工具在不在 PATH 里
which aapt2
which d8
which apksigner
which javac
which sdkmanager

# 检查环境变量
echo $JAVA_HOME
echo $ANDROID_HOME
echo $PATH
```

> 如果 `which aapt2` 没输出，说明 PATH 里没包含 build-tools 目录。执行：
> ```bash
> export PATH=$JAVA_HOME/bin:$ANDROID_HOME/build-tools/34.0.0:$PATH
> ```

### 14.2 android.jar 找不到

```bash
# 检查文件是否存在
ls -la $ANDROID_HOME/platforms/android-34/android.jar

# 如果不存在，重新安装
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH
yes | sdkmanager "platforms;android-34"
```

### 14.3 SDK 下载卡住/太慢

```bash
# 看目录大小有没有在增长
du -sh $ANDROID_HOME
# 隔几秒再跑一次
du -sh $ANDROID_HOME

# 如果大小不变，说明卡住了
# build-tools 可以直接下载：
curl -sL -o build-tools_r34-linux.zip \
    "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
```

### 14.4 编译报错

```bash
# 看完整错误信息（去掉 2>&1 | tail 等截断）
cd /data/user/work/MonkeyCode/mobile/android-apk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/data/user/work/android-sdk
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/build-tools/34.0.0:$PATH
ANDROID_JAR=$ANDROID_HOME/platforms/android-34/android.jar

# 手动跑 javac 看详细错误
javac -source 11 -target 11 -classpath $ANDROID_JAR \
    -d /tmp/test-classes \
    app/src/main/java/com/monkeyCode/ai/MainActivity.java

# 如果报 "package com.monkeyCode.ai2 does not exist" 之类
# 说明 Java 文件的 package 声明和文件路径不匹配
# 检查：
head -1 build/variant-ai2/app/src/main/java/com/monkeyCode/ai2/MainActivity.java
# 应该输出: package com.monkeyCode.ai2;
```

### 14.5 aapt2 报错

```bash
# 看 aapt2 的详细输出
aapt2 compile --dir app/src/main/res -o /tmp/test-res/ -v

# link 时加 --verbose
aapt2 link -I $ANDROID_JAR --manifest app/src/main/AndroidManifest.xml -v ...
```

### 14.6 签名失败

```bash
# 检查密钥文件是否存在
ls -la build/variant-ai2/build/debug.keystore

# 重新生成密钥
keytool -genkey -keystore /tmp/test.keystore -alias test \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android \
    -dname "CN=Test, OU=Dev, O=Test, L=Beijing, ST=Beijing, C=CN"

# 验证密钥
keytool -list -keystore /tmp/test.keystore -storepass android
```

### 14.7 GitHub API 调用失败

```bash
# 检查 token 是否有效
curl -s -H "Authorization: token 你的TOKEN" \
    https://api.github.com/user | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('用户:', d.get('login', '未知'))
print('消息:', d.get('message', 'OK'))
"

# 检查 release 是否存在
curl -s -H "Authorization: token 你的TOKEN" \
    https://api.github.com/repos/liliangxing/MonkeyCode/releases/tags/v26080701 \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('ID:', d.get('id', '不存在'))"
```

### 14.8 git 推送失败

```bash
# 看远程地址
git remote -v

# 看分支追踪关系
git branch -vv

# 如果推送被拒绝（远程有新提交），先拉取
git pull --rebase origin 260324.1.22
git push origin 260324.1.22
```

---

## 十五、踩过的坑完整记录

按时间顺序记录实际操作中遇到的所有问题，方便你避开。

### 坑 1：sdkmanager 下载 build-tools 卡住

| 项目 | 内容 |
|------|------|
| **现象** | 执行 `sdkmanager "build-tools;34.0.0" ...` 后，命令一直不结束，但 `build-tools/` 目录始终为空。`platforms;android-34` 和 `platform-tools` 装上了 |
| **排查** | 用 `du -sh android-sdk` 看目录大小，发现增长极慢（几分钟才长 6MB） |
| **原因** | 网络不稳定，Google 服务器下载大文件时偶尔会卡 |
| **解决** | 停掉 sdkmanager，直接用 `curl` 下载 build-tools 压缩包（`build-tools_r34-linux.zip`），手动解压到 `build-tools/34.0.0/` 目录 |
| **教训** | sdkmanager 适合一次性装全套，但如果卡住，直接下载压缩包更快更可控 |

### 坑 2：platforms/android-34 目录为空（只有 .installer）

| 项目 | 内容 |
|------|------|
| **现象** | sdkmanager 中断后，`platforms/android-34/` 目录下只有一个 `.installer` 子目录，没有 `android.jar` |
| **排查** | `ls -la android-sdk/platforms/android-34/` 只看到 `.installer` |
| **原因** | sdkmanager 安装过程中被中断（我停掉了卡住的命令），platform 只装了一半 |
| **解决** | 单独再跑一次 `sdkmanager "platforms;android-34"`，这次正常完成了 |
| **教训** | sdkmanager 被中断后可能留下半成品。重新安装同一个组件会自动修复 |

### 坑 3：脚本没有执行权限

| 项目 | 内容 |
|------|------|
| **现象** | 运行 `./build-variant.sh` 报 `zsh:1: permission denied: ./build-variant.sh` |
| **排查** | 用 `ls -la build-variant.sh` 看权限，发现没有 `x`（执行）权限 |
| **原因** | 创建文件后忘了 `chmod +x`，或者 `chmod` 和构建写在同一个命令里，前面的命令出错导致 `chmod` 没执行 |
| **解决** | 单独执行 `chmod +x build-variant.sh build-all.sh` |
| **教训** | 新建的 `.sh` 文件一定要单独执行一次 `chmod +x`，别和其他命令混在一起 |

### 坑 4：验证工具链时 android.jar 不存在

| 项目 | 内容 |
|------|------|
| **现象** | 运行 `ls -la $ANDROID_HOME/platforms/android-34/android.jar` 报 `No such file or directory` |
| **排查** | 这就是坑 2 的表现。`aapt2 version` 和 `d8 --version` 都正常（因为它们是 build-tools 里的），但 `android.jar` 在 platform 里 |
| **解决** | 见坑 2 的解决方案 |
| **教训** | 验证工具链时要检查所有四个东西：`aapt2`、`d8`、`apksigner`、`android.jar`，少一个都不行 |

---

## 十六、常见问题 FAQ

**Q1：我能不能在 Windows 上做？**

可以，但需要装 WSL（Windows Subsystem for Linux）。在 WSL 里按本指南操作即可。不建议用 Git Bash，因为 `apt-get` 等命令在 Git Bash 里用不了。

**Q2：构建出来的 APK 能直接在手机上安装吗？**

能，但因为是 debug 签名（自签名），手机需要开启"允许安装未知来源应用"。正式发布建议用正式签名。

**Q3：三个 App 能同时在一台手机上运行吗？**

能。因为包名不同（`com.monkeyCode.ai`、`com.monkeyCode.ai2`、`com.monkeyCode.ai3`），Android 系统把它们当作三个独立 App。每个 App 有独立的数据存储空间，互不干扰。

**Q4：为什么三个 APK 大小几乎一样？**

因为它们的代码完全相同，只是包名字符串、应用名字符串和签名不同。这些差异只有几个字节，对 APK 大小几乎没有影响。

**Q5：如果想生成更多变体（Monkey4、Monkey5...）怎么办？**

修改 `build-all.sh`，加一行：
```bash
"$DIR/build-variant.sh" ai4 Monkey4 Monkey4.apk "$OUT_DIR"
```
或者单独运行：
```bash
./build-variant.sh ai4 Monkey4 Monkey4.apk
```

**Q6：`SERVER_URL` 那个 `monkeycode-ai.com` 能改吗？**

能改，但改了就连不上 MonkeyCode 服务器了，App 会白屏。除非你有自己的 MonkeyCode 服务器实例，否则不要改。

**Q7：build/ 目录越来越大怎么办？**

`build/` 目录是编译中间产物，可以随时删除。运行 `rm -rf mobile/android-apk/build/` 清理，下次构建会自动重建。`build.sh` 开头就有 `rm -rf "$WORK_DIR"` 保证每次干净构建。

**Q8：GitHub Token 过期了怎么办？**

去 GitHub → Settings → Developer settings → Personal access tokens 重新生成。如果旧的 token 还在命令历史里，记得清除：`history -d 行号`。

---

## 十七、本指南用到的工具逐个说明

| 工具 | 用途 | 本指南在哪用 |
|------|------|-------------|
| `git` | 版本控制，下载/提交代码 | clone、commit、push |
| `curl` | 命令行下载文件、调用 API | 下载 SDK、上传 APK、查 Release |
| `apt-get` | Ubuntu 包管理器 | 安装 Java 17 |
| `unzip` | 解压 zip 文件 | 解压 cmdline-tools、build-tools |
| `python3` | 运行 Python 脚本 | 改身份信息、解析 API 返回 |
| `javac` | Java 编译器 | 编译 MainActivity.java |
| `aapt2` | Android 资源打包工具 | 编译资源、链接 APK |
| `d8` | Dex 编译器 | .class → .dex |
| `apksigner` | APK 签名工具 | 签名、验证签名 |
| `keytool` | 密钥管理工具 | 生成签名密钥 |
| `zip` | 压缩工具 | 把 .dex 塞进 APK |
| `find` | 文件查找 | 定位源文件 |
| `grep` | 文本搜索 | 搜索源码中的关键字 |
| `du` | 查看目录大小 | 排查下载是否卡住 |
| `ls` | 列目录 | 验证文件是否存在 |
| `chmod` | 修改文件权限 | 给脚本加执行权限 |
| `yes` | 不断输出 y | 自动接受 SDK 许可协议 |
| `head` | 看文件开头 | 查看包声明 |

---

## 十八、完整命令速查表（从头到尾复制粘贴版）

> 以下命令按顺序排列，把 `你的TOKEN` 替换成你自己的 GitHub Token，从头到尾可以跑通整个流程。

```bash
# ===== 0. 准备工作目录 =====
cd /data/user/work

# ===== 1. 检查现有工具 =====
git --version && java -version 2>&1 && python3 --version

# ===== 2. 克隆仓库 =====
git clone https://你的TOKEN@github.com/liliangxing/MonkeyCode.git
cd MonkeyCode
git log --oneline -3    # 确认 1a60b21a 在 HEAD

# ===== 3. 安装 Java 17 =====
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-17-openjdk-headless
/usr/lib/jvm/java-17-openjdk-amd64/bin/java -version

# ===== 4. 下载 Android cmdline-tools =====
cd /data/user/work
curl -sL -o cmdline-tools.zip \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
mkdir -p android-sdk/cmdline-tools
unzip -q cmdline-tools.zip -d android-sdk/cmdline-tools
mv android-sdk/cmdline-tools/cmdline-tools android-sdk/cmdline-tools/latest

# ===== 5. 用 sdkmanager 安装 platform 和 platform-tools =====
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/data/user/work/android-sdk
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH
yes | sdkmanager --licenses >/dev/null 2>&1
sdkmanager "platforms;android-34" "platform-tools"

# ===== 6. 手动安装 build-tools（避免 sdkmanager 卡住）=====
curl -sL -o build-tools_r34-linux.zip \
    "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
unzip -q build-tools_r34-linux.zip -d bt-tmp
mkdir -p android-sdk/build-tools/34.0.0
cp -r bt-tmp/android-14/* android-sdk/build-tools/34.0.0/
rm -rf bt-tmp

# ===== 7. 验证工具链 =====
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/build-tools/34.0.0:$PATH
aapt2 version && d8 --version && apksigner --version
ls -la $ANDROID_HOME/platforms/android-34/android.jar

# ===== 8. 创建构建脚本（见第九节，此处省略文件内容）=====
# 把 build-variant.sh 和 build-all.sh 的内容写入对应文件
cd /data/user/work/MonkeyCode/mobile/android-apk
chmod +x build-variant.sh build-all.sh

# ===== 9. 一键构建三个 APK =====
./build-all.sh /data/user/work/apks

# ===== 10. 验证 APK 身份 =====
for apk in MonkeyCode Monkey2 Monkey3; do
    echo "=== $apk.apk ==="
    aapt2 dump badging /data/user/work/apks/$apk.apk 2>/dev/null | grep -E "^package:|application-label:"
done

# ===== 11. 提交到代码仓库 =====
cd /data/user/work/MonkeyCode
git add mobile/android-apk/build-variant.sh mobile/android-apk/build-all.sh
git commit -m "feat(android-apk): one-click multi-variant APK builder (Monkey2/Monkey3)"
git push origin 260324.1.22

# ===== 12. 上传 APK 到 GitHub Release =====
cd /data/user/work/apks
TOKEN="你的TOKEN"
REL_ID=366754264
for f in Monkey2.apk Monkey3.apk; do
    curl -s -X POST \
      -H "Authorization: token $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/vnd.android.package-archive" \
      --data-binary @"$f" \
      "https://uploads.github.com/repos/liliangxing/MonkeyCode/releases/$REL_ID/assets?name=$f"
done

# ===== 13. 确认发布结果 =====
curl -s -H "Authorization: token $TOKEN" \
    https://api.github.com/repos/liliangxing/MonkeyCode/releases/$REL_ID \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Release:', d['name'])
for a in d['assets']:
    print(f'  {a[\"name\"]} - {a[\"browser_download_url\"]}')
"
```

---

> **文档结束**。如有疑问，对照"排查错误工具箱"和"踩过的坑"两节。核心思路就一句话：**复制源码 → 改包名和应用名 → 编译签名 → 上传发布**。
