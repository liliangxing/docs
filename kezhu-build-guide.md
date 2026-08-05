# kezhu Android APK 构建配置完整指南

> 适用对象：技术基础一般，对命令行不熟悉的开发者
> 目标：从零开始配置 GitHub Actions，自动构建 kezhu Android APK
> 最后更新：2026-08-02

---

## 目录

1. [项目背景](#1-项目背景)
2. [最终效果展示](#2-最终效果展示)
3. [从零开始的完整步骤](#3-从零开始的完整步骤)
4. [每一步的详细解释（大白话）](#4-每一步的详细解释大白话)
5. [踩过的坑和避坑指南](#5-踩过的坑和避坑指南)
6. [构建好的 APK 怎么用](#6-构建好的-apk-怎么用)
7. [常见问题 FAQ](#7-常见问题-faq)
8. [附录：最终可用的 workflow 文件](#8-附录最终可用的-workflow-文件)

---

## 1. 项目背景

### 1.1 这是什么项目？

- **kezhu** 是一个 Android 应用（APK 文件），本质上是一个"浏览器外壳"
- 它打开手机浏览器，显示 `time24.cn` 这个网站
- 网站上有一些佛教音频（MP3 格式），用户可以下载播放

### 1.2 为什么要配置自动构建？

原来 APK 是用 Android Studio 手动点击"生成"按钮打出来的。现在我们想让 GitHub 服务器自动帮我们打包，好处是：
- 不用开 Android Studio，更新代码就自动出 APK
- 别人也能从网上下载最新的 APK

---

## 2. 最终效果展示

配置成功后，你将在 GitHub 上看到：

```
Build APK · liliangxing/kezhu
✓ Build APK  completed success  55s
```

然后 GitHub 服务器会产出 `app-debug.apk`（约 2.1MB 的文件），可以直接下载安装到手机。

### 2.1 构建成功的截图

```
BUILD SUCCESSFUL in 55s
3 actionable tasks: 3 executed
```

---

## 3. 从零开始的完整步骤

### 3.1 环境检查

在开始之前，先检查你的工具是否齐全：

```bash
# 检查 Git 是否安装
git --version
# 输出类似：git version 2.39.0

# 检查是否安装了 GitHub CLI（和 GitHub 网站对话的工具）
gh --version
# 输出类似：gh version 2.45.0

# 检查是否已登录 GitHub
gh auth status
# 输出应该包含：✓ Logged in to github.com account xxx
```

如果没有安装或者没登录，先处理这些前置条件。

### 3.2 获取项目代码

```bash
# 把代码从 GitHub 复制到本地
git clone https://github.com/liliangxing/kezhu.git
cd kezhu
```

### 3.3 查看项目结构

```bash
ls -la
```

应该看到这样的目录结构（大致）：

```
kezhu/
├── app/                    ← 安卓应用主要代码在这里
│   ├── build.gradle        ← 应用构建配置
│   └── src/
│       └── main/
│           ├── AndroidManifest.xml
│           ├── java/       ← Java 源代码
│           └── res/        ← 图片、布局文件
├── build.gradle            ← 顶层构建配置
├── gradle/                 ← Gradle 包装器目录
│   └── wrapper/
│       └── gradle-wrapper.properties
├── gradle.properties
├── settings.gradle
└── .github/                ← GitHub Actions 配置
    └── workflows/          ← 自动化脚本在这里
```

### 3.4 创建 GitHub Actions 工作流文件

新建文件：`.github/workflows/build.yml`

```bash
# 创建目录（如果不存在）
mkdir -p .github/workflows

# 创建文件并编辑
nano .github/workflows/build.yml
```

> 📝 小贴士：Windows 用户可以用记事本，Mac 用户可以用文本编辑。在服务器上 `nano` 是最简单的编辑器，用 Ctrl+O 保存，Ctrl+X 退出。

### 3.5 编写 workflow 内容

把下面的内容完整复制进去（后面会有详细解释）：

```yaml
name: Build APK

# 什么时候触发自动构建
on:
  push:
    branches: [ main, master ]  # 代码推送到 main 或 master 分支时
  workflow_dispatch:            # 也支持手动在 GitHub 网页上点按钮触发

# 环境变量
env:
  ANDROID_HOME: /usr/local/lib/android/sdk

jobs:
  build:
    runs-on: ubuntu-latest       # 使用 Ubuntu 系统的服务器

    steps:
    # 第 1 步：拉取代码
    - name: Checkout code
      uses: actions/checkout@v4

    # 第 2 步：安装 JDK 17（给 Android SDK 工具用）
    - name: Set up JDK 17 (for Android SDK Tools)
      uses: actions/setup-java@v4
      with:
        java-version: '17'
        distribution: 'temurin'

    # 第 3 步：接受 Android SDK 许可协议
    - name: Accept Android SDK licenses
      run: |
        yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses

    # 第 4 步：安装需要的 Android SDK 组件
    - name: Install Android SDK Platform 27 + Build-tools
      run: |
        yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platforms;android-27" "build-tools;27.0.3"

    # 第 5 步：安装 JDK 8（给 Gradle 构建用）
    - name: Set up JDK 8 (for Gradle 5.4.1 build)
      uses: actions/setup-java@v4
      with:
        java-version: '8'
        distribution: 'temurin'

    # 第 6 步：缓存 Gradle 依赖
    - name: Cache Gradle
      uses: actions/cache@v4
      with:
        path: |
          ~/.gradle/caches
          ~/.gradle/wrapper
        key: ${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle*', '**/gradle/wrapper/gradle-wrapper.properties') }}
        restore-keys: |
          ${{ runner.os }}-gradle-

    # 第 7 步：下载 Gradle（项目里没有 gradlew）
    - name: Download and set up Gradle 5.4.1
      run: |
        wget -q https://services.gradle.org/distributions/gradle-5.4.1-bin.zip -O /tmp/gradle.zip
        unzip -q /tmp/gradle.zip -d /opt/
        echo "/opt/gradle-5.4.1/bin" >> $GITHUB_PATH

    # 第 8 步：构建 APK
    - name: Build Debug APK
      run: gradle assembleDebug --stacktrace

    # 第 9 步：上传构建产物
    - name: Upload APK Artifact
      uses: actions/upload-artifact@v4
      with:
        name: kezhu-apk
        path: app/build/outputs/apk/debug/app-debug.apk
        retention-days: 30
```

### 3.6 修改项目依赖配置

打开项目根目录的 `build.gradle` 文件，修改仓库地址：

```bash
nano build.gradle
```

找到 `buildscript { repositories { ... } }` 和 `allprojects { repositories { ... } }` 两处，

把原来的：
```groovy
repositories {
    google()
    jcenter()
}
```

改为：
```groovy
repositories {
    maven { url 'https://maven.aliyun.com/repository/central' }
    maven { url 'https://maven.aliyun.com/repository/google' }
    maven { url 'https://maven.aliyun.com/repository/public' }
    google()
    mavenCentral()
}
```

> 🔑 为什么？因为 JCenter 已经于 2021 年关闭，如果不改，编译时会报"找不到依赖"错误。

### 3.7 提交代码并推送

```bash
# 添加所有修改的文件
git add .github/workflows/build.yml build.gradle

# 提交，写清楚做了什么
git commit -m "ci: add GitHub Actions workflow for APK build"

# 推送到 GitHub（触发自动构建）
git push origin master
```

### 3.8 监控构建进度

```bash
# 查看最近的构建任务
gh run list --limit 3

# 或者看更详细的信息
gh run view <运行编号>

# 只看报错（如果有）
gh run view <运行编号> --log-failed
```

### 3.9 下载构建好的 APK

构建成功后，下载 APK 文件：

```bash
# 创建下载目录并下载
mkdir -p ~/apk_downloads
gh run download <运行编号> --name kezhu-apk --dir ~/apk_downloads

# 检查文件
ls -la ~/apk_downloads/
# 应该看到：app-debug.apk（约 2MB）
```

### 3.10 创建 Release（可选）

如果想给别人分享带版本号的下载链接：

```bash
# 创建 Release
gh release create v1.0.0 \
  --title "kezhu v1.0.0" \
  --notes "自动构建的 APK" \
  ~/apk_downloads/app-debug.apk
```

---

## 4. 每一步的详细解释（大白话）

### 4.1 为什么要用 GitHub Actions？

打个比方：
- **手动构建** = 你自己在厨房做饭。每次都要买菜、切菜、炒菜。
- **GitHub Actions** = 雇了个机器人厨师。你只要把食材（代码）放进冰箱（GitHub），机器人就自动帮你做好饭（APK）端出来。

### 4.2 JDK 8 和 JDK 17 是什么意思？

JDK 是 Java 开发工具包，就像不同版本的扳手。

- **JDK 8**：老版本，但这个项目用的 Gradle 5.4.1 只兼容 JDK 8（就像老汽车只能加 92 号油）
- **JDK 17**：新版本，新的 Android SDK 工具需要它才能运行

> 💡 你可以理解成：项目太老了，只能用老版本的构建工具，但新的 Android SDK 需要新版本的 JDK，所以两个都要装。

### 4.3 Gradle 和 gradlew 是什么？

- **Gradle**：构建工具，像一个机器人厨师的菜谱执行器。它读取项目配置，一步步执行编译、打包。
- **gradlew**：Gradle 的手柄/遥控器。通常项目里会自带一个 `gradlew` 文件，这样不用全局安装 Gradle。
- **本项目的问题**：项目里没有 `gradlew` 文件！所以 workflow 里要额外下载 Gradle。

### 4.4 sdkmanager --licenses 是什么意思？

Android SDK 的使用需要许可协议。就像安装软件要点"我同意"。

命令 `sdkmanager --licenses` 就是一次性把 Android SDK 所有许可都自动点了同意。

### 4.5 阿里云镜像是什么？

本来 Android 依赖默认从 Google 和 JCenter 下载。但：
- JCenter 已经关了（公司倒闭了）
- Google 在国内访问慢/不稳定

所以加阿里云镜像（国内服务器），速度快很多，就像把下载源从国外网站换成国内镜像站。

### 4.6 assembleDebug 是什么意思？

```
assemble = 组装
Debug = 调试版
```

就是"组装出一个调试版本的 APK"。调试版可以直接安装测试，只是没有做正式发布的一些优化（比如代码混淆）。

---

## 5. 踩过的坑和避坑指南

### 坑 1：actions/cache@v2 和 upload-artifact@v2 已废弃

**错误现象**：
```
This request has been automatically failed because it uses a deprecated version 
of `actions/cache: v2`. Please update your workflow to use v3/v4
```

**原因**：GitHub 不再支持 v2 版本的缓存动作。

**解决**：把所有 `@v2` 改成 `@v4`。

```yaml
# ❌ 错误（会失败）
uses: actions/checkout@v2
uses: actions/cache@v2

# ✅ 正确
uses: actions/checkout@v4
uses: actions/cache@v4
```

### 坑 2：setup-android action 需要 JDK 17

**错误现象**：
```
Error: The process '.../sdkmanager' failed with exit code 1
This tool requires JDK 17 or later. Your version was detected as 1.8.0_502.
```

**原因**：新版 Android SDK 的 cmdline-tools 用 JDK 17 编译的，需要在 JDK 17 环境运行。但项目构建又要用 JDK 8。

**解决**：不用 setup-android action，分两步走：
1. 先设 JDK 17，运行 sdkmanager（接受许可、安装 SDK 组件）
2. 再设 JDK 8，运行 Gradle 构建

```yaml
# ✅ 正确做法
- name: Set up JDK 17 (for Android SDK Tools)    # 给 sdkmanager 用
  uses: actions/setup-java@v4
  with:
    java-version: '17'

- name: Accept Android SDK licenses
  run: yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses

- name: Set up JDK 8 (for Gradle build)           # 给 Gradle 用
  uses: actions/setup-java@v4
  with:
    java-version: '8'
```

### 坑 3：项目里没有 gradlew

**错误现象**：
```
chmod: cannot access 'gradlew': No such file or directory
```

**原因**：.gradle 的 gradlew 是随项目提交的，但本项目没有提交这个文件。

**解决**：workflow 里手动下载 Gradle：

```yaml
- name: Download and set up Gradle 5.4.1
  run: |
    wget -q https://services.gradle.org/distributions/gradle-5.4.1-bin.zip -O /tmp/gradle.zip
    unzip -q /tmp/gradle.zip -d /opt/
    echo "/opt/gradle-5.4.1/bin" >> $GITHUB_PATH
```

> 💡 也可以手动把 gradlew 提交到项目里，以后就不用每次下载了。

### 坑 4：JCenter 依赖失效

**错误现象**：
```
Could not find com.tencent.mm.opensdk:wechat-sdk-android-without-mta:5.3.1
Could not find com.zhy:okhttputils:2.6.2
```

**原因**：JCenter 仓库 2021 年底就关了。项目依赖的微信 SDK 和 OkHttpUtils 原来是从 JCenter 下载的。

**解决**：在 `build.gradle` 里把 `jcenter()` 替换成阿里云镜像 + Maven Central：

```groovy
repositories {
    maven { url 'https://maven.aliyun.com/repository/central' }
    maven { url 'https://maven.aliyun.com/repository/google' }
    maven { url 'https://maven.aliyun.com/repository/public' }
    google()
    mavenCentral()
}
```

### 坑 5：JAVA_HOME 环境变量没有正确设置（踩过的隐形坑）

**解释**：当同时用两个版本的 JDK 时，第二个 `setup-java` 会自动覆盖 `JAVA_HOME` 环境变量，指向 JDK 8。这正好符合我们后面构建的需求。

但如果顺序反了（先 JDK 8 再 JDK 17），JAVA_HOME 会指向 JDK 8，导致后面的 sdkmanager 运行失败。

**正确顺序**：先 JDK 17（sdkmanager）→ 再 JDK 8（Gradle 构建）

### 坑 6：GitHub 网络不稳定

**错误现象**：
```
GnuTLS recv error (-110): The TLS connection was non-properly terminated
Failed to connect to github.com port 443 after 130000 ms
```

**原因**：国内访问 GitHub 有时不稳定，TLS 连接超时被重置。

**解决**：重试几次就好，或者设置 Git 用 HTTP/1.1：

```bash
git config http.version HTTP/1.1
git push origin master
```

### 坑 7：FTP 服务器速率限制

**错误现象**：
```
curl: (67) Access denied: 530
```

**原因**：Windows FTP 服务器同一 IP 短时间连太多次就会锁定。

**解决**：等 5-10 分钟自动恢复，或者换一个工具（如 FileZilla）。

---

## 6. 构建好的 APK 怎么用

### 6.1 直接安装到安卓手机

方法 1：从 GitHub Release 页面下载
1. 打开 https://github.com/liliangxing/kezhu/releases
2. 点击下载 `app-debug.apk`
3. 在手机上允许"安装未知来源应用"

方法 2：从 FTP 下载
- 访问 `xingli.w58.cndns5.com/kezhu.apk`

### 6.2 APK 是什么？

APK 就是安卓应用的安装包，相当于 Windows 上的 `.exe` 文件。双击（或点击）就能安装。

---

## 7. 常见问题 FAQ

**Q：构建需要多长时间？**
A：首次约 2-3 分钟（要下载依赖），之后约 40-60 秒（有缓存）。

**Q：构建失败怎么办？**
A：用 `gh run view <编号> --log-failed` 看报错信息，对照第 5 节的"踩坑指南"排查。

**Q：每次推送代码都自动构建吗？**
A：是的，workflow 里配置了推送到 main/master 分支就自动触发。也可以去 GitHub Actions 页面手动点"Run workflow"。

**Q：APK 会过期吗？**
A：GitHub Actions 产物默认保留 30 天。Release 里的 APK 永久保留。

**Q：我可以修改 APP 名字或图标吗？**
A：可以！APP 配置在 `app/src/main/AndroidManifest.xml` 和 `app/src/main/res/` 目录下。

---

## 8. 附录：最终可用的 workflow 文件

完整的 `.github/workflows/build.yml` 文件内容（保存好备用）：

```yaml
name: Build APK

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

env:
  ANDROID_HOME: /usr/local/lib/android/sdk

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up JDK 17 (for Android SDK Tools)
      uses: actions/setup-java@v4
      with:
        java-version: '17'
        distribution: 'temurin'

    - name: Accept Android SDK licenses
      run: |
        yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses

    - name: Install Android SDK Platform 27 + Build-tools
      run: |
        yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platforms;android-27" "build-tools;27.0.3"

    - name: Set up JDK 8 (for Gradle 5.4.1 build)
      uses: actions/setup-java@v4
      with:
        java-version: '8'
        distribution: 'temurin'

    - name: Cache Gradle
      uses: actions/cache@v4
      with:
        path: |
          ~/.gradle/caches
          ~/.gradle/wrapper
        key: ${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle*', '**/gradle/wrapper/gradle-wrapper.properties') }}
        restore-keys: |
          ${{ runner.os }}-gradle-

    - name: Download and set up Gradle 5.4.1
      run: |
        wget -q https://services.gradle.org/distributions/gradle-5.4.1-bin.zip -O /tmp/gradle.zip
        unzip -q /tmp/gradle.zip -d /opt/
        echo "/opt/gradle-5.4.1/bin" >> $GITHUB_PATH

    - name: Build Debug APK
      run: gradle assembleDebug --stacktrace

    - name: Upload APK Artifact
      uses: actions/upload-artifact@v4
      with:
        name: kezhu-apk
        path: app/build/outputs/apk/debug/app-debug.apk
        retention-days: 30
```

---

## 文档维护

- 作者：CatPaw AI 助手
- 适用项目：github.com/liliangxing/kezhu
- 适用环境：GitHub Actions (ubuntu-latest)
- 最后更新：2026-08-02
