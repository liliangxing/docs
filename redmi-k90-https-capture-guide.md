# 红米K90 利用 Shizuku + HttpCanary + MT管理器 实现 HTTPS 全量抓包指南

> 免Root · Android 抓包实战
>
> 设备：红米K90 ｜ 系统：Android 16 / HyperOS 3 ｜ Shizuku 13.6.0 ｜ HttpCanary 3.3.5 ｜ MT管理器 2.26.7

在未 Root 的红米K90（Android 16 / HyperOS 3）上，用三款软件协作，把绝大多数 App 的 HTTPS 流量解密成可直观查看的明文请求与响应。

---

## 一句话结论：能不能做到？

能——但要看 App 的"防护等级"。**未做证书固定（SSL Pinning）的 App**，配合 MT管理器改包后可以完整解密、直观查看明文；**做了 Pinning 的大厂 App（微信、抖音、银行等）**仅靠这三款软件难以突破，需要额外的 LSPatch/Frida。

Shizuku 在这里扮演"免 Root 提权"的角色，HttpCanary 负责中间人解密，MT管理器负责改包让 App 信任抓包证书。

| ✓ 能抓到明文 | ✗ 仅靠这三款难抓 |
|---|---|
| 未做 Pinning 的普通 App、自研/测试 App、部分信任用户证书的 App。改包后请求体、响应体（JSON、图片、表单）在 HttpCanary 里直接可见。 | 做了证书固定（Pinning）的金融、社交大厂 App；带签名校验、改包即闪退的 App；以及开启 VPN 检测会主动断网的 App。 |

---

## 目录

1. 三款软件分工与设备背景
2. 抓包原理速览
3. 阶段一：启动 Shizuku（无线调试）
4. 阶段二：HttpCanary 装证书 + 抓包
5. 阶段三：MT管理器改包信任用户证书
6. 阶段四（进阶）：Shizuku 临时系统证书注入
7. SSL Pinning 绕过与能力边界
8. 能力矩阵：哪些能抓、哪些不能
9. 常见问题排错

---

## 1. 三款软件分工与设备背景

先明确每个工具"干什么活"，这是整套流程能跑通的基础。

### Shizuku 13.6.0.r1086.2650830c —— 免 Root 提权中台

通过无线调试建立 ADB Binder 连接，让普通 App 以 **shell 级特权**调用系统 API，无需 Root、无需解锁 Bootloader。它是 HttpCanary、MT管理器执行提权操作（装系统证书、读写受保护目录）的"通行证"。

### HttpCanary 3.3.5（黄鸟）—— MITM 抓包核心

基于 Android **VpnService** 的中间人抓包引擎，自带 CA 根证书，对 HTTPS 做 MITM 解密；提供 JSON / 图片 / Hex / 预览等可视化视图，请求重发、断点编辑。不需要 Root 即可基本工作。

### MT管理器 2.26.7 —— APK 改包工具

反编译 / 重打包 APK，修改 `AndroidManifest.xml` 与 `network_security_config.xml`，让目标 App 信任用户证书；内置签名功能；其终端可调用 Shizuku 提权读写系统目录。

### 设备背景：红米K90

红米K90 出厂搭载 **Android 16 / Xiaomi HyperOS 3**，处理器为骁龙 8 Elite。这一点对抓包至关重要：从 Android 7.0（API 24）起，系统默认**不再信任用户安装的 CA 证书**；而 Android 14 起，系统 CA 证书的存储目录还从 `/system/etc/security/cacerts/` 迁移到了 `/apex/com.android.conscrypt/cacerts/`。这两个变化正是"现代 Android 抓包难"的根因，也决定了本指南的分阶段策略。

> **关键认知**：未 Root 时，**无法永久把 CA 证书写进系统信任库**。所以本指南的策略是：能改包的 App 用 MT管理器改包信任用户证书；想"全量免改包"则用 Shizuku 做**临时**系统证书注入（重启失效）。这不是工具的缺陷，而是 Android 安全机制使然。

---

## 2. 抓包原理速览

HttpCanary 的本质是一个"中间人（MITM）"：它在手机本地建一个 VPN 隧道，所有 App 的流量都先经过它，再转发给真实服务器。对 HTTPS，它用**自己生成的 CA 根证书**给每个域名现场签发一张"伪证书"来解密——前提是 App 得信任这张 CA。App 不信任，握手就会失败、流量就无法解密。

```
目标 App ──HTTPS 请求──> HttpCanary(VPN+MITM) ──真实 HTTPS 转发──> 真实服务器
                              │
                        用自有 CA 现签伪证书
                        解密 → 明文
                              ▲
                              │ App 校验信任
              HttpCanary CA（用户/系统证书库）
```

因此整条链路的成败归结为一个问题：**怎么让目标 App 信任 HttpCanary 的 CA 证书**。本指南给出三层递进方案：

- **第一层**：把 CA 装成用户证书 → 只对"愿意信任用户证书"的 App 有效（少数）。
- **第二层**：用 MT管理器改包，强制目标 App 信任用户证书 → 对**未做 Pinning**的 App 有效（多数）。
- **第三层**：用 Shizuku 临时把 CA 注入系统信任库 → 免改包，对所有**未做 Pinning**的 App 有效，但重启失效。

### 整体工作流与决策路径

```
① 启动 Shizuku(无线调试配对)
        │
        ▼
② HttpCanary 导出并安装 CA 用户证书
        │
        ├─ 目标App信任用户证书? ── 是/老旧App ──> ✅ 直接抓包查看明文
        │
        └─ 否(现代App)
                │
                ▼
        ③ MT管理器改包 network_security_config
           信任用户证书 → 重签名安装
                │
                ├─ App 有 SSL Pinning? ── 无 ──> ✅ 抓包查看明文
                │
                └─ 有 ──> ④ 需 LSPatch+TrustMeAlready 或 Frida（超出三件套）

   ② ──可选进阶──> ③' Shizuku 临时系统证书注入(免改包) ──> ✅ 抓包查看明文
```

---

## 3. 阶段一：启动 Shizuku（无线调试配对）

Shizuku 是后续提权操作的基础，必须先把它跑起来。K90 上无需连接电脑，用"无线调试"即可。

1. **开启开发者选项**：设置 → 我的设备 → 全部参数与信息 → 连续点击「版本号」7 次，提示"已处于开发者模式"。
2. **开启无线调试**：设置 → 更多设置 → 开发者选项 → 打开「无线调试」。首次开启会弹窗确认，同意即可。
3. **配对 Shizuku**：在「无线调试」页面点击「使用配对码配对设备」，记下显示的**配对码**与端口。打开 Shizuku App →「启动」区域选择「通过无线调试启动」→ 输入配对码 → 配对成功。
4. **启动服务**：回到 Shizuku 首页，状态显示**「运行中」**即成功。后续 HttpCanary、MT管理器在申请提权时会自动调用它。

> **提示**：无线调试启动的 Shizuku 在**手机重启后会断开**，需要重新配对启动一次。HyperOS 的省电策略可能杀后台，建议把 Shizuku 加入「省电策略：无限制」。

---

## 4. 阶段二：HttpCanary 装证书 + 抓包

这一步把 HttpCanary 的 CA 装进**用户证书库**，并启动抓包。对于愿意信任用户证书的 App，到此就能直接看到明文。

1. **授予 VPN 权限**：打开 HttpCanary，首次启动会请求建立 VPN 连接，允许。它靠 VPN 拦截全网流量。
2. **导出 CA 证书**：设置 → SSL 证书设置 → 导出 `HttpCanary.pem` 根证书到本地。
3. **安装为用户证书**：系统设置 → 安全 → 加密与凭据 → 安装证书 → 选择「**CA 证书**」（注意不是"VPN 和应用"层级不够）→ 选中刚导出的 `.pem` 文件。HyperOS 的入口较深，可在设置里直接搜「CA 证书」。
4. **开始抓包**：回到 HttpCanary 主界面，点右下角播放按钮启动抓包。打开任意目标 App 操作，流量会实时流入列表。
5. **直观查看**：点开任意一条记录，切到「请求」「响应」标签，HttpCanary 会按内容类型自动渲染——JSON 折叠树、图片直接显示、表单键值对一一列出，这就是"直观看到数据"的效果。

> **分水岭**：如果某个 App 的 HTTPS 请求显示**证书错误 / 握手失败 / 无网络**，说明它**不信任用户证书**（现代 App 几乎都是如此）。请进入阶段三，用 MT管理器 改包。

> **关于 HttpCanary 的 Shizuku 模式**：部分 HttpCanary 构建提供「Shizuku 模式」入口，可用 Shizuku 提权来安装/移动证书并提升抓包能力，但**这不等于能把证书永久写进系统库**——未 Root 时系统分区只读的限制依旧存在。真正的"系统级信任"要靠阶段四的临时注入。

---

## 5. 阶段三：MT管理器改包信任用户证书

这是整套方案的**核心杀招**：直接改目标 App 的网络安全配置，让它信任用户证书（即 HttpCanary 的 CA），从而完成握手解密。

### 操作步骤

1. **提取目标 APK**：用 MT管理器 的「安装包提取」功能，从已安装的 App 中导出 APK；或直接拿到 APK 安装包。
2. **打开并定位清单文件**：MT管理器 点击 APK → 查看 → 打开 `AndroidManifest.xml`。
3. **添加网络安全配置引用**：在 `<application>` 标签内添加属性（若已存在则不重复加）：

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ... 其他原有属性保持不变 ...>
```

4. **创建/编辑配置文件**：进入 `res/xml/` 目录，新建 `network_security_config.xml`（已有则编辑），内容如下，**同时信任 system 与 user 证书**：

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system"/>
            <certificates src="user"/>
        </trust-anchors>
    </base-config>
</network-security-config>
```

5. **保存并签名**：保存修改 → 退出 → MT管理器 对 APK 执行「签名」（用 MT 自带签名，选 ApkSignature / v2 签名）。
6. **卸载原版、安装改包版**：先卸载原 App（签名不同无法覆盖安装），再安装改好的 APK。打开 HttpCanary 抓包 + 打开改包 App 操作，HTTPS 明文即可见。

> **限制：签名校验会反制**：带**签名校验**的 App（微信、QQ、银行、部分大厂客户端）改包重签后，会因为签名不一致而**装不上、启动崩溃或闪退**。这类 App 此方案无效，需走阶段四的临时系统证书注入或 Frida 动态 Hook。

> **注意**：改包会改变 App 签名，**无法登录需要签名校验的账号体系**、无法使用支付功能；仅适合分析其网络接口。改包后的 App 不代表原版，请勿用于正式环境。

---

## 6. 阶段四（进阶）：Shizuku 临时系统证书注入

如果不想逐个改包，想**免改包就让所有 App 信任 HttpCanary CA**，可以用 Shizuku 做"临时系统证书注入"：把 CA 证书塞进系统信任库，对所有未做 Pinning 的 App 立即生效。

### 原理

利用 Linux 的 tmpfs（内存文件系统）挂载，覆盖系统 CA 目录，再把原系统证书 + HttpCanary CA 一起复制进去。Android 14+ 需同时处理新目录 `/apex/com.android.conscrypt/cacerts/` 与旧目录 `/system/etc/security/cacerts/`。

### 操作思路

1. **拿到 HttpCanary CA 的哈希命名文件**：把导出的 `.pem` 转成系统证书命名格式（文件名为证书 Subject 哈希 + `.0`）。可用 MT管理器 终端执行 `openssl x509 -subject_hash_old -in HttpCanary.pem` 取哈希，重命名为 `<hash>.0`。

2. **用 Shizuku 提权执行注入脚本**：在 MT管理器 的终端里切到 Shizuku 提权模式（或用支持 Shizuku 的"CA 证书移动"类工具），执行 tmpfs 挂载 + 证书拷贝 + SELinux 上下文修正。核心命令示意：

```bash
# 1. 用 tmpfs 覆盖系统 CA 目录（需 shell 提权）
mount -t tmpfs tmpfs /system/etc/security/cacerts
cp /apex/com.android.conscrypt/cacerts/* /system/etc/security/cacerts/
cp /sdcard/<hash>.0 /system/etc/security/cacerts/
chmod 644 /system/etc/security/cacerts/*
restorecon -R /system/etc/security/cacerts

# 2. Android 14+ 同步注入 conscrypt apex 目录
mount -t tmpfs tmpfs /apex/com.android.conscrypt/cacerts
cp /system/etc/security/cacerts/* /apex/com.android.conscrypt/cacerts/
restorecon -R /apex/com.android.conscrypt/cacerts
```

3. **验证**：打开任意未做 Pinning 的 App，HttpCanary 即可解密其 HTTPS，无需改包。

> **重要限制**：
> - **① 临时性**：tmpfs 是内存盘，**重启手机即失效**，需重新执行脚本。
> - **② 成功率因机型而异**：`mount` 需要 CAP_SYS_ADMIN 能力，部分强化 SELinux 的 HyperOS 版本可能拒绝 shell 用户挂载，注入会失败；K90 上可尝试，不保证成功。
> - **③ 仍是用户态操作**：不等于 Root，无法永久写入系统分区。

> **务实建议**：如果临时注入在 K90 上失败，**回退到阶段三的改包方案**是更稳的路径：虽然要逐个改包，但成功率高、不依赖挂载能力。临时注入更适合"快速看一眼大量 App"的场景。

---

## 7. SSL Pinning 绕过与能力边界

即便系统证书就位，做了**证书固定（SSL Pinning）**的 App 仍会把 HttpCanary 的伪证书识别为伪造而拒绝连接。Pinning 是写在 App 代码里的固定证书校验，**改 network_security_config 解决不了**。

### 仅靠这三款软件能做到什么

- MT管理器 可改网络安全配置、改部分明文 Pinning 配置，但**无法处理代码级硬编码 Pinning**。
- Shizuku 提供提权，但不提供 Hook 能力，**不能动态绕过 Pinning**。
- HttpCanary 只负责抓包，**不内置 Pinning 绕过**。

### 要突破 Pinning 需要的额外工具（超出三件套）

- **免 Root 路线**：LSPatch（给 App 内嵌 LSPosed 环境）+ TrustMeAlready 模块，给目标 App 打补丁绕过 Pinning。
- **动态 Hook 路线**：Frida + SSL-unpinning 脚本，需 USB 连电脑，运行时注入绕过。这是最通用的方案。
- **Root 路线**：Magisk + Trust User Certs 模块 + JustTrustMe，一劳永逸但需解锁 BL。

> **诚实边界**：用"Shizuku + HttpCanary + MT管理器"这三件套，**无法抓取做了 SSL Pinning 的大厂 App**。这是工具能力的天花板，不是操作问题。要抓这类 App，必须引入 LSPatch 或 Frida。

---

## 8. 能力矩阵：哪些能抓、哪些不能

下表汇总不同 App 类型在本方案下的可抓性，帮助你快速判断该用哪一层方案。

| App 类型 | 信任用户证书 | SSL Pinning | 签名校验 | 仅三件套可抓 | 推荐方案 |
|---|---|---|---|---|---|
| 自研 / 测试 App | 是 | 无 | 无 | ✓ 可 | 阶段二：装用户证书直接抓 |
| 普通第三方 App（未固定） | 否 | 无 | 无/弱 | ✓ 可 | 阶段三：MT改包信任用户证书 |
| 普通 App（批量免改包） | 否 | 无 | — | 视机型 | 阶段四：Shizuku 临时系统证书注入 |
| 大厂 App（微信/抖音/银行） | 否 | 有 | 有 | ✗ 不可 | 需 LSPatch+TrustMeAlready 或 Frida |
| 带 VPN 检测的 App | — | — | — | ✗ 难 | 需反检测 Hook，超出三件套 |
| 老旧 App（targetSDK≤23） | 是 | 无 | — | ✓ 可 | 阶段二：装用户证书直接抓 |

---

## 9. 常见问题排错

### 抓包时所有 App 都断网
多半是 VPN 冲突——Android 同一时刻只能有一个 VPN 服务。关掉其他 VPN（加速器、Clash、AdGuard 等）再开 HttpCanary；或重启手机后优先启动 HttpCanary。

### HTTPS 显示"证书错误 / 握手失败"
App 不信任 HttpCanary CA。检查：① 用户证书是否装对入口（选「CA 证书」而非「VPN 和应用」）；② 现代App需走阶段三改包；③ 改包后仍失败说明可能有 Pinning，走阶段七。

### 改包后 App 闪退 / 装不上
签名校验反制。确认已先卸载原版再装改包版；若仍闪退，说明 App 有运行时签名校验，无法用改包方案，改走临时系统证书注入或 Frida。

### 抓到内容是乱码
该请求可能是压缩（gzip/br）或非文本协议。HttpCanary 一般会自动解压；若仍乱码，检查是否开启了内容压缩，或在设置里开启「自动解压」。

### Shizuku 重启后失效 / 被杀后台
无线调试启动的 Shizuku 重启必断，需重新配对。把 Shizuku 加入 HyperOS「省电策略：无限制」，并锁定后台不被清理。

### 临时系统证书注入失败（mount 报错）
SELinux 拒绝了 shell 用户的挂载操作，属机型/系统版本差异。K90 上若失败，回退到阶段三改包方案，成功率更高。

---

## 参考资料

1. GSMArena, Xiaomi Redmi K90 规格页：Android 16 / HyperOS 3 / 骁龙 8 Elite。https://m.gsmarena.com/xiaomi_redmi_k90_5g-14280.php
2. ZOL 中关村在线，红米 Redmi K90 参数：操作系统 Xiaomi HyperOS 3。https://detail.zol.com.cn/2146/2145333/param.shtml
3. nzero (velog), Android 14 以上 HTTPS 证书系统证书安装：系统 CA 目录迁移至 /apex/com.android.conscrypt/cacerts。https://velog.io/@nzero/AOS-Android-14-이상-https-인증서-설치하기
4. CSDN，Android 14/15 抓包新姿势：不用 Root 也能搞定系统证书信任（tmpfs 临时系统证书注入方案）。https://blog.csdn.net/weixin_42531925/article/details/160274619
5. MT 论坛（binmt.cc），ProxyPin 抓包问题讨论帖：免 Root 抓包五大方案、MT 改 manifest 信任用户证书、SSL Pinning 绕过路径。https://bbs.binmt.cc/forum.php?mod=viewthread&tid=166326
6. HTTP Canary 官网（黄鸟抓包工具），常见问题：CA 证书安装与 HTTPS 抓包说明。http://httpcanary.cn/
7. phcorner.org, How to bypass SSL Pinning on Non-rooted Devices [2025]：MT管理器 新建 network_security_config 信任用户证书流程。https://phcorner.org/threads/how-to-bypass-ssl-pinning-on-non-rooted-devices-2025.2257133/latest
8. oguzhanstech.com, SSL Pinning Bypass: Network Security Config：network_security_config.xml 同时信任 system 与 user 证书示例。https://oguzhanstech.com/2025/08/25/ssl-pinning-bypass-network-security-config.html
9. LEMONSYS，Android 13/14 注入系统级自定义 CA 证书：tmpfs 挂载 + SELinux 上下文修正方法。https://www.lemonsys.cn/tech_803/
10. 奇珀网，HttpCanary 最新版使用说明：VPN 冲突与同时仅能一个 VPN 服务的注意事项。https://down.7po.com/apps/16914.html

---

> **合法使用声明**：本指南仅供移动应用开发调试、自有产品测试与授权范围内的安全研究使用。请仅对您拥有或已获授权的 App 与设备进行抓包分析；未经授权拦截他人应用流量、获取他人数据属于违法行为，后果自负。改包后的 App 不可替代原版用于正式环境与支付场景。
