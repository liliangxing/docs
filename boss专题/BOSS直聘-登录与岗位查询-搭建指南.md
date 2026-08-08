# BOSS直聘 浏览器自动化登录与岗位查询 搭建指南

> 本文档记录了一次完整的「用代码/Agent 自动登录 BOSS直聘并查询岗位」的尝试过程。
> 面向读者：**技术一般的普通人** 和 **后续接手继续突破的 AI Agent**。
> 写作原则：大白话、逐步记录命令、标注成功与失败、说明为什么这么做。
> 配套代码仓库：`https://github.com/liliangxing/boss2`（BOSS直聘 APK 反编译源码，内含 API 接口定义）
> 文档日期：2026-08-07

---

## 目录

1. [这个任务到底要干什么](#一这个任务到底要干什么)
2. [为什么不能用最简单的办法（curl）](#二为什么不能用最简单的办法curl)
3. [第一步：准备工作环境](#三第一步准备工作环境)
4. [第二步：浏览器访问 BOSS直聘（踩坑最多的地方）](#四第二步浏览器访问-boss直聘踩坑最多的地方)
5. [第三步：通过 GeeTest 图片验证码（成功经验）](#五第三步通过-geetest-图片验证码成功经验)
6. [第四步：进入登录页，填手机号发验证码](#六第四步进入登录页填手机号发验证码)
7. [第五步：网易易盾滑块验证（当前卡点）](#七第五步网易易盾滑块验证当前卡点)
8. [登录成功之后：查询岗位的 API 方案](#八登录成功之后查询岗位的-api-方案)
9. [调试命令大全（排查错误必备）](#九调试命令大全排查错误必备)
10. [核心工具脚本：gt_browser.py（持久浏览器控制台）](#十核心工具脚本gt_browserpy持久浏览器控制台)
11. [给后续 Agent 的交接说明](#十一给后续-agent-的交接说明)
12. [完整避坑清单（只看这一节也行）](#十二完整避坑清单只看这一节也行)

---

## 一、这个任务到底要干什么

**目标**：自动登录 BOSS直聘，查询「佛山、广州最近一周发布的、适合女性、无经验要求或只需简单电脑操作」的岗位，整理成一份 Markdown 文档。

**为什么不能手动做**：岗位多、要筛选、要整理成表格，手动太慢。希望用代码/Agent 自动化完成。

**整体思路（一句话）**：
> 用一个「能打开真实网页的浏览器」去访问 BOSS直聘 → 人工配合过一次验证码 → 登录 → 在浏览器里用 JS 调用 BOSS直聘的接口拿岗位数据 → 整理成 Markdown。

**为什么必须用浏览器**：BOSS直聘有很强的反爬机制，直接用 `curl` 调接口会被识别为异常环境，接口返回错误。这一点下面详细说。

---

## 二、为什么不能用最简单的办法（curl）

**结论先行：`curl` 直接调 BOSS直聘 API 必失败，会返回 `code: 37`（您的环境存在异常）。**

原因分析（大白话）：

1. BOSS直聘的前端页面里，有一个叫 `__zp_stoken__` 的加密令牌，是**网页里的 JS 代码在你打开页面的那一刻动态算出来的**，带有效时间和用户身份。
2. 这个令牌的算法在 `boss2` 仓库的反编译源码里有，但它需要浏览器环境才能算出正确的值。
3. `curl` 没有浏览器环境，就算你手动抓了 Cookie 带上，BOSS直聘还是能识别出「这个请求不是从正常浏览器发出的」，于是返回 `code: 37`。

**所以正确路径是**：让请求**真的从一个浏览器页面里发出**（用页面里的 `fetch` 函数），这样带上的令牌才是合法的。

> boss2 仓库里有一份更详细的官方教程文档：
> `boss2/docs/BOSS直聘API岗位获取搭建文档.md`
> 里面第九节写了怎么在浏览器里用 fetch 批量查岗位，第十节写了怎么整理成 Markdown。

---

## 三、第一步：准备工作环境

### 3.1 先搞清楚环境里有什么

```bash
# 查看 Python 和 Node 版本（浏览器自动化两种语言都能写）
python3 --version
node --version
npm --version

# 查看系统里有没有装浏览器
which chromium chromium-browser google-chrome firefox

# 查看有没有装浏览器自动化库
python3 -c "import playwright; print('playwright ok')"
node -e "require('puppeteer')"
```

**我们当时的输出**：
- Python 3.11.2，Node v22.22.0 —— 都有
- chromium/chrome/firefox —— **全都没有**
- playwright / puppeteer —— **都没装**

> ⚠️ **避坑**：这个环境是干净的 Linux 服务器（没有图形界面、没有浏览器），所以要全部自己装。如果你的环境有浏览器，可以跳过装浏览器的部分，直接装自动化库。

### 3.2 安装浏览器自动化库（Playwright）

我们选 **Python 的 Playwright**（比 puppeteer 好装、文档全、操作简单）。

```bash
pip3 install --break-system-packages -q playwright
```

> `--break-system-packages` 是因为新版 Debian/Ubuntu 系统对 pip 全局安装有保护，加了这个参数才允许装到系统全局。
> `-q` 是安静模式，少打印日志。

装完确认一下：

```bash
python3 -c "import playwright; print('playwright ok')"
```

### 3.3 下载浏览器内核（Chromium）

Playwright 只是个「遥控器」，还需要真的浏览器内核才能干活。下载它：

```bash
python3 -m playwright install chromium --with-deps
```

- `chromium`：下载 Chrome 内核（headless shell，约 115MB）
- `--with-deps`：顺便安装浏览器运行所需的系统库（这一步很重要，缺了库浏览器起不来）

> 这个过程会等一会，看到下载进度条走完就说明好了。
> 如果中途网络慢失败，重跑一遍同样的命令即可（会断点续传）。

### 3.4 验证：让浏览器真的打开 BOSS直聘

写一小段测试代码，用浏览器访问 BOSS直聘首页：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)   # headless = 无头模式（不弹窗口）
    pg = b.new_page()
    pg.goto('https://www.zhipin.com/', timeout=30000)
    print('TITLE:', pg.title())
    print('URL:', pg.url)
    b.close()
```

**当时输出**：
```
TITLE: BOSS直聘-找工作BOSS直聘直接谈！招聘求职找工作！
URL: https://www.zhipin.com/beijing/?seoRefer=index
```

✅ **成功**：浏览器能打开 BOSS直聘首页，能拿到页面标题。环境搭建完成。

> 💡 大白话解释上面的代码：
> - `sync_playwright()` 开启一个遥控器
> - `chromium.launch()` 启动浏览器（headless 就是不开窗口，在后台跑）
> - `new_page()` 开一个标签页
> - `goto()` 让这个标签页访问指定网址
> - `title()` / `url` 读出页面的标题和地址

---

## 四、第二步：浏览器访问 BOSS直聘（踩坑最多的地方）

环境搭好了，接下来正式登录。这一步我们踩了好几个坑，**每一个都值得记录**。

### 4.1 坑①：直接访问登录页，页面被 JS 跳转到空白页

**尝试**：直接访问登录页 `https://www.zhipin.com/web/user/`

**结果**：页面加载完所有资源后，URL 变成了 `about:blank`（空白页），啥也没有。

**排查过程**（这一步怎么发现的）：

在浏览器里监听所有网络请求，看页面到底干了什么：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.on('request', lambda r: print('REQ:', r.url[:100]))
    pg.on('response', lambda r: print('RESP:', r.status, r.url[:100]))
    pg.goto('https://www.zhipin.com/web/user/', timeout=30000)
    pg.wait_for_timeout(4000)
    print('FINAL URL:', pg.url)
    b.close()
```

**发现**：登录页的 JS 文件（`user-sign.js`、`user-login.js`）都正常加载了，说明网络没问题；但页面里的 JS 执行后把页面跳转到了 `about:blank`。

**结论**：BOSS直聘检测到我们用的是「无头浏览器」（headless），故意把页面跳空，不给你看登录页。

> 💡 大白话：就像银行柜台看你戴了口罩墨镜，觉得你形迹可疑，直接把窗口关了。
> headless 浏览器有几个「指纹」特征（比如没有窗口、`navigator.webdriver` 为 true），反爬系统靠这些认出来的。

### 4.2 坑②：访问首页，被重定向到「安全验证」页（IP 风控）

**尝试**：换个思路，先访问首页 `https://www.zhipin.com/`，再找登录入口。

**结果**：URL 被重定向到了：
```
https://www.zhipin.com/web/passport/zp/verify.html?callbackUrl=...
```

页面标题：`安全验证 - BOSS直聘`，内容大致是：

```
安全验证
当前 IP 地址可能存在异常访问行为，完成验证后即可正常使用。
为了您的账户安全，请完成以下验证
点击按钮进行验证
```

**结论**：我们这台服务器（云主机）的 IP 被 BOSS直聘标记为「异常 IP」，进入任何页面都会先弹安全验证，验证通过后才放行。

> 💡 大白话：BOSS直聘把「机房 IP / 数据中心 IP」单独标记。普通家用宽带 IP 访问没这个验证，但我们这种云服务器 IP 一上来就被拦。
> 这个 IP 风控**跟 headless 无关**——就算用有窗口的浏览器也一样被拦。

### 4.3 尝试绕过坑①：换有窗口模式（headful）

headless 被认出来了，那就试试有窗口模式？Linux 服务器没有显示器，用 `xvfb`（虚拟显示器）顶替。

**先装依赖**（xvfb 的配套工具）：

```bash
apt-get install -y xauth
```

> `xauth` 是 xvfb 需要的辅助工具，缺了它 `xvfb-run` 会报 `xauth command not found`。

**用 xvfb 跑有窗口的浏览器**：

```bash
xvfb-run -a python3 your_script.py
```

其中 `your_script.py` 里 `chromium.launch(headless=False)`（不开 headless）。

**结果**：仍然是 `verify.html` 安全验证页。

**结论**：IP 风控是绕不开的第一道坎，不管 headless 还是有窗口，都要先过安全验证。只能老实做验证码。

### 4.4 小结：访问 BOSS直聘的「地形图」

到这一步，我们搞清楚了访问 BOSS直聘要闯几道关：

```
访问任意页面
    │
    ▼
① IP 风控：verify.html 安全验证  ←── 必过，我们卡在这的第一步
    │  （点按钮 → 弹出 GeeTest 图片验证码）
    ▼
② 验证通过 → 才放行到真正页面
    │
    ▼
③ 登录页 /web/user/  ── 登录时还有第二道验证码（网易易盾滑块）
```

**成功路径**：`verify.html 安全验证` → `GeeTest 3x3 图片点选` → 通过 → `登录页` → `填手机号+发验证码` → `网易易盾滑块` → 登录成功。

下面分别讲每一步怎么过。

---

## 五、第三步：通过 GeeTest 图片验证码（成功经验）

### 5.1 验证页长什么样

`verify.html` 页面上有一个按钮（class 是 `geetest_radar_btn`，中文提示「点击按钮进行验证」）。点它之后会弹出一个 GeeTest 验证码弹窗：

![GeeTest 验证码弹窗](images/boss-zhipin-login/01-geetest-captcha-full.png)

**验证码类型**：3x3 图片点选验证。弹窗顶部写着「请选中下图中所有的：」后面跟着一个**物体小图标**，下面是 3x3 共 9 张图片，要求你点选所有「包含目标物体」的格子。

![GeeTest 3x3 网格](images/boss-zhipin-login/02-geetest-grid.jpg)

> 💡 大白话：像小学的「找一找」，题目说「找出所有的小汽车」，你就在下面 9 张图里把有小汽车的格子点一遍，然后点「确认」。

### 5.2 怎么让程序把验证码「弹出来」

写代码：打开 verify 页 → 点验证按钮 → 验证码弹窗出现。

```python
pg.goto('https://www.zhipin.com/web/passport/zp/verify.html?callbackUrl=...', timeout=30000)
pg.wait_for_timeout(4000)
btn = pg.query_selector('.geetest_radar_btn')
btn.click()
pg.wait_for_timeout(6000)
```

### 5.3 怎么把验证码内容「抓出来」给人工看

验证码弹窗里有两类关键东西：

1. **9 个格子的图片**（class 是 `geetest_item_img`），它们的 `src` 就是图片地址；
2. **提示要选的物体图标**（class 是 `geetest_tip_img`），它的 `background-image` 里有图片地址。

抓取它们的地址：

```python
# 抓 9 个格子的图片地址（第一个格子的 src 就代表整张网格图）
imgs = pg.query_selector_all('.geetest_item_img')
grid_url = imgs[0].get_attribute('src')

# 抓提示图标地址
tip = pg.query_selector('.geetest_tip_img')
style = tip.get_attribute('style')
import re
m = re.search(r'url\("([^"]+)"\)', style)
tip_url = m.group(1)
```

再把网格图下载到本地：

```python
import urllib.request
req = urllib.request.Request(grid_url, headers={'User-Agent':'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=20).read()
open('/tmp/captcha_grid.jpg', 'wb').write(data)
```

> 💡 大白话：图片地址长这样 `https://static.geetest.com/captcha_v3/.../xxx.jpg?challenge=...`。
> 直接下载就能得到验证码图片。

**顺便抓 9 个格子的坐标**（后面点击要用）：

```python
items = pg.query_selector_all('.geetest_item_wrap')
for i, it in enumerate(items):
    box = it.bounding_box()   # 得到 {x, y, width, height}
    cx = box['x'] + box['width']/2
    cy = box['y'] + box['height']/2
    print(f'格子{i}: 中心({cx:.0f},{cy:.0f})')
```

**格子编号规则**（后面让用户报编号用）：
```
1左上  2上中  3右上
4中左  5正中  6中右
7左下  8下中  9右下
```

### 5.4 让图片能被「人」看到（两个方案）

验证码是图片，程序自己认不出来（我们当时 AI 的识图服务余额不足），所以把图片发给**人**来看。

**方案 A（推荐）：起一个本地图片服务器 + 获取预览链接**

```bash
# 先把图片放到一个目录
mkdir -p /tmp/captcha_view
cp captcha_grid.jpg snap.png /tmp/captcha_view/

# 在后台起一个最简单的 HTTP 文件服务器
python3 -m http.server 8899 --bind 0.0.0.0
```

然后给这个端口申请一个公网预览链接（平台能力），把链接发给用户，用户就能在浏览器里看到验证码图片了。

> 💡 大白话：`python3 -m http.server 8899` 是 Python 自带的最简网页服务器，把当前目录里的文件以网页形式暴露出去。访问 `http://地址:8899/文件名` 就能看到对应文件。

**方案 B：上传到云存储 OSS 拿临时链接**

获取一个临时上传地址，然后：

```bash
curl -s -X PUT -H "Content-Type: image/jpeg" --upload-file captcha_grid.jpg "https://...上传地址..."
```

上传完会得到一个可访问的 URL，发给用户也行。

> ⚠️ 避坑：OSS 临时链接**10 分钟过期**，过期后图片就看不到了，需要重新上传。

### 5.5 用户识别后，程序点击格子并确认

用户看完图片，告诉你「要点 3、6、7、8 号格子」。程序执行：

```python
# 按中心坐标点格子（格子3 中心 x=754,y=408，以此类推）
pg.mouse.click(754, 408)   # 格子3
pg.mouse.click(754, 521)   # 格子6
pg.mouse.click(530, 633)   # 格子7
pg.mouse.click(642, 633)   # 格子8

# 点「确认」按钮
pg.click('text=确认')
pg.wait_for_timeout(3000)
```

**验证结果**：页面出现「验证成功,正在为您跳转中...」，验证码通过！

✅ **这一段是完整的成功经验**：IP 风控的 GeeTest 验证码 = 点击弹出 → 抓图发给人看 → 人报格子号 → 程序点格子 + 点确认 → 通过。

> ⚠️ 避坑：
> 1. 验证码有**时效性**（约 1 分钟），用户看图片太久、或者程序点慢了，验证码会过期，需要点「刷新验证」重新来。
> 2. 点格子之前**先确认验证码没变**：重新抓一次 `grid_url`，和之前对比，一样才点。
> 3. 验证失败时页面会跳到空白（about:blank），这时要点「刷新验证」重新走一遍。

---

## 六、第四步：进入登录页，填手机号发验证码

### 6.1 跳转到登录页

```python
pg.goto('https://www.zhipin.com/web/user/', timeout=30000)
pg.wait_for_timeout(5000)
```

看到登录页内容（「验证码登录/注册」「我要找工作」「我要招聘」等）就说明进来了：

![登录页](images/boss-zhipin-login/03-login-page.png)

### 6.2 填手机号

```python
phone = '13477975671'
el = pg.query_selector('input[name=tel], input[name=phone], input[placeholder*=手机号]')
el.click()
pg.keyboard.press('Control+A')   # 全选（防止残留内容）
pg.keyboard.type(phone)
```

> 💡 大白话：`query_selector` 在页面里找一个输入框。BOSS直聘登录框的 name 是 `tel`（手机号）。先点一下让光标进去，再全选清空，再输入手机号。

### 6.3 点「发送验证码」→ 触发第二道验证码

```python
pg.click('text=发送验证码')
pg.wait_for_timeout(1500)
```

**结果**：页面下方弹出一个**网易易盾滑块验证**：「向右拖动滑块填充拼图」。

![网易易盾滑块](images/boss-zhipin-login/04-yidun-slider.png)

> ⚠️ 注意：短信验证码要先过这个滑块才能真的发出去。滑块不过，短信不会发，手机收不到验证码。
> 这个滑块就是**当前的卡点**，见下一节。

---

## 七、第五步：网易易盾滑块验证（当前卡点）

### 7.1 滑块验证码的结构（先搞懂再动手）

网易易盾滑块由三部分组成：

1. **背景图**：一张大图，上面有一个「凹槽」（缺口），图片地址在 `.yidun_bg-img` 的 src；
2. **拼图块**：一块小图，要拖到凹槽里，图片地址在 `.yidun_jigsaw` 的 src，图里就是拼图块的形状（带透明背景）；
3. **滑块按钮**：class 是 `yidun_slider`，按住它向右拖动，拼图块跟着移动。

![滑块背景图（带缺口）](images/boss-zhipin-login/05-slider-bg.png)

![拼图块](images/boss-zhipin-login/06-jigsaw.png)

**要解决的问题**：算出滑块要拖多远 = 凹槽（缺口）的水平位置 − 滑块起始位置。

### 7.2 尝试①：用 JS 模拟鼠标事件（失败）

**思路**：直接在页面里用 JS 伪造 mousedown / mousemove / mouseup 事件，骗过滑块。

```python
# 通过页面的 JS 伪造鼠标事件（❌ 失败）
pg.evaluate("""
  (() => {
    const slider = document.querySelector('.yidun_slider');
    const r = slider.getBoundingClientRect();
    const sx = r.x + r.width/2, sy = r.y + r.height/2;
    // ... 分步触发 mousemove 到目标 x ...
  })()
""")
```

**结果**：拖完了，滑块**弹回原位**（class 里的 `--hover` 状态都没了），验证失败。

**原因**：网易易盾对鼠标事件的校验很严。它检测的是**真实的输入设备事件**（有硬件坐标、有事件序列特征），纯 JS 伪造的事件会被识破。

> 💡 大白话：易盾像个严格的考官，JS 伪造的鼠标动作是「照稿念」，它一眼就看出你在演戏，直接判失败。

### 7.3 尝试②：用 Playwright 真实鼠标拖拽（失败但更接近了）

**改进**：不用 JS 伪造，改用 Playwright 的 `mouse` 系列 API（这个是浏览器真实输入管线，比 JS 伪造真实得多）。

```python
def human_drag(pg, sx, sy, tx, ty):
    import time, random
    pg.mouse.move(sx, sy)     # 先移到滑块上
    pg.mouse.down()            # 按住
    steps = 30 + random.randint(0, 10)
    for i in range(1, steps + 1):
        progress = i / steps
        ease = 1 - (1 - progress) ** 3     # 缓动曲线，模拟人手先慢后快的节奏
        x = sx + (tx - sx) * ease
        y = sy + (ty - sy) * ease + random.uniform(-1.5, 1.5)  # 加一点抖动
        pg.mouse.move(x, y)
        time.sleep(random.uniform(0.008, 0.02))   # 每步间隔
    pg.mouse.move(tx, ty)
    time.sleep(0.1)
    pg.mouse.up()             # 松手
```

**当时尝试**：直接拖到最右端（`x=582` 拖到 `x=919`，轨道右边界）。

**结果**：滑块还是弹回原位，验证失败。

**分析**：这次拖动动作本身是真实的，但**拖动的距离不对**——缺口不在最右端，拖过头了。网易易盾的判定是「拼图块是否正好对准凹槽」，差太多就失败。

### 7.4 缺口定位：为什么不能随便拖

正确的做法是：**先算出缺口位置，再精准拖过去**。当时的尝试（都还没成功，记录供后续参考）：

**尝试 A：OpenCV 检测圆**（因为提示是「选所有圆」，缺口是圆形）

```bash
pip3 install --break-system-packages -q opencv-python-headless
```

```python
import cv2, numpy as np
img = cv2.imread('bg.png')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20,
                           param1=100, param2=20, minRadius=5, maxRadius=30)
```

**结果**：检测出几百个圆（背景图里圆形物体太多），分不清哪个是缺口。❌ 此路不通。

**尝试 B：OCR 定位文字**

```bash
apt-get install -y tesseract-ocr
```

```python
# 提取背景图中所有文字的位置
tesseract bg.png stdout --psm 11 tsv
```

**结果**：OCR 识别结果乱七八糟（背景图是图片不是文字，OCR 误识别），无法定位。❌ 此路不通。

### 7.5 用户的宝贵提示（重要线索）

在尝试过程中，用户提示了一个关键信息：

> **滑块的最左侧要对齐背景图里「BOSS」字样中字母 O 的中心。**

也就是说：
- 背景图里有一段 **BOSS** 文字（很可能是 BOSS直聘 logo 或水印）；
- 目标对准位置 = BOSS 中第二个字母 **O** 的水平中心；
- 滑块**左边缘**（不是中心）要对齐这个中心。

**还没完成的部分**（给后续接手的你）：
1. 拿到背景图，定位「BOSS」文字中字母 O 的水平中心 x 坐标；
2. 计算拖动距离 = O 中心 x − 滑块左边缘 x（滑块左边缘在 x≈582）；
3. 用 7.3 节的真实鼠标拖拽函数拖过去；
4. 松手后检查滑块是否成功（成功时滑块区域会消失/出现验证通过的提示）；
5. 成功后马上点「发送验证码」，手机收到短信后填入并登录。

> 💡 定位 O 字母中心的思路建议：
> - 用模板匹配：下载拼图块图片（`jigsaw.png`，就是缺口形状），在背景图里做模板匹配找缺口位置，这是网易易盾通用的解法；
> - 或者：人工看背景图截图，直接报出 O 中心的大概 x 坐标（背景图显示区域从 x≈581 开始，宽≈358，人可以按比例估算）；
> - 或者：给背景图加网格线（参考我们用 PIL 加网格的做法），让人报格子序号再换算坐标。

---

## 八、登录成功之后：查询岗位的 API 方案

登录成功后，接下来的动作 boss2 仓库的文档写得很清楚，这里搬运核心思路：

### 8.1 在浏览器里用 fetch 查岗位

```javascript
// 在浏览器控制台执行（关键：credentials: 'include' 带上登录 Cookie）
fetch('https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=' +
  encodeURIComponent('文员') + '&city=101280800&page=1&pageSize=30', {
  credentials: 'include',
  headers: { 'Accept': 'application/json' }
})
.then(r => r.json())
.then(d => {
  window._jobData = d.zpData.jobList.map(j => ({
    jobName: j.jobName, company: j.brandName, salary: j.salaryDesc,
    experience: j.jobExperience, degree: j.jobDegree,
    city: j.cityName, district: j.areaDistrict, business: j.businessDistrict,
    skills: j.skills, labels: j.jobLabels, industry: j.brandIndustry,
    welfare: j.welfareList,
    bossName: j.bossName, bossTitle: j.bossTitle, jobId: j.encryptJobId
  }));
})
```

**关键参数**：
- `query`：搜索关键词（中文要 `encodeURIComponent` 编码，如「文员」→ `%E6%96%87%E5%91%98`）
- `city`：城市代码。佛山 = `101280800`，广州 = `101280100`
- `pageSize`：每页条数，最大 30
- `scene=1`：找工作场景

**城市代码对照**（来自 boss2 文档/源码）：
| 城市 | city 代码 |
|------|----------|
| 广州 | 101280100 |
| 佛山 | 101280800 |

### 8.2 常用搜索关键词

| 关键词 | URL 编码 |
|--------|---------|
| 文员 | %E6%96%87%E5%91%98 |
| 客服 | %E5%AE%A2%E6%9C%8D |
| 前台 | %E5%89%8D%E5%8F%B0 |
| 数据录入 | %E6%95%B0%E6%8D%AE%E5%BD%95%E5%85%A5 |

### 8.3 API 返回的状态码含义

| code | 含义 | 处理 |
|------|------|------|
| 0 | 成功 | 正常处理 |
| 37 | 环境异常（限流/风控） | 等 2-3 秒重试，或换浏览器环境 |

> ⚠️ 避坑：**别连续疯狂请求**，每次请求间隔 2-3 秒，否则会被限流（code:37）。用 setTimeout 分批慢慢查。

### 8.4 筛选「适合女性、无经验、简单电脑操作」岗位

- 关键词优先：文员、客服、前台、数据录入、行政助理、资料整理
- 经验要求：优先 `jobExperience` 为「经验不限」「在校/应届」「1年以内」的
- 学历：`jobDegree` 优先「学历不限」「高中」「大专」
- 发布时间：接口返回里有岗位刷新时间，选最近一周内的

### 8.5 整理成 Markdown

拿到数据后按「城市 → 岗位类型」分组，整理成表格：

```markdown
# 佛山&广州岗位推荐整理

> 数据来源：BOSS直聘 API 实时查询
> 查询时间：2026-08-07

## 一、佛山市岗位

### 1. 文员类岗位

| 序号 | 岗位名称 | 公司 | 经验要求 | 学历 | 区域 | 福利亮点 |
|------|---------|------|---------|------|------|---------|
| 1 | 文职录入文员 | 银雁科技 | 经验不限 | 大专 | 南海区 | 五险一金 |
```

---

## 九、调试命令大全（排查错误必备）

这一节是排查问题时最常用的命令，都是真实用过的。

### 9.1 查看页面当前状态（URL、标题、Cookie）

```python
pg.evaluate("window.location.href")        # 当前 URL
pg.evaluate("document.title")              # 页面标题
pg.evaluate("document.cookie")             # 当前所有 Cookie
pg.evaluate("document.body.innerText.substring(0,500)")  # 页面可见文字前500字
```

> 💡 大白话：`pg.evaluate()` 就是在页面里执行一段 JS 并把结果返回给你。看页面状态全靠它。

### 9.2 截图看页面长什么样

```python
pg.screenshot(path='/tmp/snap.png')                       # 截当前可见区域
pg.screenshot(path='/tmp/snap.png', full_page=True)       # 截整个页面（长图）
element.screenshot(path='/tmp/elem.png')                  # 截某个元素
```

> ⚠️ 避坑：给元素截图时如果元素不可见（比如被 CSS 隐藏），会一直等不到，报 timeout。这时改成截全屏。

### 9.3 判断当前是不是登录页 / 验证页

```python
pg.evaluate("window.location.href.includes('/web/user/')")   # 是否登录页
pg.evaluate("window.location.href.includes('/verify')")      # 是否验证页
```

### 9.4 检查验证码是否过期（点格子前必做）

```python
# 重新抓验证码图地址，和之前对比
pg.evaluate("document.querySelectorAll('.geetest_item_img')[0].getAttribute('src')")
```

### 9.5 检查登录是否成功

```python
pg.evaluate("document.cookie.includes('__zp_stoken__')")   # 是否拿到了登录令牌
```

> 💡 `__zp_stoken__` 是登录后的关键 Cookie，有它才说明登录成功。

### 9.6 测试 API 连通性

```javascript
// 在浏览器里执行，只测通不通
fetch('https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=test&city=101280800&page=1&pageSize=1', {
  credentials: 'include'
}).then(r => r.json()).then(d => {
  console.log('code:', d.code, 'msg:', d.message, '条数:', d.zpData?.jobList?.length || 0);
})
```

### 9.7 检查元素存不存在 / 位置在哪

```python
# 查滑块在不在，以及它的位置
pg.evaluate("(() => { var s = document.querySelector('.yidun_slider'); if(!s) return 'none'; var r = s.getBoundingClientRect(); return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height}) })()")
```

---

## 十、核心工具脚本：gt_browser.py（持久浏览器控制台）

调试过程中写了一个**持久的浏览器控制台脚本**，通过往一个命令文件里写命令来控制浏览器，非常实用，后续接手的 Agent 可以直接复用。

**为什么需要它**：每次跑一个 Python 脚本就开一个浏览器、验证码全部作废，效率太低。这个脚本让**一个浏览器一直开着**，我随时给它发命令（跳转、点击、拖动、执行 JS），它把结果和截图写出来。

**使用方法**：

```bash
# 1. 启动（后台运行）
nohup python3 -u gt_browser.py > gt_browser.log 2>&1 &

# 2. 发命令（往命令文件写一行命令）
echo "STATUS" > gt_cmd.txt            # 看状态+截图
echo "GOTO_LOGIN" > gt_cmd.txt        # 去登录页
echo "FILL_PHONE:13477975671" > gt_cmd.txt   # 填手机号
echo "SEND_SMS" > gt_cmd.txt          # 发验证码
echo "CLICK:530:521" > gt_cmd.txt     # 点某坐标
echo "DRAG:602:400:919:400" > gt_cmd.txt     # 鼠标拖拽
echo "EVAL:document.title" > gt_cmd.txt      # 执行任意 JS

# 3. 看结果
tail -5 gt_browser.log
```

**支持的命令列表**：

| 命令 | 作用 |
|------|------|
| `STATUS` | 保存状态、截图 |
| `GOTO_LOGIN` | 跳转登录页（若被弹回验证页会自动点验证按钮） |
| `CLICK:x:y` | 鼠标点击坐标 (x,y) |
| `CONFIRM` | 点击「确认」按钮 |
| `REFRESH` | 刷新验证码 |
| `DRAG:sx:sy:tx:ty` | 真实鼠标拖拽（带人手缓动曲线） |
| `FILL_PHONE:手机号` | 填手机号 |
| `FILL_CODE:验证码` | 填短信验证码 |
| `SEND_SMS` | 点发送验证码 |
| `SUBMIT_LOGIN` | 点登录/注册 |
| `EVAL:js代码` | 执行任意 JS |
| `GOTO:url` | 跳转任意地址 |
| `EXIT` | 退出 |

**完整脚本代码**：

```python
import json
import os
import random
import time

from playwright.sync_api import sync_playwright

CMD_FILE = "/tmp/opencode/gt_cmd.txt"
STATE_FILE = "/tmp/opencode/gt_state.json"
SNAP_DIR = "/tmp/opencode/snapshots"
PROFILE = "/tmp/opencode/pw_profile"

os.makedirs(SNAP_DIR, exist_ok=True)
os.makedirs(PROFILE, exist_ok=True)


def save_state(pg):
    state = {"url": pg.url, "title": pg.title(), "cookies": ""}
    try:
        state["cookies"] = pg.evaluate("document.cookie")
    except Exception:
        pass
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def human_drag(pg, sx, sy, tx, ty):
    pg.mouse.move(sx, sy)
    pg.mouse.down()
    steps = 30 + random.randint(0, 10)
    for i in range(1, steps + 1):
        progress = i / steps
        ease = 1 - (1 - progress) ** 3
        x = sx + (tx - sx) * ease
        y = sy + (ty - sy) * ease + random.uniform(-1.5, 1.5)
        pg.mouse.move(x, y)
        time.sleep(random.uniform(0.008, 0.02))
    pg.mouse.move(tx, ty)
    time.sleep(0.1)
    pg.mouse.up()
    return f"dragged {sx},{sy} -> {tx},{ty}"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch_persistent_context(
            PROFILE,
            headless=True,
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        pg = b.new_page()
        pg.goto(
            "https://www.zhipin.com/web/passport/zp/verify.html?callbackUrl=https%3A%2F%2Fwww.zhipin.com%2F",
            timeout=30000,
        )
        pg.wait_for_timeout(4000)
        try:
            btn = pg.query_selector(".geetest_radar_btn")
            if btn:
                btn.click()
                pg.wait_for_timeout(5000)
        except Exception:
            pass
        save_state(pg)
        pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
        with open(CMD_FILE, "a") as f:
            f.write("READY\n")

        while True:
            time.sleep(2)
            if not os.path.exists(CMD_FILE):
                continue
            with open(CMD_FILE) as f:
                lines = f.readlines()
            if not lines:
                continue
            cmd = lines[-1].strip()
            if cmd == "READY":
                continue
            with open(CMD_FILE, "w") as f:
                f.write("READY\n")

            if cmd == "STATUS":
                save_state(pg)
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd.startswith("CLICK:"):
                parts = cmd.split(":")
                if len(parts) >= 3:
                    x, y = float(parts[1]), float(parts[2])
                    pg.mouse.click(x, y)
                    pg.wait_for_timeout(800)
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd == "CONFIRM":
                pg.click("text=确认")
                pg.wait_for_timeout(3000)
                save_state(pg)
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd == "REFRESH":
                try:
                    pg.click("text=刷新验证")
                except Exception:
                    pass
                pg.wait_for_timeout(3000)
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd == "GOTO_LOGIN":
                pg.goto("https://www.zhipin.com/web/user/", timeout=30000)
                pg.wait_for_timeout(5000)
                if "/web/passport/zp/verify" in pg.url:
                    try:
                        btn = pg.query_selector(".geetest_radar_btn")
                        if btn:
                            btn.click()
                            pg.wait_for_timeout(5000)
                    except Exception:
                        pass
                save_state(pg)
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd.startswith("DRAG:"):
                parts = cmd.split(":")
                if len(parts) >= 5:
                    sx, sy, tx, ty = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    print("DRAG_RESULT:", human_drag(pg, sx, sy, tx, ty))
                pg.wait_for_timeout(2500)
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd == "SEND_SMS":
                try:
                    pg.click("text=发送验证码")
                    pg.wait_for_timeout(1500)
                except Exception:
                    pass
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd == "SUBMIT_LOGIN":
                try:
                    pg.click("text=登录/注册")
                except Exception:
                    pass
                pg.wait_for_timeout(5000)
                save_state(pg)
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd.startswith("FILL_PHONE:"):
                phone = cmd.split(":", 1)[1]
                try:
                    el = pg.query_selector("input[name=tel], input[name=phone], input[placeholder*=手机号]")
                    if el:
                        el.click()
                        pg.keyboard.press("Control+A")
                        pg.keyboard.type(phone)
                except Exception:
                    pass
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd.startswith("FILL_CODE:"):
                code = cmd.split(":", 1)[1]
                try:
                    el = pg.query_selector("input[name=code], input[placeholder*=验证码], input[placeholder*=短信]")
                    if el:
                        el.click()
                        pg.keyboard.type(code)
                except Exception:
                    pass
                pg.screenshot(path=os.path.join(SNAP_DIR, "snap.png"))
            elif cmd.startswith("EVAL:"):
                expr = cmd.split(":", 1)[1]
                try:
                    r = pg.evaluate(expr)
                    print("EVAL_RESULT:", str(r)[:2000])
                except Exception as e:
                    print("EVAL_ERROR:", e)
            elif cmd == "EXIT":
                print("EXIT")
                b.close()
                break


if __name__ == "__main__":
    main()
```

> ⚠️ 两个踩过的坑，脚本里已经修好：
> 1. `save_state` 读取 cookie 时，如果页面是空白页（about:blank）会报 `SecurityError` 导致整个脚本崩溃。已加 try/except 保护。
> 2. `launch_persistent_context` + 持久化 profile 目录：保证浏览器重启后 Cookie 还在，不用每次重新过验证码。（但我们实测重启后验证 Cookie 没有保留，仍需注意。）

---

## 十一、给后续 Agent 的交接说明

如果你是要接着完成这个任务的 Agent，请先看这里：

### 当前进度

- ✅ 环境搭好（playwright + chromium 已装）
- ✅ 搞清了访问链路（IP 风控 → GeeTest → 登录页 → 网易易盾滑块）
- ✅ GeeTest 图片验证码已成功通过（人工配合）
- ✅ 已进入登录页，手机号 `13477975671` 已填入
- ❌ **卡在网易易盾滑块**：直接拖到最右失败，用户提示「滑块左边缘要对齐背景图里 BOSS 字样中 O 字母的中心」，尚未完成

### 下一步任务清单（按顺序）

1. **重新启动持久浏览器**（如果已停止）：
   ```bash
   cd /tmp/opencode
   nohup python3 -u gt_browser.py > gt_browser.log 2>&1 &
   ```
2. **重新触发滑块**：`GOTO_LOGIN` 后 `FILL_PHONE:13477975671` → `SEND_SMS`
3. **定位缺口**：下载背景图（`.yidun_bg-img` 的 src），用**模板匹配**（用拼图块 `jigsaw.png` 在背景图里找匹配位置）或人工辅助确定「BOSS」中 O 的中心 x 坐标。
4. **精准拖动**：`DRAG:滑块左边缘x:y:O中心x:y`，滑块左边缘 x≈582，y≈400。
5. **验证成功标志**：滑块拖对后，验证区会消失或出现「验证通过」；失败则滑块弹回 x=582。
6. **发短信 → 收验证码 → 登录**：手机收到短信后 `FILL_CODE:xxxx` → `SUBMIT_LOGIN`。
7. **查询岗位**：见第八节，用 `EVAL:fetch(...)` 在浏览器里查佛山/广州的岗位。
8. **整理 Markdown**：按城市分组整理成文档交付。

### 给接手的你的一些忠告

1. **先读 boss2 仓库的官方文档**：`boss2/docs/BOSS直聘API岗位获取搭建文档.md`，那是最权威的参考。
2. **别用 curl 调 API**，必挂 code:37。必须在浏览器页面里 fetch。
3. **验证码有实效性**，操作要快；过期了就 `REFRESH` 重新抓图给人看。
4. **网易易盾滑块别用 JS 伪造事件**，必失败。用 Playwright 的 `mouse` 系列（真实输入管线）+ 人手缓动曲线。
5. **日志要看 `gt_browser.log`**，命令结果都在里面（`DRAG_RESULT`、`EVAL_RESULT`、`EVAL_ERROR`）。
6. **截图在 `/tmp/opencode/snapshots/snap.png`**，每次命令后都会更新，配合图片服务器看当前页面状态。
7. 如果滑块反复失败，很可能是**拖动轨迹不够像人**：可以增加随机停顿、来回微调（先拖过头再回来一点）。

---

## 十二、完整避坑清单（只看这一节也行）

### 环境类
- [x] Linux 无浏览器环境：`playwright install chromium --with-deps` 一次性装好
- [x] pip 装包要加 `--break-system-packages`
- [x] xvfb 跑有窗口浏览器需要先 `apt-get install -y xauth`

### 反爬类
- [x] **IP 风控**：云服务器 IP 会被 BOSS直聘拦截，先进 verify.html 安全验证页
- [x] **headless 检测**：直接访问登录页会被 JS 跳转到 about:blank 空白页
- [x] **curl 调 API 必挂**：返回 code:37，必须在浏览器里 fetch
- [x] **接口限流**：请求间隔 2-3 秒，别连续猛发

### 验证码类
- [x] GeeTest 3x3 图片点选：抓图 → 给人看 → 人报格子号 → 程序点格子+确认
- [x] 验证码有时效性（约 1 分钟），过期要点刷新重来
- [x] 点格子前先确认验证码没变（对比 grid_url）
- [x] 网易易盾滑块：**不能用 JS 伪造鼠标事件**（必失败），要用 Playwright 真实鼠标 + 缓动曲线
- [x] 滑块要对准缺口位置才能过，随便拖（比如拖到最右）会失败
- [x] 定位缺口可以：模板匹配（用拼图块图在背景图里匹配）最靠谱；OpenCV 圆形检测、OCR 识别文字都试过，不可靠

### 脚本类
- [x] about:blank 页读 cookie 会抛 SecurityError 导致脚本崩溃 → save_state 加 try/except
- [x] 持久化 profile（launch_persistent_context）重启后验证 Cookie 可能不保留，需重新过验证码
- [x] 给元素截图时元素不可见会一直 timeout → 改截全屏

---

> **附：相关文件位置**
> - boss2 源码：`/tmp/opencode/boss2/`
> - 官方教程文档：`/tmp/opencode/boss2/docs/BOSS直聘API岗位获取搭建文档.md`
> - 持久浏览器脚本：`/tmp/opencode/gt_browser.py`
> - 截图目录：`/tmp/opencode/snapshots/`
> - 图片预览目录：`/tmp/opencode/captcha_view/`
> - 手机号：`13477975671`
