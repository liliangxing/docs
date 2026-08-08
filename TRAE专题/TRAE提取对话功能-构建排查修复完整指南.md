# TRAE 提取对话功能：构建 · 排查 · 修复 完整指南

> 写给谁：技术一般的人，以及"没那么聪明的 Agent"。
> 只要照着本文一步步来，就能：搭好构建环境 → 复现三个 Bug → 定位根因 → 修复 → 验证 → 发布。
>
> 涉及版本：v33（翻页 API 修复）、v34（文件名 + 预览修复），日期 2026-08-08。
>
> 关于截图：本机是纯命令行（Linux/root）环境，生成不了图片。所以我把关键命令的**真实输出原样贴出来**当证据（等效于截图）。需要真截图的地方，文中有"在手机上怎么看/怎么截"的说明。

---

## 目录

1. [人话版总结](#1-人话版总结)
2. [这个工程是干什么的（背景）](#2-这个工程是干什么的背景)
3. [构建是怎么工作的（先懂原理再动手）](#3-构建是怎么工作的先懂原理再动手)
4. [第一次搭环境，坑全在这（重要，先看）](#4-第一次搭环境坑全在这重要先看)
5. [改完代码怎么快速验证](#5-改完代码怎么快速验证)
6. [Bug 一：历史消息拉不全 / 顺序乱 / 失败误报（v33）](#6-bug-一历史消息拉不全--顺序乱--失败误报v33)
7. [Bug 二：文件名用了最后一条消息（v34）](#7-bug-二文件名用了最后一条消息v34)
8. [Bug 三：预览网页打不开 netERR_ACCESS_DENIED（v34）](#8-bug-三预览网页打不开-neterr_access_deniedv34)
9. [通用排查工具箱](#9-通用排查工具箱)
10. [发布流程（git + GitHub Release）](#10-发布流程git--github-release)
11. [命令速查表](#11-命令速查表)
12. [避坑清单（对着一条条查）](#12-避坑清单对着一条条查)

---

## 1. 人话版总结

| Bug | 现象 | 一句话根因 | 一句话修法 |
|---|---|---|---|
| 历史消息不全/乱序/失败误报 | 导出的对话缺消息、顺序乱、偶尔报"API 成功"但内容空 | 翻页参数 `before_id` 和服务端 `anchor` API 对不上，翻页提前停；多页内容没按时间逆序合并；首页失败没拦住就继续拼文档 | 翻页改用 `anchor_created_at_ms`（对齐原 APK）、按返回条数判断还有没有下一页、多页逆序合并、首页失败直接返回 null |
| 文件名用最后一条消息 | 文件名是对话里"最新"那句话，不是第一句 | 翻页从新到旧，代码只在 `firstQuestion==null` 时赋值，取到的是第一页（最新）的第一条 | 改成每次无条件覆盖，循环结束自然留下"最早"那条 |
| 预览网页打不开 | 提取后跳转预览页，报 `net::ERR_ACCESS_DENIED` | 预览用的 `SimpleWebViewActivity` 没开启 `file://` 访问权限（Android 7+ 默认禁止） | 改用 `FileProvider` 生成 `content://` 地址，WebView 默认允许 `content://` |

---

## 2. 这个工程是干什么的（背景）

TRAE 是一个安卓 App（包名 `com.bytedance.trae.cn3`）。我们做的是往这个 APK 里**注入一段我们自己的代码**，实现一个"提取当前对话、导出成 Markdown 文件"的功能。

关键限制：我们**不能改原 App 的源码**，只能通过"替换 APK 里某一个 dex 文件"的方式把新功能塞进去。

一个 APK 的本质是一个 zip 包，里面有：
- `classes.dex`、`classes2.dex` ... `classes9.dex`：一堆编译后的字节码（每个 dex 是一坨 Java/Kotlin 编译产物）
- `resources.arsc`、`AndroidManifest.xml`、图片资源等

我们的注入策略：原 APK 的 `classes9.dex` 里恰好是空白/无关紧要的内容，我们把自己编译的类打包成新的 `classes9.dex` 替换进去。这样 App 里就多了我们注入的类，被 `ExtractHelper`（我们注入的入口）调用。

工程目录结构（`liliangxing/trae-cn3` 仓库）：

```
trae-cn3/
├── build.sh                  # 一键构建脚本（装工具/编译/替换/签名/验证）
├── source/
│   ├── java/com/bytedance/trae/conversation/extract/
│   │   ├── ExtractHelper.java        # 主流程：读DB/调API/写文件/预览/推送
│   │   ├── ApiMessageFetcher.java    # 调 TRAE 后端 API 翻页拉消息
│   │   ├── GitHubPusher.java         # 把 MD 推到 GitHub
│   │   └── FileLogger.java           # 日志工具（重要！调试靠它）
│   ├── stubs/                        # "桩"类：编译时占位，运行用真类
│   └── smali/                        # 反编译出来的原 App 类（参考用）
├── releases/                         # 每个版本的说明 README
└── docs/、BUILD_SCRIPT/              # 说明文档
```

---

## 3. 构建是怎么工作的（先懂原理再动手）

`build.sh` 需要两个参数：**输入 APK**（上一个版本）、**输出 APK**（新版本）。

```bash
bash build.sh /data/user/work/trae_cn3_v33.apk /data/user/work/trae_cn3_v34.apk
```

内部一共 6 步（理解这个流程，后面排查才知道卡在哪一步）：

```
步骤1  检查/安装工具（JDK、apktool、baksmali、uber-apk-signer、keystore、dx、android.jar）
步骤2  把我们写的 Java 编译 → dx 转 dex → baksmali 反编译成 smali
步骤3  用 apktool 解包输入 APK，把新 smali 覆盖进 classes9
步骤4  zip 方式把新的 classes9.dex 塞回 APK，删除旧签名
步骤5  用 uber-apk-signer 重新签名（v2+v3）
步骤6  验证：签名、完整性、dex 内容、关键字符串
```

每个步骤结束都有日志输出（`=== 步骤 X: ... ===`）。构建时盯着日志看到哪一步，就知道卡在哪。

术语：**smali** 是 Android 反编译的中间语言（类似汇编），`baksmali` 把 dex 翻译成 smali，`apktool` 解包/打包 APK。

---

## 4. 第一次搭环境，坑全在这（重要，先看）

### 4.0 工具清单

| 工具 | 作用 | 来源 |
|---|---|---|
| JDK 17 | 编译 Java | `apt-get install -y default-jdk` |
| apktool 2.9.3 | 解包/打包 APK | 下载 jar |
| baksmali 2.5.2 | dex ↔ smali 互转 | 下载 jar |
| uber-apk-signer 1.3.0 | 给 APK 签名 | 下载 jar |
| dx 1.13 | Java class → dex | 下载 build-tools 26.0.1 |
| android.jar (API 23) | 编译时的安卓 SDK | 下载 |
| keystore | 签名密钥 | `keytool` 生成 |

这些大多由 `build.sh` 步骤 1 自动处理，但**有两处它搞不定**，需要手动补救，就是下面 4.2 和 4.3 两个坑。

### 4.1 下载"输入 APK"（每个新版本都从上一个版本起）

以 v32 → v33 为例。先看 GitHub Release 上有哪些版本：

```bash
curl -s https://api.github.com/repos/liliangxing/trae-cn3/releases \
  | python3 -c "import json,sys; [print(r['tag_name'], [a['name'] for a in r['assets']]) for r in json.load(sys.stdin)]"
```

拿到最新的 APK 下载地址（示例）：
```bash
curl -sL -o /data/user/work/trae_cn3_v32.apk \
  "https://github.com/liliangxing/trae-cn3/releases/download/v32/trae_cn3_v32.apk"

# 下载完一定要看大小对不对（约 111MB），小了就是下到了错误页面
ls -la /data/user/work/trae_cn3_v32.apk
md5sum /data/user/work/trae_cn3_v32.apk
```

### 4.2 坑 1：Debian 12 没有 android.jar（android-sdk-platform 包被移除了）

**现象**：`build.sh` 跑到"安装 android-sdk-platform"后报：

```
安装 android-sdk-platform...
错误: 找不到 android.jar
```

**排查**：确认一下这个包到底存不存在：

```bash
apt-cache search android-sdk
# 结果里只有 build-tools / platform-tools，没有 android-sdk-platform 或 android-sdk-platform-23
apt-cache policy android-sdk-platform android-sdk-platform-23
# 两行都是 "Candidate: (none)"，说明 deb12 仓库里根本没这个包
```

**避坑**：不要浪费时间折腾 apt。直接手动下载 android.jar（API 23），放到 build.sh 期望的位置：

```bash
# 方案 A（推荐，稳定）：Sable 镜像
curl -sL -o /tmp/android23.jar \
  "https://raw.githubusercontent.com/Sable/android-platforms/master/android-23/android.jar"
# 大小应约 23.9MB

# 验证下载的文件是有效 zip/jar（不是 HTML 错误页）
unzip -t /tmp/android23.jar | tail -2
# 输出: No errors detected in compressed data of android23.jar.

mkdir -p /usr/lib/android-sdk/platforms/android-23
cp /tmp/android23.jar /usr/lib/android-sdk/platforms/android-23/android.jar
```

**为什么放到这个路径**：`build.sh` 里写死了 `ANDROID_JAR=/usr/lib/android-sdk/platforms/android-23/android.jar`，只要这个文件存在，build.sh 就会跳过安装直接用。

### 4.3 坑 2：build-tools 29 没有 dx；装了 dx 1.11 又遇到 Java 8 报错

**现象 1**：`build.sh` 步骤 2 的"dx 转 dex"失败。日志：

```
安装 android-sdk-build-tools...
```

然后步骤 2 里跑 dx 报一堆：

```
Caused by: com.android.dx.cf.iface.ParseException: bad class file magic (cafebabe) or version (0034.0000)
...
8 errors; aborting
```

**先解释**：`0034` 是十六进制 = 十进制的 `52`，即 class 文件的 major version 52 = **Java 8** 编译产物。dx 1.11（build-tools 23.0.1）**不支持 Java 8 的 class**，只到 Java 7（major 51）。

**排查命令**：确认我们的 class 确实是 Java 8（major 52）：

```bash
javap -v /data/user/work/build/classes/com/bytedance/trae/conversation/extract/ExtractHelper.class \
  | grep "major version"
# 输出: major version: 52
```

**避坑**：不要用 build-tools 23 的 dx。要换 **dx 1.13（build-tools 26.0.1）**：

```bash
curl -sL -o /tmp/bt26.zip "https://dl.google.com/android/repository/build-tools_r26.0.1-linux.zip"
unzip -o -q /tmp/bt26.zip          # 解出 android-8.0.0/
ls android-8.0.0/dx android-8.0.0/lib/dx.jar   # 确认 dx 和它依赖的 jar 都在

# 装到 build.sh 期望的路径（debian 目录下）
mkdir -p /usr/lib/android-sdk/build-tools/debian/lib
cp android-8.0.0/dx            /usr/lib/android-sdk/build-tools/debian/dx
cp android-8.0.0/lib/dx.jar    /usr/lib/android-sdk/build-tools/debian/lib/dx.jar
chmod +x /usr/lib/android-sdk/build-tools/debian/dx

# 验证版本，必须是 1.13（1.11 就会踩上面的坑）
/usr/lib/android-sdk/build-tools/debian/dx --version
# 输出: dx version 1.13
```

**为什么 dx 脚本要配 `lib/dx.jar`**：`dx` 是个 shell 脚本，默认到同目录的 `lib/dx.jar` 找真正的实现，所以 dx 和 lib/dx.jar 必须成对放。

### 4.4 坑 3：从 dl.google.com 下载 zip，有时拿到的是 HTML

**现象**：`curl` 下载一个 zip，结果 `unzip` 报错：

```
unzip: cannot find zipfile directory in one of platform-23.zip ...
```

**排查**：看下下载的东西到底是啥：

```bash
ls -la platform-23.zip        # 只有 1.4KB，明显不是 60MB 的 zip
head -c 200 platform-23.zip | strings | head -3
# 输出是 <!DOCTYPE html>，说明下到了一个 404 页面
```

**原因**：文件名写错了。Google SDK 仓库的正确文件名要用它官方的索引查：

```bash
curl -s "https://dl.google.com/android/repository/repository2-3.xml" \
  | grep -oE 'platform-23[^"<]*\.zip'
# 输出: platform-23_r03.zip     ← 注意是 r03，不是 r02！
```

**避坑**：凡是 `dl.google.com/android/repository/` 下的 zip，先拿上面这行命令查准确文件名再下。或者干脆用 4.2 的 Sable 镜像，少折腾。

### 4.5 工具装好后自检

```bash
java -version                    # openjdk 17
/usr/lib/android-sdk/build-tools/debian/dx --version   # dx version 1.13
ls -la /usr/lib/android-sdk/platforms/android-23/android.jar   # 23.9MB
ls -la /data/user/work/apktool.jar /data/user/work/baksmali.jar /data/user/work/uber-apk-signer.jar
# 三个 jar 都在且非空（build.sh 会自动下载，也可手动预下载）
```

---

## 5. 改完代码怎么快速验证

### 5.1 本地快速编译（不用每次构建整个 APK）

改完 Java 代码，先别急着跑 `build.sh`（那要解包 111MB 的 APK，很慢）。先在本地把代码编译一遍，语法错误秒出：

```bash
# 第 1 步：编译所有 stub 类
find source/stubs -name "*.java" > /tmp/stub_files.txt
mkdir -p /tmp/jc_out
javac -source 8 -target 8 -cp /usr/lib/android-sdk/platforms/android-23/android.jar \
  -d /tmp/jc_out @/tmp/stub_files.txt
# 只要没有 error 就算过（warning 忽略）

# 第 2 步：MediaStore.Downloads 是 API 29+ 才有，android.jar 是 API 23，所以要单独补一个 stub
mkdir -p /tmp/ms/src/android/provider /tmp/ms/classes
# 手动写一个 MediaStore.java（内容见 build.sh 第 103-118 行），然后：
javac -source 8 -target 8 -cp /usr/lib/android-sdk/platforms/android-23/android.jar \
  -d /tmp/ms/classes /tmp/ms/src/android/provider/MediaStore.java
(cd /tmp/ms/classes && jar cf /tmp/ms/mediastub.jar .)

# 第 3 步：编译我们的 extract 包（classpath 顺序很重要：mediastub 放最前）
javac -source 8 -target 8 \
  -cp "/tmp/ms/mediastub.jar:/usr/lib/android-sdk/platforms/android-23/android.jar:/tmp/jc_out" \
  -d /tmp/jc_out \
  source/java/com/bytedance/trae/conversation/extract/*.java
# exit 0 就说明代码能编译过
```

**为什么 classpath 顺序有讲究**：`MediaStore.Downloads` 在 android.jar（API 23）里不存在，只有我们的 mediastub 提供。Java 编译按 classpath 顺序找类，把 mediastub 放最前才能让 `MediaStore` 用我们的 stub。

### 5.2 完整构建的成功判据

跑完 `build.sh`，日志末尾必须同时看到这几点才算成功：

```
01. trae_cn3_v34.apk
    - zipalign verified
    - signature verified [v2, v3]          ← 签名 OK
No errors detected in compressed data of ...  ← 完整性 OK
生成 N 个 Smali 文件                           ← 编译的类都在（我们这是 8 个）
--- 关键参数验证 ---
OK                                           ← 代码里的关键字符串真的进 APK 了
构建完成！
输出 APK: /data/user/work/trae_cn3_v34.apk
```

**看日志技巧**：build.sh 是长任务，放"后台终端"跑（别在会话里干等），输出会写进日志文件，随时可以看：

```bash
# 假设后台终端返回 terminal id = T1
tail -30 /tmp/terminal_T1.log     # 看最新进度
```

---

## 6. Bug 一：历史消息拉不全 / 顺序乱 / 失败误报（v33）

### 6.1 现象

- 长对话导出后**消息不全**（早期版本只拉到最近几条，或中间断档）
- 多页拉取时**顺序乱**（新消息跑到旧消息前面）
- 偶尔**第一页请求失败**，但界面上还提示"API 成功"，导出的内容是空的

### 6.2 排查过程

**第 1 步：看现象对应代码**。问题集中在 `ApiMessageFetcher.java`（专门负责调 API 翻页拉消息的类）。用日志和代码对照：

```
文件里 FileLogger.log(TAG, "API-P" + page + ": ...") 会打印每一页拉取情况
```

**第 2 步：看 API 请求长什么样**。翻页代码原来是这样：

```java
urlBuilder.append("api/solo_hub/v1/conversations/messages/anchor?conversation_id=");
urlBuilder.append(conversationId);
urlBuilder.append("&before_limit=10&after_limit=0&include_anchor=true");
if (beforeId != null) {
    urlBuilder.append("&before_id=").append(beforeId);
}
```

**第 3 步：怀疑参数和服务端对不上**。`anchor` 这个接口名暗示它用的是"锚点"（锚 = 某一时刻的位置），翻页应该用时间戳而不是消息 ID。于是翻出原 APK 反编译源码里的同类请求（`source/smali/` 和 `source/java/` 里有整个 App 的反编译结果），确认原 App 用的是 `anchor_created_at_ms` 参数。

**这是最核心的方法论**：**当猜不到服务端接口该怎么调时，去翻原 APK 的反编译代码，看原 App 自己是怎么调这个接口的，照抄。** 原 App 一定能正常工作，所以它怎么传参数，我们就怎么传。

**第 4 步：看翻页终止条件**。原来：

```java
boolean hasMore = data.optBoolean("has_more", false);
```

但服务端可能根本不返回 `has_more` 字段，于是第一页后就停了 → 消息不全。改成"返回条数达到一页就继续"更稳。

**第 5 步：看多页拼接**。原代码每页直接往 `allUserContent` 追加，但每页内部消息是倒序（最新在前），多页之间又叠加翻页方向，整体就乱了。需要"整页"为单位收集，最后统一逆序。

**第 6 步：看首页失败**。原代码第一页失败把 `markdown=null` 然后 `break`，但循环外的代码没有拦住，仍会继续拼出"空文档"并提示成功。需要加失败标记。

### 6.3 根因

1. 翻页参数用 `before_id`（消息 ID），服务端 `anchor` 接口认的是 `anchor_created_at_ms`（毫秒时间戳）→ 翻页失效
2. 用 `include_anchor=true`，每页都重复包含锚点消息
3. 判断"还有没有下一页"依赖服务端可能不返回的 `has_more` 字段 → 提前停
4. 多页内容拼接没有按时间正序合并 → 乱序
5. 首页失败后没有阻止后续拼文档 → 空文档+误报成功

### 6.4 修改内容（改后）

```java
// 1) URL 参数对齐原 APK
urlBuilder.append("&before_limit=").append(pageSize);
urlBuilder.append("&after_limit=0&include_anchor=false");     // include_anchor 改 false
if (anchorCreatedAtMs != null) {
    urlBuilder.append("&anchor_created_at_ms=").append(anchorCreatedAtMs);  // 时间戳翻页
}

// 2) 游标从消息里取 created_at_ms（原取 message_id）
String nextAnchor = oldestMsg.optString("created_at_ms");
if (nextAnchor == null || nextAnchor.length() == 0) {
    nextAnchor = oldestMsg.optString("created_at");
}

// 3) 还有没有下一页：条数达到一页就继续（并兼容服务端显式返回 has_more）
boolean hasMore = arrayLen >= pageSize;
if (data.has("has_more")) {
    hasMore = data.optBoolean("has_more", hasMore);
}

// 4) 每页先存成一个"正序块"，最后逆序合并（因为翻页方向是从新到旧）
java.util.ArrayList<String> pageBlocks = new java.util.ArrayList<>();
// ...每页: pageBlocks.add(pageBlock.toString())...
for (int i = pageBlocks.size() - 1; i >= 0; i--) {
    if (allUserContent.length() > 0) allUserContent.append("\n\n");
    allUserContent.append(pageBlocks.get(i));
}

// 5) 首页失败标记，最后不再拼文档
boolean apiFailed = false;
// ...首页失败时: apiFailed = true;  break;...
if (apiFailed) {
    markdown = null;     // 不再构建空文档
}
```

### 6.5 验证

- 构建成功后，用 baksmali 反编译新 APK 的 `classes9.dex`，确认关键字符串在：

```bash
unzip -o /data/user/work/trae_cn3_v33.apk classes9.dex -d /tmp/verify
java -jar /data/user/work/baksmali.jar d /tmp/verify/classes9.dex -o /tmp/verify/smali

# 应能看到 &before_limit= 字符串（build.sh 步骤 6 的"关键参数验证"也做这件事）
grep "before_limit" /tmp/verify/smali/com/bytedance/trae/conversation/extract/ApiMessageFetcher.smali
```

- 真机验证：手机装新 APK，打开一个长对话点"提取"，去日志文件看 `API-P0 / API-P1 ...` 翻页记录和导出的消息数。

---

## 7. Bug 二：文件名用了最后一条消息（v34）

### 7.1 现象

导出的 MD 文件叫 `最后一句话.md`，用户想要的应该是对话**开头第一句**。

### 7.2 排查过程

**第 1 步**：文件名在 `ExtractHelper.buildFileName(firstQuestion)` 里生成，`firstQuestion` 来自 `ApiMessageFetcher.getLastFirstUserMessage()`。

**第 2 步**：看 `firstQuestion` 是在哪赋值的。原代码：

```java
if (firstQuestion == null) {
    firstQuestion = content;   // 只在空的时候赋值一次
}
```

**第 3 步**：意识到问题。翻页顺序是**从新到旧**（第一页是最新的消息），循环里第一次遇到 `firstQuestion==null` 赋值，取到的就是**第一页第一条 = 最新一条消息**。名字当然就是最后一句。

**一句话总结方法论**：**变量名"first"有歧义——"循环里第一次赋值" 不等于 "对话里第一条"**。要看清楚数据遍历的方向。

### 7.3 修复

改成**无条件覆盖**，循环结束后留下的自然是最后一次赋值 = 全局最早一条（因为翻页从新到旧，最后处理的一定最早）：

```java
if (content != null && content.length() > 0) {
    // 翻页从新到旧，循环结束时 firstQuestion 即全局最早一条用户消息
    firstQuestion = content;      // 原来是 if (firstQuestion == null) 才赋值
    totalUserCount++;
    pageUserMessages.add(content);
}
```

### 7.4 顺手加了个安全点：文件名里 GitHub token 脱敏

用户消息里有时会贴 GitHub 的认证 token（`ghp_...` / `github_pat_...`），文件名会把它带出来，泄露隐私。在 `buildFileName` 里用正则替换：

```java
// 脱敏 GitHub 认证 token（classic PAT / fine-grained PAT / OAuth 等）
name = name.replaceAll(
    "gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{30,}",
    "xxx");
```

**为什么先脱敏再截断**：`github_pat_` 开头的 token 很长（60+ 字符），如果先截断成 50 字符再脱敏，正则就匹配不完整。必须先脱敏再截断。

---

## 8. Bug 三：预览网页打不开 net::ERR_ACCESS_DENIED（v34）

这是最值得讲的一个，因为它的排查路径是"现象 → 怀疑层 → 读源码 → 查配置 → 定方案"的完整链条。

### 8.1 现象

点"提取对话"后，页面跳到一个预览界面，但白屏报错：

```
位于 file:///data/user/0/com.bytedance.trae.cn3/cache/TRAE/xxx.md.html 的网页无法加载，因为：
net::ERR_ACCESS_DENIED
```

### 8.2 排查链（跟着走）

**第 1 步：看现象本身给的线索。** 地址是 `file:///data/user/0/.../cache/TRAE/xxx.md.html`，错误是 `ERR_ACCESS_DENIED`（访问被拒）。这是 **WebView 加载本地文件被权限拒绝**的典型错误。

**第 2 步：找负责预览的类。** 搜代码里谁在用这个文件路径：

```bash
grep -rn "SimpleWebViewActivity" source/java --include="*.java"
```

找到 `ExtractHelper.java` 里：

```java
final Intent intent = new Intent(activity, SimpleWebViewActivity.class);
intent.putExtra("extra_url", Uri.fromFile(cacheHtmlFile).toString());  // file:// 地址
```

**第 3 步：读 SimpleWebViewActivity 的源码，确认它没开 file 权限。** 这是反编译出来的（Kotlin → Java）。看它的 `onCreate` 里 WebView 的设置：

```java
webView.getSettings().setJavaScriptEnabled(true);
webView.getSettings().setDomStorageEnabled(true);
// ← 注意：从头到尾没有 setAllowFileAccess(true)！
webView.loadUrl(stringExtra);
```

**关键知识点**：Android 7.0（API 24）开始，WebView 默认 **禁止 `file://` 访问**（`setAllowFileAccess` 默认 false）。这个 Activity 只开了 JS 和 DOM 存储，没开 file 访问 → 加载 `file://` 必然 `ERR_ACCESS_DENIED`。

而且这个类在原 APK 的 `classes5.dex` 里，**我们改不了它**（我们的注入只替换 classes9.dex）。所以不能指望给它加一行 `setAllowFileAccess(true)`。

**第 4 步：想别的路子 —— WebView 默认允许什么？** 查证：WebView 默认 `setAllowContentAccess(true)`，也就是 **`content://` 地址是可以加载的**。于是思路变成：**别用 file://，改用 content:// 加载同一个 HTML。**

**第 5 步：怎么生成 content:// 地址？用 App 自己现成的 FileProvider。** 原 APK 的 Manifest 里有：

```bash
grep -oE '<provider[^>]*>' trae_cn3_decoded/AndroidManifest.xml
# 关键一行：
# <provider android:authorities="com.bytedance.trae.cn3.uri.key" android:exported="false"
#           android:name="androidx.core.content.FileProvider" .../>
```

但 FileProvider 不是任何文件都能生成地址的，它受 `file_paths` 白名单限制。看 App 自带的文件路径配置：

```bash
cat trae_cn3_decoded/res/xml/trae_conversation_filepaths.xml
# 里面有：
# <cache-path name="internal_cache_root" path="/update" />
# <cache-path name="app_camera" path="camera" />
```

**第 6 步：对上路径。** FileProvider 的 `cache-path path="/update"` 允许 `getCacheDir()/update/` 目录下的任意文件。所以把 HTML 从 `cache/TRAE/` 改写到 `cache/update/TRAE/`，就能用 FileProvider 生成合法的 content:// 地址。

**第 7 步：编译期 stub。** 我们的 extract 代码要调用 `FileProvider.getUriForFile(...)`，但编译的 classpath 里没有这个类（android.jar 是 API 23 的基础库，不含 androidx）。项目的惯用解法：加一个**桩（stub）类**，编译期占位，运行期用 App 里真实的类：

```java
// source/stubs/androidx/core/content/FileProvider.java
package androidx.core.content;

import android.content.Context;
import android.net.Uri;
import java.io.File;

public class FileProvider {
    public static Uri getUriForFile(Context context, String authority, File file) {
        return null;   // 只是让编译通过，运行时会用 App 里的真实实现
    }
}
```

**为什么 stub 不会把错误代码带进 APK**：build.sh 只把 `source/java/.../extract/*.java` 编译出的 class 转 dex，stub 只是 classpath 里的"编译依赖"，不会进入 APK。运行时 App 用的是自己 classes5.dex 里的真实 FileProvider。

### 8.3 修复代码

```java
// HTML 写到 FileProvider 允许的目录：cache/update/TRAE/
File cacheHtmlDir = new File(context.getCacheDir(), "update/TRAE");
if (!cacheHtmlDir.exists()) cacheHtmlDir.mkdirs();
File cacheHtmlFile = new File(cacheHtmlDir, mdFileName + ".html");
// ...写入 HTML...

// 用 FileProvider 生成 content:// 地址（不再是 file://）
Uri previewUri = androidx.core.content.FileProvider.getUriForFile(
    context, "com.bytedance.trae.cn3.uri.key", cacheHtmlFile);
intent.putExtra("extra_url", previewUri.toString());
```

另外把预览 HTML 从"依赖 CDN 的 marked.js"改成**Java 端静态渲染**：原来 HTML 里引 `https://cdn.jsdelivr.net/npm/marked/...` 在线转 markdown，没网就白屏。现在用 `ExtractHelper` 里新增的 `markdownToHtml()` 直接把 markdown 转成静态 HTML，完全离线可用。

### 8.4 为什么这样修（原理收口）

| 方式 | 为什么不行 / 行 |
|---|---|
| `file://` 内部缓存 | WebView 默认禁止 file 访问（API 24+），报 ERR_ACCESS_DENIED。Activity 代码在别的 dex，改不了 |
| `content://`（FileProvider） | WebView 默认允许 content 访问（`setAllowContentAccess` 默认 true），且 App 已配置好 FileProvider + file_paths，直接复用 |
| 改 SimpleWebViewActivity | 它在 classes5.dex，超出我们可替换范围（只替换 classes9） |

### 8.5 验证

构建成功后反编译 dex，确认三样东西都进去了：

```bash
unzip -o /data/user/work/trae_cn3_v34.apk classes9.dex -d /tmp/verify34
java -jar /data/user/work/baksmali.jar d /tmp/verify34/classes9.dex -o /tmp/verify34/smali

grep -o "com.bytedance.trae.cn3.uri.key" /tmp/verify34/smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali
# 有输出 = FileProvider authority 进 APK 了

grep -o "update/TRAE" /tmp/verify34/smali/com/bytedance/trae/conversation/extract/ExtractHelper.smali
# 有输出 = 缓存路径改对了
```

真机验证：手机上点"提取"，预览页应能直接看到渲染后的对话内容（离线也 OK）。

---

## 9. 通用排查工具箱

### 9.1 看日志（第一件事）

代码里大量 `FileLogger.log(TAG, "StepX: ...")`。它做两件事：

1. 打 **logcat**：`Log.e(tag, message, ...)` —— 手机连电脑开 USB 调试后用 `adb logcat` 看，或手机上用"开发者选项 → 系统日志"类 App 看
2. 写**文件**：`/storage/emulated/0/Android/data/com.bytedance.trae.cn3/files/trae-cn3.log`（App 专属目录，不用权限）

**在手机上怎么看/截图**：用"文件管理器"App 打开 `Android/data/com.bytedance.trae.cn3/files/trae-cn3.log`，点"提取"操作后刷新，就能看到一行行 `Step9a / Step10 / Step11b ...` 的执行记录。要截图就截这个日志文件，配合操作顺序，基本能还原执行到哪一步、卡在哪一步。

### 9.2 用 git 看清改动

```bash
git status                    # 哪些文件改了
git diff                      # 具体改了什么
git diff --stat               # 改动量概览
git log --oneline -8          # 看提交风格（好照着写 commit message）
```

### 9.3 反编译验证"代码真的进 APK 了"

```bash
unzip -o <apk> classes9.dex -d /tmp/v
java -jar /data/user/work/baksmali.jar d /tmp/v/classes9.dex -o /tmp/v/smali
find /tmp/v/smali -name "*.smali" -path "*extract*" | sort
# 应看到 8 个类：ApiMessageFetcher(+$1) / ExtractHelper(+$1..3) / FileLogger / GitHubPusher
grep "要验证的字符串" /tmp/v/smali/.../xxx.smali
```

### 9.4 javap 看 class 版本（诊断 dx 报错用）

```bash
javap -v xxx.class | grep "major version"   # 52=Java8, 51=Java7
```

### 9.5 验证 APK 完整性和签名

```bash
unzip -t trae_cn3_v34.apk | tail -2     # No errors detected = OK
java -jar /data/user/work/uber-apk-signer.jar -a trae_cn3_v34.apk -y   # 校验签名
# 期望输出：signature verified [v2, v3]
```

### 9.6 长任务放后台跑

build.sh 这类要跑很久的，用后台终端执行，日志落文件，随时 `tail` 查看，避免阻塞。

### 9.7 一次只改一个点

改 → 本地 javac 快速编译 → （必要时）构建 → 验证 → 再改下一个。今天三个 Bug 是分三次提交、三次构建、三次验证，每个改动独立可回退。

---

## 10. 发布流程（git + GitHub Release）

### 10.1 提交代码

```bash
cd /tmp/opencode/trae-cn3
git add <具体文件>          # 只 add 改动的源码，别把编译产物/test jks 提交进去
git status --short          # 确认暂存内容
git commit -m "fix: 一句话说清改了什么"   # 风格看 git log --oneline，都是 fix:/feat:/docs:
```

**注意**：仓库没配提交者身份时会报 `Author identity unknown`，用历史提交者的身份（看 `git log --format='%an <%ae>'`）配置一次：

```bash
git config user.name "TRAE Agent"
git config user.email "trae-agent@bytedance.com"
```

### 10.2 GitHub 认证（发布需要写权限）

环境里的 git credential helper 可能不可用（报 `server returned status 500`）。用用户提供的 Personal Access Token（PAT）走 `gh`：

```bash
echo "<你的PAT>" | gh auth login --with-token
gh auth status                # 看到 Logged in to github.com 即成功
gh auth setup-git             # 让 git push 也能用这套凭据
git push origin main
```

**不要把 token 打印到文档/日志/聊天里。** 上面的 `<你的PAT>` 是占位符。

### 10.3 创建 GitHub Release

```bash
gh release create v34 /data/user/work/trae_cn3_v34.apk \
  --title "v34 - 一句话标题" \
  --notes-file /tmp/notes.md \
  --repo liliangxing/trae-cn3

# 确认
gh release view v34 --repo liliangxing/trae-cn3 --json tagName,assets \
  --jq '.tagName + " " + ([.assets[].name] | join(","))'
```

版本号规则：最新 release 是 v32 → 新版本 v33 → v34，逐号递增。

---

## 11. 命令速查表

```bash
# 下载输入 APK
curl -sL -o /data/user/work/trae_cn3_v33.apk "https://github.com/liliangxing/trae-cn3/releases/download/v33/trae_cn3_v33.apk"

# 一键构建（先看 4.2/4.3 装好 android.jar 和 dx）
bash build.sh /data/user/work/trae_cn3_v33.apk /data/user/work/trae_cn3_v34.apk

# 本地快速编译
find source/stubs -name "*.java" > /tmp/stub_files.txt && mkdir -p /tmp/jc_out
javac -source 8 -target 8 -cp /usr/lib/android-sdk/platforms/android-23/android.jar -d /tmp/jc_out @/tmp/stub_files.txt
javac -source 8 -target 8 -cp "/tmp/ms/mediastub.jar:/usr/lib/android-sdk/platforms/android-23/android.jar:/tmp/jc_out" -d /tmp/jc_out source/java/com/bytedance/trae/conversation/extract/*.java

# 验证 dex 内容
unzip -o <apk> classes9.dex -d /tmp/v && java -jar /data/user/work/baksmali.jar d /tmp/v/classes9.dex -o /tmp/v/smali

# 验证签名 / 完整性
java -jar /data/user/work/uber-apk-signer.jar -a <apk> -y
unzip -t <apk> | tail -2

# 发布
gh release create v34 <apk> --title "..." --notes-file /tmp/notes.md --repo liliangxing/trae-cn3
```

---

## 12. 避坑清单（对着一条条查）

1. **android.jar 缺失** → deb12 没有 android-sdk-platform 包，去 Sable 镜像下载放 `/usr/lib/android-sdk/platforms/android-23/android.jar`（4.2）
2. **dx 报 `bad class file magic ... version (0034.0000)`** → dx 1.11 不支持 Java 8，换 dx 1.13（4.3）
3. **dl.google.com 下 zip 变成 HTML** → 文件名错了，用 repository2-3.xml 查准确名，或直接用镜像（4.4）
4. **下载的大文件大小明显不对** → 检查是不是下到了错误页（`ls -la` + `head -c`）
5. **改代码后构建失败** → 先用 5.1 本地 javac 快速定位语法错误
6. **翻页接口调不对** → 翻原 APK 反编译代码，照抄原 App 的参数（6.2）
7. **文件名不对** → 看清楚数据遍历方向，"循环第一次"≠"对话第一条"（7.2）
8. **`file://` 打不开预览** → Android 7+ WebView 默认禁 file，改用 App 现有 FileProvider 的 content://（8.2）
9. **新增要用到 App 内部类/androidx 类** → 加 stub 类到 `source/stubs/`，只占位编译，不进 APK（8.2 第 7 步）
10. **`git commit` 报 Author identity unknown** → 按历史作者配置 `git config user.name/user.email`（10.1）
11. **push/release 没权限** → `gh auth login --with-token` + `gh auth setup-git`（10.2）
12. **token 别泄露** → 正则脱敏进文件名；token 也别写进文档和日志（7.4 / 10.2）
13. **长任务别在前台等** → 后台终端跑，`tail` 看日志（9.6）
