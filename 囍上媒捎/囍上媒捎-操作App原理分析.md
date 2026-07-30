<div align="center">
  <img src="https://img.shields.io/badge/囍上媒捎-操作App原理分析-8B1538?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgZmlsbD0id2hpdGUiPjx0ZXh0IHg9IjEiIHk9IjEyIiBmb250LXNpemU9IjE0Ij7wn5mNPC90ZXh0Pjwvc3ZnPg==" alt="囍上媒捎"/>
  <br><br>
  <h1>我不是终端，为什么能操作 App？</h1>
  <p><strong>核心结论：没有安装安卓模拟器，操作的是 H5 网页版 + 直接调用后端 API</strong></p>
  <p>文档版本：2.0　|　编写日期：2026-07-30</p>
</div>

---

## 一、先纠正一个常见误解

### 1.1 我没有安装任何安卓模拟器

很多人会自然地把"能操作 App"等同于"在模拟器里安装并运行 APK"。这个等式只对**原生 Android App**成立。在本项目中，我没有安装 Android Studio、Genymotion、Bluestacks、夜神模拟器，也没有任何虚拟机或 Android SDK。

### 1.2 我到底是什么

你可以把我理解为运行在**TRAE 云端沙箱**里的一个 AI 代理。我所在的环境不是你自己的电脑，而是一个远程 Linux 容器。这个容器里提供了：

- Python、Node.js、命令行工具
- 通过 MCP 协议暴露出来的浏览器
- 访问公网的能力
- 读写沙箱内文件的能力

所以"安装模拟器"这件事，如果是在你的本地电脑上完成，我确实做不到；在沙箱里安装模拟器理论上可行，但**完全没有必要**。

---

## 二、为什么没必要装模拟器

### 2.1 囍上媒捎有两套前端

同一个业务后台，通常同时服务两类客户端：

| 客户端类型 | 形态 | 运行环境 | 是否需要安装 |
|---|---|---|---|
| 原生 App | Android APK / iOS IPA | 手机系统 | 需要下载安装 |
| H5 网页版 | HTML + Vue/UniApp + WebSocket | 任意浏览器 | 不需要安装 |

囍上媒捎的 H5 地址是：

```
https://h-app.xsms-club.com/
```

在浏览器里打开这个链接，呈现的界面、账号体系、会员数据、消息系统，和原生 App 是同一套后台。对于登录、查询会员、发送文本消息这些需求，H5 版已经完全够用。

---

## 三、整体数据流

下面这张图说明了你的一句话，是如何最终变成 App 里的真实操作的。

```mermaid
flowchart LR
    A[你在 TRAE 输入指令] --> B[TRAE 对话窗口]
    B --> C[TRAE 远程沙箱]
    C --> D[MCP 集成浏览器]
    D --> E[Headless Chromium]
    E --> F[HTTPS / WebSocket]
    F --> G[囍上媒捎 H5 站点]
    G --> H[囍上媒捎后端服务]
    H --> I[数据库 / 环信 IM]
```

| 层级 | 组件 | 作用 |
|---|---|---|
| 1 | 你的指令 | "打开 App 登录" 这类自然语言 |
| 2 | TRAE 对话窗口 | 解析意图，决定调用哪些工具 |
| 3 | TRAE 远程沙箱 | 安全的云端 Linux 环境 |
| 4 | MCP 集成浏览器 | 浏览器自动化协议与工具集 |
| 5 | Headless Chromium | 无界面 Chrome，接收自动化指令 |
| 6 | HTTPS / WebSocket | 浏览器正常访问网站和 IM 服务 |
| 7 | 囍上媒捎 H5 站点 | 网页版 App 的前端代码 |
| 8 | 囍上媒捎后端服务 | 账号、会员、消息等业务逻辑 |
| 9 | 数据库 / 环信 IM | 持久化数据和即时通讯服务 |

---

## 四、浏览器为什么能"登录"App

### 4.1 H5 与原生 App 共用同一套账号

H5 站点登录时，向同一个后端发起登录请求。请求参数、加密方式、返回的 Token，与原生 App 完全一致。

以囍上媒捎为例：

| 项目 | 内容 |
|---|---|
| 登录接口 | `POST /xsms/api/member/login/password` |
| 密码加密 | AES-ECB，密钥 `xsms123456789000` |
| 签名方式 | CryptoJS AES 加密时间戳后 Base64 |
| 返回字段 | `id`、`token`、`nickname` 等 |

后端只认账号、密码和签名，不关心请求来自原生 App 还是浏览器。

### 4.2 登录后浏览器拿到凭证

登录成功，H5 前端会把 `accessToken` 和 `userId` 保存在浏览器内存或 LocalStorage 中。后续查询会员、发送消息等请求，都会在 HTTP Header 里带上这些凭证。

这个机制与原生 App 把 Token 存到本地存储、再在请求中携带，本质完全相同。

---

## 五、浏览器自动化的具体原理

### 5.1 MCP 集成浏览器是什么

MCP 是 Model Context Protocol，即"模型上下文协议"。TRAE 通过它把 Chrome 浏览器的操作封装成可调用的函数：

| 工具函数 | 功能 |
|---|---|
| `browser_navigate` | 打开某个 URL |
| `browser_type` | 在输入框里填内容 |
| `browser_click` | 点击按钮 |
| `browser_evaluate` | 在当前页面执行 JavaScript |
| `browser_wait_for` | 等待某个文本或元素出现 |
| `browser_take_screenshot` | 截图留证 |
| `browser_network_requests` | 抓取网络请求 |

### 5.2 一次登录动作的内部流程

以"用手机号 150****0897 登录"为例：

1. `browser_navigate` 打开 `https://h-app.xsms-club.com/`
2. `browser_click` 点击"密码登录"入口
3. `browser_type` 在手机号输入框填入 `150****0897`
4. `browser_type` 在密码输入框填入 `123456`
5. `browser_click` 勾选用户协议
6. `browser_click` 点击"登录"按钮
7. 浏览器自动向后端发起登录请求，后端返回 Token
8. H5 前端保存 Token，页面跳转到首页
9. `browser_evaluate` 执行 JS 读取当前用户 ID，确认登录成功

看起来和真人操作一样，只是每一步由程序触发。

---

## 六、消息是怎么真正发出去的

### 6.1 第一次的误区：把推送通知当成消息

项目初期，我曾直接调用后端的推送接口，结果返回"success"，但消息并没有出现在 App 的聊天记录里。原因是：推送通知和 IM 消息是两条不同的通道。

| 通道 | 入口 | 用户能否在聊天记录看到 |
|---|---|---|
| 推送通知 | `POST /xsms/api/.../push` | 不能 |
| 环信 IM 消息 | 通过 WebSocket 发送 | 能 |

### 6.2 正确的消息通道：环信 Web SDK

囍上媒捎的消息系统基于环信 Easemob IM。H5 版同样集成了环信的 Web SDK，通过 WebSocket 与环信服务器建立长连接，再调用发送消息 API。

我在浏览器里执行的 JavaScript 直接调用页面内已加载的环信 SDK：

```javascript
conn.send({
  to: '目标会员ID',
  type: 'txt',
  body: { type: 'txt', msg: '我可能盐吃多了，总是闲得想你。' }
});
```

这段代码运行在 H5 页面的上下文中，和页面自身调用的方式没有区别，因此消息会进入正常的聊天记录。

---

## 七、另一条路径：直接调用后端 API

除了浏览器自动化，我还通过 Python 脚本直接调用了囍上媒捎的后端接口。这条路径不需要打开浏览器。

### 7.1 从 APK 里提取接口

Android APK 本质上是一个压缩包，其中的 JavaScript 代码经过 Webpack 打包。通过反编译和解析，可以恢复出：

- 接口地址
- 请求参数结构
- AES 加密密钥和 IV
- 签名算法

### 7.2 Python 脚本模拟登录和查询

```python
# 伪代码示意
import requests

# 1. 获取 access token
token = requests.get(BASE_URL + "/upms/api/access/token").json()["data"]["token"]

# 2. 用 AES-ECB 加密密码后登录
encrypted_pwd = aes_ecb_encrypt("123456", "xsms123456789000")
login = requests.post(
    BASE_URL + "/xsms/api/member/login/password",
    json={"phone": "150****0897", "password": encrypted_pwd},
    headers={"accessToken": token}
).json()

user_id = login["data"]["id"]
access_token = token

# 3. 查询会员列表
members = requests.get(
    BASE_URL + "/xsms/api/member/query/list",
    params={"sex": "1", "ageStart": "33", "ageEnd": "43"},
    headers={"accessToken": access_token, "userId": user_id}
).json()
```

这种方式完全绕过浏览器，直接和后台交互，效率更高，适合批量查询和数据处理。

---

## 八、两种路径的能力对比

| 能力 | H5 浏览器自动化 | Python 直接调用 API |
|---|---|---|
| 是否需要打开浏览器 | 是 | 否 |
| 是否能发送 IM 消息 | 是，通过环信 Web SDK | 否，缺少 WebSocket 会话 |
| 是否能批量查询会员 | 可以，但较慢 | 非常适合 |
| 是否能截图留证 | 可以 | 不可以 |
| 是否能模拟真实用户界面操作 | 可以 | 不可以 |
| 本项目用途 | 登录、发消息、截图 | 批量查询、生成报告 |

---

## 九、H5 版与原生 App 的能力对比

| 能力 | 原生 App | H5 网页版 | 本项目实际使用 |
|---|---|---|---|
| 安装包 | 需要 APK / IPA | 无需安装 | 无需安装 |
| 运行环境 | Android / iOS | 任意浏览器 | Headless Chromium |
| 消息发送 | 原生 IM SDK | 环信 Web SDK | 环信 Web SDK |
| 接口加密 | AES + 签名 | AES + 签名 | 相同 |
| 推送通知 | 系统级推送 | 浏览器通知 | 未使用 |
| 文件系统 | 可读写本地 | 受限 | 受限 |
| 摄像头/麦克风 | 可直接调用 | 需授权 | 未使用 |

对于本项目需要的功能，H5 版已经完全可以覆盖。

---

## 十、常见误解澄清

### 误解 1："你在模拟器里装了 App"

**正解：** 没有模拟器。打开的是网页链接，浏览器自动渲染 H5 页面。

### 误解 2："你能远程控制我的手机"

**正解：** 不能。所有操作都在 TRAE 远程沙箱的浏览器里完成，和你的手机没有任何连接。

### 误解 3："你用 AutoJS 操作手机"

**正解：** 不是 AutoJS。AutoJS 需要在 Android 设备上运行，本项目使用的是浏览器自动化工具。

### 误解 4："浏览器版和 App 版数据不同步"

**正解：** 数据同源。H5 和原生 App 调用同一套后端接口、同一个数据库、同一个账号体系。在 H5 里发送的消息，在原生 App 的消息列表里也能看到。

---

## 十一、总结

能操作 App 的核心原因，不是因为安装了模拟器，而是因为：

1. 囍上媒捎提供了 H5 网页版，功能与原生 App 基本一致；
2. TRAE 内置了 MCP 集成浏览器，可以自动化控制 Headless Chromium；
3. 浏览器访问 H5 站点后，通过正常登录流程拿到 Token；
4. 后续所有界面操作，包括发消息，都是调用页面内的标准 JavaScript API；
5. 对于批量查询等任务，则直接通过 Python 调用后端 REST API。

本质上，这是**"用浏览器自动化操作网页应用 + 用脚本直接调用后端接口"**，而不是**"在模拟器里安装并操作原生 App"**。

<div align="center">
  <br>
  <p><strong>—— 囍上媒捎 · 技术原理分析 ——</strong></p>
</div>
