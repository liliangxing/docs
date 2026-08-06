# TRAE CN3 APK 逆向修改、Smali 转 Java、重新打包完整指南

> 适用对象：技术基础一般、对命令行不熟悉的开发者或 AI Agent
> 目标：从原始 APK 出发，修改 Smali 代码，还原成可读 Java 源码，再重新打包成功能一模一样的 APK
> 最后更新：2026-08-06
> 结论先行：**整个过程分三大阶段——APK 解包修改、Smali 转 Java、重新打包签名。最大的坑是签名方案（必须 v2/v3）和 Smali 寄存器类型冲突（会导致 VerifyError 闪退）。**

---

## 目录

1. [问题背景：我们要干什么](#1-问题背景我们要干什么)
2. [环境准备：需要装哪些工具](#2-环境准备需要装哪些工具)
3. [第一步：APK 解包（把 APK 拆成文件夹）](#3-第一步apk-解包把-apk-拆成文件夹)
4. [第二步：理解 Smali 代码结构](#4-第二步理解-smali-代码结构)
5. [第三步：修改 Smali 代码（注入新功能）](#5-第三步修改-smali-代码注入新功能)
6. [第四步：APK 重新打包](#6-第四步apk-重新打包)
7. [第五步：APK 签名（最大的坑）](#7-第五步apk-签名最大的坑)
8. [第六步：VerifyError 避坑指南](#8-第六步verifyerror-避坑指南)
9. [第七步：Smali 转可读 Java 源码](#9-第七步smali-转可读-java-源码)
10. [第八步：Java 编译回 Smali（逆向验证）](#10-第八步java-编译回-smali逆向验证)
11. [第九步：全量反编译（jadx 批量处理）](#11-第九步全量反编译jadx-批量处理)
12. [第十步：验证与测试](#12-第十步验证与测试)
13. [避坑清单（失败经验总结）](#13-避坑清单失败经验总结)
14. [完整命令速查表](#14-完整命令速查表)
15. [调试排查常用命令](#15-调试排查常用命令)
16. [工具与技能说明](#16-工具与技能说明)
17. [附录：关键文件说明](#17-附录关键文件说明)

---

## 1. 问题背景：我们要干什么

### 1.1 一句话说明

我们有一个 Android APK（TRAE CN3 应用），需要：
1. **解包**它，修改里面的代码（注入"对话提取"功能）
2. 把修改后的 Smali 代码**还原成人类可读的 Java 源码**
3. **重新打包**成 APK，功能跟原来一模一样，不能闪退

### 1.2 为什么要这么做

- APK 是编译后的二进制文件，不能直接改代码
- 需要用工具反编译成 Smali（类似汇编语言），修改后再编译回去
- Smali 代码很难读，所以要还原成 Java 方便理解和维护
- 重新打包后必须正确签名，否则手机装不上或闪退

### 1.3 整体流程图

```
原始 APK
  ↓ apktool d (解包)
解包后的文件夹 (Smali代码 + 资源文件)
  ↓ 修改 Smali 文件
修改后的 Smali
  ↓ apktool b (重新打包)
未签名 APK
  ↓ uber-apk-signer (签名)
签名后的 APK (可安装)
  ↓ jadx (反编译)
可读 Java 源码
```

---

## 2. 环境准备：需要装哪些工具

### 2.1 工具清单

| 工具名 | 用途 | 版本要求 | 安装方式 |
|--------|------|---------|---------|
| Java (JDK) | 运行各种 Java 工具 | 11+ | 系统包管理器 |
| apktool | APK 解包/打包 | 最新版 | 下载 jar 文件 |
| baksmali | dex 转 Smali | 最新版 | 下载 jar 文件 |
| smali | Smali 转 dex | 最新版 | 下载 jar 文件 |
| d8 | Java class 转 dex | 最新版 | Android SDK 或下载 |
| uber-apk-signer | APK 签名 | 最新版 | 下载 jar 文件 |
| jadx | dex/Smali 转 Java | 1.5.0+ | 下载 zip 包 |
| git | 提交代码到仓库 | 2.x | 系统包管理器 |

### 2.2 安装命令

```bash
# 1. 检查 Java 是否已安装
java -version
# 期望输出：openjdk version "11.0.x" 或更高

# 2. 如果没有 Java，安装它
apt-get update && apt-get install -y openjdk-11-jdk

# 3. 检查 git
git --version
# 如果没有，安装：apt-get install -y git

# 4. 下载 apktool（APK 解包打包工具）
# 方法一：直接安装
apt-get install -y apktool
# 方法二：下载 jar（推荐，版本更新）
wget https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar -O /usr/local/bin/apktool.jar
# 创建启动脚本
echo '#!/bin/bash' > /usr/local/bin/apktool
echo 'java -jar /usr/local/bin/apktool.jar "$@"' >> /usr/local/bin/apktool
chmod +x /usr/local/bin/apktool

# 5. 下载 baksmali 和 smali（dex <-> smali 转换）
wget https://github.com/google/smali/releases/download/v2.5.2/baksmali-2.5.2.jar -O /data/user/work/baksmali.jar
wget https://github.com/google/smali/releases/download/v2.5.2/smali-2.5.2.jar -O /data/user/work/smali.jar

# 6. 下载 d8（Java class 转 dex）
# d8 通常在 Android SDK 中，也可以单独下载
# 如果有 Android SDK：路径在 $ANDROID_HOME/build-tools/版本号/d8
# 或者从 Android SDK 下载 build-tools

# 7. 下载 uber-apk-signer（APK 签名工具，支持 v2/v3 签名）
wget https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar -O /data/user/work/uber-apk-signer.jar

# 8. 下载 jadx（反编译工具，把 dex/smali 转成 Java）
wget https://github.com/skylot/jadx/releases/download/v1.5.0/jadx-1.5.0.zip -O /tmp/jadx.zip
unzip /tmp/jadx.zip -d /data/user/work/jadx_tool
# 测试安装
/data/user/work/jadx_tool/bin/jadx --version
# 期望输出：1.5.0
```

### 2.3 验证所有工具

```bash
# 一次性检查所有工具
echo "=== Java ===" && java -version 2>&1
echo "=== apktool ===" && apktool --version 2>&1
echo "=== baksmali ===" && java -jar /data/user/work/baksmali.jar --version 2>&1
echo "=== uber-apk-signer ===" && java -jar /data/user/work/uber-apk-signer.jar --version 2>&1
echo "=== jadx ===" && /data/user/work/jadx_tool/bin/jadx --version 2>&1
echo "=== git ===" && git --version
```

### 2.4 创建工作目录

```bash
# 创建工作目录（所有操作都在这里进行）
mkdir -p /data/user/work
mkdir -p /workspace
```

> **为什么要分两个目录？**
> - `/data/user/work` 是工作目录，放工具、临时文件、解包项目
> - `/workspace` 是输出目录，最终交付的 APK 和文件放这里
> - 这样分开是为了不让临时文件污染最终交付物

---

## 3. 第一步：APK 解包（把 APK 拆成文件夹）

### 3.1 为什么要解包

APK 本质上是一个 ZIP 压缩包，里面包含：
- `classes*.dex` — 编译后的代码（类似 Java 的 .class，但格式不同）
- `resources.arsc` — 编译后的资源索引
- `res/` — 资源文件（图片、布局等）
- `AndroidManifest.xml` — 应用配置文件
- `lib/` — native 库（.so 文件）

解包后，dex 文件会被转换成 Smali 代码（人类可读的格式），方便修改。

### 3.2 解包命令

```bash
# 把 APK 解包到一个文件夹
apktool d /path/to/original.apk -o /data/user/work/trae_cn3_decoded -f

# 参数说明：
# d        — decode（解包）
# -o       — output（输出到哪个文件夹）
# -f       — force（如果文件夹已存在，强制覆盖）
```

### 3.3 解包后的目录结构

```bash
ls /data/user/work/trae_cn3_decoded/
```

期望输出：
```
AndroidManifest.xml   ← 应用配置
apktool.yml           ← apktool 的配置文件（记住版本号等）
assets/               ← 静态资源
build/                ← 构建缓存（apktool 自动生成）
lib/                  ← native 库
original/             ← 原始的 META-INF（签名信息）
res/                  ← 资源文件
smali/                ← 第一个 dex 的 Smali 代码
smali_classes2/       ← 第二个 dex 的 Smali 代码
smali_classes3/       ← 第三个 dex 的 Smali 代码
...                   ← 可能有多个 smali_classes 文件夹
smali_classes9/       ← 第九个 dex 的 Smali 代码（我们的自定义代码在这里）
unknown/              ← apktool 不认识的文件
```

### 3.4 查看代码结构

```bash
# 看看有多少个 Smali 文件
find /data/user/work/trae_cn3_decoded -name "*.smali" | wc -l
# 输出示例：67895

# 看看 smali_classes9 里面有什么（我们自定义的代码）
find /data/user/work/trae_cn3_decoded/smali_classes9 -name "*.smali" | head -20

# 找到我们注入的代码所在目录
find /data/user/work/trae_cn3_decoded -path "*/conversation/extract/*.smali" | sort
```

> **关键说明：为什么有多个 smali_classes 文件夹？**
> Android 一个 dex 文件最多容纳 65536 个方法。大应用方法数远超这个限制，所以拆成多个 dex 文件。apktool 解包时，每个 dex 对应一个 smali_classes 文件夹。`smali` 是第一个 dex，`smali_classes2` 是第二个，以此类推。

---

## 4. 第二步：理解 Smali 代码结构

### 4.1 Smali 是什么

Smali 是 Android dex 字节码的人类可读表示形式，类似 Java 的字节码。语法举例：

```smali
# 定义一个类
.class public Lcom/example/MyClass;
.super Ljava/lang/Object;

# 定义一个方法
.method public doSomething(Ljava/lang/String;)V
    .registers 2  # 这个方法用 2 个寄存器

    # 调用 System.out.println("Hello")
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "Hello"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V

    return-void
.end method
```

### 4.2 关键语法速查

| Smali 语法 | Java 等价 | 说明 |
|-----------|----------|------|
| `.class Lcom/pkg/Name;` | `package com.pkg; class Name` | 类声明 |
| `.super Ljava/lang/Object;` | `extends Object` | 父类 |
| `.method` / `.end method` | `{ }` | 方法定义 |
| `.registers N` | — | 方法使用 N 个寄存器 |
| `v0, v1, v2...` | 局部变量 | 寄存器（类似变量） |
| `p0, p1, p2...` | this, 参数1, 参数2 | 参数寄存器 |
| `const-string v0, "text"` | `String v0 = "text"` | 字符串常量 |
| `invoke-virtual {v0, v1}` | `v0.method(v1)` | 调用方法 |
| `invoke-static {v0}` | `ClassName.method(v0)` | 调用静态方法 |
| `move-result-object v0` | `v0 = 上面方法的结果` | 获取返回值 |
| `if-eqz v0, :label` | `if (v0 == null) goto label` | 空判断跳转 |
| `return-void` | `return` | 无返回值 |

### 4.3 查看目标代码

```bash
# 查看我们要修改的文件
cat /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ExtractHelper.smali | head -50
```

---

## 5. 第三步：修改 Smali 代码（注入新功能）

### 5.1 我们要做什么修改

在这个项目中，我们注入了 4 个自定义类：

| 类名 | 作用 | 所在路径 |
|------|------|---------|
| `ExtractHelper` | 对话提取核心逻辑 | `smali_classes9/.../extract/ExtractHelper.smali` |
| `ApiMessageFetcher` | 从服务器 API 拉取消息 | `smali_classes9/.../extract/ApiMessageFetcher.smali` |
| `FileLogger` | 文件日志工具 | `smali_classes9/.../extract/FileLogger.smali` |
| `GitHubPusher` | 推送到 GitHub 仓库 | `smali_classes9/.../extract/GitHubPusher.smali` |

### 5.2 如何修改 Smali 文件

直接用文本编辑器修改 `.smali` 文件即可。修改时注意：

1. **寄存器不能跨类型复用**（详见第六步避坑）
2. **方法签名必须一致**（方法名、参数类型、返回类型）
3. **catch 块必须捕获 Throwable**（不是 Exception）

### 5.3 在调用处注入 Hook

需要找到原有的代码调用点，插入我们的功能调用：

```bash
# 搜索哪些文件引用了 ExtractHelper
grep -rn "ExtractHelper" /data/user/work/trae_cn3_decoded/smali*/ --include="*.smali" | grep -v "extract/"
```

期望输出：
```
smali_classes5/.../TaskFragment.smali:725: sget-object v5, Lcom/bytedance/trae/conversation/extract/ExtractHelper;->INSTANCE:...
smali_classes5/.../ConversationActivity$initTitleBar$3$1.smali:304: sget-object v2, Lcom/bytedance/trae/conversation/extract/ExtractHelper;->INSTANCE:...
```

> **为什么要知道调用点？**
> 修改后重新打包，必须确保调用点的代码没有变。如果调用点找不到你的类，运行时会直接闪退（ClassNotFoundException）。

---

## 6. 第四步：APK 重新打包

### 6.1 打包命令

```bash
# 把修改后的文件夹重新打包成 APK
apktool b /data/user/work/trae_cn3_decoded -o /workspace/trae_cn3_unsigned.apk

# 参数说明：
# b        — build（打包）
# -o       — output（输出到哪个文件）
```

### 6.2 打包成功输出

期望输出：
```
I: Smaling smali_classes7 folder into classes7.dex...
I: Smaling smali_classes8 folder into classes8.dex...
I: Smaling smali_classes9 folder into classes9.dex...
I: Building apk file...
I: Importing assets...
I: Importing lib...
I: Importing unknown files...
I: Built apk into: /workspace/trae_cn3_unsigned.apk
```

### 6.3 打包失败怎么办

```bash
# 如果报错 "could not find smali file"
# 检查 smali 文件路径是否正确
find /data/user/work/trae_cn3_decoded -name "*.smali" | wc -l

# 如果报错 "invalid smali"
# 检查 smali 语法是否正确
# 常见错误：少了 .end method、寄存器编号超出范围等

# 清理构建缓存重新打包
rm -rf /data/user/work/trae_cn3_decoded/build
apktool b /data/user/work/trae_cn3_decoded -o /workspace/trae_cn3_unsigned.apk
```

> **为什么要清理 build 缓存？**
> apktool 会缓存上次构建的中间文件。如果你修改了 Smali 文件但缓存没更新，打包时可能用的还是旧代码。删除 `build` 文件夹可以强制全量重新构建。

---

## 7. 第五步：APK 签名（最大的坑）

### 7.1 为什么签名是最重要的步骤

**这是整个过程中最大的坑！** Android 7.0+ 要求 APK 必须包含 v2 或 v3 签名。如果只有 v1 签名（老的 jarsigner 方式），安装到手机后会出现：

- **"package info is null"** 错误
- 应用安装后立即闪退
- `getPackageInfo()` 返回 null

### 7.2 错误方法（绝对不要用）

```bash
# ❌ 错误！jarsigner 只生成 v1 签名，Android 14 无法识别
jarsigner -keystore xxx.keystore app.apk alias
```

### 7.3 正确方法：使用 uber-apk-signer

```bash
# ✅ 正确！生成 v2+v3 签名 + zipalign 对齐
java -jar /data/user/work/uber-apk-signer.jar \
  -a /workspace/trae_cn3_unsigned.apk \
  --out /workspace \
  --ks /data/user/work/trae3.keystore \
  --ksAlias trae3 \
  --ksPass trae123 \
  --ksKeyPass trae123 \
  --allowResign
```

### 7.4 参数详解

| 参数 | 含义 | 为什么要这个值 |
|------|------|--------------|
| `-a` | 输入 APK 文件路径 | 指向未签名的 APK |
| `--out` | 输出目录 | 签名后的 APK 输出到这里 |
| `--ks` | keystore 文件路径 | 签名证书文件 |
| `--ksAlias` | 证书别名 | keystore 中的条目名 |
| `--ksPass` | keystore 密码 | 解锁 keystore 文件 |
| `--ksKeyPass` | key 密码 | 解锁私钥 |
| `--allowResign` | 允许重新签名 | 如果 APK 已有签名，覆盖它 |

### 7.5 创建 Keystore（首次需要）

如果还没有 keystore 文件，需要创建一个：

```bash
keytool -genkey -v \
  -keystore /data/user/work/trae3.keystore \
  -storepass trae123 \
  -alias trae3 \
  -keypass trae123 \
  -keyalg RSA -keysize 2048 \
  -validity 10000 \
  -dname "CN=TRAE3, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN"
```

> **注意：keystore 一旦创建，证书指纹就固定了。如果换了 keystore，用户必须先卸载旧版本才能安装新版本（因为签名不一致）。所以一定要保管好 keystore 文件和密码！**

### 7.6 验证签名

```bash
# 验证签名是否正确
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v22.apk -y
```

期望输出（关键部分）：
```
VERIFY
- zipalign verified
- signature verified [v2, v3]
  Subject: CN=TRAE3, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN
  SHA256: 991c81d7... / SHA256withRSA
  Expires: Sun Dec 21 23:47:42 UTC 2053
```

> **必须看到 `signature verified [v2, v3]` 才算成功！**
> 如果只看到 `[v1]`，说明签名方案不对，安装后一定会闪退。

### 7.7 重命名最终 APK

```bash
# uber-apk-signer 输出的文件名很长，重命名一下
mv /workspace/trae_cn3_unsigned-aligned-signed.apk /workspace/trae_cn3_v22.apk
```

---

## 8. 第六步：VerifyError 避坑指南

### 8.1 什么是 VerifyError

VerifyError 是 Android 运行时（ART）在加载 dex 文件时，发现字节码不合法而抛出的错误。**应用一启动就闪退，日志里会看到 `VerifyError`。**

### 8.2 最常见原因：寄存器类型冲突

Smali 中每个寄存器（v0, v1, v2...）在同一位置不能持有不同类型的值。

**错误示例：**
```smali
# v0 先存了 String
const-string v0, "hello"
# ...
# 然后又在同一个分支点存了 File
new-instance v0, Ljava/io/File;
# → VerifyError! v0 在合并点类型不一致
```

### 8.3 修复方法：专用寄存器

**核心原则：日志用固定寄存器，数据用另外的寄存器，永远不混用。**

```smali
# 正确做法：v12, v13 专门用于日志，永远只持有 String
const-string v12, "ExtractHelper"
const-string v13, "Step1: started"
invoke-static {v12, v13}, Lcom/.../FileLogger;->log(Ljava/lang/String;Ljava/lang/String;)V

# v0 用于数据流
new-instance v0, Ljava/lang/StringBuilder;
```

### 8.4 其他 VerifyError 常见原因

| 错误信息 | 原因 | 修复方法 |
|---------|------|---------|
| `register vX has type Reference: A but expected Reference: B` | 同一寄存器在不同分支持有不同类型 | 使用专用寄存器，不跨类型复用 |
| `invoke-super/virtual can't be used on private method` | 用 `invoke-virtual` 调用 private 方法 | 改用 `invoke-direct` |
| `Invalid register: v16+` | `.registers` 太大，参数寄存器超过 v15 | 减少寄存器数量，或用 `move-object/from16` 把参数复制到低寄存器 |

### 8.5 调试 VerifyError 的命令

```bash
# 1. 查看手机日志（需要 adb）
adb logcat | grep -i "verifyerror"

# 2. 用 baksmali 反编译 dex 检查代码
java -jar /data/user/work/baksmali.jar d classes9.dex -o /tmp/check_smali

# 3. 查看可疑方法的寄存器使用
grep -A5 ".registers" /tmp/check_smali/.../ExtractHelper.smali

# 4. 检查是否有 catch 块捕获了 Throwable（不是 Exception）
grep "catch" /tmp/check_smali/.../ExtractHelper.smali
# 应该看到：.catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0
```

> **为什么要捕获 Throwable 而不是 Exception？**
> VerifyError 本身是 Error，不是 Exception。如果 catch 只捕获 Exception，VerifyError 不会被捕获，应用直接崩溃。捕获 Throwable 可以兜住所有错误。

---

## 9. 第七步：Smali 转可读 Java 源码

### 9.1 为什么要转成 Java

Smali 代码非常难读（类似汇编语言），维护成本极高。转成 Java 后：
- 代码结构一目了然
- 可以用 IDE 的代码补全和检查功能
- 方便后续修改和调试

### 9.2 方法一：手写 Java（适用于自定义类）

对于我们自己注入的 4 个类，直接手写 Java 源码最清晰：

```java
// ExtractHelper.java — 对话提取核心逻辑
package com.bytedance.trae.conversation.extract;

public final class ExtractHelper {
    public static final ExtractHelper INSTANCE = new ExtractHelper();

    public final void start(Activity activity, String conversationId, String title) {
        performExtract(activity, conversationId, title);
    }

    private void performExtract(Activity activity, String conversationId, String title) {
        // ... 完整的提取逻辑
    }
}
```

### 9.3 方法二：用 jadx 反编译（适用于已有代码）

对于 APK 中已有的代码（我们没写过的），用 jadx 自动反编译：

```bash
# 反编译整个 APK
/data/user/work/jadx_tool/bin/jadx \
  --output-dir /data/user/work/jadx_output \
  --no-res \
  --show-bad-code \
  --threads-count 4 \
  /workspace/trae_cn3_v22.apk
```

**参数说明：**

| 参数 | 含义 | 为什么要加 |
|------|------|----------|
| `--output-dir` | 输出目录 | Java 文件输出到这里 |
| `--no-res` | 不反编译资源文件 | 我们只需要代码，不需要资源 |
| `--show-bad-code` | 显示无法完美反编译的代码 | 有些代码 jadx 无法完美还原，加这个参数会尽力输出 |
| `--threads-count` | 线程数 | 多线程加速反编译 |

### 9.4 jadx 反编译结果

```bash
# 统计反编译的 Java 文件数量
find /data/user/work/jadx_output/sources -name "*.java" | wc -l
# 输出：18421（第一次反编译）

# 查看 com.bytedance.trae 包
find /data/user/work/jadx_output/sources/com/bytedance/trae -name "*.java" | wc -l
# 输出：1010
```

> **注意：jadx 第一次反编译可能有部分文件缺失（某些类反编译失败被跳过）。解决办法是逐个 dex 单独反编译，然后合并结果。详见第九步。**

---

## 10. 第八步：Java 编译回 Smali（逆向验证）

### 10.1 为什么要做逆向验证

手写 Java 后，需要验证它编译出来的 Smali 跟我们之前手动修改的 Smali 功能一致。这是"确保功能一模一样"的关键步骤。

### 10.2 编译流程

```
Java 源码 (.java)
  ↓ javac (Java 编译器)
Java 字节码 (.class)
  ↓ d8 (Android 编译器)
Android dex (.dex)
  ↓ baksmali (反汇编)
Smali 代码 (.smali)
```

### 10.3 具体命令

```bash
# Step 1: 创建源码目录和 stub 依赖
mkdir -p /data/user/work/compile_src/com/bytedance/trae/conversation/extract
# 把手写的 Java 源码放进去
cp /workspace/java_src/com/bytedance/trae/conversation/extract/*.java \
   /data/user/work/compile_src/com/bytedance/trae/conversation/extract/

# Step 2: 创建 stub 类（让编译通过）
# 为什么需要 stub？因为 Java 源码引用了 APK 中的其他类（如 TraeApplication），
# 编译时需要找到这些类。stub 类就是空壳，只提供方法签名让编译通过。
# 详见第 17 节附录

# Step 3: 编译 Java → .class
javac -source 1.8 -target 1.8 \
  -cp /data/user/work/android.jar:/data/user/work/compile_src \
  -d /data/user/work/compile_classes \
  $(find /data/user/work/compile_src -name "*.java")

# 参数说明：
# -source 1.8 -target 1.8  — 用 Java 8 语法和字节码
# -cp                        — classpath，指定依赖的 jar 和目录
# -d                         — 编译输出目录

# Step 4: .class → .dex
d8 \
  --output /data/user/work/compile_classes \
  --lib /data/user/work/android.jar \
  $(find /data/user/work/compile_classes -name "*.class")

# Step 5: .dex → .smali
java -jar /data/user/work/baksmali.jar d \
  /data/user/work/compile_classes/classes.dex \
  -o /data/user/work/new_smali
```

### 10.4 替换 Smali 文件

```bash
# 把新生成的 Smali 替换到解包项目中
cp /data/user/work/new_smali/com/bytedance/trae/conversation/extract/*.smali \
   /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/
```

### 10.5 验证 Smali 一致性

```bash
# 对比新旧 Smali 的方法签名是否一致
echo "=== 对比方法签名 ==="
grep "^\.method" /data/user/work/new_smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali
grep "^\.method" /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ExtractHelper.smali

# 对比完整文件
diff /data/user/work/new_smali/.../ExtractHelper.smali \
     /data/user/work/trae_cn3_decoded/smali_classes9/.../ExtractHelper.smali
# 如果没有输出，说明完全一致
```

> **为什么要创建 stub 类？**
> Java 编译器需要知道所有引用的类。比如 ExtractHelper 引用了 `TraeApplication`，但 TraeApplication 的源码很复杂，我们不需要修改它。所以创建一个空壳的 TraeApplication，只保留方法签名，让编译器能通过。stub 类**不会**被打包进 APK，因为最终我们用的是 baksmali 生成的 Smali 文件，不是编译的 .class。

---

## 11. 第九步：全量反编译（jadx 批量处理）

### 11.1 为什么要逐个 dex 反编译

jadx 一次性反编译整个 APK 时，部分类可能因为依赖关系复杂而反编译失败（被跳过）。解决办法是逐个 dex 单独反编译，然后合并结果。

### 11.2 逐个 dex 反编译

```bash
# 创建输出目录
mkdir -p /data/user/work/jadx_all_dex

# 逐个反编译 9 个 dex 文件
for dex in /data/user/work/trae_cn3_decoded/build/apk/classes*.dex; do
  echo "--- 反编译 $(basename $dex) ---"
  /data/user/work/jadx_tool/bin/jadx \
    --output-dir /data/user/work/jadx_all_dex/$(basename $dex .dex) \
    --no-res \
    --show-bad-code \
    --deobf \
    "$dex"
done
```

### 11.3 合并结果

```bash
# 创建合并目录
mkdir -p /data/user/work/jadx_merged

# 先把第一次完整反编译的结果复制过去
cp -r /data/user/work/jadx_output/sources/* /data/user/work/jadx_merged/

# 再从各 dex 的结果中补充缺失文件
for dir in /data/user/work/jadx_all_dex/*/sources; do
  cd "$dir"
  find . -name "*.java" | while read f; do
    target="/data/user/work/jadx_merged/$f"
    if [ ! -f "$target" ]; then
      mkdir -p "$(dirname "$target")"
      cp "$f" "$target"
    fi
  done
done

# 统计最终文件数
find /data/user/work/jadx_merged -name "*.java" | wc -l
# 输出：37987
```

### 11.4 验证关键类

```bash
# 验证所有关键类都存在
echo "ExtractHelper: $(find /data/user/work/jadx_merged -name 'ExtractHelper.java' -path '*/extract/*' | head -1)"
echo "TraeApplication: $(find /data/user/work/jadx_merged -name 'TraeApplication.java' | head -1)"
echo "BuildConfig: $(find /data/user/work/jadx_merged -name 'BuildConfig.java' -path '*/conversation/*' | head -1)"
echo "ServiceManager: $(find /data/user/work/jadx_merged -name 'ServiceManager.java' -path '*/aweme/*' | head -1)"
```

> **为什么用 `--deobf` 参数？**
> APK 打包时可能会做混淆（把类名改成 a, b, c 等）。`--deobf` 让 jadx 尝试还原更有意义的类名。但不是所有混淆都能还原，所以有些类名可能还是 a/b/c。

---

## 12. 第十步：验证与测试

### 12.1 APK 完整性验证

```bash
# 1. 验证 ZIP 完整性
unzip -t /workspace/trae_cn3_v22.apk 2>&1 | tail -3
# 期望输出：No errors detected

# 2. 验证签名
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v22.apk -y 2>&1 | tail -10
# 期望输出：signature verified [v2, v3] + zipalign verified

# 3. 验证 dex 文件列表
unzip -l /workspace/trae_cn3_v22.apk | grep "classes.*dex"
# 应该看到 9 个 dex 文件
```

### 12.2 dex 内容验证

```bash
# 从 APK 中提取 classes9.dex 并反编译检查
mkdir -p /tmp/verify
cd /tmp/verify
unzip -o /workspace/trae_cn3_v22.apk classes9.dex
java -jar /data/user/work/baksmali.jar d classes9.dex -o verify_smali

# 检查自定义类是否都在
find verify_smali -name "*.smali" -path "*/extract/*" | sort
# 应该看到 5 个文件：
# ApiMessageFetcher$1.smali
# ApiMessageFetcher.smali
# ExtractHelper.smali
# FileLogger.smali
# GitHubPusher.smali
```

### 12.3 关键参数验证

```bash
# 验证 API 参数
grep "before_limit" verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
# 应该看到：const-string v3, "&before_limit=10&after_limit=0&include_anchor=true"

# 验证 GitHub 仓库地址
grep "liliangxing" verify_smali/com/bytedance/trae/conversation/extract/GitHubPusher.smali
# 应该看到：const-string v3, "https://api.github.com/repos/liliangxing/trae-cn2/contents/docs/"

# 验证调用入口
grep -rn "ExtractHelper" /data/user/work/trae_cn3_decoded/smali_classes5/ --include="*.smali" | grep -v "extract/"
# 应该看到 TaskFragment 和 ConversationActivity 的调用
```

### 12.4 方法签名对比

```bash
# 对比 dex 中的方法签名和源码的方法签名
echo "=== ExtractHelper 方法签名 ==="
grep "^\.method" verify_smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali

echo "=== ApiMessageFetcher 方法签名 ==="
grep "^\.method" verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali

echo "=== FileLogger 方法签名 ==="
grep "^\.method" verify_smali/com/bytedance/trae/conversation/extract/FileLogger.smali

echo "=== GitHubPusher 方法签名 ==="
grep "^\.method" verify_smali/com/bytedance/trae/conversation/extract/GitHubPusher.smali
```

### 12.5 清理临时文件

```bash
rm -rf /tmp/verify
```

---

## 13. 避坑清单（失败经验总结）

### 坑 1：package info is null（最常见）

| 项目 | 说明 |
|------|------|
| **症状** | APK 安装后提示 "package info is null"，或应用无法启动 |
| **原因** | 只用了 v1 签名（jarsigner），Android 7.0+ 需要 v2/v3 签名 |
| **解决** | 使用 uber-apk-signer 签名，必须看到 `signature verified [v2, v3]` |
| **避坑** | **永远不要用 jarsigner！** 用 uber-apk-signer 或 apksigner |

### 坑 2：VerifyError 闪退

| 项目 | 说明 |
|------|------|
| **症状** | 应用启动后立即闪退，日志显示 VerifyError |
| **原因** | Smali 寄存器在不同分支持有不同类型 |
| **解决** | 用专用寄存器（如 v12/v13 只用于日志），不跨类型复用 |
| **避坑** | catch 块捕获 Throwable 而不是 Exception；寄存器编号不超过 v15 |

### 坑 3：数据库查询返回空

| 项目 | 说明 |
|------|------|
| **症状** | 日志显示 "messages list is empty" |
| **原因** | 查错了数据库表名（`conversation_detail` 是空的，消息在 `chat_message` 表） |
| **解决** | 先查询 `chat_message`，如果空再查 `conversation_detail`，最后走 API |
| **避坑** | 添加详细的诊断日志，每一步都记录结果 |

### 坑 4：API 400 参数错误

| 项目 | 说明 |
|------|------|
| **症状** | API 返回 400，错误信息 "cause=invalid" |
| **原因** | `before_limit` 参数值太大（200 或 50），API 不接受 |
| **解决** | 用 `before_limit=10`（App 的默认值） |
| **避坑** | 不确定的参数先用小值测试，看 App 原本的默认值是多少 |

### 坑 5：SSL 证书验证失败

| 项目 | 说明 |
|------|------|
| **症状** | API 请求失败，报 SSL 错误 |
| **原因** | 内部域名使用自签名证书 |
| **解决** | 创建 trust-all 的 SSLSocketFactory，信任所有证书 |
| **避坑** | 只在必要时使用 trust-all，生产环境应该正确配置证书 |

### 坑 6：编译报错找不到类

| 项目 | 说明 |
|------|------|
| **症状** | javac 编译报错 "cannot find symbol" |
| **原因** | Java 源码引用了 APK 中的类，但编译时找不到 |
| **解决** | 创建 stub 类（空壳类，只保留方法签名） |
| **避坑** | stub 类要包含所有被引用的方法和字段 |

### 坑 7：keystore 密码错误

| 项目 | 说明 |
|------|------|
| **症状** | 签名时报 "keystore was tampered with, or password was incorrect" |
| **原因** | 密码输错了（比如把 `trae123` 输成 `trae3123`） |
| **解决** | 仔细核对密码，查看 APK_BUILD_SPEC.md 中的记录 |
| **避坑** | 密码记录在 APK_BUILD_SPEC.md 中，每次签名前核对 |

### 坑 8：jadx 反编译部分类缺失

| 项目 | 说明 |
|------|------|
| **症状** | jadx 反编译后，某些类（如 ExtractHelper）不存在 |
| **原因** | jadx 处理整个 APK 时，部分类反编译失败被跳过 |
| **解决** | 逐个 dex 单独反编译，然后合并结果 |
| **避坑** | 反编译后验证关键类是否存在 |

---

## 14. 完整命令速查表

### 14.1 从零开始完整流程

```bash
# ====== 1. 解包 ======
apktool d original.apk -o /data/user/work/trae_cn3_decoded -f

# ====== 2. 修改 Smali 代码 ======
# （手动编辑 .smali 文件）

# ====== 3. 打包 ======
apktool b /data/user/work/trae_cn3_decoded -o /workspace/unsigned.apk

# ====== 4. 签名 ======
java -jar /data/user/work/uber-apk-signer.jar \
  -a /workspace/unsigned.apk \
  --out /workspace \
  --ks /data/user/work/trae3.keystore \
  --ksAlias trae3 \
  --ksPass trae123 \
  --ksKeyPass trae123 \
  --allowResign

# ====== 5. 重命名 ======
mv /workspace/unsigned-aligned-signed.apk /workspace/trae_cn3_final.apk

# ====== 6. 验证签名 ======
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_final.apk -y

# ====== 7. 全量反编译 Java ======
# 7a. 整体反编译
/data/user/work/jadx_tool/bin/jadx \
  --output-dir /data/user/work/jadx_output \
  --no-res --show-bad-code \
  /workspace/trae_cn3_final.apk

# 7b. 逐个 dex 反编译
for dex in /data/user/work/trae_cn3_decoded/build/apk/classes*.dex; do
  /data/user/work/jadx_tool/bin/jadx \
    --output-dir /data/user/work/jadx_all_dex/$(basename $dex .dex) \
    --no-res --show-bad-code --deobf \
    "$dex"
done

# 7c. 合并
mkdir -p /data/user/work/jadx_merged
cp -r /data/user/work/jadx_output/sources/* /data/user/work/jadx_merged/
for dir in /data/user/work/jadx_all_dex/*/sources; do
  cd "$dir"
  find . -name "*.java" | while read f; do
    target="/data/user/work/jadx_merged/$f"
    [ ! -f "$target" ] && mkdir -p "$(dirname "$target")" && cp "$f" "$target"
  done
done
```

### 14.2 Java 编译回 Smali

```bash
# 编译 Java → .class
javac -source 1.8 -target 1.8 \
  -cp /data/user/work/android.jar:/data/user/work/compile_src \
  -d /data/user/work/compile_classes \
  $(find /data/user/work/compile_src -name "*.java")

# 编译 .class → .dex
d8 --output /data/user/work/compile_classes \
   --lib /data/user/work/android.jar \
   $(find /data/user/work/compile_classes -name "*.class")

# 反编译 .dex → .smali
java -jar /data/user/work/baksmali.jar d \
  /data/user/work/compile_classes/classes.dex \
  -o /data/user/work/new_smali
```

### 14.3 提交到 Git 仓库

```bash
# 克隆仓库
git clone https://用户名:token@github.com/liliangxing/trae-cn2.git

# 进入仓库
cd trae-cn2-repo
git config user.email "bot@example.com"
git config user.name "Bot"

# 添加文件
git add -A

# 提交
git commit -m "feat: add Java source files"

# 推送
git push origin main
```

---

## 15. 调试排查常用命令

### 15.1 查看 APK 信息

```bash
# 查看 APK 中的文件列表
unzip -l app.apk | head -30

# 查看 APK 中的 dex 文件
unzip -l app.apk | grep "classes.*dex"

# 验证 APK 完整性
unzip -t app.apk

# 查看 APK 大小和 MD5
ls -lh app.apk
md5sum app.apk
```

### 15.2 查看 Smali 代码

```bash
# 搜索特定类
find /data/user/work/trae_cn3_decoded -name "ClassName.smali"

# 搜索引用了某类的地方
grep -rn "ClassName" /data/user/work/trae_cn3_decoded/smali*/ --include="*.smali"

# 查看方法签名
grep "^\.method" file.smali

# 查看字段
grep "^\.field" file.smali

# 统计 Smali 文件数量
find /data/user/work/trae_cn3_decoded -name "*.smali" | wc -l
```

### 15.3 dex 文件操作

```bash
# 从 APK 中提取 dex
unzip app.apk classes9.dex -d /tmp/

# dex → smali
java -jar baksmali.jar d classes9.dex -o /tmp/smali_output

# smali → dex
java -jar smali.jar a /tmp/smali_input -o /tmp/output.dex
```

### 15.4 对比验证

```bash
# 对比两个 Smali 文件
diff file1.smali file2.smali

# 对比两个目录
diff -rq dir1/ dir2/

# 查看方法签名是否一致
grep "^\.method" file1.smali
grep "^\.method" file2.smali
```

### 15.5 查看手机日志（如有 adb）

```bash
# 查看所有日志
adb logcat

# 过滤闪退日志
adb logcat | grep -i "crash\|error\|fatal\|verifyerror"

# 查看特定应用的日志
adb logcat | grep "com.bytedance.trae"

# 查看日志文件（应用自己写的日志）
adb shell cat /sdcard/Android/data/com.bytedance.trae.cn3/files/trae-cn3.log
```

### 15.6 查看 AndroidManifest

```bash
# 查看包名和版本
grep "package=\|versionCode\|versionName" AndroidManifest.xml

# 查看 apktool.yml
cat apktool.yml | grep "versionCode\|versionName"
```

---

## 16. 工具与技能说明

### 16.1 本文档使用的工具

所有操作只需要以下基本能力：

| 能力 | 说明 | 本文是否用到 |
|------|------|------------|
| 读写文件 | 创建和编辑文本文件 | ✅ 修改 Smali、Java 文件 |
| 执行 bash 命令 | 在终端运行命令 | ✅ 所有操作 |
| 下载文件 | wget/curl 下载工具 | ✅ 下载 jadx 等 |
| git 操作 | clone/commit/push | ✅ 提交到仓库 |

### 16.2 不需要特殊技能

本文档**不依赖**以下任何特殊能力：
- ❌ 不需要 MCP 工具
- ❌ 不需要浏览器自动化
- ❌ 不需要 Lark/飞书技能
- ❌ 不需要 AI 图片生成
- ❌ 不需要特殊 IDE 插件

### 16.3 工具下载地址汇总

| 工具 | 下载地址 |
|------|---------|
| apktool | https://bitbucket.org/iBotPeaches/apktool/downloads/ |
| baksmali/smali | https://github.com/google/smali/releases |
| uber-apk-signer | https://github.com/patrickfav/uber-apk-signer/releases |
| jadx | https://github.com/skylot/jadx/releases |
| Android SDK (d8) | https://developer.android.com/studio |
| OpenJDK | https://adoptium.net/ 或 `apt-get install openjdk-11-jdk` |

### 16.4 GitHub 仓库信息

| 仓库 | 用途 |
|------|------|
| `liliangxing/trae-cn2` | APK 源码（Smali + Java） |
| `liliangxing/docs` | 文档仓库（本文档提交到这里） |

Git 认证方式：HTTPS + Personal Access Token

```bash
# 克隆时带上 token 认证
git clone https://用户名:token@github.com/liliangxing/trae-cn2.git
```

### 16.5 如果你是 AI Agent

如果你是另一个 AI Agent，读到这份文档去执行任务，请注意：

1. **你只需要基本的文件读写和 bash 执行能力**，不需要任何特殊 skill 或 MCP
2. **所有命令都可以直接复制执行**，注意替换路径和文件名
3. **签名密码是 `trae123`**，keystore 在 `/data/user/work/trae3.keystore`
4. **最大的坑是签名**：必须用 uber-apk-signer，不能用 jarsigner
5. **第二大坑是 VerifyError**：Smali 寄存器不要跨类型复用
6. **修改 Smali 后一定要清理 build 缓存**再重新打包
7. **jadx 反编译后要验证关键类是否存在**，不存在就逐个 dex 反编译

---

## 17. 附录：关键文件说明

### 17.1 项目文件结构

```
/data/user/work/
├── trae3.keystore          ← 签名证书（密码: trae123）
├── uber-apk-signer.jar     ← 签名工具
├── baksmali.jar            ← dex→smali 工具
├── smali.jar               ← smali→dex 工具
├── android.jar             ← Android SDK stub（编译用）
├── d8.jar                  ← class→dex 工具
├── jadx_tool/              ← jadx 反编译工具
├── trae_cn3_decoded/       ← APK 解包目录
│   ├── AndroidManifest.xml
│   ├── apktool.yml
│   ├── smali/              ← dex 1 的 smali
│   ├── smali_classes2/     ← dex 2 的 smali
│   ├── ...
│   ├── smali_classes9/     ← dex 9 的 smali（自定义代码）
│   │   └── com/bytedance/trae/conversation/extract/
│   │       ├── ExtractHelper.smali
│   │       ├── ApiMessageFetcher.smali
│   │       ├── ApiMessageFetcher$1.smali
│   │       ├── FileLogger.smali
│   │       └── GitHubPusher.smali
│   └── build/              ← 构建缓存（打包前删掉）
├── compile_src/            ← Java 源码（编译用）
├── compile_classes/        ← 编译输出（.class + .dex）
├── new_smali/              ← 从 Java 编译的 smali
├── jadx_output/            ← jadx 反编译输出
├── jadx_all_dex/           ← 逐 dex 反编译输出
└── jadx_merged/            ← 合并后的 Java 源码

/workspace/
├── trae_cn3_v22.apk        ← 最终 APK（签名后）
├── APK_BUILD_SPEC.md       ← 打包签名规范文档
└── java_src/               ← 手写的 Java 源码
    └── com/bytedance/trae/conversation/extract/
        ├── ExtractHelper.java
        ├── ApiMessageFetcher.java
        ├── FileLogger.java
        └── GitHubPusher.java
```

### 17.2 自定义类说明

| 类名 | 文件 | 功能 | 关键方法 |
|------|------|------|---------|
| ExtractHelper | ExtractHelper.smali | 对话提取入口 | `start(Activity, String, String)` |
| ApiMessageFetcher | ApiMessageFetcher.smali | API 拉取消息 | `fetch(String, String, String, String)` |
| FileLogger | FileLogger.smali | 文件日志 | `log(String, String)` / `log(String, String, Throwable)` |
| GitHubPusher | GitHubPusher.smali | 推送到 GitHub | `push(String, File)` |
| ApiMessageFetcher$1 | ApiMessageFetcher$1.smali | SSL 信任管理器（内部类） | X509TrustManager 实现 |

### 17.3 Stub 类说明

编译 Java 时需要创建以下 stub 类（空壳类，只保留方法签名）：

- `TraeApplication` — 提供 `Companion.getInst()` 方法
- `ServiceManager` — 提供 `get()` 和 `getService()` 方法
- `ILoginService` — 接口，提供 `getAccountInfo()` 方法
- `AccountInfo` — 提供 `getUserId()` 方法
- `DatabaseManager` — 提供 `getDatabase()` 方法
- `DatabaseOpenHelper` — 提供 `getReadableDatabase()` 方法
- `ChatMessageDao` / `ConversationDetailDao` — 数据库 DAO
- `SdkCommonHttpImpl` — 提供 `getToken()` 方法
- `TraeHttpConnection` — 提供 `baseUrl()` 方法
- `BuildConfig` — 提供 `getGITHUB_TOKEN()` 方法
- `SimpleWebViewActivity` — WebView Activity

> Stub 类**不会**被打包进 APK。它们只是让 javac 编译通过。最终用的是 baksmali 生成的 Smali 文件。

### 17.4 Keystore 信息

| 属性 | 值 |
|------|-----|
| 文件路径 | `/data/user/work/trae3.keystore` |
| 别名 | `trae3` |
| 密码 | `trae123` |
| Key 密码 | `trae123` |
| 证书主体 | `CN=TRAE3, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN` |
| 算法 | RSA 2048, SHA256withRSA |
| 有效期 | 10000 天 |

---

## 总结

### 成功步骤回顾

```
1. apktool d → 解包 APK
2. 修改 Smali 文件（注意寄存器规则）
3. apktool b → 重新打包
4. uber-apk-signer → 签名（v2+v3）
5. 验证签名 → 必须看到 [v2, v3]
6. jadx → 反编译成 Java
7. 逐个 dex 反编译 → 补充缺失文件
8. 提交到 Git 仓库
```

### 三大铁律

1. **签名永远用 uber-apk-signer，不用 jarsigner**
2. **Smali 寄存器不跨类型复用，catch 捕获 Throwable**
3. **打包前删 build 缓存，打包后验证签名**
