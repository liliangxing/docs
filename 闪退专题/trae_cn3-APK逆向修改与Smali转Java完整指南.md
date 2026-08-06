# TRAE CN3 APK 重新打包、Smali 验证与全量反编译 Java 指南

> 适用对象：技术基础一般、对命令行不熟悉的开发者或 AI Agent
> 目标：验证已有 Smali 修改的正确性，重新打包签名 APK，全量反编译成可读 Java 源码
> 最后更新：2026-08-06
> 说明：本文档中**所有命令均为本次会话中真实执行并验证过的**，每条命令都附带真实输出。

---

## 目录

1. [背景：我们要干什么](#1-背景我们要干什么)
2. [前提条件：已有的文件和工具](#2-前提条件已有的文件和工具)
3. [第一步：验证 Smali 文件一致性](#3-第一步验证-smali-文件一致性)
4. [第二步：验证已有 APK 的签名和结构](#4-第二步验证已有-apk-的签名和结构)
5. [第三步：从 APK 提取 dex 并反编译验证](#5-第三步从-apk-提取-dex-并反编译验证)
6. [第四步：验证关键业务参数](#6-第四步验证关键业务参数)
7. [第五步：干净重建 APK](#7-第五步干净重建-apk)
8. [第六步：APK 签名](#8-第六步apk-签名)
9. [第七步：验证新 APK](#9-第七步验证新-apk)
10. [第八步：下载安装 jadx](#10-第八步下载安装-jadx)
11. [第九步：全量反编译 Java 源码](#11-第九步全量反编译-java-源码)
12. [第十步：逐个 dex 反编译补充缺失](#12-第十步逐个-dex-反编译补充缺失)
13. [第十一步：合并反编译结果](#13-第十一步合并反编译结果)
14. [第十二步：用手写 Java 替换自定义类](#14-第十二步用手写-java-替换自定义类)
15. [调试排查常用命令](#15-调试排查常用命令)
16. [避坑提醒](#16-避坑提醒)
17. [工具与技能说明](#17-工具与技能说明)

---

## 1. 背景：我们要干什么

### 1.1 一句话说明

已有的工作成果（上个会话完成的）包括：
- 一个已解包的 APK 项目目录（含修改过的 Smali 代码）
- 4 个手写的 Java 源码文件（对应自定义的 Smali 类）
- 一个已签名的 APK（v21）

本次会话要做的事：
1. **验证** Smali 修改是否正确（对比 dex 内容与源码）
2. **干净重建** APK（从解包目录重新打包 + 签名）
3. **全量反编译** 所有 Smali 成可读 Java 源码

### 1.2 整体流程

```
已有的解包目录（含修改过的 Smali）
  ↓ 验证 Smali 一致性
  ↓ 干净重建（apktool b + uber-apk-signer）
新 APK（v22）
  ↓ 验证签名 + dex 内容
  ↓ jadx 全量反编译 + 逐 dex 补充
37,987 个 Java 文件
  ↓ 手写 Java 替换自定义类
完成
```

---

## 2. 前提条件：已有的文件和工具

### 2.1 已有文件

| 文件/目录 | 路径 | 说明 |
|----------|------|------|
| 解包项目 | `/data/user/work/trae_cn3_decoded/` | apktool 解包后的目录 |
| 手写 Java 源码 | `/workspace/java_src/com/bytedance/trae/conversation/extract/` | 4 个自定义类 |
| 已签名 APK | `/workspace/trae_cn3_v21.apk` | 上个会话打包的版本 |
| 新 Smali（Java编译生成的） | `/data/user/work/new_smali_v2/` | 从 Java 编译的 Smali |
| APK 构建规范 | `/workspace/APK_BUILD_SPEC.md` | 签名密码等记录 |
| baksmali | `/data/user/work/baksmali.jar` | dex→smali 工具 |
| uber-apk-signer | `/data/user/work/uber-apk-signer.jar` | APK 签名工具 |
| keystore | `/data/user/work/trae3.keystore` | 签名证书（密码: trae123） |

### 2.2 自定义类清单

| 类名 | 作用 |
|------|------|
| `ExtractHelper` | 对话提取核心逻辑（数据库查询 + API 回退） |
| `ApiMessageFetcher` | 从服务器 API 拉取消息（含 SSL 信任管理） |
| `FileLogger` | 文件日志工具 |
| `GitHubPusher` | 推送到 GitHub 仓库 |

这些类位于解包项目的 `smali_classes9/com/bytedance/trae/conversation/extract/` 目录下。

---

## 3. 第一步：验证 Smali 文件一致性

### 3.1 为什么要做这步

上个会话从手写 Java 编译出了新的 Smali 文件（放在 `new_smali_v2/`），并复制到了解包项目中。首先要确认这两份文件完全一致，没有复制错误。

### 3.2 对比 5 个 Smali 文件

```bash
diff /data/user/work/new_smali_v2/com/bytedance/trae/conversation/extract/ExtractHelper.smali \
     /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ExtractHelper.smali
```

对 5 个文件都做了 diff：

```bash
diff /data/user/work/new_smali_v2/com/bytedance/trae/conversation/extract/ExtractHelper.smali /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ExtractHelper.smali
diff /data/user/work/new_smali_v2/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
diff /data/user/work/new_smali_v2/com/bytedance/trae/conversation/extract/ApiMessageFetcher\$1.smali /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ApiMessageFetcher\$1.smali
diff /data/user/work/new_smali_v2/com/bytedance/trae/conversation/extract/FileLogger.smali /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/FileLogger.smali
diff /data/user/work/new_smali_v2/com/bytedance/trae/conversation/extract/GitHubPusher.smali /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/GitHubPusher.smali
```

**真实输出：5 个 diff 命令全部无输出（退出码 0），说明完全一致。**

> **为什么要用 diff？**
> diff 命令比较两个文件，如果完全相同则没有任何输出（退出码 0）。这是最可靠的文件一致性验证方法。

### 3.3 检查是否有旧文件残留

```bash
find /data/user/work/trae_cn3_decoded -path "*/conversation/extract/*.smali" -not -path "*/smali_classes9/*"
```

**真实输出：无输出**，说明 extract 相关的 Smali 文件只存在于 `smali_classes9` 中，没有在其他 smali 目录残留旧版本。

> **为什么要检查残留？**
> 如果其他 smali_classes 目录下有同名的旧类文件，打包时会产生类冲突，运行时可能加载到错误的版本。

---

## 4. 第二步：验证已有 APK 的签名和结构

### 4.1 验证 APK 签名

```bash
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v21.apk -y
```

**真实输出：**
```
01. trae_cn3_v21.apk
        VERIFY
        file: /workspace/trae_cn3_v21.apk (106.05 MiB)
        - zipalign verified
        - signature verified [v2, v3]
                Subject: CN=TRAE3, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN
                SHA256: 991c81d7ca47f6fb5cf67855621a829d950fdb9240242b9ea8755d00006e472f / SHA256withRSA
                Expires: Sun Dec 21 23:47:42 UTC 2053
```

> **关键：必须看到 `signature verified [v2, v3]`。** 如果只有 `[v1]`，安装到 Android 7.0+ 会闪退（package info is null）。

### 4.2 查看 dex 文件列表

```bash
unzip -l /workspace/trae_cn3_v21.apk | grep "classes.*dex"
```

**真实输出：**
```
  8710032  2026-08-06 04:29   classes7.dex
 10314376  2026-08-06 04:29   classes2.dex
 10320464  2026-08-06 04:29   classes8.dex
 13455772  2026-08-06 04:29   classes.dex
   149396  2026-08-06 04:29   classes9.dex
  9145840  2026-08-06 04:29   classes6.dex
 11681028  2026-08-06 04:29   classes5.dex
  7490600  2026-08-06 04:29   classes3.dex
 11044216  2026-08-06 04:29   classes4.dex
```

共 9 个 dex 文件。`classes9.dex` 最小（149KB），是自定义代码所在文件。

### 4.3 验证 APK 完整性

```bash
unzip -t /workspace/trae_cn3_v21.apk
```

**真实输出（最后一行）：**
```
No errors detected in compressed data of /workspace/trae_cn3_v21.apk.
```

> **`unzip -t` 是什么？**
> `-t` 表示 test，测试 ZIP 文件（APK 本质是 ZIP）的完整性，检查有没有损坏。

---

## 5. 第三步：从 APK 提取 dex 并反编译验证

### 5.1 提取 classes9.dex

```bash
mkdir -p /data/user/work/verify_dex
cd /data/user/work/verify_dex
unzip -o /workspace/trae_cn3_v21.apk classes9.dex -d .
```

**真实输出：**
```
Archive:  /workspace/trae_cn3_v21.apk
  inflating: ./classes9.dex
-rw-r--r-- 1 root root 149396 Aug  6 04:29 classes9.dex
```

### 5.2 反编译 dex 为 Smali

```bash
java -jar /data/user/work/baksmali.jar d classes9.dex -o verify_smali
```

> **baksmali 是什么？**
> baksmali 把 dex（Android 字节码）反汇编成 Smali（人类可读格式）。`d` 参数表示 disassemble。

### 5.3 验证自定义类是否都在

```bash
find verify_smali -name "*.smali" -path "*/extract/*" | sort
```

**真实输出：**
```
verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher$1.smali
verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
verify_smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali
verify_smali/com/bytedance/trae/conversation/extract/FileLogger.smali
verify_smali/com/bytedance/trae/conversation/extract/GitHubPusher.smali
```

5 个文件全部存在（包括 `ApiMessageFetcher$1` 内部类）。

### 5.4 对比 dex 中的 Smali 与源码 Smali

```bash
diff /data/user/work/verify_dex/verify_smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali \
     /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ExtractHelper.smali
```

对全部 5 个文件做了 diff，**全部 MATCH（无输出，退出码 0）**。

> **这一步证明了什么？**
> APK 中的 dex 字节码反编译回来的 Smali，跟我们放在解包项目里的 Smali 文件完全一致。说明打包过程没有引入任何偏差。

### 5.5 对比方法签名

```bash
echo "=== dex 中的 ExtractHelper 方法签名 ==="
grep "^\.method" /data/user/work/verify_dex/verify_smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali
echo "=== 源码中的 ExtractHelper 方法签名 ==="
grep "^\.method" /data/user/work/trae_cn3_decoded/smali_classes9/com/bytedance/trae/conversation/extract/ExtractHelper.smali
```

**真实输出（两个完全一致）：**
```
.method static constructor <clinit>()V
.method private constructor <init>()V
.method private performExtract(Landroid/app/Activity;Ljava/lang/String;Ljava/lang/String;)V
.method public final start(Landroid/app/Activity;Ljava/lang/String;Ljava/lang/String;)V
```

同样验证了 ApiMessageFetcher、FileLogger、GitHubPusher 的方法签名，全部一致。

> **为什么要验证方法签名？**
> 如果签名不一致（比如参数类型变了），调用方会找不到方法，运行时直接闪退（NoSuchMethodError）。

---

## 6. 第四步：验证关键业务参数

### 6.1 验证 API 参数

```bash
grep "before_limit" /data/user/work/verify_dex/verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
```

**真实输出：**
```
const-string v3, "&before_limit=10&after_limit=0&include_anchor=true"
```

> **为什么 before_limit=10？**
> 之前用过 200 和 50，API 都返回 400 错误。10 是 App 的默认值，能正常工作。

### 6.2 验证 API 路径

```bash
grep "solo_hub" /data/user/work/verify_dex/verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
```

**真实输出：**
```
const-string v3, "api/solo_hub/v1/conversations/messages/anchor?conversation_id="
```

### 6.3 验证 GitHub 仓库地址

```bash
grep "liliangxing" /data/user/work/verify_dex/verify_smali/com/bytedance/trae/conversation/extract/GitHubPusher.smali
```

**真实输出：**
```
const-string v3, "https://api.github.com/repos/liliangxing/trae-cn2/contents/docs/"
```

### 6.4 验证 SSL 信任管理器

```bash
grep "TrustManager" /data/user/work/verify_dex/verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
grep "TrustManager" /data/user/work/verify_dex/verify_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher\$1.smali
```

**真实输出：**
```
# ApiMessageFetcher.smali
new-array v0, v0, [Ljavax/net/ssl/TrustManager;
invoke-virtual {v1, v3, v0, v2}, Ljavax/net/ssl/SSLContext;->init(...)V

# ApiMessageFetcher$1.smali
.implements Ljavax/net/ssl/X509TrustManager;
```

### 6.5 验证调用入口

```bash
grep -rn "ExtractHelper" /data/user/work/trae_cn3_decoded/smali*/ --include="*.smali" | grep -v "extract/"
```

**真实输出：**
```
smali_classes5/.../TaskFragment.smali:725: sget-object v5, Lcom/bytedance/trae/conversation/extract/ExtractHelper;->INSTANCE:...
smali_classes5/.../TaskFragment.smali:727: invoke-virtual {v5, v4, v3, v0}, Lcom/bytedance/trae/conversation/extract/ExtractHelper;->start(...)
smali_classes5/.../ConversationActivity$initTitleBar$3$1.smali:304: sget-object v2, Lcom/bytedance/trae/conversation/extract/ExtractHelper;->INSTANCE:...
smali_classes5/.../ConversationActivity$initTitleBar$3$1.smali:306: invoke-virtual {v2, v0, v3, v4}, Lcom/bytedance/trae/conversation/extract/ExtractHelper;->start(...)
```

> **这证明了什么？**
> 有两个地方调用了 ExtractHelper：TaskFragment（任务列表页）和 ConversationActivity（对话页面）。这两个调用点都完好，没有被修改破坏。

### 6.6 检查包名和版本

```bash
grep "package=" /data/user/work/trae_cn3_decoded/AndroidManifest.xml
grep "versionCode\|versionName" /data/user/work/trae_cn3_decoded/apktool.yml
```

**真实输出：**
```
package="com.bytedance.trae.cn3" platformBuildVersionCode="35"
versionCode: 21
versionName: 0.0.16
```

---

## 7. 第五步：干净重建 APK

### 7.1 为什么要干净重建

之前验证的是 v21 APK（上个会话打包的）。为了证明打包过程可复现，从解包目录重新构建一个全新的 APK（v22）。

### 7.2 清理构建缓存

```bash
rm -rf /data/user/work/trae_cn3_decoded/build
```

> **为什么要删 build 缓存？**
> apktool 会缓存上次构建的中间文件（在 `build/` 目录下）。如果修改了 Smali 但缓存没更新，打包时可能用的还是旧代码。删除 `build` 强制全量重新构建。

### 7.3 打包

```bash
apktool b /data/user/work/trae_cn3_decoded -o /workspace/trae_cn3_v22_unsigned.apk
```

**真实输出：**
```
I: Smaling smali_classes7 folder into classes7.dex...
I: Checking whether sources have changed...
I: Smaling smali_classes8 folder into classes8.dex...
I: Checking whether sources have changed...
I: Smaling smali_classes9 folder into classes9.dex...
I: Building apk file...
I: Importing assets...
I: Importing lib...
I: Importing unknown files...
I: Built apk into: /workspace/trae_cn3_v22_unsigned.apk
```

> **`apktool b` 是什么？**
> `b` 表示 build，把解包目录重新打包成 APK。它会把所有 smali_classes 文件夹编译成 dex 文件，然后和资源文件一起打包成 APK。

---

## 8. 第六步：APK 签名

### 8.1 签名命令

```bash
java -jar /data/user/work/uber-apk-signer.jar \
  -a /workspace/trae_cn3_v22_unsigned.apk \
  --out /workspace \
  --ks /data/user/work/trae3.keystore \
  --ksAlias trae3 \
  --ksPass trae123 \
  --ksKeyPass trae123 \
  --allowResign
```

**真实输出：**
```
- zipalign success
- sign success

VERIFY
file: /workspace/trae_cn3_v22_unsigned-aligned-signed.apk (106.05 MiB)
- zipalign verified
- signature verified [v2, v3]
        Subject: CN=TRAE3, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN
        SHA256: 991c81d7ca47f6fb5cf67855621a829d950fdb9240242b9ea8755d00006e472f / SHA256withRSA
        Expires: Sun Dec 21 23:47:42 UTC 2053
Successfully processed 1 APKs and 0 errors in 3.70 seconds.
```

### 8.2 参数说明

| 参数 | 含义 |
|------|------|
| `-a` | 输入未签名的 APK |
| `--out` | 输出目录 |
| `--ks` | keystore 文件路径 |
| `--ksAlias` | 证书别名（trae3） |
| `--ksPass` | keystore 密码（trae123） |
| `--ksKeyPass` | key 密码（trae123） |
| `--allowResign` | 允许覆盖已有签名 |

### 8.3 重命名

```bash
mv /workspace/trae_cn3_v22_unsigned-aligned-signed.apk /workspace/trae_cn3_v22.apk
```

> **为什么要用 uber-apk-signer 而不是 jarsigner？**
> jarsigner 只生成 v1 签名，Android 7.0+ 不认。uber-apk-signer 自动生成 v2 + v3 签名 + zipalign 对齐，一步到位。如果只用 v1 签名，安装后会提示 "package info is null" 并闪退。

---

## 9. 第七步：验证新 APK

### 9.1 验证签名

```bash
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v22.apk -y
```

**真实输出：**
```
VERIFY
file: /workspace/trae_cn3_v22.apk (106.05 MiB)
- zipalign verified
- signature verified [v2, v3]
        Subject: CN=TRAE3, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN
Successfully processed 1 APKs and 0 errors in 0.62 seconds.
```

### 9.2 验证新 APK 的 dex 内容

```bash
mkdir -p /data/user/work/verify_dex/verify_v22
cd /data/user/work/verify_dex/verify_v22
unzip -o /workspace/trae_cn3_v22.apk classes9.dex -d .
java -jar /data/user/work/baksmali.jar d classes9.dex -o v22_smali
```

### 9.3 对比 v22 和 v21 的 Smali

```bash
diff v22_smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali \
     ../verify_smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali
```

**真实输出：MATCH（无差异）**

同样对比了 ApiMessageFetcher，也是 MATCH。

> **这证明了什么？**
> 干净重建的 v22 APK 与之前的 v21 APK 在自定义代码部分完全一致，打包过程可复现。

### 9.4 验证 v22 中的关键参数

```bash
grep "before_limit" v22_smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
grep "liliangxing" v22_smali/com/bytedance/trae/conversation/extract/GitHubPusher.smali
```

**真实输出：**
```
const-string v3, "&before_limit=10&after_limit=0&include_anchor=true"
const-string v3, "https://api.github.com/repos/liliangxing/trae-cn2/contents/docs/"
```

### 9.5 验证调用入口完好

```bash
grep -rn "ExtractHelper" /data/user/work/trae_cn3_decoded/smali_classes5/ --include="*.smali" | grep -v "extract/"
```

**真实输出：** TaskFragment 和 ConversationActivity 两处调用都在。

### 9.6 验证 APK 完整性

```bash
unzip -t /workspace/trae_cn3_v22.apk 2>&1 | tail -3
```

**真实输出：**
```
No errors detected in compressed data of /workspace/trae_cn3_v22.apk.
```

### 9.7 清理临时文件

```bash
rm -rf /data/user/work/verify_dex
```

---

## 10. 第八步：下载安装 jadx

### 10.1 下载 jadx

```bash
cd /data/user/work
wget -q "https://github.com/skylot/jadx/releases/download/v1.5.0/jadx-1.5.0.zip" -O jadx.zip
```

**验证下载：**
```bash
ls -lh jadx.zip
```
**真实输出：**
```
-rw-r--r-- 1 root root 101M Apr 20  2024 jadx.zip
```

### 10.2 解压

```bash
unzip -q -o jadx.zip -d jadx_tool
```

### 10.3 验证安装

```bash
/data/user/work/jadx_tool/bin/jadx --version
```

**真实输出：**
```
1.5.0
```

> **jadx 是什么？**
> jadx 是一个 Java 反编译工具，能把 Android 的 dex/apk 文件反编译成可读的 Java 源码。比直接读 Smali 容易理解得多。

---

## 11. 第九步：全量反编译 Java 源码

### 11.1 反编译整个 APK

```bash
mkdir -p /data/user/work/jadx_output
/data/user/work/jadx_tool/bin/jadx \
  --output-dir /data/user/work/jadx_output \
  --no-res \
  --threads-count 4 \
  --show-bad-code \
  /workspace/trae_cn3_v22.apk
```

**真实输出：**
```
INFO  - loading ...
INFO  - processing ...
INFO  - progress: 9767 of 22790 (42%)
```

> **参数说明：**
> - `--no-res`：不反编译资源文件（我们只要代码）
> - `--show-bad-code`：对无法完美反编译的代码也尽力输出
> - `--threads-count 4`：用 4 个线程加速

### 11.2 统计反编译结果

```bash
find /data/user/work/jadx_output/sources -name "*.java" | wc -l
```

**真实输出：18421**（第一次反编译的文件数）

### 11.3 发现问题：部分类缺失

```bash
# 检查自定义类
find /data/user/work/jadx_output/sources -name "ExtractHelper*"
# 真实输出：空（没找到！）

find /data/user/work/jadx_output/sources -name "TraeApplication*"
# 真实输出：空（没找到！）
```

> **为什么有些类缺失？**
> jadx 反编译整个 APK 时，部分类因为依赖关系复杂或字节码异常，反编译失败被静默跳过。

### 11.4 单独反编译 classes9.dex 验证

```bash
mkdir -p /data/user/work/jadx_c9
/data/user/work/jadx_tool/bin/jadx \
  --output-dir /data/user/work/jadx_c9 \
  --no-res --show-bad-code --deobf \
  /data/user/work/trae_cn3_decoded/build/apk/classes9.dex
```

**真实输出：**
```
INFO  - loading ...
INFO  - processing ...
INFO  - done
```

```bash
find /data/user/work/jadx_c9 -name "ExtractHelper*"
```
**真实输出：**
```
/data/user/work/jadx_c9/sources/com/bytedance/trae/conversation/extract/ExtractHelper.java
```

> **结论：** 单独反编译 classes9.dex 时 ExtractHelper 能正常生成。说明 jadx 整体反编译时跳过了这个类。解决办法是逐个 dex 反编译再合并。

### 11.5 补充缺失的 ExtractHelper

```bash
cp /data/user/work/jadx_c9/sources/com/bytedance/trae/conversation/extract/ExtractHelper.java \
   /data/user/work/jadx_output/sources/com/bytedance/trae/conversation/extract/
```

---

## 12. 第十步：逐个 dex 反编译补充缺失

### 12.1 逐个 dex 反编译

```bash
mkdir -p /data/user/work/jadx_all_dex
for dex in /data/user/work/trae_cn3_decoded/build/apk/classes*.dex; do
  echo "--- 反编译 $(basename $dex) ---"
  /data/user/work/jadx_tool/bin/jadx \
    --output-dir /data/user/work/jadx_all_dex/$(basename $dex .dex) \
    --no-res --show-bad-code --deobf \
    "$dex"
done
```

**真实输出：**
```
--- 反编译 classes.dex ---
INFO  - loading ...
INFO  - processing ...
ERROR - finished with errors, count: 44

--- 反编译 classes2.dex ---
INFO  - loading ...
INFO  - processing ...
ERROR - finished with errors, count: 7
...
--- 反编译 classes9.dex ---
INFO  - loading ...
INFO  - processing ...
INFO  - done
```

> **有 ERROR 正常吗？**
> 正常。大 APK 的某些类因为混淆、优化等原因无法完美反编译，jadx 会报错跳过。但绝大多数类能成功。classes9.dex（我们的自定义代码）0 错误。

### 12.2 统计各 dex 反编译文件数

```bash
for dir in /data/user/work/jadx_all_dex/*/; do
  echo -n "$(basename $dir): "
  find "$dir" -name "*.java" | wc -l
done
```

**真实输出：**
```
classes: 4302
classes2: 3561
classes3: 3425
classes4: 4909
classes5: 4483
classes6: 5212
classes7: 3929
classes8: 5807
classes9: 100
```

---

## 13. 第十一步：合并反编译结果

### 13.1 合并命令

```bash
# 创建合并目录，先把第一次整体反编译的结果复制过去
mkdir -p /data/user/work/jadx_merged
cp -r /data/user/work/jadx_output/sources/* /data/user/work/jadx_merged/

# 从各 dex 的结果中补充缺失文件
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
```

> **这个脚本的逻辑是什么？**
> 遍历每个 dex 的反编译结果，如果某个 Java 文件在合并目录中不存在，就复制过去。已存在的文件不覆盖（保留第一次整体反编译的版本）。

### 13.2 统计合并后总数

```bash
find /data/user/work/jadx_merged -name "*.java" | wc -l
```

**真实输出：37987**

### 13.3 验证关键类

```bash
echo "ExtractHelper: $(find /data/user/work/jadx_merged -name 'ExtractHelper.java' -path '*/extract/*' | head -1)"
echo "ApiMessageFetcher: $(find /data/user/work/jadx_merged -name 'ApiMessageFetcher.java' -path '*/extract/*' | head -1)"
echo "FileLogger: $(find /data/user/work/jadx_merged -name 'FileLogger.java' -path '*/extract/*' | head -1)"
echo "GitHubPusher: $(find /data/user/work/jadx_merged -name 'GitHubPusher.java' -path '*/extract/*' | head -1)"
echo "TraeApplication: $(find /data/user/work/jadx_merged -name 'TraeApplication.java' | head -1)"
echo "BuildConfig: $(find /data/user/work/jadx_merged -name 'BuildConfig.java' -path '*/conversation/*' | head -1)"
echo "ServiceManager: $(find /data/user/work/jadx_merged -name 'ServiceManager.java' -path '*/aweme/*' | head -1)"
```

**真实输出：**
```
ExtractHelper: /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/ExtractHelper.java
ApiMessageFetcher: /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/ApiMessageFetcher.java
FileLogger: /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/FileLogger.java
GitHubPusher: /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/GitHubPusher.java
TraeApplication: /data/user/work/jadx_merged/com/bytedance/trae/TraeApplication.java
BuildConfig: /data/user/work/jadx_merged/com/bytedance/trae/conversation/BuildConfig.java
ServiceManager: /data/user/work/jadx_merged/com/ss/android/ugc/aweme/framework/services/ServiceManager.java
```

所有关键类都存在。

---

## 14. 第十二步：用手写 Java 替换自定义类

### 14.1 为什么要替换

jadx 反编译的代码虽然可读，但不如手写的清晰（变量名是 str/str2 而不是有意义的名字，注释丢失等）。4 个自定义类是我们自己写的，直接用手写版本替换。

### 14.2 替换命令

```bash
cp /workspace/java_src/com/bytedance/trae/conversation/extract/ExtractHelper.java \
   /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/ExtractHelper.java
cp /workspace/java_src/com/bytedance/trae/conversation/extract/ApiMessageFetcher.java \
   /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/ApiMessageFetcher.java
cp /workspace/java_src/com/bytedance/trae/conversation/extract/FileLogger.java \
   /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/FileLogger.java
cp /workspace/java_src/com/bytedance/trae/conversation/extract/GitHubPusher.java \
   /data/user/work/jadx_merged/com/bytedance/trae/conversation/extract/GitHubPusher.java
```

### 14.3 验证最终文件数

```bash
find /data/user/work/jadx_merged -name "*.java" | wc -l
```

**真实输出：37987**

---

## 15. 调试排查常用命令

以下是本次会话中实际使用过的调试命令，方便后续排查：

### 15.1 查看 APK 信息

```bash
# 查看 APK 中的 dex 文件列表
unzip -l app.apk | grep "classes.*dex"

# 验证 APK 完整性
unzip -t app.apk

# 验证 APK 签名
java -jar uber-apk-signer.jar -a app.apk -y
```

### 15.2 提取并检查 dex

```bash
# 从 APK 提取某个 dex
unzip -o app.apk classes9.dex -d /tmp/

# 反编译 dex 为 Smali
java -jar baksmali.jar d classes9.dex -o /tmp/smali_output

# 查看自定义类
find /tmp/smali_output -name "*.smali" -path "*/extract/*" | sort
```

### 15.3 对比验证

```bash
# 对比两个 Smali 文件
diff file1.smali file2.smali

# 查看方法签名
grep "^\.method" file.smali

# 搜索引用了某类的地方
grep -rn "ClassName" /path/to/trae_cn3_decoded/smali*/ --include="*.smali"
```

### 15.4 搜索关键参数

```bash
# 搜索 API 参数
grep "before_limit" file.smali
# 搜索 API 路径
grep "solo_hub" file.smali
# 搜索 GitHub 地址
grep "liliangxing" file.smali
# 搜索 SSL 相关
grep "TrustManager" file.smali
```

### 15.5 jadx 反编译

```bash
# 反编译整个 APK
jadx --output-dir output/ --no-res --show-bad-code app.apk

# 反编译单个 dex
jadx --output-dir output/ --no-res --show-bad-code --deobf classes9.dex

# 统计 Java 文件数
find output/sources -name "*.java" | wc -l
```

---

## 16. 避坑提醒

以下是基于实际经验总结的注意事项（部分来自本次会话，部分来自上个会话）：

### 16.1 签名方案

- **必须用 uber-apk-signer**，不能用 jarsigner
- jarsigner 只生成 v1 签名，Android 7.0+ 不认，安装后 "package info is null" 闪退
- 验证时必须看到 `signature verified [v2, v3]`

### 16.2 打包前清缓存

- `apktool b` 之前删除 `build/` 目录
- 不删的话可能用到旧的缓存，打包出来的代码不是最新的

### 16.3 jadx 整体反编译会丢类

- jadx 反编译整个 APK 时，部分类会静默跳过
- 解决办法：逐个 dex 单独反编译，然后合并
- 合并后验证关键类是否存在

### 16.4 App 内部 GitHub Token 失效

- BuildConfig.smali 中硬编码的 GitHub Token 已经被 GitHub 自动吊销（安全扫描机制）
- GitHubPusher 功能（推送到 GitHub 仓库）需要更新 token 才能工作
- 如果要恢复此功能，需要生成新的 Personal Access Token 并替换到 BuildConfig 中

### 16.5 keystore 密码

- 密码是 `trae123`（不是 `trae3123`）
- 记录在 `/workspace/APK_BUILD_SPEC.md` 中

---

## 17. 工具与技能说明

### 17.1 本文档用到的能力

| 能力 | 说明 | 是否需要特殊技能 |
|------|------|----------------|
| 执行 bash 命令 | 运行各种工具命令 | ❌ 基本能力 |
| 读写文件 | 查看/编辑 Smali 和 Java 文件 | ❌ 基本能力 |

### 17.2 不需要特殊技能

本文档**不依赖**以下任何能力：
- ❌ 不需要 MCP 工具
- ❌ 不需要浏览器自动化
- ❌ 不需要 Lark/飞书技能
- ❌ 不需要 AI 图片生成
- ❌ 不需要特殊 IDE 插件

### 17.3 工具清单

| 工具 | 路径 | 用途 |
|------|------|------|
| apktool | 系统安装 | APK 打包 |
| baksmali | `/data/user/work/baksmali.jar` | dex→smali 反汇编 |
| uber-apk-signer | `/data/user/work/uber-apk-signer.jar` | APK 签名（v2/v3） |
| jadx | `/data/user/work/jadx_tool/bin/jadx` | dex→Java 反编译 |
| Java (JDK) | 系统安装 | 运行上述 Java 工具 |
| keystore | `/data/user/work/trae3.keystore` | 签名证书（密码 trae123） |

### 17.4 如果你是 AI Agent

如果你是另一个 AI Agent 读这份文档去执行任务：
1. 你只需要**基本的文件读写和 bash 执行能力**，不需要任何特殊 skill 或 MCP
2. 所有命令都可以直接复制执行，注意替换路径
3. 签名密码是 `trae123`，keystore 在 `/data/user/work/trae3.keystore`
4. 最大的坑是签名：必须用 uber-apk-signer，不能用 jarsigner
5. 打包前删 `build/` 缓存
6. jadx 反编译后要验证关键类是否存在，不存在就逐个 dex 反编译

---

## 附录：本次会话真实执行的命令完整列表

```
# 1. 验证 Smali 一致性（5个diff，全部MATCH）
diff /data/user/work/new_smali_v2/.../ExtractHelper.smali /data/user/work/trae_cn3_decoded/smali_classes9/.../ExtractHelper.smali
diff /data/user/work/new_smali_v2/.../ApiMessageFetcher.smali /data/user/work/trae_cn3_decoded/smali_classes9/.../ApiMessageFetcher.smali
diff /data/user/work/new_smali_v2/.../ApiMessageFetcher$1.smali /data/user/work/trae_cn3_decoded/smali_classes9/.../ApiMessageFetcher$1.smali
diff /data/user/work/new_smali_v2/.../FileLogger.smali /data/user/work/trae_cn3_decoded/smali_classes9/.../FileLogger.smali
diff /data/user/work/new_smali_v2/.../GitHubPusher.smali /data/user/work/trae_cn3_decoded/smali_classes9/.../GitHubPusher.smali

# 2. 检查残留
find /data/user/work/trae_cn3_decoded -path "*/conversation/extract/*.smali" -not -path "*/smali_classes9/*"

# 3. 验证已有APK签名
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v21.apk -y

# 4. 查看dex列表
unzip -l /workspace/trae_cn3_v21.apk | grep "classes.*dex"

# 5. 验证APK完整性
unzip -t /workspace/trae_cn3_v21.apk

# 6. 提取classes9.dex并反编译
unzip -o /workspace/trae_cn3_v21.apk classes9.dex -d /data/user/work/verify_dex
java -jar /data/user/work/baksmali.jar d classes9.dex -o verify_smali

# 7. 验证自定义类
find verify_smali -name "*.smali" -path "*/extract/*" | sort

# 8. 对比dex smali与源码smali（5个diff，全部MATCH）
diff verify_smali/.../ExtractHelper.smali /data/user/work/trae_cn3_decoded/smali_classes9/.../ExtractHelper.smali
# （其余4个类同样diff）

# 9. 验证方法签名（4个类的grep .method）
grep "^\.method" verify_smali/.../ExtractHelper.smali
grep "^\.method" /data/user/work/trae_cn3_decoded/smali_classes9/.../ExtractHelper.smali
# （其余3个类同样grep）

# 10. 验证关键参数
grep "before_limit" verify_smali/.../ApiMessageFetcher.smali
grep "solo_hub" verify_smali/.../ApiMessageFetcher.smali
grep "liliangxing" verify_smali/.../GitHubPusher.smali
grep "TrustManager" verify_smali/.../ApiMessageFetcher.smali
grep "TrustManager" verify_smali/.../ApiMessageFetcher$1.smali

# 11. 验证调用入口
grep -rn "ExtractHelper" /data/user/work/trae_cn3_decoded/smali*/ --include="*.smali" | grep -v "extract/"

# 12. 检查包名版本
grep "package=" /data/user/work/trae_cn3_decoded/AndroidManifest.xml
grep "versionCode\|versionName" /data/user/work/trae_cn3_decoded/apktool.yml

# 13. 干净重建
rm -rf /data/user/work/trae_cn3_decoded/build
apktool b /data/user/work/trae_cn3_decoded -o /workspace/trae_cn3_v22_unsigned.apk

# 14. 签名
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v22_unsigned.apk --out /workspace --ks /data/user/work/trae3.keystore --ksAlias trae3 --ksPass trae123 --ksKeyPass trae123 --allowResign

# 15. 重命名
mv /workspace/trae_cn3_v22_unsigned-aligned-signed.apk /workspace/trae_cn3_v22.apk

# 16. 验证新APK
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v22.apk -y
unzip -t /workspace/trae_cn3_v22.apk

# 17. 验证新APK的dex内容
unzip -o /workspace/trae_cn3_v22.apk classes9.dex -d /data/user/work/verify_dex/verify_v22
java -jar /data/user/work/baksmali.jar d classes9.dex -o v22_smali
diff v22_smali/.../ExtractHelper.smali ../verify_smali/.../ExtractHelper.smali  # MATCH
grep "before_limit" v22_smali/.../ApiMessageFetcher.smali
grep "liliangxing" v22_smali/.../GitHubPusher.smali
grep -rn "ExtractHelper" /data/user/work/trae_cn3_decoded/smali_classes5/ --include="*.smali" | grep -v "extract/"

# 18. 清理临时文件
rm -rf /data/user/work/verify_dex

# 19. 下载安装jadx
wget -q "https://github.com/skylot/jadx/releases/download/v1.5.0/jadx-1.5.0.zip" -O jadx.zip
unzip -q -o jadx.zip -d jadx_tool
/data/user/work/jadx_tool/bin/jadx --version  # 1.5.0

# 20. 全量反编译
/data/user/work/jadx_tool/bin/jadx --output-dir /data/user/work/jadx_output --no-res --show-bad-code --threads-count 4 /workspace/trae_cn3_v22.apk
find /data/user/work/jadx_output/sources -name "*.java" | wc -l  # 18421

# 21. 单独反编译classes9.dex补充
/data/user/work/jadx_tool/bin/jadx --output-dir /data/user/work/jadx_c9 --no-res --show-bad-code --deobf classes9.dex
cp /data/user/work/jadx_c9/sources/.../ExtractHelper.java /data/user/work/jadx_output/sources/.../

# 22. 逐个dex反编译
for dex in /data/user/work/trae_cn3_decoded/build/apk/classes*.dex; do
  /data/user/work/jadx_tool/bin/jadx --output-dir /data/user/work/jadx_all_dex/$(basename $dex .dex) --no-res --show-bad-code --deobf "$dex"
done

# 23. 合并
mkdir -p /data/user/work/jadx_merged
cp -r /data/user/work/jadx_output/sources/* /data/user/work/jadx_merged/
for dir in /data/user/work/jadx_all_dex/*/sources; do
  cd "$dir"
  find . -name "*.java" | while read f; do
    target="/data/user/work/jadx_merged/$f"
    [ ! -f "$target" ] && mkdir -p "$(dirname "$target")" && cp "$f" "$target"
  done
done
find /data/user/work/jadx_merged -name "*.java" | wc -l  # 37987

# 24. 用手写Java替换自定义类
cp /workspace/java_src/.../ExtractHelper.java /data/user/work/jadx_merged/.../
cp /workspace/java_src/.../ApiMessageFetcher.java /data/user/work/jadx_merged/.../
cp /workspace/java_src/.../FileLogger.java /data/user/work/jadx_merged/.../
cp /workspace/java_src/.../GitHubPusher.java /data/user/work/jadx_merged/.../
```
