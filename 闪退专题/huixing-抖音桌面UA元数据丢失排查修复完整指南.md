# huixing（抖音管家）桌面 UA 后抖音视频元数据丢失：排查修复完整指南

> 适用对象：技术基础一般、对命令行不熟悉的开发者
> 目标：看懂"为什么视频详情没了、怎么查出来的、用了哪些工具、为什么这么修、验证链路怎么搭、别踩哪些坑"
> 最后更新：2026-08-09
> 结论先行：**为了修复"抖音提示请尝试在抖音内观看"，上一个提交把 WebView 的 UA 改成了桌面 Chrome。这一改，抖音把页面当成电脑浏览器，返回的是 JS 动态渲染（SPA）的页面——视频详情是页面里的脚本"后补"调接口拿的，静态 HTML 里根本没有。App 里抓静态 HTML 的老代码全部落空，于是标题/作者/封面/播放地址全丢。修复方法：在页面里注入一段 JS（hook），偷听 detail 接口的返回，把 JSON 缓存下来再传给 Java 解析。**

---

## 目录

1. [问题背景：好好的，为什么突然丢详情](#1-问题背景好好的为什么突然丢详情)
2. [为什么之前的 agent 都没修好](#2-为什么之前的-agent-都没修好)
3. [工具准备：这次用到的东西](#3-工具准备这次用到的东西)
4. [排查第一步：git 找"元凶提交"](#4-排查第一步git-找元凶提交)
5. [排查第二步：搞懂"SPA 动态渲染"到底是什么](#5-排查第二步搞懂spa-动态渲染到底是什么)
6. [排查第三步：用无头浏览器看真实页面里有什么](#6-排查第三步用无头浏览器看真实页面里有什么)
7. [排查第四步：详情到底藏在哪个接口](#7-排查第四步详情到底藏在哪个接口)
8. [修复方案设计：为什么选"注入 hook"这条路](#8-修复方案设计为什么选注入-hook-这条路)
9. [代码实现：两个文件各做了什么](#9-代码实现两个文件各做了什么)
10. [验证：把整条链路在电脑上跑通](#10-验证把整条链路在电脑上跑通)
11. [构建 APK：编译打包验证](#11-构建-apk编译打包验证)
12. [真机 WebView 与无头环境的差别（指纹问题）](#12-真机-webview-与无头环境的差别指纹问题)
13. [避坑清单：所有失败经验汇总](#13-避坑清单所有失败经验汇总)
14. [构建环境搭建完整命令](#14-构建环境搭建完整命令)
15. [命令速查表（可直接复制）](#15-命令速查表可直接复制)
16. [常见问题 FAQ](#16-常见问题-faq)
17. [给其他 agent 的接力指引](#17-给其他-agent-的接力指引)
18. [附录：关键代码最终内容](#18-附录关键代码最终内容)

---

## 1. 问题背景：好好的，为什么突然丢详情

### 1.1 项目与仓库

| 项 | 值 |
|----|----|
| 项目仓库 | `liliangxing/huixing`（分支 main） |
| App 名字 | 抖音管家（包名 `com.hx.huixing`） |
| 功能 | 分享抖音链接进来，自动解析出标题/作者/封面/播放地址并下载 |

App 的流程：用户把抖音视频分享链接发给 App → App 用 WebView 打开链接 → WebView 加载完页面后，App 抓取页面源码（`getSource`）→ 从源码里用 Jsoup 选择器抠出标题、作者、封面、播放地址 → 下载。

### 1.2 症状

- 修复"无法播放"之后，**标题、作者、封面、播放地址**全部解析不出来
- 解析结果变成空，App 无法下载

### 1.3 时间线（关键）

```
e0969a6 → 1ee5d09 → 7dc8ca5 → 196afa5（元凶）→ bc1af82（本次修复）
```

- 提交 `196afa5`：为了修"抖音链接提示'请尝试在抖音内观看'无法播放"，把 WebView 的 UA（浏览器标识）改成了桌面 Chrome。
- 提交 `bc1af82`：本次修复（本指南讲的就是它）。

---

## 2. 为什么之前的 agent 都没修好

之前的 agent 接到"抖音详情解析不出来"的活，做法是：**打开源码，一个文件一个文件读，猜哪里逻辑不对**（是不是选择器写错、是不是 null 没判、是不是编码问题……）。

方向全错了。真正的问题**不在任何一行业务代码里**，而在"**页面变了**"：

- 以前：WebView 是手机 UA，抖音给**静态 HTML**，标题作者封面播放地址全写在 HTML 里，Jsoup 一抓就有。
- 现在：WebView 是桌面 UA，抖音给**电脑版 SPA 页面**，HTML 里啥都没有，详情是页面里的 JS 脚本"后补"调接口拿到的。

> **排查"解析不出数据"这类问题，第一步是看"页面里到底有什么"，而不是读业务代码。** 数据在页面里没有，代码写得再对也没用。

---

## 3. 工具准备：这次用到的东西

| 工具 | 作用 | 怎么装（Linux） |
|------|------|----------------|
| `git` | 查提交历史、切代码 | 一般自带 |
| `curl` | 直接发 HTTP 请求，测接口 | 一般自带 |
| `playwright` | 无头浏览器，模拟 Chrome 打开真实网页、截图、监听接口 | `npm install -g playwright` + `npx playwright install chromium` |
| `node` | 跑 playwright 脚本 | 一般自带 |
| JDK 11 | 编译 Android 代码 | 见第 14 节 |
| Gradle 5.4.1 | 打包工具（项目要求的版本） | 见第 14 节 |
| Android SDK (platform 27) | Android 编译必需 | 见第 14 节 |

**为什么用 playwright 而不是自己写网络请求？** 抖音这种大网站，页面是 JS 动态拼的，只有真正的浏览器内核才能把它跑起来。playwright 就是"遥控一个无头 Chrome"，能打开网页、执行 JS、截图、还能监听浏览器发出的每一个接口请求——这是排查这类问题最重要的工具。

---

## 4. 排查第一步：git 找"元凶提交"

### 4.1 命令

```bash
cd /tmp/opencode/huixing
git log --oneline -5
```

### 4.2 屏幕输出

```
196afa5 fix: WebView 改用桌面 Chrome UA，修复抖音链接提示'请尝试在抖音内观看'无法播放
7dc8ca5 refactor: 水印修复服务优化（进度显示/超时处理/下载重试）
f7248ea refactor: 水印修复服务增加重试/失败追踪/日志
e0969a6 fix: 升级 lombok 到 1.18.30 以兼容 JDK 11，跳过 greendao/externalNativeBuild（使用预构建产物）
1ee5d09 feat: 批量水印视频修复功能
```

最近的提交 `196afa5` 恰好就是"改桌面 UA"。**而详情丢失正好是这次改完之后出现的**——时间上完全对得上，嫌疑最大。

### 4.3 看这个提交到底改了什么

```bash
git show 196afa5 --stat
git show 196afa5 | grep -E "^[+-].*(UserAgent|userAgent|Chrome|setUserAgent)"
```

**输出（关键行）：**

```
app/src/main/java/com/hx/huixing/fragment/WebviewFragment.java | 4 ++++
+        // 使用桌面 Chrome UA 后，抖音会按桌面浏览器处理并进入正常播放页面（与 Chrome 桌面模式一致）。
+        webSettings.setUserAgentString("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
```

**大白话解释：** `196afa5` 把 WebView 的 UA 改成桌面 Chrome。UA 就是浏览器自报家门的一句话，网站靠它判断"你是手机还是电脑"。改成桌面 UA 后，抖音就把我们的 WebView 当成电脑浏览器了——播放问题解决了，但页面也从"手机版静态页"换成了"电脑版动态页"。

> **为什么这步重要：** 找到"哪个改动引起问题"是排查的一半。改 UA 和丢详情是一起出现的，说明**丢详情是改 UA 的副作用**。

---

## 5. 排查第二步：搞懂"SPA 动态渲染"到底是什么

### 5.1 什么是 SPA

普通网页（老式手机版抖音）：服务器直接把"标题、作者、封面、播放地址"写进 HTML 返回，浏览器打开就能看到，抓源码就有。

SPA（单页应用，电脑版抖音就是这种）：服务器只返回一个**空壳 HTML**，里面是一个 JS 脚本。浏览器把 JS 跑起来，JS 再偷偷调接口（比如 `/aweme/v1/web/aweme/detail`）拿到视频详情，然后自己把标题、作者画到页面上。

**后果：** 我们 App 的 `getSource` 拿到的是"页面跑完 JS 之后"的 HTML，理论上也该有内容……但 App 抓 HTML 的时机、以及 Jsoup 选择器（`video[src]`、`cssTitle` 等）是照着老版静态页写的，在 SPA 页面上全都匹配不到。而且 SPA 里视频用的是 canvas/flv 流，页面上甚至没有 `<video src>` 标签。所以全丢。

### 5.2 关键疑问：SPA 页面跑完后，HTML 里应该有详情吧？

不一定。详情是通过接口"后补"的，**不一定被画进 DOM 的静态 HTML 里**（可能画在 canvas 上，可能只存在 JS 变量里，可能藏在某个 div 的 data 属性里）。**必须用真浏览器打开页面实际看一眼**，不能靠猜。

---

## 6. 排查第三步：用无头浏览器看真实页面里有什么

### 6.1 准备测试链接

本次实测用的抖音视频：

```
https://www.douyin.com/video/7670020387090641531
```

（原分享短链 `https://v.douyin.com/oRGD5aVY6zw/` 会重定向到上面的完整地址。）

### 6.2 写一个诊断脚本（collect_diag.js）

这个脚本用 playwright 打开真实页面，然后检查几件事：页面最终地址、标题、`#RENDER_DATA`（SPA 的初始数据容器）、有没有 `<video>` 标签、有没有详情文字；同时监听 `detail` 接口有没有被调用、返回多少字节。

**脚本关键代码：**

```javascript
const { chromium } = require('playwright');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36';

page.on('response', async r => {
  if (r.url().includes('/aweme/v1/web/aweme/detail')) {
    let body = '';
    try { body = await r.text(); } catch (e) {}
    console.log('detail 接口被调用:', r.status(), 'body长度:', body.length);
  }
});

await page.goto('https://www.douyin.com/video/7670020387090641531',
               { waitUntil: 'domcontentloaded', timeout: 45000 });
await page.waitForTimeout(6000);  // 等 SPA 渲染完

const info = await page.evaluate(() => ({
  title: document.title,
  renderDataLen: document.getElementById('RENDER_DATA') ? document.getElementById('RENDER_DATA').textContent.length : 0,
  videoTags: document.querySelectorAll('video').length,
  descCandidates: [...document.querySelectorAll('[class*="desc"]')].map(e => e.textContent.trim().slice(0, 60))
}));
console.log(JSON.stringify(info, null, 1));
await page.screenshot({ path: 'images/douyin-fix/real-douyin-video-page.png' });
```

### 6.3 真实输出

```
STEP1: goto https://www.douyin.com/video/7670020387090641531
STEP2: wait 6s for SPA render
STEP3: page analysis
{
 "finalUrl": "https://www.douyin.com/video/7670020387090641531",
 "title": "",
 "renderDataLen": 186090,
 "videoTags": 0,
 "videoSrc": "",
 "descCandidates": [],
 "hasHookCache": "not-set"
}
STEP5: detail API responses observed (from page JS)
[]
```

### 6.4 这份数据说明了什么（大白话）

| 检查项 | 结果 | 含义 |
|--------|------|------|
| 页面最终地址 | 正确停在视频页 | 页面加载没问题 |
| `document.title` | 空 | 连浏览器标签标题都没渲染出来 |
| `#RENDER_DATA` | 186090 字符 | SPA 的"初始数据"很大，但这是整个页面的框架数据 |
| `<video>` 标签数 | 0 | **原代码 `video[src]` 选择器必然失效** |
| 详情文字候选 | 空 | **原代码 cssTitle 选择器必然失效** |
| detail 接口响应 | 0 条 | 无头环境里页面脚本调 detail 也没返回数据（后面第 12 节讲原因） |

**截图（页面真实样子）：**

![真实抖音视频页](images/douyin-fix/real-douyin-video-page.png)

**判断：** 桌面 UA 下，页面是 SPA 空壳，标题/作者/封面/播放地址**不在静态 HTML 里**，原 Jsoup 选择器全军覆没。这就是"为什么数据没了"的铁证。

> **技巧：** `#RENDER_DATA` 很大但没用，说明"有数据"和"有视频详情"是两回事。排查时不要看到大 JSON 就高兴，要**精确匹配目标字段**（本例就是 desc/昵称/video src）。

---

## 7. 排查第四步：详情到底藏在哪个接口

### 7.1 用 curl 直接测 detail 接口

```bash
curl -s -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36" \
     -w "\nHTTP %{http_code}, size %{size_download}\n" \
     "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=7670020387090641531"
```

### 7.2 真实输出

```
HTTP 200, size 0
```

**也就是说：** 接口返回 HTTP 200（"请求成功"），但**内容 0 字节**（空的）。原因是抖音对 detail 这类接口做了签名校验（请求里要带 `a_bogus` 等加密签名参数），用 curl 裸调没有签名，就被风控"礼貌地"返回空。

### 7.3 结论：这条路堵死，必须换思路

- curl 直接调接口：**不行**（没签名，返回空）。
- 用 playwright 打开页面、看页面自己调接口：页面里确实会调 detail，但返回也被风控挡住（无头环境，第 12 节讲）。
- **唯一可行的路：让页面自己调接口、我们在页面里"偷听"。** 抖音页面自己的脚本调 detail 时是**带齐签名和 cookie**的（字节码生成 `a_bogus`），只要在页面里注入一段 JS，把这个接口的返回拦截下来缓存住，就能拿到真实详情——这正是本方案的钥匙。

> **思维转变：** 与其"从外面想办法拿到接口数据"，不如"在页面内部等数据自己送上门"。网站的反爬只防"外部来路"，防不了"页面自己人"。

---

## 8. 修复方案设计：为什么选"注入 hook"这条路

### 8.1 候选方案对比

| 方案 | 想法 | 为什么不行/不选 |
|------|------|-----------------|
| 改接口签名重放 | 在 Java 里算 `a_bogus` 签名再调 detail | 签名算法在抖音 JS 里，会变，逆向成本高、易挂 |
| 解析 `#RENDER_DATA` | SPA 的初始数据 186KB 很大 | 实测里面没有当前视频详情，都是框架数据 |
| 用 JS 注入 hook 偷听 detail 接口（**选中**） | 页面里塞一段 JS，改掉 `fetch` 和 `XMLHttpRequest`，当 detail/post 接口有返回时，把 JSON 存到 `window.__HX_DY__` | 签名由页面自己的脚本生成，天然合法；改动只在 WebView 层，不动服务器 |

### 8.2 全链路设计图（大白话）

```
用户分享抖音链接
      │
      ▼
WebView 打开视频页
      │  shouldInterceptRequest 拦截主文档
      ▼
用 HttpURLConnection 重新下载 HTML（桌面 UA + cookie）
      │  在 </head> 前塞进 DY_HOOK 脚本
      ▼
WebView 加载"改造过的 HTML"
      │  hook 改写了 window.fetch / XMLHttpRequest
      ▼
页面脚本调 detail 接口（带签名）
      │  hook 偷听到返回 → window.__HX_DY__ = 详情JSON
      ▼
onPageFinished 触发 getSource 注入脚本
      │  把 __HX_DY__ base64 编码塞进 <div id="__hx_dy_json">
      ▼
Java 端 getSource 收到 HTML
      │  extractDyDetail 读出 base64 → 解码成 JSON
      ▼
handleDouyinDetail 用 fastjson 递归找 aweme
      │  取出 desc→标题、nickname→作者、cover→封面、play_addr→播放地址
      ▼
下载成功
```

### 8.3 为什么要 base64 转一圈

`window.__HX_DY__` 里的详情 JSON 是**原始字符串**，直接塞进 HTML 会有一堆转义问题（引号、换行、`<`、`>`），Java 端解析很容易坏。所以：

1. 页面里用 `btoa(unescape(encodeURIComponent(json)))` 把 UTF-8 字符串编码成 **base64**（只有字母数字和 `+/=`，绝对安全）。
2. base64 塞进一个隐藏的 `<div id="__hx_dy_json">`。
3. Java 端用 `android.util.Base64.decode(...)` 解码回字符串，再交给 fastjson 解析。

> **为什么用 `android.util.Base64`：** 它是系统自带（API 8 就有的类），项目 minSdk 是 14，直接能用，不需要额外引库，也不触发 Java 8 desugaring 的坑。

---

## 9. 代码实现：两个文件各做了什么

只改了 2 个文件（共 269 行新增）。提交 `bc1af82`。

### 9.1 `MyWebViewClient.java`：负责"装监听器"

这个文件是 WebView 的"客户端"，页面加载的每个环节（开始、结束、每个请求）都会经过它。在这里干了三件事：

#### 9.1.1 拦截主文档，注入 hook

`shouldInterceptRequest` 会在"页面要加载某个请求"前被调用，给它机会**偷偷换掉响应**。我们只对抖音 PC 视频页/图文页的主文档动手（`/video/`、`/note/`），其它请求一律放行：

```java
private boolean isDouyinVideoPage(String url) {
    return url != null && url.startsWith("https://www.douyin.com")
            && (url.contains("/video/") || url.contains("/note/"));
}

@SuppressLint("NewApi")
private WebResourceResponse interceptDouyin(String url) {
    try {
        String html = fetchHtml(url);          // 重新下载一次 HTML（桌面UA + cookie）
        if (html == null) return null;          // 下载失败就放行，别影响页面
        int idx = html.toLowerCase().lastIndexOf("</head>");
        if (idx >= 0) {
            html = html.substring(0, idx) + DY_HOOK + html.substring(idx);
        } else {
            html = DY_HOOK + html;
        }
        return new WebResourceResponse("text/html", "UTF-8",
                new ByteArrayInputStream(html.getBytes("UTF-8")));
    } catch (Exception e) {
        return null;
    }
}
```

**注意（很关键的坑）：** 项目 minSdk=14，`shouldInterceptRequest` 必须**两个重载都实现**：

```java
// 旧版签名（API 21 以下走这个）
public WebResourceResponse shouldInterceptRequest(WebView view, String url)
// 新版签名（API 21+ 走这个），还要判断 request.isForMainFrame()
public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request)
```

只写一个，在部分系统上不会生效。

**为什么要用 HttpURLConnection 重新下载 HTML？** 因为 `shouldInterceptRequest` 拿到的响应对象不能直接改写内容。干脆自己再下载一次原始 HTML（带 cookie，保证登录态），注入脚本后再返回给 WebView。

#### 9.1.2 hook 脚本本体（DY_HOOK）

核心逻辑：**改掉 `window.fetch` 和 `XMLHttpRequest.prototype.send`**，判断请求地址里含 `/aweme/v1/web/aweme/detail`（视频详情）或 `/aweme/v1/web/aweme/post`（图文/主页作品列表），就在返回时把 JSON 文本缓存进 `window.__HX_DY__`：

```javascript
window.fetch = function() {
    var u = arguments[0];
    var p = 原来的fetch(...);
    var su = 取到请求地址;
    if (地址包含 '/aweme/v1/web/aweme/detail' 或 '/aweme/v1/web/aweme/post') {
        p.then(function(r) {
            r.clone().text().then(function(t) {
                if (t && t.length > 80) { window.__HX_DY__ = t; }
            });
        });
    }
    return p;
};
```

`XMLHttpRequest` 同理：`open` 时记住地址，`send` 时挂一个 `load` 事件，返回后把 `responseText` 存进 `__HX_DY__`。**两个都改**，因为抖音页面 fetch 和 XHR 都可能用。

#### 9.1.3 getSource 注入脚本（loadSourceJs）

App 原有机制：页面加载完成后用 `window.java_obj.getSource(html)` 把 DOM 交给 Java。我们在这个脚本里加一步——如果 `__HX_DY__` 有内容，就 base64 编码后塞进一个隐藏 div，跟着 DOM 一起交出去：

```javascript
setTimeout(function() {
    var h = document.getElementsByTagName('html')[0].innerHTML;
    var s = '<head>' + h + '</head>';
    var d = window.__HX_DY__;
    if (d) {
        d = btoa(unescape(encodeURIComponent(d)));   // UTF-8 → base64
        s = '<head>' + h + '<div id="__hx_dy_json" style="display:none;">' + d + '</div></head>';
    }
    window.java_obj.getSource(s);
}, 7000);
```

### 9.2 `WebviewFragment.java`：负责"拆开偷听来的数据"

这个文件收到 DOM 后，原来的流程是先跑老选择器。我们在最前面加了"**先看有没有偷听来的 detail**"：

```java
// 抖音分支开头：
String dyDetail = extractDyDetail(document);          // 1. 从隐藏 div 里取出 base64 → 解码
if (dyDetail != null && handleDouyinDetail(document, dyDetail)) {
    return;                                            // 2. 解析成功就直接用，不走老逻辑
}
// 3. 解析失败才回退到老选择器逻辑
```

`extractDyDetail`：用 Jsoup 找 `div#__hx_dy_json`，读出 base64 文本，`Base64.decode` 成字符串。

`handleDouyinDetail`：把 JSON 交给 fastjson 的 `findAweme`（递归搜索，找一个同时有 `aweme_id`、`video`、`author` 三个字段的对象，这就是视频详情），然后取出：

| JSON 字段 | 映射到 App 的哪个字段 |
|-----------|----------------------|
| `desc` | 标题 `title` |
| `author.nickname` | 作者 `album`（App 里"专辑"位置装作者名） |
| `video.cover.url_list[0]`（没有就 `origin_cover`） | 封面 `coverPath` |
| `video.play_addr.url_list[0]`（没有就 `bit_rate[0].play_addr`） | 播放地址 `artist`（App 里"艺术家"位置装播放直链） |

`firstUrl`：从 `url_list` 数组里取第一个 URL（抖音会给多个备选 CDN 地址，取第一个就行）。

`findAweme`：**递归遍历**整个 JSON（对象遍历 value、数组遍历元素），找到 `aweme_id + video + author` 齐全的对象就返回。这样不依赖 detail 返回的字段层级，稳。

### 9.3 顺带的小修复

- `document.title()` 兜底：`desc` 为空时用页面标题，并剥离 `" - 抖音"` 后缀。
- 图文页误判修复：当页面是 `www.douyin.com/video/` 且没有封面也没有 video 标签时，只回传已有封面，**不再误走图集解析流程**。

---

## 10. 验证：把整条链路在电脑上跑通

真机 WebView 无法在这个环境直接跑，但**可以把"hook → base64 → Java 解析"整条链路在 playwright 里模拟出来**（第 12 节讲为什么只能模拟）。

### 10.1 思路

1. 用 playwright 起一个页面，手动注入**从 Java 源码里原样提取的 DY_HOOK**。
2. 页面里主动调一次 detail 接口（路由拦截掉，喂一个构造的 detail JSON，模拟真机返回）。
3. 验证 hook 是否把 detail JSON 缓存进 `window.__HX_DY__`。
4. 执行 getSource 注入脚本，从 DOM 里挖出 base64，解码成 JSON。
5. 用 JS 复刻 Java 的 `findAweme/firstUrl` 解析逻辑，验证标题/作者/封面/播放地址是否正确。

### 10.2 运行命令

```bash
cd /tmp/opencode
NODE_PATH=$(npm root -g) node verify_link2.js
```

### 10.3 真实输出

```
hook cached detail JSON: yes (610 chars)
PARSED: {
 "title": "验证视频描述：抖音元数据测试",
 "nickname": "测试作者昵称",
 "cover": "https://p3-sign.douyinpic.com/tos-cn-p-0015/test_cover.jpeg",
 "play": "https://aweme.snssdk.com/aweme/v1/play/?video_id=v0300fa70000bvotiif7dmhgj5pb3q90&media_type=4&ratio=720p&line=0"
}
ALL CHECKS PASSED
```

### 10.4 说明（大白话）

- "hook cached detail JSON: yes (610 chars)" → **hook 成功偷听到接口返回并缓存**。
- PARSED 里四个字段全部正确 → **Java 解析逻辑（复刻版）正确**。
- "ALL CHECKS PASSED" → 断言全过（标题包含测试文案、作者名对、播放地址含 `video_id=`、封面地址含 `test_cover`）。

> **这个验证的价值：** 它证明了"只要 detail 接口能返回真实 JSON，整条链路就能把元数据解析出来"。剩下的唯一变量是"真机上 detail 接口到底返不返回"——这是第 12 节的指纹问题。

---

## 11. 构建 APK：编译打包验证

### 11.1 编译

```bash
cd /tmp/opencode/huixing
export JAVA_HOME=/opt/jdk11
export PATH=$JAVA_HOME/bin:/opt/gradle/gradle-5.4.1/bin:$PATH
gradle :app:compileDebugJavaWithJavac --console=plain
```

**真实输出（成功）：**

```
BUILD SUCCESSFUL in 7s
50 actionable tasks: 1 executed, 49 up-to-date
```

### 11.2 打包

```bash
gradle :app:assembleDebug --console=plain
```

**真实输出（成功）：**

```
> Task :app:stripDebugDebugSymbols UP-TO-DATE
Compatible side by side NDK version was not found.   ← 这个警告可忽略（不用 NDK 的 strip）
> Task :app:mergeDexDebug
> Task :app:packageDebug
> Task :app:assembleDebug

BUILD SUCCESSFUL in 14s
86 actionable tasks: 4 executed, 82 up-to-date
```

### 11.3 产物

```
app/build/outputs/apk/debug/BPA_V1.3.1_20260809.apk   ← 约 23MB，24,313,851 字节
```

---

## 12. 真机 WebView 与无头环境的差别（指纹问题）

### 12.1 现象

在这个开发环境里（无头浏览器/curl），detail 接口的表现：

| 方式 | 结果 |
|------|------|
| `curl` 直接调 detail | HTTP 200，**0 字节** |
| playwright 无头 Chrome 打开页面，看页面自己调 detail | 监听不到返回（也是空的） |

### 12.2 原因：风控指纹

抖音的 detail 接口需要签名（`a_bogus` 等），而且风控会判断"来的是不是真浏览器"：

- **curl**：没有签名，直接拒（返回空）。
- **playwright 无头 Chrome**：浏览器签名缺失/异常（无头模式的 WebDriver 标记、字体、GPU、Canvas 指纹都跟真浏览器不一样），抖音识别出"这是自动化环境"，detail 也返回空。

### 12.3 为什么真机 WebView 大概率没问题

真机 App 里的 **Android 系统 WebView** 是完整的浏览器内核：

- **没有无头浏览器标记**，指纹跟普通 Chrome 一致。
- **有真实设备信息**（屏幕、GPU、字体、UA 与设备匹配）。
- **有正常 cookie 链**（从打开首页开始一路带过来）。

所以真机上页面脚本调 detail 时，抖音大概率判定为正常用户，返回真实详情 JSON。hook 就能缓存到真数据。

### 12.4 诚实说明局限

本环境**无法端到端验证真机上的真实 detail 返回**。所以验证做到"模拟 detail JSON + 链路正确解析"这一层。**建议拿到真机/抓包确认后的真实 detail 字段，对照第 9.2 节映射表核对一遍**，字段结构如有小差异，只需微调 `handleDouyinDetail`。

---

## 13. 避坑清单：所有失败经验汇总

这一节是本次排查过程中**真实踩过的坑**，每个都附了当时的失败现场和解决办法。

### 13.1 playwright 的 `*` 号不匹配 `/` 号（调了一天的大坑）

**现象：** 用 `page.route('**/aweme/v1/web/aweme/detail*', ...)` 拦截 detail 接口，死活拦不住，请求跑到了真网，返回空 JSON。

**原因：** playwright 的路由通配符里，**`*` 只匹配"不含 `/`"的字符**。detail 接口地址后面是 `/?aweme_id=...`，带着 `/`，所以 `*` 匹配不了。

**解决：** 用两个 `**`（双星，可以匹配含 `/`）：

```javascript
await page.route('**/aweme/v1/web/aweme/detail**', route => route.fulfill({
    status: 200, contentType: 'application/json', body: detailJson
}));
```

**教训：** 路由拦截不生效时，**先打印实际请求 URL**（`page.on('request', ...)`），跟 pattern 逐字符对，别猜。

### 13.2 `addScriptTag` 注入脚本不能带 `<script>` 标签

**现象：** 用 `page.addScriptTag({ content: hook })` 注入 hook，页面里 `window.fetch` 还是原生的，hook 完全没执行。

**原因：** `addScriptTag` 的 `content` 是要执行的**裸 JS 代码**。而我从 Java 源码里提取的 hook 字符串是带 `<script>...</script>` 标签的完整 HTML，直接塞进 JS 执行器就是语法错误。

**解决：** 先剥掉标签再注入：

```javascript
const hook = m[1].replace(/^<script>/, '').replace(/<\/script>$/, '');
```

**教训：** 判断"脚本有没有执行"，最直接的办法是看它改的东西：`window.fetch.toString().slice(0, 40)`——是 `function(){var u=arguments[0]...` 就说明被 hook 包了，还是 `[native code]` 就说明没生效。

### 13.3 about:blank 页面里 fetch 跨域直接失败

**现象：** 在 `page.setContent(html)` 造的空白页里，页面脚本 fetch detail 接口，报 `TypeError: Failed to fetch`，路由也没拦到。

**原因：** about:blank 页面的 origin 是 `null`，fetch 抖音的 https 接口属于跨域请求，被浏览器 CORS 拦下（模拟的响应没带 `Access-Control-Allow-Origin` 头）。

**解决（验证脚本里）：** 要么给路由 fulfill 加 CORS 头，要么**用同源页面**（页面地址就是 `https://www.douyin.com/video/...`，fetch 同源，没有 CORS 问题）。本项目验证用的是同源方案。**真实 App 里不存在这个问题**（页面本来就在 douyin.com 域下）。

### 13.4 `waitUntil: 'load'` 会超时

**现象：** `page.goto(videoUrl, { waitUntil: 'load', timeout: 60000 })` 超时。

**原因：** 抖音页面有大量第三方脚本/埋点/长连接资源，`load` 事件（所有资源加载完）永远等不到。

**解决：** 用 `domcontentloaded`（DOM 解析完就返回）再手动 `waitForTimeout` 或 `waitForFunction` 等 SPA 渲染：

```javascript
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(6000);
```

### 13.5 curl 调 detail 返回 200 但 0 字节

**现象：** `curl` 调 detail 接口返回 `HTTP 200, size 0`。

**原因：** 抖音对接口做签名校验（`a_bogus`），无签名请求返回空。**不要以为 200 就是成功**，要同时看 `size_download`。

**教训：** 一切接口测试，**把 `-w "\nHTTP %{http_code}, size %{size_download}\n"` 加进 curl**，避免被"200 空壳"误导。

### 13.6 `apt` 装不上 JDK 11

**现象：** `apt-get install -y openjdk-11-jdk-headless` 报 `E: Package 'openjdk-11-jdk-headless' has no installation candidate`。

**原因：** 系统源的 JDK 11 包不存在（源里只有 JDK 17）。

**解决：** 直接下载 Temurin JDK 11 二进制解压使用（见第 14 节）。

### 13.7 手动下载 Android platform-27 的 zip 是坏包

**现象：** 从某些镜像下载 `platform-27.zip`，只有 1449 字节，`unzip` 报 `End-of-central-directory signature not found`。

**原因：** 下载源返回了错误页面/空文件。

**解决：** 改用 `dl.google.com/android/repository/` 官方源的 zip，或直接用 `sdkmanager` 安装（见第 14 节）。**下载任何压缩包后先 `ls -la` 看大小**，几百字节必是坏包。

### 13.8 首次编译报 100 个 error（中间态）

**现象：** 改代码过程中跑 `gradle :app:compileDebugJavaWithJavac`，报 100 个 `class, interface, or enum expected`。

**原因：** 代码还没改完（括号不配对）就编译了。

**解决：** 改完整个逻辑再编译。**这种报错别逐条看，看第一条**（`error: class, interface, or enum expected` 后面全是连锁反应）。

### 13.9 一些无害警告

- `Compatible side by side NDK version was not found.`：不用 NDK，忽略。
- `Some input files use or override a deprecated API`：老项目的正常提示，忽略。

### 13.10 其它要点

- **minSdk=14** 决定了：`shouldInterceptRequest` 要写两个重载；`android.util.Base64` 可用（API 8+）。
- **fastjson**（`com.alibaba.fastjson`）项目已自带，直接用，不用新引库。
- hook 的地址匹配用 `indexOf(...) >= 0` 判断子串，比正则更省心、更不易错。

---

## 14. 构建环境搭建完整命令

本环境是全新搭的，按下面的顺序一步步来（成功路径）。**每条命令都先想清楚再执行。**

### 14.1 JDK 11

```bash
# 检查系统有没有 JDK
java -version

# apt 装 openjdk-11 会失败（源里没有），直接下载 Temurin JDK 11 解压
cd /tmp/opencode
curl -sL -o jdk11.tar.gz "https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.22%2B7/OpenJDK11U-jdk_x64_linux_hotspot_11.0.22_7.tar.gz"
mkdir -p /opt/jdk11
tar -xzf jdk11.tar.gz -C /opt/jdk11 --strip-components=1

# 验证
/opt/jdk11/bin/java -version
# 输出: openjdk version "11.0.22" 2024-01-16
```

### 14.2 Gradle 5.4.1

```bash
cd /tmp/opencode
curl -sL -o gradle-5.4.1-bin.zip "https://services.gradle.org/distributions/gradle-5.4.1-bin.zip"
mkdir -p /opt/gradle
unzip -q gradle-5.4.1-bin.zip -d /opt/gradle

# 验证
/opt/gradle/gradle-5.4.1/bin/gradle --version
```

> 为什么是 5.4.1：项目 `gradle-wrapper.properties` 里写的就是这个版本，AGP 3.5.3 配套。**用新版本 Gradle 会各种不兼容**，别乱升。

### 14.3 Android SDK（platform 27 + build-tools 27.0.3）

```bash
mkdir -p /opt/android-sdk
cd /opt/android-sdk

# platform（android-27）
curl -sL -o platform-27_r01.zip "https://dl.google.com/android/repository/platform-27_r01.zip"
unzip -q platform-27_r01.zip        # 解压出 android-27 目录

# build-tools 27.0.3
curl -sL -o build-tools_r27.0.3-linux.zip "https://dl.google.com/android/repository/build-tools_r27.0.3-linux.zip"
unzip -q build-tools_r27.0.3-linux.zip -d build-tools/27.0.3

# 补 licenses（Gradle 检查到没 license 会拒绝构建）
mkdir -p /opt/android-sdk/licenses
echo "d56f5187479451eabf01fb78af6dfcb131a6481e" > /opt/android-sdk/licenses/android-sdk-license
```

> **避坑：** 千万别从乱七八糟的镜像下 platform zip（坏包只有 1KB），一律用 `dl.google.com/android/repository/` 官方源。

### 14.4 让项目认识 SDK

在项目根目录建 `local.properties`：

```bash
echo "sdk.dir=/opt/android-sdk" > /tmp/opencode/huixing/local.properties
```

### 14.5 playwright（诊断工具）

```bash
npm install -g playwright
npx playwright install chromium
```

**真实输出：** `Chrome Headless Shell 151.0.7922.34 (playwright chromium-headless-shell v1234) downloaded to /root/.cache/ms-playwright/...`

> `npx playwright install chromium` 会下载约 115MB 的无头 Chrome，必须等它下载完。

### 14.6 一条龙构建命令

```bash
cd /tmp/opencode/huixing
export JAVA_HOME=/opt/jdk11
export PATH=$JAVA_HOME/bin:/opt/gradle/gradle-5.4.1/bin:$PATH
gradle :app:assembleDebug --console=plain
```

---

## 15. 命令速查表（可直接复制）

```bash
# 1) 查看最近提交，找元凶
git log --oneline -5
git show 196afa5 --stat

# 2) 看页面 DOM 里到底有什么（collect_diag.js）
NODE_PATH=$(npm root -g) node collect_diag.js

# 3) 测 detail 接口（注意看 size）
curl -s -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36" \
     -w "\nHTTP %{http_code}, size %{size_download}\n" \
     "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=7670020387090641531"

# 4) 跑链路验证
NODE_PATH=$(npm root -g) node verify_link2.js

# 5) 编译 + 打包
export JAVA_HOME=/opt/jdk11
export PATH=$JAVA_HOME/bin:/opt/gradle/gradle-5.4.1/bin:$PATH
gradle :app:compileDebugJavaWithJavac --console=plain
gradle :app:assembleDebug --console=plain

# 6) 看产物
ls -la app/build/outputs/apk/debug/
```

---

## 16. 常见问题 FAQ

**Q1：hook 会不会影响抖音页面本身的运行？**
不会。hook 只是"旁听"detail/post 接口的返回，不改动请求，不拦截、不篡改，返回原样透传给页面。万一 hook 出错，整体包在 `try{}catch(e){}` 里，静默失败，页面照常。

**Q2：为什么只有 `/video/` 和 `/note/` 页面才注入 hook？**
只有这两个页面才需要解析详情。首页、用户主页等不需要，注入越少越稳。

**Q3：`fetch` 和 `XMLHttpRequest` 为什么要都改？**
抖音页面两套都可能用。只改一个，另一个发请求就漏了。

**Q4：detail JSON 结构会不会变？**
有可能。但 `findAweme` 是递归找"同时有 `aweme_id + video + author` 的对象"，只要这三个字段还在，层级怎么变都能找到。字段名如果抖音改名，只需微调取值处（第 9.2 节映射表）。

**Q5：为什么用 base64 而不是直接把 JSON 塞进 div？**
原始 JSON 里的 `"`、`<`、`>`、换行会破坏 HTML 和 JS 字符串解析。base64 只含 `A-Za-z0-9+/=`，塞进 HTML 绝对安全。

**Q6：`gradle :app:assembleDebug` 报 NDK 警告要不要管？**
不用。`Compatible side by side NDK version was not found` 只影响 NDK 的 strip 工具，项目不编译原生 C/C++，忽略即可。

---

## 17. 给其他 agent 的接力指引

如果你接手继续优化，按这个思路走：

1. **拿到真机 detail 返回的真实 JSON**（真机 WebView + 抓包，或 Fiddler/Charles），对照第 9.2 节映射表核对字段：
   - `desc`、`author.nickname`、`video.cover.url_list[0]`、`video.play_addr.url_list[0]`、`video.bit_rate[0].play_addr.url_list[0]`
   - 若字段层级/名字有变，只改 `handleDouyinDetail` 的取值，不动 hook。
2. **若真机上 hook 没生效**，优先排查：
   - `isDouyinVideoPage` 的 URL 匹配（新链接路径变化？）
   - `fetchHtml` 下载失败（cookie 为空 / UA 被改）
   - `onPageFinished` 里的 `myLoadUrl(view, url, loadSourceJs(7000))` 是否在抖音分支执行（`url.contains("douyin.com")`）
   - `getSource` 脚本执行后 `div#__hx_dy_json` 是否存在（不存在就是 hook 没缓存到）
3. **快捷排查入口**：在 `loadSourceJs` 里临时把 `__HX_DY__` 的长度通过 `console.log` 打出来，或在 Java 端 `extractDyDetail` 返回 null 时打日志，判断断点在哪一环。
4. **不要动桌面 UA**：播放依赖它。若要动，请在真机上回归"播放 + 元数据"两项。
5. 本指南提到的验证脚本（`collect_diag.js`、`verify_link2.js`）都在 `/tmp/opencode/` 下，可直接改 URL 复用。

---

## 18. 附录：关键代码最终内容

### 18.1 DY_HOOK（MyWebViewClient.java，第 43 行）

```java
private static final String DY_HOOK = "<script>(function(){window.__HX_DY__=null;try{var f=window.fetch;if(f){window.fetch=function(){var u=arguments[0];var p=f.apply(this,arguments);try{var su=typeof u==='string'?u:(u&&u.url||'');if(su.indexOf('/aweme/v1/web/aweme/detail')>=0||su.indexOf('/aweme/v1/web/aweme/post')>=0){p.then(function(r){try{r.clone().text().then(function(t){if(t&&t.length>80){window.__HX_DY__=t;}});}catch(e){}});}}catch(e){}return p;}}var o=XMLHttpRequest.prototype.open;var s=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.open=function(m,u){this._hu=u;return o.apply(this,arguments);};XMLHttpRequest.prototype.send=function(){var x=this;try{var su=x._hu||'';if(su.indexOf('/aweme/v1/web/aweme/detail')>=0||su.indexOf('/aweme/v1/web/aweme/post')>=0){x.addEventListener('load',function(){try{if(x.responseText&&x.responseText.length>80){window.__HX_DY__=x.responseText;}}catch(e){}});}}catch(e){}return s.apply(this,arguments);};}catch(e){}})();</script>";
```

### 18.2 loadSourceJs（MyWebViewClient.java，第 52 行）

```java
private String loadSourceJs(int delayMs) {
    return "javascript:setTimeout(function(){var h=document.getElementsByTagName('html')[0].innerHTML;" +
            "var s='<head>'+h+'</head>';try{var d=window.__HX_DY__;if(d){d=btoa(unescape(encodeURIComponent(d)));" +
            "s='<head>'+h+'<div id=\"__hx_dy_json\" style=\"display:none;\">'+d+'</div></head>';}}catch(e){}" +
            "window.java_obj.getSource(s);}," + delayMs + ");";
}
```

### 18.3 shouldInterceptRequest 两个重载（MyWebViewClient.java，第 138/149 行）

```java
@Override
@SuppressWarnings("deprecation")
public WebResourceResponse shouldInterceptRequest(WebView view, String url) {
    if (isDouyinVideoPage(url)) {
        WebResourceResponse r = interceptDouyin(url);
        if (r != null) {
            return r;
        }
    }
    return super.shouldInterceptRequest(view, url);
}

@Override
public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
    if (request.isForMainFrame() && isDouyinVideoPage(request.getUrl().toString())) {
        WebResourceResponse r = interceptDouyin(request.getUrl().toString());
        if (r != null) {
            return r;
        }
    }
    return super.shouldInterceptRequest(view, request);
}
```

### 18.4 handleDouyinDetail / extractDyDetail / findAweme / firstUrl（WebviewFragment.java，第 516 行起）

```java
private String extractDyDetail(Document document) {
    try {
        Elements els = document.select("div#__hx_dy_json");
        if (els.isEmpty()) {
            return null;
        }
        String b64 = els.get(0).text();
        if (TextUtils.isEmpty(b64)) {
            return null;
        }
        return new String(Base64.decode(b64, Base64.DEFAULT), "UTF-8");
    } catch (Exception e) {
        return null;
    }
}

private boolean handleDouyinDetail(Document document, String dyDetail) {
    try {
        com.alibaba.fastjson.JSONObject json = com.alibaba.fastjson.JSONObject.parseObject(dyDetail);
        com.alibaba.fastjson.JSONObject aweme = findAweme(json);
        if (aweme == null) {
            return false;
        }
        com.alibaba.fastjson.JSONObject video = aweme.getJSONObject("video");
        if (video == null) {
            return false;
        }
        String desc = aweme.getString("desc");
        String nickname = null;
        com.alibaba.fastjson.JSONObject author = aweme.getJSONObject("author");
        if (author != null) {
            nickname = author.getString("nickname");
        }
        String cover = firstUrl(video.getJSONObject("cover"));
        if (cover == null) {
            cover = firstUrl(video.getJSONObject("origin_cover"));
        }
        String play = firstUrl(video.getJSONObject("play_addr"));
        if (play == null) {
            com.alibaba.fastjson.JSONArray br = video.getJSONArray("bit_rate");
            if (br != null && br.size() > 0) {
                play = firstUrl(br.getJSONObject(0).getJSONObject("play_addr"));
            }
        }
        if (play == null) {
            return false;
        }
        if (TextUtils.isEmpty(desc)) {
            desc = document.title();
            if (desc != null && desc.contains(" - ")) {
                desc = desc.substring(0, desc.lastIndexOf(" - ")).trim();
            }
        }
        if (!TextUtils.isEmpty(desc)) {
            currentMusic.setTitle(desc);
        }
        if (nickname != null && !nickname.isEmpty()) {
            currentMusic.setAlbum(nickname);
        }
        currentMusic.setArtist(play);
        Bundle bundle = new Bundle();
        if (!TextUtils.isEmpty(cover)) {
            bundle.putString("coverPath", cover);
        }
        bundle.putString("data", play);
        ViewUtils.sendMessage(webviewHandler, bundle);
        return true;
    } catch (Exception e) {
        return false;
    }
}

private com.alibaba.fastjson.JSONObject findAweme(Object o) {
    if (o instanceof com.alibaba.fastjson.JSONObject) {
        com.alibaba.fastjson.JSONObject obj = (com.alibaba.fastjson.JSONObject) o;
        if (obj.containsKey("aweme_id") && obj.containsKey("video") && obj.containsKey("author")) {
            return obj;
        }
        for (Object v : obj.values()) {
            com.alibaba.fastjson.JSONObject r = findAweme(v);
            if (r != null) {
                return r;
            }
        }
    } else if (o instanceof com.alibaba.fastjson.JSONArray) {
        com.alibaba.fastjson.JSONArray arr = (com.alibaba.fastjson.JSONArray) o;
        for (int i = 0; i < arr.size(); i++) {
            com.alibaba.fastjson.JSONObject r = findAweme(arr.get(i));
            if (r != null) {
                return r;
            }
        }
    }
    return null;
}

private String firstUrl(com.alibaba.fastjson.JSONObject obj) {
    if (obj == null) {
        return null;
    }
    com.alibaba.fastjson.JSONArray list = obj.getJSONArray("url_list");
    if (list != null && list.size() > 0) {
        return list.getString(0);
    }
    return null;
}
```
