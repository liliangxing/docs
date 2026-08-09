# TRAE CN3 积分显示修复完整排查搭建指南

> 适用对象：技术基础一般、对命令行不熟悉的开发者或 AI Agent
> 目标：从零开始排查并修复 TRAE CN3 App 中"积分显示为 0.0M"的问题
> 项目仓库：https://github.com/liliangxing/trae-cn3
> 最后更新：2026-08-09

---

## 这份文档是干什么的

TRAE CN3 是一个逆向修改的 Android App。用户有 4500 个积分，但 App 右下角的悬浮窗一直显示"0.0M"，而不是正常的"4.5K"。之前有好几个 AI Agent 尝试修复，但都没彻底解决。

这份文档记录了我从头到尾的完整排查过程：怎么发现问题、用了什么工具、跑了哪些命令、踩了什么坑、最终怎么修好的。目的是让其他技术一般的 Agent 或开发者，能照着这份文档一步步复现整个排查和修复过程。

---

## 1. 问题是什么

### 1.1 现象

用户报告：App 任务详情页右下角有一个积分悬浮显示，但一直显示"0.0M"。用户实际有 4500 积分，应该显示为"4.5K"。

### 1.2 为什么之前的 Agent 没修好

之前的 Agent 试图通过 App 内部的积分管理链路（`CreditsBalanceManager` -> `TocCreditsPolicy` -> `UserPayIdentityService`）来获取积分数据。这条链路依赖太多内部组件，初始化时机复杂，经常拿不到数据，导致显示 0。

### 1.3 我的思路

不依赖 App 内部的积分管理链路，直接用 `HttpsURLConnection` 调用官方额度 API，跟设置页用的是同一个接口。这样绕过所有内部组件依赖，只要能拿到 token 就能获取积分。

---

## 2. 排查过程：怎么找到问题根源

### 2.1 第一步：阅读已有代码和文档

先搞清楚项目里已有什么。项目仓库的 `README.md` 和 `AGENTS_GUIDE.md` 是必读文件，里面记录了项目结构、构建流程和已知问题。

```bash
# 克隆项目仓库
git clone https://github.com/liliangxing/trae-cn3.git
cd trae-cn3

# 阅读项目说明
cat README.md
cat AGENTS_GUIDE.md
```

**为什么要先读文档？** 因为这个项目已经有了完整的构建流程、签名规范和避坑指南。不读文档直接动手，大概率会重复踩坑。

### 2.2 第二步：找到积分相关的源码文件

项目有 37,983 个 Java 文件（jadx 反编译的），需要精确定位到积分相关的代码。

```bash
# 搜索包含 "Credits" 或 "Quota" 的 Java 文件
find source/java -name "*.java" | xargs grep -l "Credits\|Quota" | head -20
```

**真实输出（关键文件）：**
```
source/java/com/bytedance/trae/conversation/extract/QuotaOverlay.java
source/java/com/bytedance/trae/conversation/CreditsBalanceManager.java
source/java/com/bytedance/trae/home/solo/setting/data/DefaultSettingsCreditsRepository.java
source/java/com/bytedance/trae/home/solo/setting/data/model/CreditsUsageResponseDto.java
source/java/com/bytedance/trae/home/solo/setting/SettingsPointsBalancePresentation.java
```

> **技巧说明：** `find` + `xargs grep -l` 是在大量文件中搜索关键词的常用组合。`-l` 参数表示只输出文件名，不输出匹配的内容行。`head -20` 限制只看前 20 个结果，避免输出太多。

### 2.3 第三步：分析官方设置页怎么获取积分

关键发现：App 的设置页（Settings）能正确显示积分。所以设置页的代码就是"标准答案"。

```bash
# 查看设置页积分仓库的源码
cat source/java/com/bytedance/trae/home/solo/setting/data/DefaultSettingsCreditsRepository.java
```

**关键发现 1：API 路径**

在 `DefaultSettingsCreditsRepository.java` 中找到了 API 路径：
```java
private static final String CREDITS_USAGE_PATH = "/trae/api/v2/pay/ide_user_ent_usage";
```

**关键发现 2：API 请求用的主机类型**

```java
// 注意这行！用的是 KmpHostType.Login，不是 AI_HOST
CREDITS_USAGE_REQUEST_OPTIONS = new KmpHttpRequestOptions(
    "user_ent_status", true, false, false,
    null, KmpHostType.Login, ...
);
```

**关键发现 3：请求体**

```java
private final String creditsUsageRequestBody() {
    JsonObjectBuilder builder = new JsonObjectBuilder();
    builder.put("require_usage", true);
    return builder.build().toString();
}
// 等价于 {"require_usage":true}
```

**关键发现 4：响应解析逻辑**

在 `toBalancePresentation` 方法中：
- 遍历 `user_entitlement_pack_list` 数组
- 取 `entitlement_base_info.quota.credits_limit`（-1 表示无限）
- 取 `usage.credits_amount`（已用积分）
- 计算 `remaining = sum(credits_limit) - sum(credits_amount)`
- 如果有 `credits_limit == -1`，显示 `∞`

> **为什么这步最重要？** 这一步揭示了问题的核心：官方设置页用的是 `KmpHostType.Login`（对应 `api.trae.cn`），而之前的 QuotaOverlay 代码用的是 `TraeHttpConnection.baseUrl()`，后者返回的是 AI_HOST（`trae-api-cn.mchost.guru`）。在 AI_HOST 上请求额度接口，会返回 404，导致拿不到数据，显示 0.0M。

### 2.4 第四步：对比旧版 QuotaOverlay 的错误

查看之前版本的 QuotaOverlay 代码（如果存在）或 smali 文件：

```bash
# 在反编译的 smali 中搜索 QuotaOverlay
find /data/user/work/trae_cn3_decoded -name "QuotaOverlay*" -type f 2>/dev/null

# 在 smali 中搜索 baseUrl 的引用
grep -rn "baseUrl\|TraeHttpConnection" /data/user/work/trae_cn3_decoded/smali_classes9/ --include="*.smali" 2>/dev/null
```

> **如果解包目录不存在，需要先用 apktool 解包 APK：**
> ```bash
> java -jar /data/user/work/apktool.jar d /workspace/trae_cn3_v38.apk -o /data/user/work/trae_cn3_decoded -f
> ```

**旧版代码的问题确认：** 旧版 QuotaOverlay 通过 `TraeHttpConnection.baseUrl()` 获取 API 主机地址，这个方法返回的是 AI_HOST（`trae-api-cn.mchost.guru`），而不是 LOGIN_HOST（`api.trae.cn`）。额度接口只在 LOGIN_HOST 上提供，所以在 AI_HOST 上请求会 404。

### 2.5 第五步：确认 API 响应格式

为了验证解析逻辑正确，需要确认 API 实际返回的 JSON 格式。可以通过以下方式：

**方法 A：用 curl 直接调 API（需要 token）**

```bash
# 替换 YOUR_TOKEN 为实际的 x-ide-token
curl -X POST 'https://api.trae.cn/trae/api/v2/pay/ide_user_ent_usage' \
  -H 'Content-Type: application/json' \
  -H 'x-ide-token: YOUR_TOKEN' \
  -d '{"require_usage":true}'
```

**预期响应格式：**
```json
{
  "code": 0,
  "user_entitlement_pack_list": [
    {
      "entitlement_base_info": {
        "quota": {
          "credits_limit": 4500
        }
      },
      "usage": {
        "credits_amount": 123.45
      }
    }
  ]
}
```

> **为什么用 curl 验证？** 在写代码之前先用 curl 确认 API 能通、返回格式对不对，比直接写代码然后猜哪里错了效率高得多。这是"先验证假设再写代码"的基本原则。

**方法 B：看 App 日志**

QuotaOverlay 代码中有 `FileLogger.log()` 调用，日志写在 `/sdcard/douyinguanjia/Log/trae-cn3.log`。可以通过 adb 查看日志：

```bash
# 查看 QuotaOverlay 日志
adb shell cat /sdcard/douyinguanjia/Log/trae-cn3.log | grep QuotaOverlay

# 实时查看日志
adb shell tail -f /sdcard/douyinguanjia/Log/trae-cn3.log | grep QuotaOverlay
```

> **如果 adb 不可用**（比如在服务器环境），可以通过 App 内的 FileLogger 输出查看。日志文件路径是 `/sdcard/douyinguanjia/Log/trae-cn3.log`。

---

## 3. 修复方案：直接调 API

### 3.1 核心改动思路

| 对比项 | 旧版（v39，有 bug） | 新版（v40，修复后） |
|--------|---------------------|---------------------|
| API 主机 | `TraeHttpConnection.baseUrl()`（AI_HOST，会 404） | 硬编码 `https://api.trae.cn`（LOGIN_HOST） |
| 积分数据来源 | `CreditsBalanceManager` 链路 | 直接用 `HttpsURLConnection` 调 API |
| 依赖组件 | 5+ 个内部组件 | 只需 `SdkCommonHttpImpl.getToken()` |
| 可靠性 | 低（组件初始化时机不定） | 高（只要 token 不为空就能拿到数据） |

### 3.2 修改的文件

只需要修改一个文件：`source/java/com/bytedance/trae/conversation/extract/QuotaOverlay.java`

### 3.3 关键代码改动

**改动 1：硬编码正确的 API 主机地址**

```java
// 旧代码（有 bug）：
// String urlStr = TraeHttpConnection.INSTANCE.baseUrl() + CREDITS_API_PATH;
// TraeHttpConnection.baseUrl() 返回 AI_HOST，额度接口不在 AI_HOST 上，会 404

// 新代码（修复后）：
private static final String LOGIN_HOST_URL = "https://api.trae.cn";
String urlStr = LOGIN_HOST_URL + CREDITS_API_PATH;
```

> **为什么硬编码而不是用 TraeHttpConnection？** 因为 `TraeHttpConnection.baseUrl()` 返回的是 AI_HOST，这个主机上没有额度接口。官方设置页用的是 `KmpHostType.Login` 来指定 LOGIN_HOST，但我们注入的自定义代码无法直接使用 Kmp 框架（那是 Kotlin 协程 + 序列化的复杂链路），所以直接硬编码 `https://api.trae.cn` 是最简单可靠的方案。

**改动 2：不依赖 CreditsBalanceManager 链路**

旧版代码通过 `CreditsBalanceManager.addListener()` 注册监听器，等 App 内部刷新积分时回调。但这个链路经常不触发回调（组件初始化时机问题），导致永远拿不到数据。

新版代码改为主动轮询：每 5 秒直接调 API，不依赖任何内部组件。

**改动 3：格式化逻辑**

```java
// 格式化剩余积分
private static String formatRemaining(long remaining) {
    if (remaining >= 1000000) {
        return String.format(Locale.US, "%.1fM", remaining / 1000000.0);
    } else if (remaining >= 10000) {
        return String.format(Locale.US, "%.1fW", remaining / 10000.0);
    } else if (remaining >= 1000) {
        return String.format(Locale.US, "%.1fK", remaining / 1000.0);
    } else {
        return String.valueOf(remaining);
    }
}
```

> **4500 积分怎么变成 4.5K 的？** 4500 >= 1000，所以走第三个分支：`4500 / 1000.0 = 4.5`，格式化为 `"%.1fK"` 就是 `"4.5K"`。

### 3.4 完整的 QuotaOverlay.java 代码结构

整个文件 379 行，核心流程如下：

```
start(Activity)
  -> 创建 TextView 悬浮在右下角
  -> fetchQuotaAsync()  // 后台线程
     -> SdkCommonHttpImpl.INSTANCE.getToken()  // 获取登录 token
     -> POST https://api.trae.cn/trae/api/v2/pay/ide_user_ent_usage
        Headers: x-ide-token, Content-Type: application/json
        Body: {"require_usage":true}
     -> parseCreditsResponse(responseBody)
        -> 遍历 user_entitlement_pack_list[]
           -> pack.entitlement_base_info.quota.credits_limit  (Long, -1=无限)
           -> pack.usage.credits_amount  (Double)
        -> remaining = sum(credits_limit>0) - sum(credits_amount)
     -> formatRemaining(remaining)  // ∞ / X.XM / X.XW / X.XK / 原始数字
     -> updateText(displayText)  // 主线程更新 TextView
  -> 每 5 秒重复 fetchQuotaAsync()

stop()
  -> 移除 TextView，停止轮询
```

---

## 4. 构建和打包：从代码到 APK

### 4.1 前提条件

需要以下工具（所有路径以实际环境为准）：

| 工具 | 路径 | 用途 |
|------|------|------|
| Java JDK | 系统安装 | 编译 Java |
| apktool 2.9.3 | `/data/user/work/apktool.jar` | APK 解包/编译 |
| baksmali 2.5.2 | `/data/user/work/baksmali.jar` | dex -> smali 反汇编 |
| smali 2.5.2 | `/data/user/work/smali.jar` | smali -> dex 汇编 |
| uber-apk-signer 1.3.0 | `/data/user/work/uber-apk-signer.jar` | APK 签名（v2+v3） |
| d8 或 dx | `/usr/lib/android-sdk/build-tools/28.0.3/d8` | .class -> .dex |
| android.jar | `/usr/lib/android-sdk/platforms/android-23/android.jar` | Android 框架类 |
| keystore | `/data/user/work/trae3.keystore` | 签名证书（密码 trae123） |

### 4.2 方式 A：用自动化脚本（推荐）

项目根目录有 `build.sh`，一键完成编译、打包、签名、验证：

```bash
# 用法
./build.sh <输入APK> <输出APK>

# 示例：从 v38 构建 v39
./build.sh /workspace/trae_cn3_v38.apk /workspace/trae_cn3_v39.apk
```

脚本会自动完成 7 个步骤：
1. 检查/安装工具
2. 编译 Java -> Smali（含 MediaStore stub）
3. classes5.dex 生命周期挂接注入
4. classes9.dex 替换自定义类
5. 组装 APK（删签名 -> 替换 dex -> 恢复 services）
6. 签名（v2+v3）
7. 自动验证（签名 + dex 完整性 + 挂接检查）

> **为什么推荐用 build.sh？** 手动操作有十几个步骤，任何一步出错都会导致 APK 无法安装或功能异常。build.sh 用 `set -e` 保证任何步骤失败立即停止，并在最后自动验证产物正确性。

### 4.3 方式 B：手动构建（理解流程）

如果想理解每一步在干什么，可以手动操作。

#### 步骤 1：安装工具

```bash
# 安装基础工具
apt-get update -qq
apt-get install -y -qq default-jdk android-sdk-build-tools

# 下载 apktool 2.9.3（不要用 apt 版本，有 bug）
wget -q "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar" \
  -O /data/user/work/apktool.jar

# 下载 uber-apk-signer
wget -q "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar" \
  -O /data/user/work/uber-apk-signer.jar

# 下载 baksmali 和 smali
wget -q "https://bitbucket.org/JesusFreke/smali/downloads/baksmali-2.5.2.jar" \
  -O /data/user/work/baksmali.jar
wget -q "https://bitbucket.org/JesusFreke/smali/downloads/smali-2.5.2.jar" \
  -O /data/user/work/smali.jar

# 生成签名证书（如果还没有）
keytool -genkey -v -keystore /data/user/work/trae3.keystore \
  -alias trae3 -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass trae123 -keypass trae123 \
  -dname "CN=TRAE3, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN"
```

> **为什么要下载 2.9.3 版本的 apktool？** apt 安装的 apktool 2.5.0 有 bug，aapt 不支持 `$` 开头的资源名。apktool 2.9.3 修复了这个问题。

#### 步骤 2：创建 MediaStore stub

> **这一步很容易漏掉！** 如果代码用了 `MediaStore.Downloads`（API 29+ 的功能），但编译用的 android.jar 是 API 23，javac 会报 `cannot find symbol: MediaStore.Downloads`，编译失败。

```bash
ANDROID_JAR=/usr/lib/android-sdk/platforms/android-23/android.jar

# 创建 MediaStore stub
mkdir -p /data/user/work/mediastub/src/android/provider
cat > /data/user/work/mediastub/src/android/provider/MediaStore.java << 'STUB'
package android.provider;
import android.net.Uri;
public final class MediaStore {
    public static final class Downloads {
        public static final String DISPLAY_NAME = "_display_name";
        public static final String MIME_TYPE = "mime_type";
        public static final String RELATIVE_PATH = "relative_path";
        public static final Uri EXTERNAL_CONTENT_URI = Uri.parse("content://media/external/downloads");
    }
}
STUB

# 编译 stub
mkdir -p /data/user/work/mediastub/classes
javac -source 8 -target 8 -cp "$ANDROID_JAR" \
  -d /data/user/work/mediastub/classes \
  /data/user/work/mediastub/src/android/provider/MediaStore.java

# 打包为 jar
cd /data/user/work/mediastub/classes
jar cf /data/user/work/mediastub/mediastub.jar .
cd /
```

> **为什么 stub 不打包进 APK？** stub 只在编译期让 javac 不报错。运行时，API 29+ 的 Android 系统自带 `MediaStore.Downloads`，不需要我们提供。如果把它打包进 APK，反而会和系统类冲突。

#### 步骤 3：编译 stub 类

项目有 16 个 stub 类（空壳类），用于解决编译依赖。比如 `SdkCommonHttpImpl.java` 提供了 `getToken()` 方法的声明，运行时由 APK 内的真实类提供实现。

```bash
REPO=/data/user/work/trae-cn3-repo

# 编译 stub 类
rm -rf /data/user/work/stubs/classes
mkdir -p /data/user/work/stubs/classes
javac -source 8 -target 8 \
  -cp "/data/user/work/mediastub/mediastub.jar:$ANDROID_JAR" \
  -d /data/user/work/stubs/classes \
  $(find "$REPO/source/stubs" -name "*.java")

# 打包 stub 为 jar
cd /data/user/work/stubs/classes
jar cf /data/user/work/stubs/stubs.jar .
cd /
```

> **注意 classpath 顺序：** MediaStore stub jar 必须放在 android.jar **前面**，否则 javac 会优先使用 android.jar 里的 MediaStore（API 23 版本没有 Downloads 内部类）。

#### 步骤 4：编译自定义 Java 文件

```bash
# 编译 extract 包下的所有 Java 文件
rm -rf /data/user/work/build/classes
mkdir -p /data/user/work/build/classes
javac -source 8 -target 8 \
  -cp "/data/user/work/mediastub/mediastub.jar:$ANDROID_JAR:/data/user/work/stubs/stubs.jar" \
  -d /data/user/work/build/classes \
  "$REPO/source/java/com/bytedance/trae/conversation/extract/"*.java
```

> **`-source 8 -target 8` 是什么意思？** 使用 Java 8 语法和字节码。Android 的 dex 工具不支持 Java 9+ 的字节码。

#### 步骤 5：转 dex 再转 smali

```bash
# 打包为 jar
cd /data/user/work/build/classes
jar cf /data/user/work/build/classes.jar .
cd /

# d8 转 dex（d8 优先，dx 回退）
D8=/usr/lib/android-sdk/build-tools/28.0.3/d8
if [ -f "$D8" ]; then
    "$D8" --release --lib "$ANDROID_JAR" \
      --output /data/user/work/build/dexout \
      /data/user/work/build/classes.jar
else
    /usr/lib/android-sdk/build-tools/debian/dx --dex \
      --output=/data/user/work/build/dexout/classes.dex \
      /data/user/work/build/classes
fi

# baksmali 反编译为 smali
rm -rf /data/user/work/build/smali
java -jar /data/user/work/baksmali.jar d \
  /data/user/work/build/dexout/classes.dex \
  -o /data/user/work/build/smali
```

> **为什么要 Java -> class -> dex -> smali 这么多步？** Android 不能直接运行 Java 字节码，需要转成 dex 格式。但 APK 里的代码是以 smali 格式存储在 dex 中的，所以需要再反编译成 smali，然后替换到 APK 对应的 dex 中。

#### 步骤 6：替换 dex 并组装 APK

```bash
INPUT_APK=/workspace/trae_cn3_v38.apk
OUTPUT_APK=/workspace/trae_cn3_v39.apk
WORKTMP=/data/user/work/fast_build

rm -rf "$WORKTMP"
mkdir -p "$WORKTMP"
cd "$WORKTMP"

# --- classes5.dex: 生命周期挂接 ---
unzip -o "$INPUT_APK" classes5.dex -d . >/dev/null
java -jar /data/user/work/baksmali.jar d classes5.dex -o c5s

# 注入 QuotaOverlay.start()/stop() 到 ConversationActivity
CA_SMALI="$WORKTMP/c5s/com/bytedance/trae/conversation/ConversationActivity.smali"
python3 "$REPO/BUILD_SCRIPT/patch_conversation_activity.py" "$CA_SMALI"

# 回编译
java -jar /data/user/work/smali.jar a c5s -o classes5_patched.dex
cp classes5_patched.dex classes5.dex

# --- classes9.dex: 替换自定义类 ---
unzip -o "$INPUT_APK" classes9.dex -d . >/dev/null
java -jar /data/user/work/baksmali.jar d classes9.dex -o c9s

# 替换 extract 类
rm -rf "c9s/com/bytedance/trae/conversation/extract"
cp -r /data/user/work/build/smali/com/bytedance/trae/conversation/extract \
      "c9s/com/bytedance/trae/conversation/extract"

java -jar /data/user/work/smali.jar a c9s -o classes9_patched.dex
cp classes9_patched.dex classes9.dex

# --- 组装 APK ---
cp "$INPUT_APK" "$OUTPUT_APK"

# 删除旧签名
zip -d "$OUTPUT_APK" "META-INF/*" 2>&1 | grep -E "deleting|warning" || true

# 替换两个 dex（-0 表示不压缩，dex 必须以不压缩方式存储）
zip -0 "$OUTPUT_APK" classes5.dex
zip -0 "$OUTPUT_APK" classes9.dex

# 恢复 META-INF/services（删除签名时被误删）
rm -rf "$WORKTMP/services"
mkdir -p "$WORKTMP/services"
unzip -o "$INPUT_APK" "META-INF/services/*" -d "$WORKTMP/services" >/dev/null 2>&1 || true
cd "$WORKTMP/services"
if ls META-INF/services/* 2>/dev/null; then
    zip "$OUTPUT_APK" META-INF/services/* 2>&1 | grep "adding" || true
fi
```

> **为什么要替换两个 dex？**
> - `classes9.dex`：存放我们的自定义类（QuotaOverlay、ExtractHelper 等）
> - `classes5.dex`：需要在 `ConversationActivity` 的 `onResume`/`onStop` 中注入 `QuotaOverlay.start()`/`stop()` 调用，这样进入对话页面时悬浮窗才显示，离开时才消失

> **为什么要恢复 META-INF/services？** `zip -d "META-INF/*"` 删除签名时，会把 `META-INF/services/` 目录也删掉。这个目录存放的是 Service Provider 配置文件（比如 `okhttp` 的配置），删掉后部分网络库会无法工作。

> **`zip -0` 是什么意思？** `-0` 表示不压缩，原样存储。Android 的 dex 文件必须以不压缩方式存储在 APK 中，否则安装后无法加载。

#### 步骤 7：签名

```bash
java -jar /data/user/work/uber-apk-signer.jar \
  -a "$OUTPUT_APK" \
  --out /workspace \
  --ks /data/user/work/trae3.keystore \
  --ksAlias trae3 \
  --ksPass trae123 \
  --ksKeyPass trae123 \
  --allowResign

# 重命名签名后的文件
SIGNED_FILE="/workspace/$(basename "$OUTPUT_APK" .apk)-aligned-signed.apk"
if [ -f "$SIGNED_FILE" ]; then
    mv "$SIGNED_FILE" "$OUTPUT_APK"
fi
```

> **绝对不能用 jarsigner！** jarsigner 只生成 v1 签名，Android 7.0+ 不认 v1，安装后会闪退（错误信息："package info is null"）。必须用 uber-apk-signer，它会生成 v2+v3 签名。

> **参数说明：**
> | 参数 | 含义 |
> |------|------|
> | `-a` | 输入 APK 路径 |
> | `--out` | 输出目录 |
> | `--ks` | keystore 文件路径 |
> | `--ksAlias` | 证书别名（trae3） |
> | `--ksPass` | keystore 密码（trae123） |
> | `--ksKeyPass` | key 密码（trae123） |
> | `--allowResign` | 允许覆盖已有签名 |

### 4.4 验证 APK

```bash
# 1. 验证签名（必须看到 [v2, v3]）
java -jar /data/user/work/uber-apk-signer.jar -a "$OUTPUT_APK" -y

# 2. 验证 APK 完整性
unzip -t "$OUTPUT_APK" 2>&1 | tail -1
# 应输出: No errors detected in compressed data of ...

# 3. 验证 classes9.dex 包含 QuotaOverlay
mkdir -p /tmp/verify && cd /tmp/verify
unzip -o "$OUTPUT_APK" classes9.dex -d .
java -jar /data/user/work/baksmali.jar d classes9.dex -o verify_smali
find verify_smali -name "QuotaOverlay.smali" -path "*/extract/*"
# 应输出: verify_smali/com/bytedance/trae/conversation/extract/QuotaOverlay.smali

# 4. 验证 classes5.dex 包含生命周期挂接
unzip -o "$OUTPUT_APK" classes5.dex -d .
java -jar /data/user/work/baksmali.jar d classes5.dex -o verify_c5
grep "QuotaOverlay;->start" verify_c5/com/bytedance/trae/conversation/ConversationActivity.smali
# 应输出: invoke-static {p0}, Lcom/bytedance/trae/conversation/extract/QuotaOverlay;->start(Landroid/app/Activity;)V
grep "QuotaOverlay;->stop" verify_c5/com/bytedance/trae/conversation/ConversationActivity.smali
# 应输出: invoke-static {}, Lcom/bytedance/trae/conversation/extract/QuotaOverlay;->stop()V

# 5. 验证 API 地址是否正确（关键修复点！）
grep "api.trae.cn" verify_smali/com/bytedance/trae/conversation/extract/QuotaOverlay.smali
# 应输出: const-string v0, "https://api.trae.cn"

# 6. 清理
rm -rf /tmp/verify
```

> **为什么要验证这么多？** 因为此前的 Agent 多次出现"改了代码但 APK 里没生效"的问题。原因包括：编译失败但错误被吞掉、build 缓存没删、dex 文件名不对等。每一步都验证才能确保最终产物正确。

---

## 5. 生命周期挂接：让悬浮窗在对话页面显示

### 5.1 为什么要挂接

QuotaOverlay 是一个独立的类，App 原本不知道它的存在。需要在 `ConversationActivity`（对话页面）的 `onResume`（页面显示时）调用 `QuotaOverlay.start()`，在 `onStop`（页面离开时）调用 `QuotaOverlay.stop()`。

### 5.2 挂接脚本

项目提供了 `BUILD_SCRIPT/patch_conversation_activity.py`，这是一个幂等的 Python 脚本，自动在 smali 中注入挂接代码。

```bash
# 用法
python3 BUILD_SCRIPT/patch_conversation_activity.py <ConversationActivity.smali路径>
```

**脚本逻辑：**
1. 如果 smali 中已有 `QuotaOverlay` 引用，跳过（幂等，多次运行不会重复注入）
2. 在 `onResume()` 的 `invoke-super` 之后插入 `QuotaOverlay.start(Activity)`
3. 在 `onStop()` 的 `return-void` 之前插入 `QuotaOverlay.stop()`

> **什么是"幂等"？** 幂等意味着同一个操作执行多次和执行一次效果相同。如果脚本已经注入过，再次运行不会重复注入，避免出错。

### 5.3 挂接后的 smali 代码

在 `ConversationActivity.smali` 的 `onResume` 方法中：

```smali
# 原始代码：调用父类 onResume
invoke-super {p0}, Lcom/bytedance/trae/common/activity/TraeCommonAppCompatActivity;->onResume()V

# 注入的代码：启动 QuotaOverlay
invoke-static {p0}, Lcom/bytedance/trae/conversation/extract/QuotaOverlay;->start(Landroid/app/Activity;)V
```

在 `onStop` 方法中：

```smali
# 注入的代码：停止 QuotaOverlay
invoke-static {}, Lcom/bytedance/trae/conversation/extract/QuotaOverlay;->stop()V

# 原始代码：方法返回
return-void
```

---

## 6. 调试排查常用命令汇总

以下是排查过程中用到的所有命令，按用途分类。如果你要手工模拟整个过程，照着这些命令一步步跑就行。

### 6.1 搜索代码

```bash
# 在 Java 源码中搜索关键词
find source/java -name "*.java" | xargs grep -l "Credits\|Quota"

# 在 smali 中搜索某个类的引用
grep -rn "QuotaOverlay" /data/user/work/trae_cn3_decoded/smali*/ --include="*.smali"

# 在 smali 中搜索方法签名
grep "^\.method" file.smali

# 在 smali 中搜索字符串常量
grep "const-string" file.smali | grep "api.trae"

# 查找某个包下的所有文件
find source/java -path "*/setting/data/*.java" -name "*.java"
```

### 6.2 APK 操作

```bash
# 查看 APK 中的 dex 文件列表
unzip -l app.apk | grep "classes.*dex"

# 验证 APK 完整性
unzip -t app.apk

# 验证 APK 签名
java -jar uber-apk-signer.jar -a app.apk -y

# 从 APK 提取某个 dex
unzip -o app.apk classes9.dex -d /tmp/

# 从 APK 提取多个文件
unzip -o app.apk classes5.dex classes9.dex -d /tmp/
```

### 6.3 dex/smali 操作

```bash
# dex -> smali（反汇编）
java -jar baksmali.jar d classes9.dex -o smali_output

# smali -> dex（汇编）
java -jar smali.jar a smali_dir -o classes9.dex

# 验证 dex 中包含某个类
dexdump -f classes9.dex | grep "QuotaOverlay"
```

### 6.4 编译相关

```bash
# 编译 Java 文件
javac -source 8 -target 8 \
  -cp "mediastub.jar:android.jar:stubs.jar" \
  -d output_dir \
  source/java/.../*.java

# class -> jar
cd output_dir && jar cf classes.jar .

# jar -> dex（d8 优先）
d8 --release --lib android.jar --output dexout classes.jar
# 或 dx 回退
dx --dex --output=classes.dex output_dir

# 查看编译是否成功（检查生成的 smali 文件数量）
find smali_output -name "*.smali" -path "*/extract/*" | wc -l
```

### 6.5 签名相关

```bash
# 签名
java -jar uber-apk-signer.jar \
  -a unsigned.apk \
  --out /workspace \
  --ks keystore.keystore \
  --ksAlias trae3 \
  --ksPass trae123 \
  --ksKeyPass trae123 \
  --allowResign

# 验证签名（必须看到 [v2, v3]）
java -jar uber-apk-signer.jar -a signed.apk -y
```

### 6.6 日志查看

```bash
# 查看 App 日志（需要 adb）
adb shell cat /sdcard/douyinguanjia/Log/trae-cn3.log

# 过滤 QuotaOverlay 相关日志
adb shell cat /sdcard/douyinguanjia/Log/trae-cn3.log | grep QuotaOverlay

# 实时查看日志
adb shell tail -f /sdcard/douyinguanjia/Log/trae-cn3.log | grep QuotaOverlay

# 查看 logcat（系统日志）
adb logcat | grep -i "trae\|quota\|UnsatisfiedLink"
```

### 6.7 对比验证

```bash
# 对比两个 smali 文件是否一致
diff file1.smali file2.smali
# 无输出 = 完全一致

# 对比 APK 中的 dex 与源码 smali
unzip -o app.apk classes9.dex -d /tmp/verify
java -jar baksmali.jar d /tmp/verify/classes9.dex -o /tmp/verify/smali
diff /tmp/verify/smali/.../QuotaOverlay.smali source/smali/.../QuotaOverlay.smali
```

---

## 7. 避坑大全

以下是实际踩过的坑和解决方案，按严重程度排序。

### 坑 1：积分显示 0.0M（本次修复的核心问题）

**原因：** API 请求发到了错误的主机。额度接口在 `api.trae.cn`（LOGIN_HOST）上，但旧代码用 `TraeHttpConnection.baseUrl()` 获取主机地址，返回的是 `trae-api-cn.mchost.guru`（AI_HOST），这个主机上没有额度接口，返回 404。

**解决：** 硬编码 `https://api.trae.cn`，不用 `TraeHttpConnection.baseUrl()`。

**排查命令：**
```bash
# 在 smali 中搜索 baseUrl 的引用
grep -rn "baseUrl\|TraeHttpConnection" smali_classes9/ --include="*.smali"

# 确认 API 地址是否正确
grep "api.trae.cn" smali_classes9/.../QuotaOverlay.smali
```

### 坑 2：用 jarsigner 签名导致"package info is null"闪退

**原因：** jarsigner 只生成 v1 签名，Android 7.0+（API 24+）要求 v2 或 v3 签名。只有 v1 签名的 APK 安装到 Android 14 上会闪退。

**解决：** 必须用 uber-apk-signer，它会自动生成 v2+v3 签名 + zipalign 对齐。

**验证命令：**
```bash
java -jar uber-apk-signer.jar -a app.apk -y
# 必须看到: signature verified [v2, v3]
```

### 坑 3：编译报错 cannot find symbol: MediaStore.Downloads

**原因：** 代码用了 `MediaStore.Downloads`（API 29+），但编译用的 android.jar 是 API 23，没有这个类。

**解决：** 创建 MediaStore stub 类，编译时把 stub jar 放在 classpath 最前面。

```bash
# 检查 android.jar 版本
ls /usr/lib/android-sdk/platforms/
# 如果只有 android-23，需要创建 stub

# 验证 stub 是否生效
javac -source 8 -target 8 \
  -cp "mediastub.jar:android.jar:stubs.jar" \
  -d output \
  source.java
# 不报错 = stub 生效
```

### 坑 4：打包后代码没变（build 缓存问题）

**原因：** apktool 会缓存上次构建的中间文件（`build/` 目录）。如果修改了 Java/Smali 但缓存没更新，打包用的还是旧代码。

**解决：** 打包前删除 `build/` 目录。

```bash
rm -rf /data/user/work/trae_cn3_decoded/build
```

### 坑 5：META-INF/services 被误删

**原因：** `zip -d apk "META-INF/*"` 删除签名时，把 `META-INF/services/` 目录也删了。这个目录存放 Service Provider 配置，删掉后部分库（如 OkHttp）无法工作。

**解决：** 从原始 APK 提取 `META-INF/services/*` 并重新打包。

```bash
unzip -o original.apk "META-INF/services/*" -d /tmp/services
cd /tmp/services
zip new.apk META-INF/services/*
```

### 坑 6：dex 文件名不标准

**原因：** smali 汇编器输出的 dex 文件名可能不标准（如 `classes5_patched.dex`），但 Android 只加载 `classes.dex`、`classes2.dex`、`classes3.dex` 等标准命名的 dex。

**解决：** 替换前重命名为标准名称。

```bash
cp classes5_patched.dex classes5.dex
cp classes9_patched.dex classes9.dex
zip -0 app.apk classes5.dex classes9.dex
```

### 坑 7：编译失败但错误被吞掉

**原因：** 构建脚本中用了 `|| true` 吞掉错误，或者没有 `set -e`，导致编译失败后继续执行，最终打包的是旧 dex。

**解决：** 每次打包后必须验证 APK 中的 smali 包含新代码。

```bash
# 验证 APK 中确实包含新代码
unzip -o app.apk classes9.dex -d /tmp/
java -jar baksmali.jar d /tmp/classes9.dex -o /tmp/smali
grep "api.trae.cn" /tmp/smali/.../QuotaOverlay.smali
# 如果没输出，说明编译失败，APK 里是旧代码
```

### 坑 8：apktool 资源编译失败

**原因：** apktool 2.9.3 的 framework apk 太旧，不认识 `dataExtractionRules` 属性，资源编译会报错。

**解决：** 不用 apktool 编译资源，只编译 dex。然后手动替换 dex 到原始 APK 中。这就是 `build.sh` 快速路径的设计思路。

### 坑 9：keystore 不存在或签名不同

**原因：** 新环境没有 keystore，或者用了新生成的 keystore（SHA256 不同），导致无法覆盖安装旧版本 APK。

**解决：** 安装前先卸载旧版本。或者确保使用同一个 keystore 文件。

```bash
# 卸载旧版本
adb uninstall com.bytedance.trae.cn3

# 安装新版本
adb install trae_cn3_v39.apk
```

### 坑 10：旧版 QuotaOverlay 依赖 CreditsBalanceManager 链路

**原因：** v39 版本的 QuotaOverlay 通过 `CreditsBalanceManager.addListener()` 注册监听器，等 App 内部刷新积分时回调。但这条链路依赖 `TocCreditsPolicy` -> `UserPayIdentityService` 等多个组件，初始化时机不确定，经常不触发回调。

**解决：** v40 版本完全不依赖这条链路，改为每 5 秒主动调 API。

---

## 8. 关键源码解读

### 8.1 QuotaOverlay.java 核心方法

#### parseCreditsResponse：解析 API 响应

```java
private static String parseCreditsResponse(String responseBody) {
    JSONObject root = new JSONObject(responseBody);

    // 1. 检查返回码（支持顶层和 data 内嵌两种结构）
    long effectiveCode = 0;
    if (root.has("code")) {
        effectiveCode = root.optLong("code", 0);
    } else {
        JSONObject dataObj = root.optJSONObject("data");
        if (dataObj != null && dataObj.has("code")) {
            effectiveCode = dataObj.optLong("code", 0);
        }
    }
    if (effectiveCode != 0) {
        return null;  // API 返回错误
    }

    // 2. 获取积分包列表（支持顶层和 data 内嵌）
    JSONArray packs = root.optJSONArray("user_entitlement_pack_list");
    if (packs == null) {
        JSONObject dataObj = root.optJSONObject("data");
        if (dataObj != null) {
            packs = dataObj.optJSONArray("user_entitlement_pack_list");
        }
    }
    if (packs == null || packs.length() == 0) {
        return null;  // 没有积分包
    }

    // 3. 遍历积分包，计算总额度和已用量
    boolean hasInfinite = false;
    long totalLimit = 0;
    double totalUsed = 0;

    for (int i = 0; i < packs.length(); i++) {
        JSONObject pack = packs.optJSONObject(i);
        JSONObject baseInfo = pack.optJSONObject("entitlement_base_info");
        JSONObject quota = baseInfo.optJSONObject("quota");
        long creditsLimit = quota.optLong("credits_limit", 0);

        if (creditsLimit == -1) {
            hasInfinite = true;  // 无限额度
        } else if (creditsLimit > 0) {
            totalLimit += creditsLimit;
            JSONObject usage = pack.optJSONObject("usage");
            if (usage != null) {
                totalUsed += usage.optDouble("credits_amount", 0);
            }
        }
    }

    // 4. 返回格式化的剩余额度
    if (hasInfinite) return "\u221e";  // ∞
    long remaining = totalLimit - Math.round(totalUsed);
    return formatRemaining(remaining);
}
```

> **为什么要支持两种 JSON 结构？** API 在不同情况下返回的 JSON 结构可能不同。有时 `user_entitlement_pack_list` 在顶层，有时嵌套在 `data` 对象里。两种都要处理，否则某些情况下解析失败。

#### formatRemaining：格式化显示

```java
private static String formatRemaining(long remaining) {
    if (remaining >= 1000000) {
        return String.format(Locale.US, "%.1fM", remaining / 1000000.0);
        // 1500000 -> "1.5M"
    } else if (remaining >= 10000) {
        return String.format(Locale.US, "%.1fW", remaining / 10000.0);
        // 50000 -> "5.0W"（万）
    } else if (remaining >= 1000) {
        return String.format(Locale.US, "%.1fK", remaining / 1000.0);
        // 4500 -> "4.5K"
    } else {
        return String.valueOf(remaining);
        // 500 -> "500"
    }
}
```

> **为什么用 `Locale.US`？** `String.format` 默认用系统语言环境。在某些语言环境下，小数点可能是逗号（如德语 `4,5K`），这会导致显示异常。指定 `Locale.US` 确保始终用英文小数点。

#### createTrustAllSocketFactory：信任所有 SSL 证书

```java
private static SSLSocketFactory createTrustAllSocketFactory() {
    TrustManager[] trustManagers = new TrustManager[]{
        new X509TrustManager() {
            public void checkClientTrusted(X509Certificate[] chain, String authType) {}
            public void checkServerTrusted(X509Certificate[] chain, String authType) {}
            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
        }
    };
    SSLContext sslContext = SSLContext.getInstance("TLS");
    sslContext.init(null, trustManagers, new SecureRandom());
    return sslContext.getSocketFactory();
}
```

> **为什么信任所有证书？** TRAE 的 API 域名可能使用了内部 CA 签发的证书，系统不信任。为了能正常请求 API，需要信任所有证书。这在生产环境中是不安全的，但对于逆向修改的 App 来说是可接受的折衷。

### 8.2 官方设置页的对比

官方设置页 `DefaultSettingsCreditsRepository.java` 用的是 Kotlin 协程 + `KmpHttpClient` + `kotlinx.serialization` 的复杂链路。我们注入的自定义代码无法使用这些 Kotlin 框架，所以用纯 Java 的 `HttpsURLConnection` + `org.json.JSONObject` 实现相同功能。

| 对比项 | 官方设置页 | 我们的 QuotaOverlay |
|--------|-----------|-------------------|
| HTTP 客户端 | KmpHttpClient | HttpsURLConnection |
| JSON 解析 | kotlinx.serialization | org.json.JSONObject |
| 异步 | Kotlin 协程 | Thread + Handler |
| 主机指定 | KmpHostType.Login | 硬编码 `https://api.trae.cn` |
| 触发方式 | 用户打开设置页 | 每 5 秒自动轮询 |

两种方式调用的是**同一个 API**（`/trae/api/v2/pay/ide_user_ent_usage`），发送**相同的请求体**（`{"require_usage":true}`），解析逻辑也**完全一致**。

---

## 9. 完整排查流程图

```
用户报告：积分显示 0.0M
    |
    v
阅读项目文档（README.md, AGENTS_GUIDE.md）
    |
    v
搜索积分相关源码（find + grep -l "Credits\|Quota"）
    |
    v
发现官方设置页能正确显示积分
    |
    v
分析官方代码（DefaultSettingsCreditsRepository.java）
    |-- 发现 API 路径: /trae/api/v2/pay/ide_user_ent_usage
    |-- 发现主机类型: KmpHostType.Login (= api.trae.cn)
    |-- 发现请求体: {"require_usage":true}
    |-- 发现解析逻辑: 遍历 user_entitlement_pack_list
    |
    v
分析旧版 QuotaOverlay 代码
    |-- 发现用了 TraeHttpConnection.baseUrl()
    |-- 发现 baseUrl() 返回 AI_HOST (trae-api-cn.mchost.guru)
    |-- 发现 AI_HOST 上没有额度接口 -> 404 -> 显示 0
    |
    v
确认问题根因：API 主机地址错误
    |
    v
编写修复方案
    |-- 硬编码 https://api.trae.cn
    |-- 用 HttpsURLConnection 直接调 API
    |-- 不依赖 CreditsBalanceManager 链路
    |-- 5 秒轮询
    |
    v
编译 Java -> Smali（含 stub 类、MediaStore stub）
    |
    v
替换 classes9.dex（自定义类）
替换 classes5.dex（生命周期挂接）
    |
    v
组装 APK + 签名（uber-apk-signer, v2+v3）
    |
    v
验证（签名 + dex 完整性 + 挂接 + API 地址）
    |
    v
安装测试 -> 4500 积分显示为 4.5K -> 修复成功
```

---

## 10. 如果你是 AI Agent

如果你是另一个 AI Agent 读这份文档去执行类似任务：

1. **先读项目文档**：`README.md` 和 `AGENTS_GUIDE.md` 是必读的，里面有项目结构、构建流程和避坑指南
2. **核心原则**：自定义代码只存 Java，不存 Smali。Smali 是编译生成的中间产物
3. **用 build.sh**：有自动化构建脚本就用，不要手动操作十几个步骤
4. **签名密码**：`trae123`，keystore 在 `/data/user/work/trae3.keystore`
5. **最大的坑是签名**：必须用 uber-apk-signer（v2+v3），不能用 jarsigner
6. **打包前删 build 缓存**：`rm -rf decoded_project/build`
7. **打包后必须验证**：反编译 APK 中的 smali，grep 关键字符串确认新代码已生效
8. **积分问题的核心**：API 主机地址必须是 `api.trae.cn`，不能用 `TraeHttpConnection.baseUrl()`
9. **不需要任何特殊 skill**：只需要基本的文件读写和 bash 执行能力

---

## 11. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v39 | 2026-08-09 | 首次添加 QuotaOverlay，但用了 CreditsBalanceManager 链路，显示 0.0M |
| v40 | 2026-08-09 | 修复：改为直接调 API，硬编码 `api.trae.cn`，4500 积分正确显示为 4.5K |

---

## 附录：完整命令速查

```bash
# ========== 1. 环境准备 ==========
apt-get install -y -qq default-jdk android-sdk-build-tools
wget -q "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar" -O /data/user/work/apktool.jar
wget -q "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar" -O /data/user/work/uber-apk-signer.jar
wget -q "https://bitbucket.org/JesusFreke/smali/downloads/baksmali-2.5.2.jar" -O /data/user/work/baksmali.jar
wget -q "https://bitbucket.org/JesusFreke/smali/downloads/smali-2.5.2.jar" -O /data/user/work/smali.jar

# ========== 2. 一键构建 ==========
cd /data/user/work/trae-cn3-repo
./build.sh /workspace/trae_cn3_v38.apk /workspace/trae_cn3_v39.apk

# ========== 3. 验证 ==========
# 签名验证
java -jar /data/user/work/uber-apk-signer.jar -a /workspace/trae_cn3_v39.apk -y
# 完整性验证
unzip -t /workspace/trae_cn3_v39.apk
# dex 内容验证
mkdir -p /tmp/verify && cd /tmp/verify
unzip -o /workspace/trae_cn3_v39.apk classes9.dex -d .
java -jar /data/user/work/baksmali.jar d classes9.dex -o smali
grep "api.trae.cn" smali/com/bytedance/trae/conversation/extract/QuotaOverlay.smali

# ========== 4. 排查命令 ==========
# 搜索积分相关代码
find source/java -name "*.java" | xargs grep -l "Credits\|Quota" | head -20
# 搜索 API 主机配置
grep -rn "baseUrl\|LOGIN_HOST\|AI_HOST\|api.trae" source/java/ --include="*.java"
# 搜索 smali 中的字符串常量
grep "const-string" smali_file.smali | grep "trae\|api\|host"

# ========== 5. 日志查看 ==========
adb shell cat /sdcard/douyinguanjia/Log/trae-cn3.log | grep QuotaOverlay
adb logcat | grep -i "trae\|quota"
```
