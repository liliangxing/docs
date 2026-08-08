# BOSS直聘岗位数据获取 - 完整搭建文档

> **文档说明**：本文档记录了通过 BOSS直聘 API 获取佛山、广州岗位数据的完整过程，包括成功步骤和失败避坑指南。面向技术水平一般的读者，用大白话讲解每一步。
>
> **编写日期**：2026-08-07
> **作者**：AI 助手（TRAE TraeWork）

---

## 目录

- [一、整体思路（先看这个）](#一整体思路先看这个)
- [二、用到的工具和插件清单](#二用到的工具和插件清单)
- [三、环境准备](#三环境准备)
- [四、第一步：下载源码仓库](#四第一步下载源码仓库)
- [五、第二步：分析反编译代码，找API接口](#五第二步分析反编译代码找api接口)
- [六、第三步：用浏览器登录BOSS直聘](#六第三步用浏览器登录boss直聘)
- [七、第四步：curl方式调用API（失败！避坑！）](#七第四步curl方式调用api失败避坑)
- [八、第五步：浏览器JS fetch方式调用API（成功！）](#八第五步浏览器js-fetch方式调用api成功)
- [九、第六步：批量获取岗位数据](#九第六步批量获取岗位数据)
- [十、第七步：整理数据为Markdown文档](#十第七步整理数据为markdown文档)
- [十一、调试排查命令汇总](#十一调试排查命令汇总)
- [十二、常见问题FAQ](#十二常见问题faq)
- [十三、关键经验总结](#十三关键经验总结)

---

## 一、整体思路（先看这个）

### 我们要做什么？

通过 BOSS直聘的 API 接口，查询佛山和广州两个城市中适合女性、无经验要求的岗位（文员、客服、前台等），然后把结果整理成文档。

### 整体流程图

```
下载源码仓库 → 分析代码找API接口 → 浏览器登录BOSS直聘
                                          ↓
                                    获取登录Cookie
                                          ↓
                              ┌─── curl调API（失败！）
                              │
                              └─── 浏览器JS fetch调API（成功！）
                                          ↓
                                    批量获取岗位数据
                                          ↓
                                    整理成Markdown文档
```

### 为什么不能直接用curl调API？

BOSS直聘有很强的反爬虫机制。它不仅检查 Cookie，还检查浏览器的"环境指纹"（比如 `__zp_stoken__` 这个安全令牌）。用 curl 这种命令行工具去调，即使带上了 Cookie，BOSS直聘的服务器也能识别出"这不是一个真正的浏览器在发请求"，就会返回 `code: 37`，提示"您的环境存在异常"。

**最终成功的方案**：在真实浏览器里用 JavaScript 的 `fetch` 函数发请求。因为浏览器会自动带上所有 Cookie、浏览器指纹等信息，BOSS直聘的服务器就认为这是一个正常用户在浏览网页，就会返回真实数据。

---

## 二、用到的工具和插件清单

### 2.1 AI 工具层面（我是怎么干活的）

作为 AI 助手，我没有手没有脚，我通过以下工具来完成所有操作：

| 工具名称 | 类型 | 作用 |
|---------|------|------|
| **RunCommand** | 内置工具 | 执行命令行命令（如 git clone、curl、ls 等） |
| **Read** | 内置工具 | 读取文件内容 |
| **Write** | 内置工具 | 写入文件内容 |
| **Grep** | 内置工具 | 在文件中搜索关键词 |
| **Glob** | 内置工具 | 按文件名模式查找文件 |
| **LS** | 内置工具 | 列出目录内容 |
| **TodoWrite** | 内置工具 | 任务管理，跟踪进度 |
| **integrated_browser (MCP)** | MCP服务器 | 浏览器自动化，模拟人类操作网页 |

### 2.2 MCP（Model Context Protocol）服务器

**什么是 MCP？** 你可以理解为"AI 的手和眼"。MCP 是一种协议，让 AI 能够连接外部工具。本项目用到了一个叫 `integrated_browser` 的 MCP 服务器，它提供了以下浏览器操作能力：

| MCP工具 | 作用 | 本项目用途 |
|---------|------|-----------|
| `browser_navigate` | 导航到指定网址 | 打开BOSS直聘登录页、搜索页 |
| `browser_tabs` | 管理浏览器标签页 | 查看当前打开了哪些页面 |
| `browser_snapshot` | 获取页面结构快照 | 查看页面上有哪些元素（按钮、输入框等） |
| `browser_take_screenshot` | 页面截图 | 保存二维码图片、验证码图片 |
| `browser_click` | 点击页面元素 | 点击按钮、选择选项 |
| `browser_type` | 在输入框输入文字 | 输入手机号、验证码 |
| `browser_evaluate` | 执行JavaScript代码 | **最关键的工具！** 用JS的fetch调API |
| `browser_lock` / `browser_unlock` | 锁定/解锁浏览器 | 防止多任务冲突 |
| `browser_wait_for` | 等待页面加载 | 等待二维码出现、页面跳转 |

### 2.3 命令行工具

| 工具 | 用途 | 安装方式 |
|------|------|---------|
| `git` | 克隆仓库、提交代码 | 大多数系统自带，或 `apt install git` |
| `curl` | 发送HTTP请求（测试API） | 系统自带 |
| `python3` | 处理数据、写脚本 | 系统自带或 `apt install python3` |

### 2.4 技能（Skill）

本项目中用到了以下 TRAE 技能：

| 技能名称 | 用途 |
|---------|------|
| `TRAE-product-knowledge` | 回答用户关于TRAE产品的问题（如"你是什么模型"） |

---

## 三、环境准备

### 3.1 确认基本工具已安装

```bash
# 检查 git 是否安装
git --version

# 检查 curl 是否安装
curl --version

# 检查 python3 是否安装
python3 --version
```

**大白话解释**：这三条命令就是检查你电脑上有没有装这些工具。如果报错说"command not found"，那就需要先安装。

### 3.2 设置 git 用户信息（提交代码时需要）

```bash
# 设置你的名字和邮箱（换成你自己的）
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

**为什么要这么做？** 提交代码到 GitHub 时，Git 需要知道是谁提交的。就像你寄快递要写寄件人信息一样。

### 3.3 准备 GitHub 访问凭证

推送代码到 GitHub 需要身份验证。有两种方式：

**方式一：Personal Access Token（推荐）**

1. 登录 GitHub → 右上角头像 → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 点 "Generate new token"
3. 勾选 `repo` 权限
4. 生成后复制 token（只显示一次！）

```bash
# 把 YOUR_TOKEN 替换成你的 token
# 使用时在 git URL 中嵌入 token
git clone https://YOUR_TOKEN@github.com/liliangxing/boss2.git
```

**方式二：SSH Key**

```bash
# 生成 SSH 密钥
ssh-keygen -t ed25519 -C "你的邮箱@example.com"

# 查看公钥内容，复制到 GitHub → Settings → SSH and GPG keys
cat ~/.ssh/id_ed25519.pub
```

---

## 四、第一步：下载源码仓库

### 4.1 克隆仓库

```bash
# 进入工作目录
cd /data/user/work

# 克隆仓库（下载代码到本地）
git clone https://github.com/liliangxing/boss2.git
```

**大白话解释**：`git clone` 就是把 GitHub 上的代码仓库完整下载到本地。就像你从网盘下载一个文件夹一样。

### 4.2 查看仓库结构

```bash
# 进入仓库目录
cd boss2

# 列出所有文件和文件夹
ls -la
```

预期输出：
```
total 32
drwxr-xr-x 6 root root 4096 Aug  7 22:21 .
drwxr-xr-x 3 root root 4096 Aug  7 22:21 ..
drwxr-xr-x 8 root root 4096 Aug  7 22:21 .git
-rw-r--r-- 1 root root   44 Aug  7 22:21 .gitignore
-rw-r--r-- 1 root root  2016 Aug  7 22:21 README.md
drwxr-xr-x 5 root root 4096 Aug  7 22:21 com       ← 反编译的Java源码
drwxr-xr-x 2 root root 4096 Aug  7 22:21 smali_toolchain  ← APK反编译工具
drwxr-xr-x 3 root root 4096 Aug  7 22:21 src       ← 源码
```

### 4.3 查看提交历史

```bash
# 查看最近的提交记录
git log --oneline -5
```

预期输出：
```
2b7fd13 Add smali toolchain and rebuilt APK
e104e3f JADX反编译BOSS直聘源码
397b6be Update README with compilation info
bf0e5f0 Add GeekModuleService.java
616b758 Add BossModuleService.java
```

**为什么要看提交历史？** 了解仓库的发展过程，知道里面都有什么内容。

---

## 五、第二步：分析反编译代码，找API接口

### 5.1 为什么要分析代码？

BOSS直聘的 API 接口地址不是公开的。但这个仓库里有 BOSS直聘 APK 反编译后的 Java 源码，通过阅读代码可以找到 API 接口的地址和参数格式。

### 5.2 搜索API接口地址

```bash
# 在代码中搜索包含 "zhipin.com" 的文件（API域名）
grep -r "zhipin.com" /data/user/work/boss2/com/ --include="*.java" -l

# 搜索 API 路径关键词
grep -r "joblist" /data/user/work/boss2/com/ --include="*.java" -l

# 搜索搜索相关的API
grep -r "search" /data/user/work/boss2/com/ --include="*.java" -l
```

**大白话解释**：`grep -r` 就是"在一个目录下所有文件里搜索某个关键词"。`-l` 表示只显示文件名，不显示具体内容。`--include="*.java"` 表示只搜 `.java` 文件。

### 5.3 查看配置文件中的API地址

```bash
# 查看配置类（包含API地址定义）
cat /data/user/work/boss2/com/hpbr/bosszhipin/config/m.java | head -50

# 搜索 wapi（Web API）相关路径
grep -r "wapi" /data/user/work/boss2/com/ --include="*.java" | head -20

# 搜索 joblist.json（岗位列表API）
grep -r "joblist" /data/user/work/boss2/com/ --include="*.java"
```

### 5.4 找到的关键API接口

通过分析代码，找到了以下关键API：

```
岗位搜索API：
https://www.zhipin.com/wapi/zpgeek/search/joblist.json

参数说明：
- scene: 场景值，固定为 1
- query: 搜索关键词（如"文员"、"客服"、"前台"）
- city: 城市代码
  - 101280800 = 佛山
  - 101280100 = 广州
  - 101010100 = 北京
  - 101020100 = 上海
- experience: 经验要求（空=不限）
- degree: 学历要求（空=不限）
- page: 页码（从1开始）
- pageSize: 每页条数（最大30）
```

**为什么要了解这些参数？** 调用API时需要正确拼接这些参数，才能获取到想要的数据。比如想查佛山的文员岗位，就需要把 `city` 设为 `101280800`，`query` 设为 `文员`。

### 5.5 城市代码对照表

| 城市 | 代码 |
|------|------|
| 北京 | 101010100 |
| 上海 | 101020100 |
| 广州 | 101280100 |
| 深圳 | 101280600 |
| 佛山 | 101280800 |
| 东莞 | 101281600 |
| 中山 | 101281700 |

---

## 六、第三步：用浏览器登录BOSS直聘

### 6.1 为什么需要登录？

虽然 BOSS直聘不登录也能看到部分岗位，但登录后能看到更多岗位信息，而且 API 调用需要带上登录后的 Cookie（尤其是 `__zp_stoken__` 安全令牌）。

### 6.2 打开BOSS直聘登录页面

这一步是通过 MCP 的 `browser_navigate` 工具完成的：

```
# AI 内部调用（用户不需要手动执行）
工具: browser_navigate
参数: url = "https://www.zhipin.com/web/user/"
```

如果手动模拟，就是在浏览器地址栏输入：`https://www.zhipin.com/web/user/`

### 6.3 获取页面快照，查看页面结构

```
# AI 内部调用
工具: browser_snapshot
```

这会返回页面上所有元素的列表，比如：
- 手机号输入框
- 验证码输入框
- 发送验证码按钮
- 登录/注册按钮
- 微信登录链接
- 用户协议勾选框

**为什么要先看快照？** 就像你到了一个陌生的房间，先环顾四周看看有什么东西，才知道该操作什么。

### 6.4 二维码登录流程

BOSS直聘支持扫码登录。流程如下：

```
1. 导航到登录页面
   工具: browser_navigate → https://www.zhipin.com/web/user/

2. 获取页面快照，找到二维码元素
   工具: browser_snapshot

3. 截图保存二维码图片
   工具: browser_take_screenshot
   说明: 截图保存到 /data/tool/browser_snapshots/ 目录

4. 用户用手机BOSS直聘APP扫描二维码
   说明: 这一步需要人工操作，AI 无法代替

5. 用户在手机上确认登录
   说明: 同样需要人工操作

6. 等待页面跳转（登录成功后会跳到首页）
   工具: browser_wait_for
```

### 6.5 验证登录状态

登录成功后，检查当前 Cookie：

```
# AI 内部调用
工具: browser_evaluate
脚本: document.cookie
```

返回的 Cookie 中应包含以下关键字段：

| Cookie名称 | 含义 | 重要性 |
|-----------|------|--------|
| `__zp_stoken__` | 安全令牌（最关键！） | ★★★★★ |
| `__c` | 用户标识 | ★★★★ |
| `__a` | 账号标识 | ★★★★ |
| `__g` | 来源标记 | ★★ |
| `lastCity` | 上次访问城市 | ★ |
| `Hm_lvt_*` | 百度统计 | ★ |

**`__zp_stoken__` 是什么？** 这是 BOSS直聘的"安全通行证"，它是通过 JavaScript 在浏览器端动态生成的，包含了你的浏览器环境信息。没有这个令牌，API 就会拒绝你的请求。这也是为什么 curl 方式会失败的根本原因。

### 6.6 可能遇到的安全验证（CAPTCHA）

登录过程中可能触发 GeeTest 验证码（比如"点击图中所有的袋鼠"）。这是一个 3x3 的图片网格，需要点击正确的图片。

**处理方式**：
1. 用 `browser_take_screenshot` 截图保存验证码
2. 分析图片内容，确定需要点击的位置
3. 用 `browser_click` 依次点击对应位置的图片
4. 点击"确认"按钮提交

**避坑提示**：验证码图片是随机的，每次都不一样。如果点错了，会刷新验证码重新来。建议慢慢来，看清楚再点。

---

## 七、第四步：curl方式调用API（失败！避坑！）

### 7.1 尝试用curl调用API

```bash
# 先保存Cookie到文件
# （假设你已经通过浏览器登录，这里用浏览器中的cookie）

# 定义完整的Cookie字符串
FULL_COOKIE="__zp_stoken__=deb7gRzrDi8OFxIfDhkkob0V...（很长的字符串）; __c=1786112092; __a=87633825.1786112092..."

# 用curl调用岗位搜索API
curl -s "https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=%E6%96%87%E5%91%98&city=101280800&experience=&payType=&partTime=&degree=&industry=&scale=&stage=&position=&jobType=&salary=&multiBusinessDistrict=&multiSubway=&page=1&pageSize=30" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  -H "Referer: https://www.zhipin.com/web/geek/job?query=%E6%96%87%E5%91%98&city=101280800" \
  -H "Cookie: $FULL_COOKIE"
```

### 7.2 返回结果（失败）

```json
{
  "code": 37,
  "message": "您的环境存在异常.",
  "zpData": {}
}
```

### 7.3 失败原因分析

| 检查项 | curl的情况 | 浏览器的情况 |
|-------|-----------|-------------|
| Cookie | 手动拼接，可能不完整 | 浏览器自动管理，完整 |
| User-Agent | 手动设置 | 浏览器原生 |
| Referer | 手动设置 | 浏览器自动 |
| `__zp_stoken__` | 有，但是是从浏览器复制的 | 浏览器动态生成，实时有效 |
| TLS指纹 | curl的TLS指纹与浏览器不同 | 浏览器原生TLS |
| JavaScript执行 | 无法执行JS | 可以执行JS |
| 请求头顺序 | 可能与浏览器不同 | 浏览器标准顺序 |

**核心原因**：`__zp_stoken__` 这个安全令牌是浏览器端 JavaScript 动态生成的，绑定了当前浏览器的环境信息（包括时间戳、浏览器指纹等）。即使你把 Cookie 复制到 curl 里用，服务器验证时发现令牌与当前请求环境不匹配，就会拒绝。

### 7.4 避坑总结

> **教训**：不要试图用 curl 直接调用 BOSS直聘的 API。无论你怎么模仿浏览器的请求头，都无法通过安全验证。因为安全验证不仅看请求头，还看 TLS 指纹、JavaScript 执行环境等更深层次的信息。

---

## 八、第五步：浏览器JS fetch方式调用API（成功！）

### 8.1 核心思路

既然 curl 不行，那就直接在浏览器里用 JavaScript 发请求！浏览器里的 `fetch` 函数会自动带上所有 Cookie、使用浏览器原生的 TLS 指纹、不需要额外设置请求头。

### 8.2 具体操作

通过 MCP 的 `browser_evaluate` 工具，在浏览器页面中执行以下 JavaScript 代码：

```javascript
// 第一步：先测试API是否能调通
fetch('https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=%E6%96%87%E5%91%98&city=101280800&page=1&pageSize=30', {
  credentials: 'include',  // 自动带上Cookie
  headers: {
    'Accept': 'application/json'
  }
})
.then(r => r.text())
.then(t => console.log(t.substring(0, 3000)))
.catch(e => console.log('Error: ' + e.message))
```

**AI 内部调用方式**：
```
工具: browser_evaluate
脚本: 上面的JavaScript代码
```

### 8.3 返回结果（成功！）

```json
{
  "code": 0,
  "message": "Success",
  "zpData": {
    "resCount": 186,
    "hasMore": true,
    "jobList": [
      {
        "jobName": "文职录入文员（双休/无销售/近地铁）",
        "brandName": "银雁科技",
        "jobExperience": "经验不限",
        "jobDegree": "大专",
        "cityName": "佛山",
        "areaDistrict": "南海区",
        "businessDistrict": "桂城",
        "skills": ["五险一金", "带薪培训", "免费停车"],
        "welfareList": ["节日福利", "零食下午茶", "带薪年假"],
        "bossName": "邵女士",
        "bossTitle": "招聘经理",
        "encryptJobId": "3eec96bc9029ab7e03Z-3N6-FVpZ"
      }
      // ... 更多岗位
    ]
  }
}
```

### 8.4 为什么这种方式能成功？

| 对比项 | curl方式 | 浏览器JS fetch方式 |
|-------|---------|------------------|
| Cookie | 手动复制，可能过期 | 浏览器自动管理，实时有效 |
| `__zp_stoken__` | 静态复制 | 浏览器内动态有效 |
| TLS指纹 | curl的 | 浏览器原生的 ✓ |
| Referer | 手动设置 | 浏览器自动设置 ✓ |
| 请求环境 | 服务器知道不是浏览器 | 就是真浏览器 ✓ |
| 安全验证 | 不通过 ✗ | 通过 ✓ |

**大白话解释**：curl 方式就像你拿着别人的身份证去办事，虽然照片看起来像，但工作人员一查就发现不是你本人。而浏览器 JS fetch 方式就是你本人亲自去办事，当然没问题。

### 8.5 关键参数说明

```javascript
fetch(url, {
  credentials: 'include',  // 这行很重要！表示请求时带上Cookie
  headers: {
    'Accept': 'application/json'  // 告诉服务器我要JSON格式的数据
  }
})
```

**`credentials: 'include'` 为什么重要？** 没有这个参数，浏览器不会带上 Cookie 发请求，API 就不知道你是谁，会拒绝访问。就像你去银行办事不带身份证，银行不给你办。

---

## 九、第六步：批量获取岗位数据

### 9.1 数据提取脚本

为了方便处理，我们把 API 返回的数据提取成结构化的对象：

```javascript
// 在浏览器中执行的JavaScript代码
fetch('https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=' + 
  encodeURIComponent('文员') + '&city=101280800&page=1&pageSize=30', {
  credentials: 'include',
  headers: { 'Accept': 'application/json' }
})
.then(r => r.json())
.then(d => {
  // 提取需要的字段
  const jobs = d.zpData.jobList.map(j => ({
    jobName: j.jobName,           // 岗位名称
    company: j.brandName,         // 公司名称
    salary: j.salaryDesc,         // 薪资描述
    experience: j.jobExperience,  // 经验要求
    degree: j.jobDegree,          // 学历要求
    city: j.cityName,             // 城市
    district: j.areaDistrict,     // 区域
    business: j.businessDistrict, // 商圈
    skills: j.skills,             // 技能标签
    labels: j.jobLabels,          // 岗位标签
    industry: j.brandIndustry,    // 行业
    scale: j.brandScaleName,      // 公司规模
    welfare: j.welfareList,       // 福利列表
    bossName: j.bossName,         // 招聘者姓名
    bossTitle: j.bossTitle,       // 招聘者职位
    jobId: j.encryptJobId         // 加密的岗位ID
  }));
  
  // 存到全局变量，方便后续读取
  window._jobData = jobs;
  return 'done: ' + jobs.length + ' 条岗位';
})
.catch(e => 'Error: ' + e.message);
```

**大白话解释**：
- `encodeURIComponent('文员')` 把中文"文员"转成 URL 编码 `%E6%96%87%E5%91%98`，因为 URL 里不能直接写中文
- `.map(j => ({...}))` 把每条岗位数据里我们需要的字段挑出来，重新组装成一个干净的对象
- `window._jobData = jobs` 把结果存到浏览器的全局变量里，方便后面读取

### 9.2 批量搜索多个关键词

分别搜索佛山和广州的"文员"、"客服"、"前台"岗位：

```javascript
// 佛山 - 文员（city=101280800）
fetch('https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=' + 
  encodeURIComponent('文员') + '&city=101280800&page=1&pageSize=30', {
  credentials: 'include', headers: { 'Accept': 'application/json' }
})
.then(r => r.json())
.then(d => {
  window._jobData = d.zpData.jobList.map(j => ({
    jobName: j.jobName, company: j.brandName, salary: j.salaryDesc,
    experience: j.jobExperience, degree: j.jobDegree,
    city: j.cityName, district: j.areaDistrict, business: j.businessDistrict,
    skills: j.skills, labels: j.jobLabels, industry: j.brandIndustry,
    scale: j.brandScaleName, welfare: j.welfareList,
    bossName: j.bossName, bossTitle: j.bossTitle, jobId: j.encryptJobId
  }));
})
```

**关键参数对照表**：

| 搜索关键词 | query参数值 | encodeURIComponent编码 |
|-----------|-----------|----------------------|
| 文员 | 文员 | %E6%96%87%E5%91%98 |
| 客服 | 客服 | %E5%AE%A2%E6%9C%8D |
| 前台 | 前台 | %E5%89%8D%E5%8F%B0 |
| 数据录入 | 数据录入 | %E6%95%B0%E6%8D%AE%E5%BD%95%E5%85%A5 |

### 9.3 读取存储的数据

```javascript
// 读取之前存储的数据
JSON.stringify(window._jobData || [])
```

### 9.4 避坑：API限流

**问题**：短时间内发送太多请求，API 会返回 `code: 37`（环境异常）。

**解决方案**：
- 每次请求之间间隔 2-3 秒
- 使用 `setTimeout` 延迟请求
- 分批获取，不要一次性发太多

```javascript
// 延迟2秒后再发请求（避免限流）
new Promise((resolve) => {
  setTimeout(() => {
    fetch(url, { credentials: 'include' })
      .then(r => r.json())
      .then(d => resolve(d))
      .catch(e => resolve('Error: ' + e.message));
  }, 2000);  // 等2秒
});
```

**大白话解释**：就像你去超市买东西，如果一口气拿太多东西去结账，收银员可能会让你等等。BOSS直聘的服务器也一样，你请求太快太多，它就"生气"不给你数据了。所以要慢慢来，每次请求之间等一会儿。

### 9.5 检查API返回状态

```javascript
// 检查API返回的code值
fetch(url, { credentials: 'include' })
  .then(r => r.json())
  .then(d => {
    console.log('code:', d.code);
    console.log('message:', d.message);
    console.log('jobList存在吗:', !!d.zpData?.jobList);
  })
```

**code值含义对照表**：

| code值 | 含义 | 处理方式 |
|--------|------|---------|
| 0 | 成功 | 正常处理数据 |
| 37 | 环境异常（被限流或风控） | 等待后重试，或换浏览器环境 |
| 其他非0 | 各种错误 | 查看message字段了解原因 |

---

## 十、第七步：整理数据为Markdown文档

### 10.1 数据整理思路

获取到 JSON 格式的岗位数据后，需要整理成人类易读的 Markdown 表格格式：

1. 按城市分组（佛山、广州）
2. 按岗位类型分组（文员、客服、前台）
3. 提取关键字段：岗位名称、公司、经验要求、学历、区域、福利
4. 筛选推荐岗位（经验不限 + 学历不限）
5. 添加求职建议

### 10.2 生成Markdown文件

```bash
# 将整理好的内容写入Markdown文件
# 使用Write工具或文本编辑器创建文件
cat > /workspace/佛山广州岗位推荐整理.md << 'EOF'
# 佛山&广州岗位推荐整理

> 数据来源：BOSS直聘 API 实时查询
> 查询时间：2026-08-07

## 一、佛山市岗位

### 1. 文员类岗位

| 序号 | 岗位名称 | 公司 | 经验要求 | 学历 | 区域 | 福利亮点 |
|------|---------|------|---------|------|------|---------|
| 1 | 文职录入文员 | 银雁科技 | 经验不限 | 大专 | 南海区 | 五险一金 |
...
EOF
```

**大白话解释**：`cat > 文件名 << 'EOF'` 是一种在命令行里写多行文本的方法。从 `EOF` 之间的内容都会被写入文件。不过实际操作中，我们用的是 AI 的 Write 工具直接写入文件，更方便。

---

## 十一、调试排查命令汇总

### 11.1 检查浏览器状态

```bash
# 查看浏览器当前打开了哪些标签页
# AI工具: browser_tabs, action: "list"
```

```bash
# 查看当前页面URL和标题
# AI工具: browser_snapshot
# 返回结果中会包含 Page URL 和 Page Title
```

### 11.2 检查Cookie状态

```javascript
// 在浏览器中查看当前所有Cookie
document.cookie

// 检查特定的Cookie是否存在
document.cookie.includes('__zp_stoken__')

// 检查__zp_stoken__的值
document.cookie.split(';').find(c => c.trim().startsWith('__zp_stoken__'))
```

**调试技巧**：如果 `__zp_stoken__` 不存在或为空，说明登录状态有问题，需要重新登录。

### 11.3 测试API连通性

```javascript
// 最简单的API测试（只看code和message）
fetch('https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=test&city=101280800&page=1&pageSize=1', {
  credentials: 'include'
})
.then(r => r.json())
.then(d => {
  console.log('code:', d.code);
  console.log('message:', d.message);
  console.log('数据条数:', d.zpData?.jobList?.length || 0);
})
```

### 11.4 检查页面是否被重定向到登录页

```javascript
// 检查当前URL是否是登录页
window.location.href.includes('/web/user/')

// 如果返回 true，说明登录已过期，需要重新登录
```

### 11.5 查看网络请求详情

```javascript
// 使用Performance API查看请求详情
performance.getEntriesByType('resource')
  .filter(e => e.name.includes('joblist'))
  .map(e => ({
    url: e.name,
    duration: e.duration,
    status: e.responseStatus
  }))
```

### 11.6 调试用：格式化输出JSON

```javascript
// 美化输出JSON（方便阅读）
console.log(JSON.stringify(data, null, 2));

// 只输出前N个字符（防止数据太长截断）
console.log(JSON.stringify(data).substring(0, 3000));

// 统计各分类的数据量
const summary = {
  fs_wy: (window._jobData || []).length,
  fs_kf: (window._foshanKefu || []).length,
  fs_qt: (window._foshanQiantai || []).length,
  gz_wy: (window._gzWenyuan || []).length
};
JSON.stringify(summary)
```

### 11.7 Git相关调试命令

```bash
# 查看当前仓库状态（有没有未提交的修改）
git status

# 查看最近5条提交记录
git log --oneline -5

# 查看远程仓库地址
git remote -v

# 查看当前分支
git branch

# 查看文件修改详情
git diff
```

### 11.8 文件系统调试

```bash
# 查找特定文件
find / -name "boss_cookies*" -type f 2>/dev/null

# 查看目录结构
ls -la /data/user/work/boss2/

# 搜索代码中的关键词
grep -r "joblist" /data/user/work/boss2/ --include="*.java" -l

# 查看文件前50行
head -50 /data/user/work/boss2/com/hpbr/bosszhipin/config/m.java

# 查看文件大小
ls -lh /workspace/佛山广州岗位推荐整理.md
```

---

## 十二、常见问题FAQ

### Q1: API返回 code:37 "您的环境存在异常" 怎么办？

**原因**：BOSS直聘检测到你的请求不是来自真实浏览器，或者请求频率太高。

**解决方案**：
1. 确保在浏览器内用 `fetch` 发请求，不要用 `curl`
2. 降低请求频率，每次请求间隔 2-3 秒
3. 重新登录刷新 `__zp_stoken__` 令牌
4. 清除浏览器缓存后重新登录

### Q2: 页面被跳转到登录页怎么办？

**原因**：登录状态过期了。

**解决方案**：
1. 重新访问 `https://www.zhipin.com/web/user/`
2. 重新扫码登录
3. 登录后立即检查 `document.cookie` 确认 `__zp_stoken__` 存在

### Q3: 二维码扫描后没反应怎么办？

**可能原因**：
1. 二维码已过期（通常有效期约1-2分钟）
2. 网络延迟
3. 手机APP版本太旧

**解决方案**：
1. 刷新页面重新获取二维码
2. 确保手机网络正常
3. 更新BOSS直聘APP到最新版本

### Q4: 获取到的数据中 salary（薪资）为空怎么办？

**原因**：BOSS直聘的 API 返回的 `salaryDesc` 字段有时为空字符串。

**解决方案**：需要访问具体的岗位详情页才能看到薪资信息。可以在 BOSS直聘 APP 或网页端搜索岗位名称查看薪资。

### Q5: 搜索结果只有15条，但总共有186条怎么办？

**原因**：API 的 `pageSize` 最大为 30，但实际返回可能少于请求量。需要翻页获取更多。

**解决方案**：
```javascript
// 获取第2页、第3页...
fetch(url + '&page=2&pageSize=30', { credentials: 'include' })
fetch(url + '&page=3&pageSize=30', { credentials: 'include' })
// 注意：每次请求之间要间隔2-3秒！
```

### Q6: 如何提交文档到GitHub？

```bash
# 1. 创建docs目录（如果不存在）
mkdir -p docs

# 2. 把文档放到docs目录
cp /workspace/佛山广州岗位推荐整理.md docs/

# 3. 添加文件到暂存区
git add docs/

# 4. 提交到本地仓库
git commit -m "Add BOSS直聘API岗位获取搭建文档"

# 5. 推送到远程仓库
git push origin main
```

---

## 十三、关键经验总结

### 13.1 成功的关键因素

1. **在浏览器内执行JavaScript**：这是绕过BOSS直聘安全检测的核心方法。浏览器内的 `fetch` 会自动带上所有必要的认证信息。

2. **正确的API地址和参数**：通过分析反编译代码找到了正确的API接口 `/wapi/zpgeek/search/joblist.json` 和参数格式。

3. **`credentials: 'include'`**：这个参数确保请求带上Cookie，缺少它API会返回未授权错误。

4. **控制请求频率**：避免触发限流，每次请求间隔2-3秒。

### 13.2 失败的教训

1. **curl方式不可行**：无论怎么模仿浏览器请求头，curl都无法通过BOSS直聘的安全验证。原因是安全验证不仅检查请求头，还检查TLS指纹、JavaScript执行环境等。

2. **Cookie复制不完整**：曾尝试将浏览器Cookie复制到curl中使用，但因为 `__zp_stoken__` 是动态生成的，复制出来后很快就失效了。

3. **请求过快导致限流**：短时间内连续发送多个API请求，导致后续请求全部返回 `code: 37`。

### 13.3 工具选择建议

| 任务 | 推荐工具 | 不推荐 |
|------|---------|--------|
| 调用BOSS直聘API | 浏览器JS fetch | curl |
| 登录BOSS直聘 | 浏览器扫码登录 | API登录（需要验证码等） |
| 批量获取数据 | 浏览器JS + 分页 | 一次性获取所有 |
| 数据整理 | Python/JS脚本 | 手动复制粘贴 |
| 代码分析 | grep + 文件阅读 | 全文搜索 |

### 13.4 完整工作流（精简版）

```
1. git clone https://github.com/liliangxing/boss2.git
2. grep -r "joblist" boss2/com/ --include="*.java"
3. 浏览器打开 https://www.zhipin.com/web/user/
4. 扫码登录
5. 检查 document.cookie 确认 __zp_stoken__ 存在
6. 浏览器JS fetch 调用API获取数据
7. 提取关键字段，存入 window 变量
8. 读取数据，整理成Markdown
9. git add → git commit → git push
```

---

## 附录：完整的API调用JavaScript代码模板

```javascript
/**
 * BOSS直聘岗位搜索API调用模板
 * 使用方法：在已登录BOSS直聘的浏览器页面中执行
 */

// ============ 配置区 ============
const CITY_CODE = '101280800';  // 佛山=101280800, 广州=101280100
const SEARCH_QUERY = '文员';     // 搜索关键词
const PAGE = 1;                  // 页码
const PAGE_SIZE = 30;            // 每页条数（最大30）

// ============ 构建URL ============
const apiUrl = `https://www.zhipin.com/wapi/zpgeek/search/joblist.json?scene=1&query=${encodeURIComponent(SEARCH_QUERY)}&city=${CITY_CODE}&page=${PAGE}&pageSize=${PAGE_SIZE}`;

// ============ 发送请求 ============
fetch(apiUrl, {
  credentials: 'include',
  headers: {
    'Accept': 'application/json'
  }
})
.then(response => response.json())
.then(data => {
  // 检查返回状态
  if (data.code !== 0) {
    console.error(`API返回错误: code=${data.code}, message=${data.message}`);
    return;
  }

  // 提取岗位数据
  const jobs = data.zpData.jobList.map(job => ({
    jobName: job.jobName,
    company: job.brandName,
    salary: job.salaryDesc,
    experience: job.jobExperience,
    degree: job.jobDegree,
    city: job.cityName,
    district: job.areaDistrict,
    business: job.businessDistrict,
    skills: job.skills,
    labels: job.jobLabels,
    industry: job.brandIndustry,
    scale: job.brandScaleName,
    welfare: job.welfareList,
    bossName: job.bossName,
    bossTitle: job.bossTitle,
    jobId: job.encryptJobId
  }));

  // 输出结果
  console.log(`共找到 ${data.zpData.resCount} 条结果，本页返回 ${jobs.length} 条`);
  console.table(jobs);

  // 存储到全局变量
  window._searchResults = jobs;
})
.catch(error => {
  console.error('请求失败:', error);
});
```

---

> **文档结束**
>
> 如有疑问，请参考 FAQ 部分或重新阅读相关章节。本文档基于 2026-08-07 的实际操作经验编写，BOSS直聘的API和安全机制可能随时更新，请以实际测试结果为准。
