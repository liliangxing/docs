# TRAE APK 多变体一键生成 搭建指南

> **目标**：基于已经构建好的 `trae_cn3_v41.apk`（包名 `com.bytedance.trae.cn3`，应用名 `TRAE3`），"克隆"出两个新 APK——`trae_v41.apk`（包名 `com.bytedance.trae.cn`，应用名 `TRAE`）和 `trae2_v41.apk`（包名 `com.bytedance.trae.cn2`，应用名 `TRAE2`），功能完全一样，只是包名和应用名不同，上传到 GitHub Release v41。
>
> 本文档用大白话写给"技术一般、对命令不熟悉"的人看。每一步都有完整命令、有"为什么这么做"的解释、有"你应该看到的结果"、有踩坑提醒。照着从上到下复制粘贴就能做出来。
>
> **特别说明**：这份文档不仅记录了成功步骤，还详细记录了排查问题的思路、用到的调试命令、踩过的坑。其他 agent 之前没修好这些问题，就是因为没有系统排查。本文档把整个排查链路写清楚，方便你手工模拟、验证、修复。

---

## 目录

- [一、这次到底要做成什么事](#一这次到底要做成什么事)
- [二、背景知识（不懂也能照做）](#二背景知识不懂也能照做)
- [三、和 MonkeyCode 方案的本质区别（重要！）](#三和-monkeycode-方案的本质区别重要)
- [四、第一步：准备工具](#四第一步准备工具)
- [五、第二步：下载基础 APK](#五第二步下载基础-apk)
- [六、第三步：摸清楚 APK 的"身份证"信息](#六第三步摸清楚-apk-的身份证信息)
- [七、第四步：排查"改包名安不安全"（最关键的一步！）](#七第四步排查改包名安不安全最关键的一步)
- [八、第五步：解包 APK](#八第五步解包-apk)
- [九、第六步：改包名和应用名](#九第六步改包名和应用名)
- [十、第七步：重打包（最容易踩坑的一步）](#十第七步重打包最容易踩坑的一步)
- [十一、第八步：签名](#十一步第八步签名)
- [十二、第九步：验证变体](#十二第九步验证变体)
- [十三、第十步：上传到 GitHub Release](#十三第十步上传到-github-release)
- [十四、排查错误工具箱（遇到问题先来这里）](#十四排查错误工具箱遇到问题先来这里)
- [十五、踩过的坑完整记录](#十五踩过的坑完整记录)
- [十六、对排查调试有帮助的命令汇总](#十六对排查调试有帮助的命令汇总)
- [十七、完整命令速查表（从头到尾复制粘贴版）](#十七完整命令速查表从头到尾复制粘贴版)
- [十八、给后来 Agent 的忠告](#十八给后来-agent-的忠告)

---

## 一、这次到底要做成什么事

TRAE 是字节跳动的 AI 编程助手，有一个 Android 手机 App。之前已经基于原版 APK 做了逆向修改，加上了"提取对话""额度显示"等功能，产出了 `trae_cn3_v41.apk`（包名 `com.bytedance.trae.cn3`，应用名 `TRAE3`）。

现在要做的是：**基于这个已经改好的 `trae_cn3_v41.apk`，"克隆"出两个新 App**，它们功能完全一样，但包名和应用名不同，这样可以在同一台手机上同时安装三个互不冲突的实例：

| APK 文件名 | 包名（package） | 应用名（label） |
|------------|----------------|----------------|
| `trae_cn3_v41.apk`（已有） | `com.bytedance.trae.cn3` | `TRAE3` |
| `trae_v41.apk`（要生成） | `com.bytedance.trae.cn` | `TRAE` |
| `trae2_v41.apk`（要生成） | `com.bytedance.trae.cn2` | `TRAE2` |

三个 App 功能完全一样（同一套代码），只是"身份证"不同，Android 系统把它们当作三个独立 App，可以同时安装、互不干扰。

---

## 二、背景知识（不懂也能照做）

### 2.1 APK 的"身份证"由什么决定

一个 APK 有三样关键身份信息，改了这三样，系统就认为它是不同的 App：

1. **包名（package）**：写在 `AndroidManifest.xml` 文件里的 `package="com.bytedance.trae.cn3"`。这是最重要的，Android 系统靠它区分 App。
2. **应用名（label）**：手机桌面上显示的名字，比如"TRAE3"。写在 `res/values/strings.xml` 的 `app_name` 字段里。
3. **resources.arsc 里的包名**：这是资源表里记录的包名，和 Manifest 的 package 要一致。

> **大白话**：包名就像人的身份证号，应用名就像人的名字。改了这两个，系统就认为是不同的人了。

### 2.2 APK 内部长什么样

APK 本质上就是一个 ZIP 压缩包，里面装着一堆文件：

```
trae_cn3_v41.apk（本质是 ZIP）
├── AndroidManifest.xml      ← 二进制格式的清单文件（含包名）
├── resources.arsc            ← 编译后的资源表（含包名、字符串）
├── classes.dex              ← 第1个 dex（编译后的代码）
├── classes2.dex ~ classes9.dex ← 第2~9个 dex
├── res/                      ← 资源文件（图片、布局等）
├── assets/                   ← 原始资源
├── lib/                      ← so 动态库
└── META-INF/                 ← 签名信息
```

> **关键**：`AndroidManifest.xml` 和 `resources.arsc` 是**二进制格式**的，不能用记事本直接打开看。需要专门工具解码。

### 2.3 改包名有两种思路

| 思路 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| **思路A：从源码重新编译** | 拿 Java 源码，改包名，重新 javac→d8→签名 | 干净彻底 | 需要 Android SDK 全套工具，源码要完整 |
| **思路B：基于现成 APK 改包名** | 拿 `trae_cn3_v41.apk`，解包→改包名→重打包→签名 | 不需要源码，快 | 要处理二进制资源，可能踩坑 |

> **这次用思路B**，因为 `trae_cn3_v41.apk` 已经是改好的成品（含逆向注入的代码），从源码重新编译不现实。

---

## 三、和 MonkeyCode 方案的本质区别（重要！）

> **为什么要讲这个？** 因为参考的 MonkeyCode 指南是"从源码编译"，而 TRAE 是"逆向 APK 改包名"，两者技术路线完全不同。如果不搞清楚区别，照搬 MonkeyCode 的方法会失败。

| 对比项 | MonkeyCode 方案 | TRAE 方案（本文） |
|--------|----------------|------------------|
| **起点** | 纯 Java 源码（`MainActivity.java`） | 已构建好的 APK（`trae_cn3_v41.apk`） |
| **编译方式** | `javac → aapt2 → d8 → apksigner` 全流程 | `apktool 解包 → 改文件 → apktool 重打包 → 签名` |
| **改包名位置** | `AndroidManifest.xml` + `strings.xml` + Java 的 `package` 声明 + 文件夹路径 | 只改 `AndroidManifest.xml` + `strings.xml`（dex 代码不用动） |
| **需要 Android SDK** | 需要（aapt2、d8、android.jar） | 不需要（apktool 自带） |
| **核心工具** | javac, aapt2, d8, apksigner | apktool, uber-apk-signer |

> **大白话**：MonkeyCode 是"从面粉烤蛋糕"，TRAE 是"买现成蛋糕改包装"。后者更简单，但有个前提——**蛋糕里的代码不能硬编码包名**（否则改了包名代码就崩了）。这个前提需要专门排查，见第七步。

---

## 四、第一步：准备工具

### 4.1 需要哪些工具

| 工具 | 干什么用的 | 怎么装 |
|------|-----------|--------|
| `java` (JDK 17+) | 运行 apktool 和签名工具 | `apt-get install default-jdk` 或已有 |
| `apktool` | 解包/重打包 APK（核心工具） | 下载 jar 文件 |
| `uber-apk-signer` | 给 APK 签名+对齐（自带 zipalign 和 apksigner） | 下载 jar 文件 |
| `python3` + `pyaxmlparser` | 检查 APK 的包名和应用名 | `pip3 install pyaxmlparser` |
| `curl` | 下载文件、调用 GitHub API | 系统自带 |
| `unzip` / `zip` | 查看/操作 APK 内部文件 | 系统自带 |

### 4.2 安装命令

```bash
# 1. 检查 Java（需要 17+）
java -version
# 如果没有或版本太低：
# apt-get update && apt-get install -y default-jdk

# 2. 下载 apktool（约 23MB）
mkdir -p /home/z/my-project/work
cd /home/z/my-project/work
wget -q "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar" -O apktool.jar
# 验证
java -jar apktool.jar --version
# 应该输出: 2.9.3

# 3. 下载 uber-apk-signer（约 3MB，自带 zipalign 和 apksigner）
wget -q "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar" -O uber-apk-signer.jar
# 验证
java -jar uber-apk-signer.jar --version
# 应该输出: 1.3.0

# 4. 安装 pyaxmlparser（Python 库，用来读 APK 的包名）
pip3 install pyaxmlparser
# 验证
python3 -c "from pyaxmlparser import APK; print('ok')"
# 应该输出: ok
```

> **为什么用 apktool 而不是直接改二进制？**
> 因为 `AndroidManifest.xml` 和 `resources.arsc` 是二进制格式，直接用文本编辑器改会破坏文件结构。apktool 能把它们解码成可读的文本（XML），改完再编译回二进制，是最可靠的方式。

> **为什么用 uber-apk-signer 而不是 apksigner？**
> 因为系统里没有装 Android SDK 的 build-tools（没有 apksigner 和 zipalign）。uber-apk-signer 是一个 Java 工具，**自带了 zipalign 和 apksigner**，一个工具搞定签名+对齐，不需要装 Android SDK。

---

## 五、第二步：下载基础 APK

我们要基于 `trae_cn3_v41.apk` 来做变体。这个文件在 GitHub Release v41 里。

### 5.1 查询 Release 信息

```bash
TOKEN="ghp_你的TOKEN"
REPO="liliangxing/trae-cn3"

# 查看 v41 release 的信息
curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/$REPO/releases/tags/v41" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Release: {d[\"name\"]}')
print(f'Release ID: {d[\"id\"]}')  # ← 这个 ID 上传时要用！
print('资产列表:')
for a in d['assets']:
    print(f'  - {a[\"name\"]} | {a[\"size\"]} bytes | asset_id: {a[\"id\"]}')
"
```

**你应该看到的结果**：

```
Release: v41 - 修复额度显示(404+0.0M)
Release ID: 367389459    ← 记住这个数字！上传时要用
资产列表:
  - trae_cn3_v41.apk | 118729650 bytes | asset_id: 507169822
```

> **为什么要记 Release ID？** 后面上传 APK 时，URL 里要用这个 ID。注意：**Release ID 和 Asset ID 是两个不同的数字**，别搞混了。Release ID 标识整个发布，Asset ID 标识发布里的单个文件。

### 5.2 下载 APK

```bash
cd /home/z/my-project/work
TOKEN="ghp_你的TOKEN"

# 通过 asset_id 下载（注意 Accept 头要设成 octet-stream）
curl -sL -H "Authorization: token $TOKEN" \
  -H "Accept: application/octet-stream" \
  "https://api.github.com/repos/liliangxing/trae-cn3/releases/assets/507169822" \
  -o trae_cn3_v41.apk

# 验证大小（约 114MB）
ls -lh trae_cn3_v41.apk
```

**你应该看到的结果**：

```
-rw-rw-r-- 1 z z 114M Aug 13 03:00 trae_cn3_v41.apk
```

> **为什么用 `Accept: application/octet-stream`？**
> 因为直接请求 `/assets/<id>` 默认返回的是 JSON 元信息（文件名、大小等）。加上这个 Accept 头，GitHub 才会返回真正的文件内容（二进制流）。`-L` 表示跟随重定向（GitHub 会把下载请求重定向到 CDN）。

---

## 六、第三步：摸清楚 APK 的"身份证"信息

下载完 APK，先别急着改，先确认它的包名和应用名到底是什么。

### 6.1 用 pyaxmlparser 检查

```bash
cd /home/z/my-project/work
python3 << 'EOF'
from pyaxmlparser import APK
a = APK("trae_cn3_v41.apk")
print(f"包名 (package):    {a.package}")
print(f"应用名 (app_name): {a.application}")
print(f"versionName:       {a.version_name}")
print(f"versionCode:       {a.version_code}")
print(f"minSdkVersion:     {a.get_min_sdk_version()}")
print(f"targetSdkVersion:  {a.get_target_sdk_version()}")
EOF
```

**你应该看到的结果**：

```
包名 (package):    com.bytedance.trae.cn3
应用名 (app_name): TRAE3
versionName:       0.0.16
versionCode:       21
minSdkVersion:     24
targetSdkVersion:  34
```

> **为什么先检查？** 确认基础 APK 的身份信息，才知道要改什么。如果输出里有 `res1 is not zero!` 或 `invalid decoded string length` 的警告，**可以忽略**——那是 pyaxmlparser 对字节跳动 APK 非标准 arsc 格式的警告，不影响读取包名和应用名。

### 6.2 检查 APK 里有哪些 dex 文件

```bash
cd /home/z/my-project/work
python3 << 'EOF'
import zipfile
with zipfile.ZipFile("trae_cn3_v41.apk") as z:
    dexes = [n for n in z.namelist() if n.endswith('.dex')]
    for d in sorted(dexes):
        print(f"  {d} ({z.getinfo(d).file_size} bytes)")
EOF
```

**你应该看到的结果**：

```
  classes.dex (13455772 bytes)
  classes2.dex (10314376 bytes)
  classes3.dex (7490600 bytes)
  classes4.dex (11044216 bytes)
  classes5.dex (11755880 bytes)
  classes6.dex (9145840 bytes)
  classes7.dex (8710032 bytes)
  classes8.dex (10320464 bytes)
  classes9.dex (171720 bytes)    ← 注意这个很小，是自定义代码
```

> **为什么要看 dex 列表？** 了解 APK 结构。9 个 dex 说明代码量很大（约 80MB），重打包时会很慢。`classes9.dex` 只有 171KB，是逆向注入的自定义代码（ExtractHelper 等）。

---

## 七、第四步：排查"改包名安不安全"（最关键的一步！）

> **为什么这是最关键的一步？** 因为如果 APK 的代码（dex）里**硬编码**了包名字符串 `com.bytedance.trae.cn3`，那改了包名后，代码运行时找不到对应的类或资源，App 会崩溃。**其他 agent 之前没修好，很可能就是跳过了这一步排查**。

### 7.1 排查思路

改包名前，必须确认以下地方**没有**硬编码 `com.bytedance.trae.cn3`：

| 位置 | 为什么危险 | 怎么查 |
|------|-----------|--------|
| **smali 代码**（dex 反编译后） | 代码里写死了包名，改了会崩 | grep 搜索 |
| **assets 目录** | 配置文件里写死包名 | grep 搜索 |
| **res/xml 目录** | XML 配置写死包名 | grep 搜索 |

> **注意**：`com.bytedance.trae.xxx`（类路径，如 `com.bytedance.trae.conversation.ConversationActivity`）**不算硬编码包名**，那是 Java 类的全限定名，不能改。我们只找完整的 `com.bytedance.trae.cn3`（包名）。

### 7.2 先解包 APK（为了能搜索 smali 代码）

```bash
cd /home/z/my-project/work
# 用 apktool 解包（约 1-2 分钟）
rm -rf decoded_cn3
java -jar apktool.jar d -f -o decoded_cn3 trae_cn3_v41.apk
```

**你应该看到的结果**（最后几行）：

```
I: Using Apktool 2.9.3 on trae_cn3_v41.apk
I: Loading resource table...
I: Decoding file-resources...
I: Decoding values */* XMLs...
I: Decoding AndroidManifest.xml with resources...
I: Regular manifest package...
I: Baksmaling classes.dex...
I: Baksmaling classes9.dex...
...（多个 dex）
I: Copying assets and libs...
I: Copying unknown files...
I: Copying original files...
I: Copying META-INF/services directory
```

> **为什么用 `d` 参数？** `d` 是 decode（解码）的意思，把二进制 APK 解成可读的文本文件。`-f` 是 force（强制覆盖），`-o decoded_cn3` 指定输出目录。

### 7.3 排查 smali 代码里有没有硬编码包名

```bash
cd /home/z/my-project/work/decoded_cn3

# 搜索 smali 代码里有没有 com/bytedance/trae/cn3（注意 smali 里用 / 不用 .）
echo "=== smali 中 cn3 出现次数 ==="
grep -r "com/bytedance/trae/cn3" smali*/ 2>/dev/null | wc -l

# 看具体是哪些文件
echo "=== 具体文件列表 ==="
grep -rl "com/bytedance/trae/cn3" smali*/ 2>/dev/null | head -20
```

**你应该看到的结果**：

```
=== smali 中 cn3 出现次数 ===
0

=== 具体文件列表 ===
（空，没有任何文件）
```

> **太好了！0 处！** 这说明代码里没有硬编码包名，改包名是安全的。代码用的是 `context.getPackageName()` 这种动态获取包名的方式，改了 Manifest 的 package 属性，代码自动适应。

> **如果这里不是 0 怎么办？** 说明代码里硬编码了包名，改包名会导致崩溃。这时有两个选择：① 用 sed 把 smali 里的 `com/bytedance/trae/cn3` 也替换成新包名（风险高，可能漏改）；② 放弃改包名方案，改用"多用户/多开"方案。本文不展开。

### 7.4 排查 assets 和 res 目录

```bash
cd /home/z/my-project/work/decoded_cn3

# 检查 assets
echo "=== assets 中是否有 cn3 ==="
grep -rl "com.bytedance.trae.cn3" assets/ 2>/dev/null | head -10

# 检查 res/xml 等配置文件（排除 values 目录，那是字符串资源，正常）
echo "=== res/xml 中是否有 cn3 ==="
grep -rl "com.bytedance.trae.cn3" res/ 2>/dev/null | grep -v "values" | head -10
```

**你应该看到的结果**：

```
=== assets 中是否有 cn3 ===
（空）

=== res/xml 中是否有 cn3 ===
（空）
```

> **为什么排除 values 目录？** 因为 `res/values/strings.xml` 里可能有 `app_name`，但那是字符串资源，不是硬编码包名。我们关心的是 assets 和 res/xml 这种配置文件。

### 7.5 确认 app_name 只有一处

```bash
cd /home/z/my-project/work/decoded_cn3
echo "=== app_name 在 strings.xml 的位置 ==="
grep -n ">TRAE3<" res/values/strings.xml
```

**你应该看到的结果**：

```
50:    <string name="app_name">TRAE3</string>
```

> **为什么确认只有一处？** 如果有多处 `TRAE3`（比如图标名、其他字符串），改的时候要小心，只改 `app_name` 那一处。这里确认只有一处，直接 sed 全局替换即可。

### 7.6 统计 AndroidManifest.xml 里要改多少处

```bash
cd /home/z/my-project/work/decoded_cn3
echo "=== Manifest 中 cn3 出现次数 ==="
grep -o "com.bytedance.trae.cn3" AndroidManifest.xml | wc -l

echo "=== Manifest 中所有含 cn3 的属性（看有哪些类型）==="
grep -oE 'android:name="[^"]*com\.bytedance\.trae\.cn3[^"]*"' AndroidManifest.xml | sort -u | head -15

echo "=== authorities 属性（provider 的授权名）==="
grep -oE 'android:authorities="[^"]*"' AndroidManifest.xml | sort -u | head -20
```

**你应该看到的结果**：

```
=== Manifest 中 cn3 出现次数 ===
44

=== Manifest 中所有含 cn3 的属性 ===
android:name="com.bytedance.trae.cn3.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"
android:name="com.bytedance.trae.cn3.permission.MIPUSH_RECEIVE"
android:name="com.bytedance.trae.cn3.permission.PRIVACY_BROADCAST"
android:name="com.bytedance.trae.cn3.permission.PROCESS_PUSH_MSG"
android:name="com.bytedance.trae.cn3.permission.PUSH_PROVIDER"
android:name="com.bytedance.trae.cn3.permission.PUSH_WRITE_PROVIDER"
android:name="com.bytedance.trae.cn3.pushsdk.action"
...（共 11 种 permission/action）

=== authorities 属性 ===
android:authorities="com.bytedance.trae.cn3.AGCInitializeProvider"
android:authorities="com.bytedance.trae.cn3.TicketGuardProvider"
android:authorities="com.bytedance.trae.cn3.TokenObjectProvider"
...（共 19 种 authorities）
```

> **为什么要看这些？** 这 44 处包括：① `package` 属性本身；② 各种 `permission`（权限名，必须和包名一致）；③ `authorities`（Provider 的授权名，必须唯一，否则和别的 App 冲突）。**这些全都要改**，用 sed 全局替换最省事。

> **为什么 authorities 必须改？** 如果两个 App 的 authorities 一样，Android 系统会认为它们是同一个 Provider，后装的会装不上（报 `INSTALL_FAILED_CONFLICTING_PROVIDER`）。所以每个变体的 authorities 必须不同——而 authorities 是以包名开头的，改了包名 authorities 自然就不同了。

---

## 八、第五步：解包 APK

> 如果第七步已经解包了 `decoded_cn3`，这一步可以跳过。但为了流程完整，这里再写一遍。**实际操作时，每个变体都要单独解包一份**（因为要改不同的包名）。

### 8.1 解包 TRAE 变体

```bash
cd /home/z/my-project/work
rm -rf decoded_trae
java -jar apktool.jar d -f -o decoded_trae trae_cn3_v41.apk
```

> **为什么每个变体单独解包？** 因为 apktool 解包后会修改文件（改包名、改应用名），如果共用一个解包目录，第二个变体会基于第一个的修改，导致包名错误。每个变体从原始 APK 独立解包，保证干净。

---

## 九、第六步：改包名和应用名

### 9.1 改包名（AndroidManifest.xml）

```bash
cd /home/z/my-project/work/decoded_trae

# 改包名：cn3 → cn
sed -i 's|com.bytedance.trae.cn3|com.bytedance.trae.cn|g' AndroidManifest.xml

# 验证：替换了多少处，有没有残留
echo "替换后 cn3 残留: $(grep -o 'com.bytedance.trae.cn3' AndroidManifest.xml | wc -l)"
echo "替换后 cn 数量: $(grep -o 'com.bytedance.trae.cn' AndroidManifest.xml | wc -l)"
```

**你应该看到的结果**：

```
替换后 cn3 残留: 0
替换后 cn 数量: 44
```

> **为什么用 `sed -i`？** `-i` 表示 in-place（直接修改文件）。`s|旧|新|g` 是替换命令，`g` 表示全局替换（一行里出现多次都换）。
>
> **为什么用 `|` 不用 `/`？** sed 的分隔符通常是 `/`，但包名里没有 `/`，用 `|` 更清晰，避免和路径混淆。

> **⚠️ 避坑提醒**：注意 `com.bytedance.trae.cn3` 包含 `com.bytedance.trae.cn`！如果先替换 `cn` 再替换 `cn3`，会导致 `cn3` 变成 `cn3`→`cn`（错误）。所以**必须先替换长的（cn3），再替换短的（cn）**。但这里我们只替换一次（cn3→cn），所以没问题。如果要做 cn3→cn2，同理直接替换即可。

### 9.2 改应用名（strings.xml）

```bash
cd /home/z/my-project/work/decoded_trae

# 改应用名：TRAE3 → TRAE
sed -i 's|<string name="app_name">TRAE3</string>|<string name="app_name">TRAE</string>|g' res/values/strings.xml

# 验证
grep "app_name" res/values/strings.xml
```

**你应该看到的结果**：

```
    <string name="app_name">TRAE</string>
```

> **为什么用完整匹配而不是只替换 `TRAE3`？** 因为如果只 `sed 's|TRAE3|TRAE|g'`，可能会误伤其他字符串（比如某个资源里恰好有 `TRAE3`）。用完整的 `<string name="app_name">TRAE3</string>` 匹配，只改 app_name 这一处，最安全。

### 9.3 TRAE2 变体同理

```bash
cd /home/z/my-project/work
rm -rf decoded_trae2
java -jar apktool.jar d -f -o decoded_trae2 trae_cn3_v41.apk

cd decoded_trae2
sed -i 's|com.bytedance.trae.cn3|com.bytedance.trae.cn2|g' AndroidManifest.xml
sed -i 's|<string name="app_name">TRAE3</string>|<string name="app_name">TRAE2</string>|g' res/values/strings.xml

# 验证
echo "cn3 残留: $(grep -o 'com.bytedance.trae.cn3' AndroidManifest.xml | wc -l)"
grep "app_name" res/values/strings.xml
```

---

## 十、第七步：重打包（最容易踩坑的一步）

> **这一步是最容易踩坑的！** 因为 APK 很大（118MB，9个dex），apktool 重打包时要把所有 smali 重新编译成 dex，非常吃内存和时间。**其他 agent 之前失败，很可能就是卡在这一步**。

### 10.1 生成签名密钥（只需一次）

```bash
cd /home/z/my-project/work

# 生成密钥（只需做一次，两个变体共用）
keytool -genkeypair -v \
    -keystore trae.keystore \
    -alias trae \
    -keyalg RSA -keysize 2048 \
    -validity 36500 \
    -storepass trae123456 \
    -keypass trae123456 \
    -dname "CN=TRAE, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN"

# 验证
keytool -list -keystore trae.keystore -storepass trae123456
```

**你应该看到的结果**：

```
Keystore type: PKCS12
Keystore provider: SUN

Your keystore contains 1 entry

trae, Aug 13, 2026, PrivateKeyEntry
Certificate fingerprint (SHA-256): 6C:47:B0:AE:...
```

> **为什么要生成密钥？** Android 要求所有 APK 必须签名才能安装。签名就像给产品盖"合格章"。`-validity 36500` 是有效期 100 年（36500天），避免过期。
>
> **为什么两个变体用同一个密钥？** 因为它们是"同源"App，用同一个签名可以共享数据（如果需要的话）。而且管理方便。

### 10.2 重打包（前台运行，可能超时）

```bash
cd /home/z/my-project/work
rm -f trae_unsigned.apk
java -Xmx3g -jar apktool.jar b -o trae_unsigned.apk decoded_trae
```

> **`-Xmx3g` 是什么？** 给 Java 虚拟机分配最大 3GB 堆内存。apktool 重打包很吃内存，不加这个可能 OOM（内存不足）被杀。
>
> **`b` 参数是什么？** build（构建），把解包目录重新打包成 APK。

**⚠️ 这一步可能遇到的问题**：

**问题1：进程被杀，APK 没生成**

如果命令运行很久没反应，或者报错退出，APK 没生成，很可能是**内存不足被系统 OOM killer 杀了**。解决方法见 10.3。

**问题2：报 `not a ZIP archive`**

如果后续签名时报 `Malformed APK: not a ZIP archive`，说明 APK 文件不完整（打包过程被中断，文件只写了一半）。解决方法：删掉 APK 重新打包。

### 10.3 重打包的避坑方案：后台运行 + 轮询

> **这是本文档最重要的避坑技巧之一！** 因为 apktool 重打包大 APK 很慢（5-10分钟），直接前台运行可能因为工具调用超时被中断。用"后台运行 + 轮询检查"的方式最稳妥。

```bash
cd /home/z/my-project/work
rm -f trae_unsigned.apk build_trae.log

# 后台运行打包，输出重定向到日志文件
nohup java -Xmx3g -jar apktool.jar b -o trae_unsigned.apk decoded_trae > build_trae.log 2>&1 &
echo "PID=$!"          # 记录进程号
echo $! > build_trae.pid

# 等几秒让它启动
sleep 3
echo "已启动"
```

然后轮询检查（每 10 秒看一次）：

```bash
cd /home/z/my-project/work
PID=$(cat build_trae.pid)
for i in $(seq 1 50); do
    if [ -f trae_unsigned.apk ]; then
        echo "✅ 构建完成! 大小: $(ls -lh trae_unsigned.apk | awk '{print $5}')"
        break
    fi
    if ! kill -0 $PID 2>/dev/null; then
        echo "⚠️ 进程结束"
        [ -f trae_unsigned.apk ] && echo "✅ APK存在" || echo "❌ APK不存在"
        break
    fi
    sleep 10
    echo "[$i] 构建中... $(tail -1 build_trae.log 2>/dev/null)"
done
tail -6 build_trae.log
```

> **`nohup ... &` 是什么？** `nohup` 让进程在后台运行，即使终端关闭也不受影响。`&` 表示放到后台。`> build_trae.log 2>&1` 把标准输出和错误输出都写到日志文件。
>
> **`kill -0 $PID` 是什么？** 这不是杀进程，而是**检测进程是否还活着**。`-0` 表示发信号0（不发真信号，只检测）。如果进程还在，返回0（真）；如果进程已结束，返回非0（假）。

### 10.4 利用 apktool 增量缓存（关键技巧！）

> **这是本文档最核心的避坑技巧！** 如果第一次打包被 OOM 杀了，**不要删解包目录重新来**！apktool 有增量构建机制：第一次打包时编译好的 dex 和 resources 会缓存在 `decoded_trae/build/` 目录，第二次打包时会跳过这些已编译的部分，直接组装 APK，几秒就完成。

**检查缓存是否存在**：

```bash
cd /home/z/my-project/work
ls decoded_trae/build/
```

**如果输出有 `apk` 和 `resources.zip`**，说明 dex 和资源都编译好了，可以直接重新打包：

```bash
cd /home/z/my-project/work
rm -f trae_unsigned.apk
java -Xmx2g -jar apktool.jar b -o trae_unsigned.apk decoded_trae
# 这次会很快（几秒到几十秒），因为跳过了 dex 编译
ls -lh trae_unsigned.apk
```

**你应该看到的结果**：

```
I: Checking whether sources has changed...
I: Checking whether sources has changed...
...（多个 "Checking whether sources has changed" 说明在跳过未改动的 dex）
I: Building resources...
I: Building apk file...
I: Copying unknown files/dir...
I: Built apk into: trae_unsigned.apk
-rw-rw-r-- 1 z z 107M Aug 13 03:04 trae_unsigned.apk
```

> **为什么能跳过 dex 编译？** 因为 apktool 会检查每个 smali 文件夹的修改时间，如果没变就用缓存里已编译的 dex。我们只改了 `AndroidManifest.xml` 和 `strings.xml`，没动 smali 代码，所以 dex 全部跳过。
>
> **这个技巧省了多少时间？** 第一次完整打包要 5-10 分钟（编译 9 个 dex），利用缓存只要 10-30 秒（只组装）。**10-20 倍提速**！

### 10.5 验证 APK 完整性

```bash
cd /home/z/my-project/work
# 检查是不是合法的 ZIP（APK 本质是 ZIP）
file trae_unsigned.apk
# 应该输出: Zip archive data, ...

# 测试 ZIP 完整性
unzip -t trae_unsigned.apk > /dev/null 2>&1 && echo "ZIP完整" || echo "ZIP损坏"
# 应该输出: ZIP完整
```

> **为什么要验证？** 如果打包过程被中断，APK 文件可能不完整（只写了一半），后续签名会报 `not a ZIP archive`。先验证完整性，避免白费功夫。

---

## 十一、第八步：签名

### 11.1 用 uber-apk-signer 签名

```bash
cd /home/z/my-project/work
java -jar uber-apk-signer.jar \
    -a trae_unsigned.apk \
    --ks trae.keystore --ksAlias trae \
    --ksPass trae123456 --ksKeyPass trae123456 \
    -o /home/z/my-project/work \
    --allowResign 2>&1 | tail -15
```

**你应该看到的结果**：

```
01. trae_unsigned.apk
        zipalign success
        sign success

        VERIFY
        file: /home/z/my-project/work/trae_unsigned-aligned-signed.apk (106.26 MiB)
        - zipalign verified
        - signature verified [v2, v3]
                Subject: CN=TRAE, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN
                SHA256: 6c47b0ae... / SHA384withRSA
                Expires: Sat Jul 20 02:58:33 UTC 2126

Successfully processed 1 APKs and 0 errors in 2.90 seconds.
```

> **`--allowResign` 是什么？** 因为原版 APK 已经有签名了（trae_cn3_v41.apk 是签过名的），uber-apk-signer 默认不会重新签名已有签名的 APK。加 `--allowResign` 允许覆盖原签名。
>
> **`[v2, v3]` 是什么？** Android 的签名方案有 v1/v2/v3/v4 四种。v2 和 v3 是 Android 7.0+ 和 9.0+ 的方案，覆盖大部分现代手机。这里两个都通过了，说明签名没问题。
>
> **输出文件名规则**：uber-apk-signer 的输出文件名是 `<输入名>-aligned-signed.apk`，即 `trae_unsigned-aligned-signed.apk`。

### 11.2 ⚠️ 签名避坑：参数格式

> **踩坑提醒**：uber-apk-signer 1.3.0 的参数解析比较严格。如果参数顺序不对，它不会报错，而是直接打印帮助信息（看起来像成功了，其实没签）。

**错误用法**（会打印帮助，不签名）：

```bash
# ❌ 缺少 --allowResign
java -jar uber-apk-signer.jar -a trae_unsigned.apk --ks trae.keystore --ksAlias trae --ksPass trae123456 --ksKeyPass trae123456 -o /home/z/my-project/work --overwrite
```

**正确用法**（必须加 `--allowResign`）：

```bash
# ✅ 加 --allowResign
java -jar uber-apk-signer.jar -a trae_unsigned.apk --ks trae.keystore --ksAlias trae --ksPass trae123456 --ksKeyPass trae123456 -o /home/z/my-project/work --allowResign
```

> **怎么判断签名成功了？** 看输出里有没有 `signature verified [v2, v3]` 和 `Successfully processed 1 APKs and 0 errors`。如果只看到帮助信息（一堆参数说明），说明签名失败。

### 11.3 重命名并移动到 download 目录

```bash
cd /home/z/my-project/work
mkdir -p /home/z/my-project/download
mv trae_unsigned-aligned-signed.apk /home/z/my-project/download/trae_v41.apk
ls -lh /home/z/my-project/download/trae_v41.apk
```

---

## 十二、第九步：验证变体

### 12.1 写验证脚本

```bash
cat > /home/z/my-project/scripts/verify_variant.py << 'EOF'
#!/usr/bin/env python3
"""验证变体 APK 的包名和应用名是否正确"""
import sys
from pyaxmlparser import APK

apk_path = sys.argv[1]
expect_pkg = sys.argv[2]
expect_label = sys.argv[3]

a = APK(apk_path)
actual_pkg = a.package
actual_label = a.application

print(f"  期望包名:   {expect_pkg}")
print(f"  实际包名:   {actual_pkg}")
print(f"  期望应用名: {expect_label}")
print(f"  实际应用名: {actual_label}")
print(f"  versionName: {a.version_name}  versionCode: {a.version_code}")

ok = (actual_pkg == expect_pkg and actual_label == expect_label)
if ok:
    print("\n  ✅ 验证通过: 包名和应用名均正确")
    sys.exit(0)
else:
    print("\n  ❌ 验证失败: 包名或应用名不匹配!")
    sys.exit(1)
EOF
```

### 12.2 验证 TRAE 变体

```bash
python3 /home/z/my-project/scripts/verify_variant.py \
    /home/z/my-project/download/trae_v41.apk \
    com.bytedance.trae.cn TRAE 2>&1 | grep -v "invalid decoded\|res1 is not"
```

**你应该看到的结果**：

```
  期望包名:   com.bytedance.trae.cn
  实际包名:   com.bytedance.trae.cn
  期望应用名: TRAE
  实际应用名: TRAE
  versionName: 0.0.16  versionCode: 21

  ✅ 验证通过: 包名和应用名均正确
```

> **为什么要验证？** 确认改包名和应用名都成功了。如果实际包名还是 `cn3`，说明 sed 没生效或 apktool 没重新编译 manifest。

---

## 十三、第十步：上传到 GitHub Release

### 13.1 确认 Release ID

```bash
TOKEN="ghp_你的TOKEN"
curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/liliangxing/trae-cn3/releases/tags/v41" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Release ID: {d[\"id\"]}')"
```

**你应该看到的结果**：

```
Release ID: 367389459
```

> **⚠️ 避坑提醒**：Release ID 是 `367389459`，不是 Asset ID（`507169822`）。上传时 URL 里用的是 **Release ID**，别搞混了！

### 13.2 上传 trae_v41.apk

```bash
TOKEN="ghp_你的TOKEN"
REPO="liliangxing/trae-cn3"
RELEASE_ID=367389459

curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/vnd.android.package-archive" \
  --data-binary @/home/z/my-project/download/trae_v41.apk \
  "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=trae_v41.apk" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ 上传成功: {d.get(\"name\")} | {d.get(\"size\")} bytes | url: {d.get(\"browser_download_url\")}') if 'name' in d else print(f'❌ 失败: {d}')"
```

**你应该看到的结果**：

```
✅ 上传成功: trae_v41.apk | 111422168 bytes | url: https://github.com/liliangxing/trae-cn3/releases/download/v41/trae_v41.apk
```

> **`Content-Type: application/vnd.android.package-archive` 是什么？** 告诉 GitHub 这是一个 Android 安装包文件。如果不设这个，GitHub 可能会把 APK 当普通文件处理。
>
> **`--data-binary @文件` 是什么？** `@` 表示从文件读取内容上传，`--binary` 表示按二进制上传（不做任何转义）。APK 是二进制文件，必须用这个。

### 13.3 上传 trae2_v41.apk

```bash
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/vnd.android.package-archive" \
  --data-binary @/home/z/my-project/download/trae2_v41.apk \
  "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=trae2_v41.apk" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ 上传成功: {d.get(\"name\")} | {d.get(\"size\")} bytes | url: {d.get(\"browser_download_url\")}') if 'name' in d else print(f'❌ 失败: {d}')"
```

### 13.4 验证最终资产列表

```bash
TOKEN="ghp_你的TOKEN"
curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/liliangxing/trae-cn3/releases/367389459" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Release: {d[\"name\"]} (tag: {d[\"tag_name\"]})')
print(f'共 {len(d[\"assets\"])} 个资产:')
for a in d['assets']:
    size_mb = a['size'] / 1024 / 1024
    print(f'  ✅ {a[\"name\"]:25s} | {size_mb:6.1f} MB')
    print(f'      URL: {a[\"browser_download_url\"]}')
"
```

**你应该看到的结果**：

```
Release: v41 - 修复额度显示(404+0.0M) (tag: v41)
共 3 个资产:
  ✅ trae2_v41.apk             |  106.3 MB
      URL: https://github.com/liliangxing/trae-cn3/releases/download/v41/trae2_v41.apk
  ✅ trae_cn3_v41.apk          |  113.2 MB
      URL: https://github.com/liliangxing/trae-cn3/releases/download/v41/trae_cn3_v41.apk
  ✅ trae_v41.apk              |  106.3 MB
      URL: https://github.com/liliangxing/trae-cn3/releases/download/v41/trae_v41.apk
```

---

## 十四、排查错误工具箱（遇到问题先来这里）

### 14.1 问题：apktool 打包时进程被杀，APK 没生成

**现象**：运行 `java -jar apktool.jar b ...` 后，等很久没反应，或者进程消失，APK 文件不存在。

**排查命令**：

```bash
# 1. 看日志
cat build_trae.log

# 2. 看内存（是不是 OOM）
free -h

# 3. 看 OOM killer 记录（需要 root）
dmesg | grep -iE "oom|kill" | tail -5

# 4. 看有没有残留的 java 进程
ps aux | grep -E "java|apktool" | grep -v grep
```

**解决方法**：

1. **加大 JVM 内存**：`java -Xmx3g -jar apktool.jar b ...`
2. **用后台运行 + 轮询**（见 10.3）
3. **利用增量缓存**（见 10.4）：第一次被杀后，`build/` 目录有缓存，第二次打包会跳过 dex 编译

### 14.2 问题：签名时报 `Malformed APK: not a ZIP archive`

**现象**：uber-apk-signer 报 `could not verify xxx.apk: Malformed APK: not a ZIP archive`

**原因**：APK 文件不完整（打包过程被中断，只写了一半）

**排查命令**：

```bash
file trae_unsigned.apk
# 如果输出不是 "Zip archive data"，说明文件损坏

unzip -t trae_unsigned.apk > /dev/null 2>&1 && echo "ZIP完整" || echo "ZIP损坏"
```

**解决方法**：删掉 APK，重新打包（利用缓存会很快）

```bash
rm -f trae_unsigned.apk
java -Xmx2g -jar apktool.jar b -o trae_unsigned.apk decoded_trae
```

### 14.3 问题：uber-apk-signer 只打印帮助信息，不签名

**现象**：运行签名命令后，输出一堆参数说明，没有 `signature verified`

**原因**：参数格式不对，或者缺少 `--allowResign`

**解决方法**：确保加了 `--allowResign`（因为原版 APK 已有签名）

```bash
java -jar uber-apk-signer.jar -a trae_unsigned.apk \
    --ks trae.keystore --ksAlias trae \
    --ksPass trae123456 --ksKeyPass trae123456 \
    -o /home/z/my-project/work --allowResign
```

### 14.4 问题：上传时报 `Not Found`

**现象**：curl 上传 APK，返回 `{'message': 'Not Found'}`

**原因**：Release ID 用错了（可能用了 Asset ID）

**排查命令**：

```bash
# 重新查询 Release ID
curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/liliangxing/trae-cn3/releases/tags/v41" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Release ID: {d[\"id\"]}')"
```

**解决方法**：用正确的 Release ID（`367389459`），不是 Asset ID

### 14.5 问题：改包名后 App 闪退

**现象**：APK 装到手机上，打开就闪退

**原因**：代码里硬编码了包名，改了包名后代码找不到对应的类/资源

**排查命令**（见第七步）：

```bash
grep -r "com/bytedance/trae/cn3" smali*/ 2>/dev/null | wc -l
# 如果不是 0，说明有硬编码
```

**解决方法**：如果 smali 里有硬编码，需要同步替换：

```bash
# 把 smali 里的包名路径也替换（风险高，谨慎）
find smali*/ -name "*.smali" -exec sed -i 's|com/bytedance/trae/cn3|com/bytedance/trae/cn|g' {} +
```

> **⚠️ 注意**：这种全局替换风险很高，可能误伤类路径。建议先备份，替换后逐个检查。如果硬编码太多，建议放弃改包名方案。

### 14.6 问题：pyaxmlparser 报 `res1 is not zero!`

**现象**：用 pyaxmlparser 读 APK 时，输出一堆 `res1 is not zero!` 和 `invalid decoded string length` 警告

**原因**：字节跳动的 APK 用了非标准的 arsc 格式（可能是反编译保护），pyaxmlparser 解析时报警告

**解决方法**：**忽略这些警告**，不影响读取包名和应用名。只要最终能输出正确的 `package` 和 `application` 就行。

---

## 十五、踩过的坑完整记录

### 坑 1：apktool 重打包 OOM 被杀

| 项目 | 内容 |
|------|------|
| **现象** | `java -jar apktool.jar b ...` 运行很久后进程消失，APK 没生成 |
| **排查** | `cat build_trae.log` 看到停在 `Smaling smali_classes8 folder` 或 `Building resources`；`free -h` 看到内存不足 |
| **原因** | APK 有 9 个 dex（共 80MB），apktool 重新 smali 编译非常吃内存，4GB 内存机器容易 OOM |
| **解决** | ① 加大 JVM 内存 `-Xmx3g`；② 用后台运行避免超时；③ **利用增量缓存**（第一次被杀后，`build/` 目录有缓存，第二次跳过 dex 编译） |
| **教训** | 大 APK 重打包一定要用增量缓存，别每次从头来 |

### 坑 2：APK 文件不完整（not a ZIP archive）

| 项目 | 内容 |
|------|------|
| **现象** | 签名时报 `could not verify xxx.apk: Malformed APK: not a ZIP archive` |
| **排查** | `file trae_unsigned.apk` 输出不是 `Zip archive data`；`unzip -t` 报损坏 |
| **原因** | apktool 打包过程被中断（OOM 或超时），APK 文件只写了一半 |
| **解决** | 删掉 APK，重新打包（利用缓存会很快） |
| **教训** | 签名前一定要先验证 APK 完整性：`unzip -t xxx.apk` |

### 坑 3：uber-apk-signer 参数格式

| 项目 | 内容 |
|------|------|
| **现象** | 运行签名命令后，只打印帮助信息，没有 `signature verified` |
| **排查** | 输出里没有 `Successfully processed` 字样 |
| **原因** | 缺少 `--allowResign` 参数（原版 APK 已有签名，不加这个不会重新签） |
| **解决** | 加上 `--allowResign` |
| **教训** | uber-apk-signer 对已有签名的 APK 必须加 `--allowResign` |

### 坑 4：Release ID 和 Asset ID 搞混

| 项目 | 内容 |
|------|------|
| **现象** | 上传 APK 时返回 `{'message': 'Not Found'}` |
| **排查** | 检查 URL 里的 ID，发现用了 Asset ID（507169822）而不是 Release ID（367389459） |
| **原因** | 两个 ID 长得很像，容易搞混 |
| **解决** | 上传时用 Release ID：`/releases/367389459/assets` |
| **教训** | Release ID 标识整个发布，Asset ID 标识发布里的单个文件。上传用 Release ID |

### 坑 5：arsc 二进制直接改包名失败

| 项目 | 内容 |
|------|------|
| **现象** | 想直接用二进制编辑器改 resources.arsc 里的包名，结果改了 APK 装不上 |
| **排查** | 解析 arsc 发现 package header 是非标准格式（headerSize=28 而标准 268） |
| **原因** | 字节跳动 APK 用了自定义/加密的 arsc 格式，直接二进制改会破坏校验 |
| **解决** | 放弃二进制 patch，用 apktool 解包+重打包（让它重新生成标准 arsc） |
| **教训** | 字节跳动的 APK 有反编译保护，别想走捷径改二进制，老老实实用 apktool |

### 坑 6：sed 替换顺序导致包名错误

| 项目 | 内容 |
|------|------|
| **现象** | 先替换 `cn3`→`cn`，再替换 `cn`→`cn2`，结果 `cn3` 变成了 `cn2` 而不是 `cn` |
| **原因** | `com.bytedance.trae.cn3` 包含 `com.bytedance.trae.cn`，短字符串会误匹配长字符串 |
| **解决** | 每个变体只做一次替换（cn3→cn 或 cn3→cn2），不要链式替换 |
| **教训** | sed 替换时注意字符串包含关系，长字符串优先 |

---

## 十六、对排查调试有帮助的命令汇总

> 这一节专门收集"排查问题时用得上的命令"，方便手工模拟整个过程。

### 16.1 查看 APK 基本信息

```bash
# 方法1：用 pyaxmlparser（推荐，不需要 aapt）
python3 -c "
from pyaxmlparser import APK
a = APK('trae_cn3_v41.apk')
print(f'包名: {a.package}')
print(f'应用名: {a.application}')
print(f'versionName: {a.version_name}')
print(f'versionCode: {a.version_code}')
"

# 方法2：用 strings 粗略看（不需要任何工具）
unzip -p trae_cn3_v41.apk AndroidManifest.xml | strings | grep -iE "trae|bytedance" | head -10
```

### 16.2 查看 APK 内部结构

```bash
# 列出所有文件
unzip -l trae_cn3_v41.apk | head -30

# 只看 dex 文件
unzip -l trae_cn3_v41.apk | grep "\.dex$"

# 看 APK 大小
ls -lh trae_cn3_v41.apk
```

### 16.3 搜索 APK 里的字符串

```bash
# 搜索整个 APK 里的字符串（二进制也搜）
strings trae_cn3_v41.apk | grep "com.bytedance.trae" | sort | uniq -c | sort -rn | head -10

# 只搜 resources.arsc
unzip -p trae_cn3_v41.apk resources.arsc | strings | grep -iE "trae" | head -20
```

### 16.4 解包后搜索代码

```bash
# 搜索 smali 代码里的硬编码包名
grep -r "com/bytedance/trae/cn3" smali*/ 2>/dev/null | wc -l

# 搜索 assets 里的硬编码包名
grep -rl "com.bytedance.trae.cn3" assets/ 2>/dev/null

# 搜索 res/xml 里的硬编码包名
grep -rl "com.bytedance.trae.cn3" res/ 2>/dev/null | grep -v "values"

# 统计 Manifest 里要改多少处
grep -o "com.bytedance.trae.cn3" AndroidManifest.xml | wc -l
```

### 16.5 检查打包结果

```bash
# 检查 APK 是不是合法 ZIP
file trae_unsigned.apk

# 测试 ZIP 完整性
unzip -t trae_unsigned.apk > /dev/null 2>&1 && echo "完整" || echo "损坏"

# 看签名后的 APK 里的 dex（确认没丢）
unzip -l trae_v41.apk | grep "\.dex$"
```

### 16.6 检查签名

```bash
# 用 uber-apk-signer 验证签名
java -jar uber-apk-signer.jar -a trae_v41.apk -y 2>&1 | tail -10

# 用 keytool 看密钥信息
keytool -list -keystore trae.keystore -storepass trae123456
```

### 16.7 检查进程和内存（排查 OOM）

```bash
# 看内存
free -h

# 看有没有残留 java 进程
ps aux | grep java | grep -v grep

# 看 OOM killer 记录（需要 root）
dmesg | grep -iE "oom|kill" | tail -5

# 检查 apktool build 缓存
ls decoded_trae/build/
```

### 16.8 解析 arsc 二进制（高级调试）

```bash
# 解析 arsc 的 package header（看包名存在哪）
python3 << 'EOF'
import zipfile, struct
with zipfile.ZipFile("trae_cn3_v41.apk") as z:
    data = z.read("resources.arsc")
# arsc table header
typ, hsz, sz, pkg_count = struct.unpack_from('<HHII', data, 0)
print(f"arsc: type=0x{typ:04x} headerSize={hsz} size={sz} packageCount={pkg_count}")
# 第一个 package
off = hsz
ptyp, phsz, psz = struct.unpack_from('<HHI', data, off)
pkg_id = struct.unpack_from('<I', data, off+8)[0]
name_raw = data[off+12:off+12+256]
name = name_raw.decode('utf-16-le', errors='replace').rstrip('\x00')
print(f"package: id=0x{pkg_id:08x} headerSize={phsz} name='{name}'")
EOF
```

> **调试技巧**：如果 arsc 的 `headerSize` 不是标准的 268，说明是字节跳动的非标准格式，别想直接二进制改包名，必须用 apktool。

### 16.9 GitHub API 调试

```bash
# 查看所有 release
curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/liliangxing/trae-cn3/releases?per_page=30" \
    | python3 -c "
import sys,json
for r in json.load(sys.stdin):
    print(f'tag: {r[\"tag_name\"]} | release_id: {r[\"id\"]} | name: {r[\"name\"]}')
    for a in r.get('assets',[]):
        print(f'    - {a[\"name\"]} | asset_id: {a[\"id\"]}')
"

# 查看单个 release 详情
curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/liliangxing/trae-cn3/releases/tags/v41" \
    | python3 -m json.tool | head -30
```

---

## 十七、完整命令速查表（从头到尾复制粘贴版）

> 以下命令按顺序执行，可以从头到尾复制粘贴。把 `你的TOKEN` 替换成你的 GitHub Token。

```bash
# ===== 0. 环境变量 =====
TOKEN="ghp_你的TOKEN"
WORK=/home/z/my-project/work
DOWNLOAD=/home/z/my-project/download
REPO="liliangxing/trae-cn3"
RELEASE_ID=367389459
mkdir -p $WORK $DOWNLOAD

# ===== 1. 准备工具 =====
cd $WORK
[ ! -f apktool.jar ] && wget -q "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar" -O apktool.jar
[ ! -f uber-apk-signer.jar ] && wget -q "https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar" -O uber-apk-signer.jar
pip3 install -q pyaxmlparser

# 生成签名密钥（只需一次）
[ ! -f trae.keystore ] && keytool -genkeypair -v \
    -keystore trae.keystore -alias trae -keyalg RSA -keysize 2048 \
    -validity 36500 -storepass trae123456 -keypass trae123456 \
    -dname "CN=TRAE, OU=Dev, O=ByteDance, L=Beijing, ST=Beijing, C=CN"

# ===== 2. 下载基础 APK =====
cd $WORK
[ ! -f trae_cn3_v41.apk ] && curl -sL -H "Authorization: token $TOKEN" \
    -H "Accept: application/octet-stream" \
    "https://api.github.com/repos/$REPO/releases/assets/507169822" \
    -o trae_cn3_v41.apk

# ===== 3. 构建函数（可复用）=====
build_variant() {
    local NAME=$1      # 变体名: trae / trae2
    local SUFFIX=$2    # 包名后缀: cn / cn2
    local LABEL=$3     # 应用名: TRAE / TRAE2

    echo "=== 构建 $NAME (com.bytedance.trae.$SUFFIX, $LABEL) ==="
    cd $WORK

    # 解包
    rm -rf decoded_$NAME
    java -jar apktool.jar d -f -o decoded_$NAME trae_cn3_v41.apk

    # 改包名和应用名
    cd decoded_$NAME
    sed -i "s|com.bytedance.trae.cn3|com.bytedance.trae.$SUFFIX|g" AndroidManifest.xml
    sed -i "s|<string name=\"app_name\">TRAE3</string>|<string name=\"app_name\">$LABEL</string>|g" res/values/strings.xml
    cd $WORK

    # 重打包（后台运行避免超时）
    rm -f ${NAME}_unsigned.apk build_${NAME}.log
    nohup java -Xmx3g -jar apktool.jar b -o ${NAME}_unsigned.apk decoded_$NAME > build_${NAME}.log 2>&1 &
    local PID=$!
    echo "打包中 PID=$PID"
    for i in $(seq 1 60); do
        [ -f ${NAME}_unsigned.apk ] && break
        kill -0 $PID 2>/dev/null || break
        sleep 10
    done
    # 如果第一次没成功，利用缓存重试
    if [ ! -f ${NAME}_unsigned.apk ]; then
        echo "第一次打包未完成，利用缓存重试..."
        java -Xmx2g -jar apktool.jar b -o ${NAME}_unsigned.apk decoded_$NAME
    fi
    unzip -t ${NAME}_unsigned.apk > /dev/null 2>&1 || { echo "❌ APK损坏"; return 1; }

    # 签名
    java -jar uber-apk-signer.jar -a ${NAME}_unsigned.apk \
        --ks trae.keystore --ksAlias trae \
        --ksPass trae123456 --ksKeyPass trae123456 \
        -o $WORK --allowResign 2>&1 | tail -5

    # 移动到 download
    mv ${NAME}_unsigned-aligned-signed.apk $DOWNLOAD/${NAME}_v41.apk

    # 验证
    python3 -c "
from pyaxmlparser import APK
a = APK('$DOWNLOAD/${NAME}_v41.apk')
print(f'  包名: {a.package}')
print(f'  应用名: {a.application}')
assert a.package == 'com.bytedance.trae.$SUFFIX', '包名错误!'
assert a.application == '$LABEL', '应用名错误!'
print('  ✅ 验证通过')
" 2>&1 | grep -v "invalid decoded\|res1 is not"
}

# ===== 4. 构建两个变体 =====
build_variant trae  cn  TRAE
build_variant trae2 cn2 TRAE2

# ===== 5. 上传到 v41 release =====
cd $DOWNLOAD
for f in trae_v41.apk trae2_v41.apk; do
    echo "=== 上传 $f ==="
    curl -s -X POST \
        -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/vnd.android.package-archive" \
        --data-binary @$f \
        "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=$f" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ {d.get(\"name\",\"失败\")} | {d.get(\"browser_download_url\",d)}') if 'name' in d else print(f'❌ {d}')"
done

# ===== 6. 验证最终结果 =====
curl -s -H "Authorization: token $TOKEN" \
    "https://api.github.com/repos/$REPO/releases/$RELEASE_ID" \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Release: {d[\"name\"]}')
for a in d['assets']:
    print(f'  ✅ {a[\"name\"]:25s} | {a[\"size\"]/1024/1024:6.1f} MB')
"
```

---

## 十八、给后来 Agent 的忠告

> 这一节专门写给后续接手这个任务的 AI Agent。其他 agent 之前没修好，主要是因为踩了以下几个坑。请仔细阅读，避免重蹈覆辙。

### 18.1 必须先排查"改包名安不安全"

> **这是最容易被忽略的一步！** 很多 agent 直接就开始改包名，结果 App 装上手机就闪退。

**必做排查**（见第七步）：

```bash
# 解包后，搜索 smali 代码里有没有硬编码包名
grep -r "com/bytedance/trae/cn3" smali*/ 2>/dev/null | wc -l
# 必须是 0 才能安全改包名
```

如果不是 0，说明代码里硬编码了包名，改了会崩。这时要么同步替换 smali 里的包名（风险高），要么放弃改包名方案。

### 18.2 不要尝试二进制 patch arsc

> **字节跳动的 APK 用了非标准 arsc 格式**，直接改二进制会破坏校验。别浪费时间在这上面，老老实实用 apktool 解包+重打包。

**验证方法**：

```bash
python3 -c "
import zipfile, struct
data = zipfile.ZipFile('trae_cn3_v41.apk').read('resources.arsc')
typ, hsz, sz, pkg_count = struct.unpack_from('<HHII', data, 0)
phsz = struct.unpack_from('<H', data, hsz+2)[0]
print(f'package headerSize={phsz} (标准是268)')
# 如果不是 268，说明是非标准格式，别想二进制改
"
```

### 18.3 大 APK 重打包要用增量缓存

> **apktool 重打包 118MB 的 APK（9个dex）非常吃内存**，4GB 内存机器容易 OOM。但 apktool 有增量缓存机制，第一次打包（即使被杀）会在 `build/` 目录留下编译好的 dex 和 resources，第二次打包会跳过这些，几秒完成。

**关键操作**：

```bash
# 第一次打包（可能 OOM 被杀）
java -Xmx3g -jar apktool.jar b -o trae_unsigned.apk decoded_trae

# 如果没成功，检查缓存
ls decoded_trae/build/
# 如果有 apk 和 resources.zip，说明缓存就绪，重新打包会很快
java -Xmx2g -jar apktool.jar b -o trae_unsigned.apk decoded_trae
```

### 18.4 签名必须加 --allowResign

> uber-apk-signer 对已有签名的 APK，默认不重新签名。必须加 `--allowResign`。

```bash
java -jar uber-apk-signer.jar -a xxx.apk --ks ... --allowResign
#                                                       ^^^^^^^^^^^^ 必须加
```

### 18.5 上传用 Release ID，不是 Asset ID

> 这两个 ID 容易搞混。Release ID 标识整个发布（367389459），Asset ID 标识发布里的单个文件（507169822）。上传时 URL 里用 Release ID。

```bash
# 正确：用 Release ID
curl -X POST ... "https://uploads.github.com/repos/$REPO/releases/367389459/assets?name=xxx.apk"

# 错误：用 Asset ID（会返回 Not Found）
curl -X POST ... "https://uploads.github.com/repos/$REPO/releases/507169822/assets?name=xxx.apk"
```

### 18.6 完整的排查链路

遇到问题时，按以下顺序排查：

1. **APK 完整性**：`file xxx.apk` + `unzip -t xxx.apk`
2. **包名正确性**：`python3 -c "from pyaxmlparser import APK; print(APK('xxx.apk').package)"`
3. **签名有效性**：`java -jar uber-apk-signer.jar -a xxx.apk -y`
4. **代码硬编码**：`grep -r "com/bytedance/trae/cn3" smali*/`
5. **内存状态**：`free -h` + `ps aux | grep java`
6. **构建日志**：`cat build_xxx.log`
7. **GitHub API**：`curl -s -H "Authorization: token $TOKEN" ...`

---

> **文档结束**。核心思路就一句话：**解包 → 排查硬编码 → 改包名和应用名 → 重打包（利用增量缓存）→ 签名 → 上传**。最容易踩的坑是 OOM（用增量缓存解决）和签名参数（加 --allowResign）。照着本文档从上到下做，一定能成功。
