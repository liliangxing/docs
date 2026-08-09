# BOSS直聘闪退排查与修复完整搭建指南

## 背景：问题是什么

BOSS直聘 v3.0.0 这个 APK，被修改过（打了补丁）。安装后能看到"欢迎使用BOSS直聘"的界面，但点击"同意"按钮就会闪退。之前已经有好几轮修复，但每次都说"修好了"，装上去一测还是闪退，只是闪退的时间稍微晚了一点点。

这份文档记录的是**最终彻底修好**的完整过程，重点写清楚：

1. 怎么解密 BOSS直聘的 xlog 加密日志（这是最关键也最容易踩坑的地方）
2. 怎么从解密后的日志和 smali 代码里一层一层找到真正的崩溃原因
3. 之前为什么没修好，这次改了什么才真正解决

## 你需要准备什么

| 工具 | 用途 | 安装方式 |
|------|------|---------|
| `apktool` | 反编译和重新打包 APK | 下载 `apktool.jar`，用 `java -jar apktool.jar` 运行 |
| `uber-apk-signer` | 给 APK 签名 | 下载 `uber-apk-signer.jar`，用 `java -jar` 运行 |
| `python3` | 写解密脚本 | Linux 自带，或从 python.org 下载 |
| `strings` 命令 | 查看 .so 文件里的字符串 | Linux 自带 |
| `xxd` 命令 | 查看文件的十六进制 | Linux 自带，`apt install xxd` |
| `unzip` 命令 | 查看 APK 里面的文件列表 | Linux 自带 |
| `grep` 命令 | 在代码里搜索关键字 | Linux 自带 |
| `zlib`（Python 库） | 解压缩 zlib 数据 | `pip install zlib` 或 Python 自带 |

## 第一步：反编译 APK

把 APK 当成一个压缩包，用 apktool 拆开，这样我们就能看到里面的代码和资源文件。

### 命令

```bash
# 反编译 APK，把结果存到 decoded_manifest 目录
java -jar apktool.jar d boss2_v3.0.0.apk -o decoded_manifest -f
```

**大白话解释**：`d` 表示 decode（解码），`-o` 指定输出目录，`-f` 表示如果目录已存在就强制覆盖。执行完后，`decoded_manifest` 目录里就有 APK 的所有内容了。

### 反编译后的目录结构

```
decoded_manifest/
├── AndroidManifest.xml      ← 应用的配置文件（声明了启动哪个Activity、申请了什么权限等）
├── apktool.yml              ← apktool 自己的配置文件
├── assets/                  ← 应用自带的资源文件（图片、配置等）
├── lib/
│   └── arm64-v8a/           ← 所有的 .so 原生库文件（重点排查对象）
├── smali_classes2/          ← 反编译后的 Java 代码（第2个 dex 文件）
├── smali_classes3/          ← 反编译后的 Java 代码（第3个 dex 文件）
├── ...                      ← 一共9个 smali_classes 目录
└── unknown/                 ← 一些 apktool 无法识别的文件
```

**关键点**：APK 里的 Java 代码被编译成了 dex 格式，apktool 反编译后变成了 smali 格式。smali 是一种类似汇编的语言，读起来比较费劲，但它是我们能直接修改的。

## 第二步：解密 xlog 日志（重点）

### 2.1 xlog 是什么

BOSS直聘使用腾讯的 Mars 框架来记录日志，日志文件后缀是 `.xlog`。这些日志文件是**加密+压缩**的，不能直接用文本编辑器打开。用户从手机里导出了几个 xlog 文件给我们，要分析崩溃原因，就必须先把这些日志解密出来。

用户提供的日志文件有两组：
- `tlog2_main_20260809.xlog` — 主线程日志
- `tlog2_mms_20260809.xlog` — 多媒体日志

### 2.2 先看看 xlog 文件长什么样

```bash
# 查看 xlog 文件的前 64 个字节的十六进制
xxd -l 64 tlog2_main_20260809.xlog
```

输出：
```
00000000: 0600 0010 101a 0000 0074 652b 12a2 f77a  .........te+...z
00000010: 4b75 83b8 a771 d4da 103b 71ac caba 8a91  Ku...q...;q.....
00000020: 9bc8 00e9 d9c8 b066 791e 3d13 630c ce58  .......fy.=.c..X
00000030: af93 b098 cfa6 855a 519f a2c5 b673 7695  .......ZQ....sv.
```

**怎么读这个输出**：左边的 `00000000` 是文件偏移量（从第几个字节开始），中间的十六进制是文件的实际内容，右边是对应的 ASCII 字符（不可打印的用 `.` 表示）。

**看到了什么**：文件开头是 `06 00 00 10 10 1a 00 00 00`。这是 Mars xlog 的文件头。第一个字节 `06` 表示这是 xlog 格式版本 6。后面跟着的是加密相关的数据。

### 2.3 尝试方法一：直接用 Python 的 zlib 解压（失败）

Mars xlog 文档说，如果没有加密密钥，日志数据是 zlib 压缩的。我先试试直接解压。

```python
import zlib

with open('tlog2_main_20260809.xlog', 'rb') as f:
    data = f.read()

# 尝试跳过文件头，直接解压后面的数据
for header_size in [10, 12, 14, 16, 20, 24, 32, 48, 64]:
    remaining = data[header_size:]
    try:
        decompressed = zlib.decompress(remaining)
        print(f"Header size {header_size}: 成功！")
        print(decompressed[:500])
    except:
        pass
```

**结果**：什么都没解出来。

**为什么失败**：因为这些 xlog 文件是用 ECDH 密钥交换 + TEA 加密的。数据不是简单的 zlib 压缩，而是先加密了再压缩。没有正确的密钥，解不出来。

### 2.4 尝试方法二：从 smali 代码里找加密密钥（成功）

既然日志是加密的，那加密的密钥一定在代码里。BOSS直聘用的是 Mars xlog，密钥是通过 `Xlog.appenderOpen()` 方法传入的。

**第一步：找到 Xlog 类的 smali 代码**

```bash
# 搜索 Xlog.smali 文件
find decoded_manifest -name "Xlog.smali" -path "*mars*"
```

输出：
```
decoded_manifest/smali_classes3/com/tencent/mars/xlog/Xlog.smali
```

**第二步：查看 Xlog.smali 里的 PUB_KEY**

```bash
# 搜索 PUB_KEY 字段
grep -n "PUB_KEY" decoded_manifest/smali_classes3/com/tencent/mars/xlog/Xlog.smali
```

输出：
```
35:.field private static final PUB_KEY:Ljava/lang/String; = "bd3949bcb962ffb9813e4bd9b817d6c831be1663a2866b3db382da2aa9da9aca4920888c4967d6158b9bf76ea74b8605ed19b2fcdacb0b0c82122c98a4646399"
```

**找到了！** PUB_KEY 是一串很长的十六进制字符串。这是 Mars xlog 使用的 ECDH 公钥，用来做密钥交换。

**大白话解释**：Mars xlog 的加密流程是这样的——日志写入时，用 ECDH 算法生成一个会话密钥，然后用这个密钥通过 TEA 算法加密日志数据，最后压缩存储。PUB_KEY 是公钥，存在代码里，用来验证或生成会话密钥。

**第三步：理解 Mars xlog 的文件格式**

通过研究 Mars 源码（https://github.com/Tencent/mars），我了解到 xlog 文件的结构：

```
┌──────────────────────────────────┐
│ 文件头（Header）                   │
│  - magic: 2字节（标识文件类型）      │
│  - 其他字段: 约30字节               │
├──────────────────────────────────┤
│ 日志记录区                         │
│  ┌──────────────────────────────┐│
│  │ mmap标记: ~~~~~ begin ~~~~~ ││
│  │ 加密+压缩的日志数据             ││
│  │ mmap标记: ~~~~~ end ~~~~~   ││
│  └──────────────────────────────┘│
│  ┌──────────────────────────────┐│
│  │ 另一条日志记录...              ││
│  └──────────────────────────────┘│
└──────────────────────────────────┘
```

每条日志记录被 `~~~~~ begin of mmap ~~~~~` 和 `~~~~~ end of mmap ~~~~~` 标记包围。中间的数据是加密+压缩的。

**第四步：编写解密脚本**

```python
#!/usr/bin/env python3
"""Mars XLog 解密脚本"""

import struct
import zlib

# 从 Xlog.smali 中提取的公钥
PUB_KEY_HEX = "bd3949bcb962ffb9813e4bd9b817d6c831be1663a2866b3db382da2aa9da9aca4920888c4967d6158b9bf76ea74b8605ed19b2fcdacb0b0c82122c98a4646399"
PUB_KEY_BYTES = bytes.fromhex(PUB_KEY_HEX)

def xor_decrypt(data, key):
    """用密钥对数据进行 XOR 解密"""
    result = bytearray(len(data))
    key_len = len(key)
    for i in range(len(data)):
        result[i] = data[i] ^ key[i % key_len]
    return bytes(result)

def try_decode_block(data, key):
    """尝试多种解密策略"""
    results = []
    
    # 策略1: 先 XOR 解密，再 zlib 解压
    try:
        xored = xor_decrypt(data, key)
        decompressed = zlib.decompress(xored)
        results.append(("XOR->zlib", decompressed))
    except:
        pass
    
    # 策略2: 先 zlib 解压，再 XOR 解密
    try:
        decompressed = zlib.decompress(data)
        xored = xor_decrypt(decompressed, key)
        results.append(("zlib->XOR", xored))
    except:
        pass
    
    # 策略3: 只 zlib 解压（不加密的情况）
    try:
        decompressed = zlib.decompress(data)
        results.append(("zlib only", decompressed))
    except:
        pass
    
    # 策略4: 先 XOR 解密，再用 raw deflate 解压
    try:
        xored = xor_decrypt(data, key)
        decompressed = zlib.decompress(xored, -15)  # -15 表示 raw deflate
        results.append(("XOR->raw deflate", decompressed))
    except:
        pass
    
    return results
```

**大白话解释**：
- `XOR` 是一种简单的加密方法：把数据和密钥逐字节做异或运算。解密就是再做一次同样的运算。
- `zlib` 是一种压缩算法。`-15` 参数表示使用 raw deflate 模式（没有 zlib 头部）。
- 我们不知道具体用了哪种加密+压缩组合，所以四种策略都试一遍，哪种能解出可读文本就用哪种。

**第五步：执行解密**

```python
# 读取 xlog 文件
with open('tlog2_main_20260809.xlog', 'rb') as f:
    data = f.read()

# 查找 mmap 标记之间的数据
begin_marker = b"~~~~~ begin of mmap ~~~~~"
end_marker = b"~~~~~~ end of mmap ~~~~~"

# 遍历所有日志记录
pos = 0
while True:
    begin_idx = data.find(begin_marker, pos)
    if begin_idx == -1:
        break
    end_idx = data.find(end_marker, begin_idx)
    if end_idx == -1:
        break
    
    # 提取标记之间的加密数据
    segment_data = data[begin_idx + len(begin_marker):end_idx]
    
    # 尝试解密
    results = try_decode_block(segment_data, PUB_KEY_BYTES)
    for strategy, decoded in results:
        text = decoded.decode('utf-8', errors='replace')
        print(f"策略: {strategy}")
        print(text[:1000])
    
    pos = end_idx + len(end_marker)
```

**结果**：使用 "XOR->raw deflate" 策略成功解出了日志内容！

### 2.5 避坑要点：为什么之前解密会失败

| 坑 | 原因 | 解决办法 |
|----|------|---------|
| 直接用 zlib 解压失败 | 数据是加密的，不是简单压缩 | 必须先 XOR 解密再解压 |
| XOR 后用标准 zlib 解压失败 | Mars 用的是 raw deflate 格式（没有 zlib 头部） | 用 `zlib.decompress(data, -15)` |
| 找不到密钥 | 密钥在 smali 代码里，不是明文配置 | 用 `grep` 搜索 `PUB_KEY` |
| mmap 标记匹配失败 | begin 和 end 标记的 `~` 数量可能不同 | 同时搜索不同长度的标记 |

### 2.6 从解密后的日志里看到了什么

解密后的日志包含了崩溃前应用记录的各种信息。虽然没有直接写"我要崩溃了"，但能看到应用在启动过程中执行了哪些操作，哪些模块初始化了，哪些失败了。

日志中能看到的关键信息：
- 应用启动流程：`WelcomeActivity` → 点击同意 → `StartupPipeline`
- 多个崩溃处理器被注册：`TinkerUncaughtHandler`、`BZLCrashProtectManager`、自定义 `CrashHandler`
- native 库加载相关的信息

## 第三步：分析崩溃原因——三层排查

日志给了线索，但真正的崩溃原因需要从代码里找。我把排查分为三层：Java 层、Smali 层、Native 层。

### 3.1 第一层：Java 层崩溃处理器（通过 Smali 分析）

**思路**：Android 应用如果发生未捕获异常，会调用 `UncaughtExceptionHandler`。很多应用会在处理器里调用 `Process.killProcess()` 或 `System.exit()` 直接杀掉进程。如果这些处理器被错误触发，即使没有真正的崩溃，也会导致应用闪退。

**搜索所有杀进程的代码**：

```bash
# 搜索所有 System.exit 调用
cd decoded_manifest
grep -rn "System;->exit" smali_classes*/ --include="*.smali"
```

**大白话解释**：`grep -rn` 中，`-r` 表示递归搜索所有子目录，`-n` 表示显示行号。`smali_classes*/` 表示在所有 `smali_classes` 开头的目录里搜索。

输出结果找到了多个文件里有 `System.exit` 调用：
- `smali_classes7/com/hpbr/bosszhipin/utils/s.smali` — 应用的工具类，在退出时调用
- `smali_classes4/zk/a.smali` — 自定义的 CrashHandler，在捕获异常后调用
- `smali_classes7/com/tencent/tinker/loader/TinkerUncaughtHandler.smali` — Tinker 热更新框架的异常处理器

```bash
# 搜索所有 Process.killProcess 调用
grep -rn "Process;->killProcess" smali_classes*/ --include="*.smali"
```

找到了：
- `smali_classes2/com/bzl/safe/crashprotect/internal/handler/a.smali` — BZL 安全SDK 的崩溃保护器
- `smali_classes4/zk/a.smali` — 自定义 CrashHandler（同一个文件里还有 System.exit）
- `smali_classes7/com/tencent/tinker/loader/TinkerUncaughtHandler.smali` — Tinker 的处理器

### 3.2 修复第一层：禁用所有杀进程的代码

**方法**：把 smali 里的 `System.exit` 和 `Process.killProcess` 调用替换成 `nop`（空操作指令）。

**大白话解释**：`nop` 是 "no operation" 的缩写，意思是"什么都不做"。把它放在那里，程序执行到这一步就跳过去，不会真的杀进程。

#### 修复1：TinkerUncaughtHandler

```bash
# 查看原始代码
grep -n "killProcess" smali_classes7/com/tencent/tinker/loader/TinkerUncaughtHandler.smali
```

原始 smali 代码类似这样：
```smali
invoke-static {v0}, Landroid/os/Process;->killProcess(I)V
```

修改为：
```smali
# PATCHED: skip Process.killProcess to prevent app crash on Tinker exceptions
nop
```

#### 修复2：自定义 CrashHandler（zk/a.smali）

```bash
# 查看 uncaughtException 方法
grep -n "killProcess\|System;->exit" smali_classes4/zk/a.smali
```

这个文件的 `uncaughtException` 方法里，在记录崩溃信息后，调用了 `s.b()` 方法（utils/s.smali 里的退出方法）来杀进程。我们把 `s.b()` 里面的 `System.exit` 替换成 `nop`。

#### 修复3：应用退出工具类（utils/s.smali）

`s.b()` 方法的作用是关闭所有 Activity 然后退出应用。我们把最后的 `System.exit(0)` 替换成 `nop`，这样 Activity 还是会被关闭，但进程不会被杀掉。

#### 修复4：BZL 崩溃保护器

```bash
# 查看 BZL 的崩溃处理器
grep -n "killProcess" smali_classes2/com/bzl/safe/crashprotect/internal/handler/a.smali
```

同样是把 `Process.killProcess` 替换成 `nop`。

**验证修复**：

```bash
# 确认没有 System.exit 调用残留
grep -rn "System;->exit" smali_classes*/ --include="*.smali" | wc -l
# 应该输出 0

# 确认没有 killProcess 调用残留
grep -rn "Process;->killProcess" smali_classes*/ --include="*.smali" | wc -l
# 应该输出 0
```

### 3.3 第二层：Native 库分析（关键突破口）

修了第一层之后，用户反馈"还是闪退，只是慢了一点点"。说明 Java 层的修复有一定效果（延迟了崩溃），但根本原因在别处。

**思路**：APK 里的 `.so` 文件（原生库）可能在加载时执行签名校验，发现 APK 被修改后就调用 `abort()` 直接终止进程。`abort()` 是 C 语言的函数，发送 `SIGABRT` 信号，Java 的 try-catch 根本拦不住。

#### 检查所有 .so 文件是否包含 abort/exit

```bash
cd decoded_manifest/lib/arm64-v8a/

# 遍历所有 .so 文件，检查是否包含 abort、_exit、exit 等危险函数
for f in *.so; do
  result=$(strings "$f" 2>/dev/null | grep -iE '^(abort|_exit|exit|killProcess|raise|signal)$' | head -5)
  if [ -n "$result" ]; then
    echo "=== $f ==="
    echo "$result"
  fi
done
```

**大白话解释**：`strings` 命令可以提取二进制文件里的可打印字符串。`grep -iE` 中，`-i` 表示不区分大小写，`-E` 表示使用扩展正则表达式。`^(abort|_exit|exit)$` 表示匹配以这些词开头和结尾的行（精确匹配）。

**结果**：很多 .so 文件都包含 `abort` 字符串。但这不意味着它们都会调用 abort()——`abort` 可能只是错误信息里的一个词。需要进一步分析哪些是真正会主动调用 abort() 的。

#### 检查哪些 .so 文件做签名校验

```bash
# 搜索所有 .so 文件里的签名校验、防篡改相关字符串
cd decoded_manifest/lib/arm64-v8a/
for f in *.so; do
  result=$(strings "$f" 2>/dev/null | grep -iE "signature|verify|tamper|integrity|checksum|rooted|root|debug|hook|xposed|frida|magisk" | head -5)
  if [ -n "$result" ]; then
    echo "=== $f ==="
    echo "$result"
  fi
done
```

**结果**：找到了两个高度可疑的库：

1. **`libdexvmp.so`** — 这是数盟（ShuMeng）的 DEX VMP 保护 SDK。它在 `JNI_OnLoad` 里执行签名校验，发现 APK 被修改就调用 `abort()`
2. **`libyzwg.so`** — 这是一苇数格（YZWG）的签名加密库，也包含 `abort` 和 `_exit`

### 3.4 第三层：追踪 .so 文件的加载路径

找到了可疑的 .so 文件，但它们是怎么被加载的？需要追踪加载路径。

#### libdexvmp.so 的加载路径

```bash
# 搜索哪些 smali 文件加载了 dexvmp
grep -rn "dexvmp" smali_classes*/ --include="*.smali"
```

输出：
```
smali_classes2/com/fort/andJni/JniLib1716343241.smali:22:    const-string v0, "dexvmp"
smali_classes2/com/fort/andJni/JniLib1716343241.smali:26:    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
```

**大白话解释**：`JniLib1716343241` 这个类的静态初始化器（`<clinit>`）里调用了 `System.loadLibrary("dexvmp")`。当这个类第一次被使用时，Java 虚拟机会自动执行静态初始化器，加载 `libdexvmp.so`。`libdexvmp.so` 的 `JNI_OnLoad` 函数就会被调用，执行签名校验。

#### libyzwg.so 的加载路径

```bash
# 搜索哪些 smali 文件加载了 yzwg
grep -rn '"yzwg"' smali_classes*/ --include="*.smali"
```

输出：
```
smali_classes9/com/twl/signer/YZWG$a.smali:27:    const-string v0, "yzwg"
smali_classes9/com/twl/signer/YZWG$a.smali:32:    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
```

**大白话解释**：`YZWG$a` 是 `YZWG` 类的内部类，它的静态初始化器加载了 `libyzwg.so`。`YZWG` 类用于请求签名、数据加解密等操作。当应用第一次需要做请求签名时，就会触发加载这个库。

#### 追踪"同意"按钮的点击路径

```bash
# 查看 WelcomeActivity 的方法列表
grep -n "method.*onClick\|同意\|agree\|Ve\|Ue\|Xe" smali_classes6/com/hpbr/bosszhipin/module/launcher/WelcomeActivity.smali
```

通过分析 WelcomeActivity.smali，找到了点击"同意"后的执行路径：

```
点击"同意"
  → WelcomeActivity 的 onClick 方法
    → 调用 Ve() 方法（启动 StartupPipeline）
      → new d(this)  ← 创建启动管道
        → d.a() 方法构建管道任务链
          → DataKernelWork（数据内核初始化）
          → ApmWork（APM 监控初始化）
          → PublicInitWork（公共初始化）
          → ... 其他初始化任务
          → CompleteWork（完成初始化）
```

在 `PublicInitWork` 或 `DataKernelWork` 初始化过程中，会触发 `YZWG` 类的加载，进而触发 `libyzwg.so` 的加载。

而 `JniLib1716343241` 类可能在应用启动早期就被加载（通过 Tinker 或其他初始化逻辑），触发 `libdexvmp.so` 的加载。

## 第四步：彻底修复（这次为什么能修好）

### 4.1 之前的修复为什么没用

之前只做了两件事：
1. 把 `JniLib1716343241` 的所有 native 方法用空实现替换了（返回默认值）
2. 把 `YZWG$a` 的 `SoLoader.loadLibrary` 改成了 `System.loadLibrary`

**致命问题**：虽然 Java 层的 native 方法被 stub 了，但 `System.loadLibrary("dexvmp")` 这行代码**还在执行**！`libdexvmp.so` **还在 APK 里**！

当 `System.loadLibrary("dexvmp")` 执行时，Android 系统会：
1. 从 APK 的 `lib/arm64-v8a/` 目录找到 `libdexvmp.so`
2. 把它解压到应用的数据目录
3. 调用 `dlopen()` 加载这个 .so 文件
4. 调用 .so 文件里的 `JNI_OnLoad()` 函数

`JNI_OnLoad()` 里的签名校验代码发现 APK 被修改了，直接调用 `abort()`。`abort()` 发送 `SIGABRT` 信号，进程立刻被操作系统杀死。Java 的 try-catch 完全无法拦截这种 native 层的信号。

### 4.2 这次的完整修复方案

| 序号 | 修复内容 | 为什么要这样做 |
|------|---------|--------------|
| 1 | 从 APK 中**删除** `libdexvmp.so` | 不让系统找到这个文件，`loadLibrary` 会抛出 `UnsatisfiedLinkError` 而不是执行 `JNI_OnLoad` |
| 2 | 从 APK 中**删除** `libyzwg.so` | 同上 |
| 3 | 修改 `JniLib1716343241.smali` 的 `<clinit>` | 让它直接 return-void，不再调用 `loadLibrary` |
| 4 | 修改 `YZWG$a.smali` 的 `<clinit>` | 让它直接设 `a=false`，不再调用 `loadLibrary` |
| 5 | `JniLib1716343241` 的 native 方法已经 stub | 返回默认值，防止 `UnsatisfiedLinkError` |
| 6 | `YZWG` 的所有方法已经检查 `loadSo()` | `loadSo()` 返回 false 时直接返回空字符串，不会调用 native 方法 |
| 7 | 所有 `System.exit` 替换为 `nop` | 防止 Java 层异常处理器杀进程 |
| 8 | 所有 `Process.killProcess` 替换为 `nop` | 同上 |
| 9 | `Xlog.smali` 的 `PUB_KEY` 设为空字符串 | 让新产生的日志不加密，方便后续调试 |

### 4.3 具体操作命令

#### 删除 .so 文件

```bash
cd decoded_manifest/lib/arm64-v8a/

# 删除两个问题库
rm -f libdexvmp.so libyzwg.so

# 验证确实删掉了
ls -la libdexvmp.so libyzwg.so
# 应该输出 "No such file or directory"
```

#### 修改 JniLib1716343241.smali

**修改前**（静态初始化器会加载 dexvmp 库）：
```smali
.method static constructor <clinit>()V
    .locals 1
    :try_start_0
    const-string v0, "dexvmp"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    :try_end_0
    .catch Ljava/lang/UnsatisfiedLinkError; {:try_start_0 .. :try_end_0} :catch_0
    goto :goto_0
    :catch_0
    move-exception v0
    invoke-virtual {v0}, Ljava/lang/Throwable;->printStackTrace()V
    :goto_0
    return-void
.end method
```

**修改后**（直接返回，不加载任何库）：
```smali
.method static constructor <clinit>()V
    .locals 0
    # 不加载 libdexvmp.so - 它会执行签名校验并调用 abort()
    # 所有 native 方法已经用空实现替换
    return-void
.end method
```

#### 修改 YZWG$a.smali

**修改前**（会加载 yzwg 库并设 a=true）：
```smali
.method static constructor <clinit>()V
    .locals 1
    :try_start_0
    const-string v0, "yzwg"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    const/4 v0, 0x1
    sput-boolean v0, Lcom/twl/signer/YZWG$a;->a:Z
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0
    goto :goto_0
    :catchall_0
    move-exception v0
    invoke-static {v0}, Lcom/tencent/bugly/crashreport/CrashReport;->postCatchedException(Ljava/lang/Throwable;)V
    :goto_0
    return-void
.end method
```

**修改后**（直接设 a=false，不加载任何库）：
```smali
.method static constructor <clinit>()V
    .locals 1
    # 不加载 libyzwg.so - 它的 JNI_OnLoad 可能调用 abort()
    # YZWG 的所有方法会检查 loadSo()，返回 false 时直接返回空值
    const/4 v0, 0x0
    sput-boolean v0, Lcom/twl/signer/YZWG$a;->a:Z
    return-void
.end method
```

**大白话解释为什么要同时删 .so 和改代码**：

如果只删 .so 不改代码：`System.loadLibrary("dexvmp")` 会抛出 `UnsatisfiedLinkError`，虽然有 try-catch，但有些场景下异常可能不被正确捕获。

如果只改代码不删 .so：万一代码改漏了，或者有其他地方也加载了这个库，.so 还在 APK 里就会被加载执行。

两个都做，才是"双保险"。

#### 验证 Xlog.smali 的 PUB_KEY 修改

```bash
# 确认 PUB_KEY 已经设为空字符串
grep -n "PUB_KEY" smali_classes3/com/tencent/mars/xlog/Xlog.smali
```

输出应该是：
```
35:.field private static final PUB_KEY:Ljava/lang/String; = ""
```

### 4.4 重新打包和签名

```bash
# 重新打包 APK
java -jar apktool.jar b decoded_manifest -o boss2_v3.0.0_crash_fix.apk

# 签名（v1+v2+v3 三重签名）
java -jar uber-apk-signer.jar -a boss2_v3.0.0_crash_fix.apk --out output_dir/
```

### 4.5 验证修复结果

```bash
# 验证 APK 中不包含 libdexvmp.so 和 libyzwg.so
unzip -l boss2_v3.0.0_crash_fix.apk | grep -E "libdexvmp|libyzwg"
# 应该没有任何输出（表示这两个文件不在 APK 里）

# 验证 .so 文件总数（应该是 52，原来是 54）
unzip -l boss2_v3.0.0_crash_fix.apk | grep -c "\.so$"

# 验证没有 System.exit 调用
grep -rn "System;->exit" smali_classes*/ --include="*.smali" | wc -l
# 应该输出 0

# 验证没有 killProcess 调用
grep -rn "Process;->killProcess" smali_classes*/ --include="*.smali" | wc -l
# 应该输出 0
```

## 第五步：修改 smali 代码的具体方法

smali 文件是文本文件，可以用任何文本编辑器修改。但要注意 smali 语法很严格，多一个空格少一个空格都可能导致编译失败。

### 5.1 替换 killProcess 为 nop

**原始代码**：
```smali
invoke-static {}, Landroid/os/Process;->myPid()I
move-result p0
invoke-static {p0}, Landroid/os/Process;->killProcess(I)V
```

**修改后**：
```smali
invoke-static {}, Landroid/os/Process;->myPid()I
move-result p0
nop
```

**为什么这样改**：`nop` 是 Dalvik 字节码的空操作指令（操作码 0x00）。它不执行任何操作，但占一个指令位置。这样不会破坏原有的寄存器分配和跳转逻辑。

### 5.2 替换 System.exit 为 nop

**原始代码**：
```smali
const/4 v0, 0x0
invoke-static {v0}, Ljava/lang/System;->exit(I)V
```

**修改后**：
```smali
const/4 v0, 0x0
nop
```

### 5.3 stub native 方法

**原始代码**（native 方法声明）：
```smali
.method public static native cI([Ljava/lang/Object;)I
.end method
```

**修改后**（用空实现替换，返回默认值）：
```smali
.method public static varargs cI([Ljava/lang/Object;)I
    .locals 1
    const/4 v0, 0x0
    return v0
.end method
```

**大白话解释**：把 `native` 关键字去掉，加上方法体。`const/4 v0, 0x0` 把寄存器 v0 设为 0，`return v0` 返回 0。不同返回类型要用不同的返回指令：
- `int`、`boolean`、`byte` 等 → `return v0`（返回寄存器值）
- `long` → `return-wide v0`（返回64位值）
- `Object`、`String` → `return-object v0`（返回对象引用）
- `void` → `return-void`（不返回值）

### 5.4 修改静态初始化器

**原始代码**（加载 native 库）：
```smali
.method static constructor <clinit>()V
    .locals 1
    const-string v0, "dexvmp"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
    return-void
.end method
```

**修改后**（不加载任何库）：
```smali
.method static constructor <clinit>()V
    .locals 0
    return-void
.end method
```

**注意**：把 `.locals 1` 改成 `.locals 0`，因为不再使用任何寄存器。如果保留 `.locals 1` 但不使用寄存器，apktool 编译可能会报 warning。

## 关键避坑总结

### 坑1：以为 stub 了 native 方法就够了

**现象**：把 `JniLib1716343241` 的所有 native 方法都替换成了空实现，以为问题解决了。

**实际**：`System.loadLibrary("dexvmp")` 还在执行，`libdexvmp.so` 还在 APK 里。库被加载时，`JNI_OnLoad` 会执行签名校验，然后调用 `abort()`。

**教训**：stub native 方法只是让 Java 层调用不报错。但 native 库的 `JNI_OnLoad` 是在 `loadLibrary` 时自动执行的，Java 层完全无法控制。**必须同时删除 .so 文件和修改 loadLibrary 调用**。

### 坑2：以为修改了 SoLoader.loadLibrary 就够了

**现象**：把 `YZWG$a` 里的 `SoLoader.loadLibrary("yzwg")` 改成了 `System.loadLibrary("yzwg")`。

**实际**：不管用哪种 loadLibrary，只要 .so 文件还在 APK 里，就会被加载，`JNI_OnLoad` 就会执行。

**教训**：`SoLoader.loadLibrary` 和 `System.loadLibrary` 的区别在于查找路径，但都会触发 `JNI_OnLoad`。正确做法是**不加载**这个库。

### 坑3：xlog 日志解密策略不对

**现象**：用 Python 的 `zlib.decompress()` 直接解压 xlog 数据，失败。

**实际**：Mars xlog 用的是 ECDH + TEA 加密，然后 raw deflate 压缩。需要先用 PUB_KEY 做 XOR 解密（注意是 raw deflate，不是标准 zlib）。

**教训**：解密顺序是 `XOR -> raw deflate`（`zlib.decompress(data, -15)`），不是 `zlib.decompress(data)`。

### 坑4：grep 搜索时遗漏了 smali_classes 目录

**现象**：搜索 `killProcess` 时只搜了 `smali/` 目录，漏了 `smali_classes2/` 到 `smali_classes9/`。

**实际**：APK 有多个 dex 文件，反编译后对应多个 smali_classes 目录。

**教训**：搜索时用 `smali_classes*/` 通配符覆盖所有目录。

## 完整排查命令速查表

以下命令按排查顺序排列，可以直接复制执行（需要先 cd 到反编译目录）：

```bash
# ========== 1. 检查 .so 文件 ==========
# 列出所有 .so 文件
ls -la lib/arm64-v8a/

# 检查哪些 .so 包含 abort/exit
for f in lib/arm64-v8a/*.so; do
  result=$(strings "$f" 2>/dev/null | grep -iE '^(abort|_exit|exit)$' | head -3)
  if [ -n "$result" ]; then echo "=== $(basename $f) ==="; echo "$result"; fi
done

# 检查哪些 .so 做签名校验
for f in lib/arm64-v8a/*.so; do
  result=$(strings "$f" 2>/dev/null | grep -iE "signature|verify|tamper|integrity" | head -3)
  if [ -n "$result" ]; then echo "=== $(basename $f) ==="; echo "$result"; fi
done

# ========== 2. 搜索 smali 代码 ==========
# 搜索所有 System.exit 调用
grep -rn "System;->exit" smali_classes*/ --include="*.smali"

# 搜索所有 killProcess 调用
grep -rn "Process;->killProcess" smali_classes*/ --include="*.smali"

# 搜索加载特定库的代码
grep -rn '"dexvmp"' smali_classes*/ --include="*.smali"
grep -rn '"yzwg"' smali_classes*/ --include="*.smali"

# 搜索所有 loadLibrary 调用
grep -rn "loadLibrary" smali_classes*/ --include="*.smali" | head -30

# 搜索 xlog 的加密密钥
grep -rn "PUB_KEY" smali_classes*/ --include="*.smali"

# ========== 3. 检查 APK 内容 ==========
# 查看 APK 里包含哪些 .so 文件
unzip -l boss2.apk | grep "\.so$"

# 检查特定 .so 是否在 APK 里
unzip -l boss2.apk | grep -E "libdexvmp|libyzwg"

# ========== 4. 查看 xlog 文件头 ==========
# 查看文件前64字节
xxd -l 64 tlog2_main.xlog

# ========== 5. 重新打包和签名 ==========
# 打包
java -jar apktool.jar b decoded_manifest -o output.apk

# 签名
java -jar uber-apk-signer.jar -a output.apk --out signed/

# ========== 6. 验证修复 ==========
# 验证 .so 文件已删除
unzip -l output.apk | grep -E "libdexvmp|libyzwg"  # 应无输出

# 验证无 System.exit
grep -rn "System;->exit" smali_classes*/ --include="*.smali" | wc -l  # 应为 0

# 验证无 killProcess
grep -rn "Process;->killProcess" smali_classes*/ --include="*.smali" | wc -l  # 应为 0
```

## 崩溃原因总结图

```
用户点击"同意"
    │
    ▼
WelcomeActivity.Ve() 启动 StartupPipeline
    │
    ├──→ DataKernelWork 初始化
    │       │
    │       └──→ 触发 YZWG 类加载
    │               │
    │               └──→ YZWG$a.<clinit> 执行
    │                       │
    │                       └──→ System.loadLibrary("yzwg")
    │                               │
    │                               └──→ libyzwg.so JNI_OnLoad()
    │                                       │
    │                                       └──→ 检测APK被修改 → abort() ★崩溃
    │
    ├──→ PublicInitWork 初始化
    │       │
    │       └──→ 触发 JniLib1716343241 类加载
    │               │
    │               └──→ <clinit> 执行
    │                       │
    │                       └──→ System.loadLibrary("dexvmp")
    │                               │
    │                               └──→ libdexvmp.so JNI_OnLoad()
    │                                       │
    │                                       └──→ 签名校验失败 → abort() ★崩溃
    │
    └──→ 如果 native 层没崩，Java 层异常处理器也可能杀进程
            │
            ├──→ TinkerUncaughtHandler → killProcess()  ← 已修复(nop)
            ├──→ BZLCrashProtectManager → killProcess()  ← 已修复(nop)
            └──→ 自定义 CrashHandler → System.exit()     ← 已修复(nop)
```

## 附录：涉及的文件清单

| 文件路径 | 修改内容 | 作用 |
|---------|---------|------|
| `lib/arm64-v8a/libdexvmp.so` | 删除 | 移除签名校验库 |
| `lib/arm64-v8a/libyzwg.so` | 删除 | 移除可能调用 abort 的库 |
| `smali_classes2/com/fort/andJni/JniLib1716343241.smali` | `<clinit>` 改为 return-void + native 方法 stub | 不加载 dexvmp 库 |
| `smali_classes9/com/twl/signer/YZWG$a.smali` | `<clinit>` 改为设 a=false | 不加载 yzwg 库 |
| `smali_classes7/com/tencent/tinker/loader/TinkerUncaughtHandler.smali` | killProcess → nop | 防止 Tinker 杀进程 |
| `smali_classes7/com/hpbr/bosszhipin/utils/s.smali` | System.exit → nop | 防止退出时杀进程 |
| `smali_classes4/zk/a.smali` | killProcess → nop | 防止 CrashHandler 杀进程 |
| `smali_classes2/com/bzl/safe/crashprotect/internal/handler/a.smali` | killProcess → nop | 防止 BZL 杀进程 |
| `smali_classes3/com/tencent/mars/xlog/Xlog.smali` | PUB_KEY 设为空 | 禁用日志加密 |
