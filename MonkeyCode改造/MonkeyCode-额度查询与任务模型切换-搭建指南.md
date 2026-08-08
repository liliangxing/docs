# MonkeyCode 今日额度查询与任务模型切换 搭建指南

> 目标：用三个邮箱账号在 monkeycode-ai.com 平台上完成两件事——(1) 查询账号"今日剩余额度"；(2) 把账号里**正在进行的任务**的模型切换成 glm-4.7。
>
> 本文档用大白话写给"技术一般"的人看，每一步都有命令、有解释、有你"应该看到的结果"、有踩坑提醒。如果你是需要照着这份文档做事的 Agent，请完整读一遍再动手，尤其注意每节的"为什么"和"避坑"。

---

## 目录

- [一、这次到底要做成什么事](#一这次到底要做成什么事)
- [二、需要提前准备什么](#二需要提前准备什么)
- [三、大白话背景知识（不懂也能照做）](#三大白话背景知识不懂也能照做)
- [四、第一部分：登录账号 + 查询今日额度](#四第一部分登录账号--查询今日额度)
- [五、第二部分：把正在进行的任务切换成 glm-4.7 模型](#五第二部分把正在进行的任务切换成-glm-47-模型)
- [六、排查错误工具箱（遇到问题先来这里）](#六排查错误工具箱遇到问题先来这里)
- [七、本指南用到的"高级工具/功能"逐个说明](#七本指南用到的高级工具功能逐个说明)
- [八、常见问题 FAQ](#八常见问题-faq)

---

## 一、这次到底要做成什么事

monkeycode-ai.com 是一个 AI 开发平台。每个账号登录后，能看到"今日还能用多少免费 tokens"（我们叫它**今日剩余额度**），也能给正在运行的任务更换底层 AI 模型。

我们做两件事：

1. **查额度**：登录账号后，调用一个接口（`GET /api/v1/users/wallet`），拿到类似下面这段数据：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "00000000-0000-0000-0000-000000000000",
    "balance": 143117,
    "daily_token_balance": 21790963,
    "daily_token_limit": 30000000
  }
}
```

含义：
- `daily_token_balance` = **今日剩余额度**（还能用约 2179 万个 tokens）
- `daily_token_limit` = 今日额度上限（3000 万 tokens）
- `balance` = 账户积分余额，单位是"分"，除以 1000 就是元（143117 分 = 143.117 元）

2. **切换任务模型**：找到某账号"正在进行的任务"，通过 WebSocket（一种长连接的通信方式）发一条"switch_model"指令，把它从 `monkeycode-basic/deepseek-v4-flash` 换成 `monkeycode-basic/glm-4.7`。

---

## 二、需要提前准备什么

| 东西 | 说明 |
|------|------|
| 一台 Linux 电脑/服务器 | 本指南所有命令在 Linux 下执行。Windows 请装 WSL 或 Git Bash |
| Python 3 | 用来写小脚本。检查：`python3 --version` |
| curl | 命令行里的"网页浏览器"，用来请求接口。检查：`curl --version` |
| git | 用来把文档提交到 GitHub（最后一步用） |
| 邮箱账号 + 密码 | 例如 `253254457@qq.com` / `000000aaa` |
| 能上网 | 需要能访问 `monkeycode-ai.com` |

> 说明：`curl` 和 `python3` 大多数 Linux 系统都自带。如果提示"command not found"，用系统自带包管理器安装，例如 Ubuntu：`apt-get update && apt-get install -y curl python3`。

---

## 三、大白话背景知识（不懂也能照做）

### 3.1 什么是"接口"（API）

接口就是网站给外部程序留的一个"窗口"。你用 `curl` 敲一个网址，网站返回一段文字（JSON），就相当于完成一次操作。

- 查询类接口：用 `GET`（读）
- 修改类接口：用 `POST` / `PUT`（写）

### 3.2 什么是 Cookie / Session（登录状态）

登录后，服务器会给你一个"通行证"，叫 Session，存在你的浏览器/脚本的 Cookie 里。之后每次请求都要带上它，服务器才知道"你是谁"。

本指南里，我们用一个文件 `cookies.txt` 专门保存它。

### 3.3 什么是 PoW 验证码（最关键的难点）

正常网页登录有图形验证码，人眼看图输入。但 monkeycode 的登录验证码**不是图片**，而是一道"数学题"：

- 服务器给你一个 30 位左右的"挑战串"（token）
- 你需要在它后面拼接内容，算出一组 sha256 哈希，找到 50 个"解"（solutions）
- 满足条件："哈希结果的前 3 位十六进制字符"等于"目标值"

我们不需要理解哈希原理，只需要**用 Python 脚本暴力试数字**：从 0 开始一个个试，直到试出符合条件的那一个。每个解平均试 4096 次，50 个解总共约 20 万次，电脑几秒就算完。

这就是为什么我们要写 Python 脚本——因为用手算不现实。

### 3.4 什么是 WebSocket

普通接口是"问一句答一句"。WebSocket 是"接根水管，双方可以随时说话"。切换任务模型必须用 WebSocket，因为任务在服务器那边一直在跑，只有通过这条长连接才能对运行中的任务下指令。

---

## 四、第一部分：登录账号 + 查询今日额度

总流程一共 5 步：

```
① 获取验证码挑战 → ② 用 Python 算出验证码答案 → ③ 兑换"验证令牌" → ④ 用 邮箱+密码+令牌 登录拿 Cookie → ⑤ 用 Cookie 查询今日额度
```

### 第 0 步：先确认环境 OK

打开终端，逐条执行下面命令（每条回车后看有没有输出版本号）：

```bash
python3 --version
curl --version
```

> 你应该看到类似 `Python 3.10.12` 和 `curl 8.x.x`。如果没有，先安装（见"二、需要提前准备什么"）。

---

### 第 1 步：获取验证码挑战（Challenge）

**命令**：

```bash
curl -sS -X POST "https://monkeycode-ai.com/api/v1/public/captcha/challenge" -H "Content-Type: application/json" -d '{}'
```

**你应该看到**（一段 JSON）：

```json
{"challenge":{"c":50,"s":32,"d":3},"expires":1786027166552,"token":"43ce4764277ae4ba70863b01b"}
```

**这个结果是什么意思**（逐个字段解释）：

| 字段 | 值 | 含义 |
|------|-----|------|
| `challenge.c` | 50 | 要算 **50 个解**（工作量） |
| `challenge.s` | 32 | 参与计算的"盐"长度是 32 位 |
| `challenge.d` | 3 | 难度：哈希前 3 位要匹配 |
| `expires` | 很长一串数字 | 过期时间（毫秒时间戳），过期要重新获取 |
| `token` | 30 位左右的十六进制 | 挑战串，**后面脚本要用** |

**为什么这样写命令**：
- `-X POST`：告诉 curl 用"写"的方式请求
- `-d '{}'`：请求体是空对象
- `-H "Content-Type: application/json"`：声明发送的是 JSON 格式
- `-sS`：安静模式但保留报错信息

**避坑提醒**：
- 把这段结果**完整复制保存**，后面的步骤要反复用到 `token`。建议存成文件：把上面命令加个 `-o challenge.json`，例如：

```bash
curl -sS -X POST "https://monkeycode-ai.com/api/v1/public/captcha/challenge" -H "Content-Type: application/json" -d '{}' -o challenge.json
cat challenge.json
```

这样 token 就保存在 `challenge.json` 里，方便后面用。

---

### 第 2 步：用 Python 算出验证码答案（PoW 求解）

写一个 Python 脚本，把它保存为 `solver.py`：

```python
import hashlib

# ===== 下面这两个函数是 go-cap 库 prng 算法的复刻，直接抄用即可，不用懂原理 =====

def fnv1a32(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def prng(seed: bytes, length: int) -> str:
    state = fnv1a32(seed)
    result = []
    while sum(len(x) for x in result) < length:
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        result.append("%08x" % state)
    return "".join(result)[:length]


# ===== 核心：算 50 个解 =====

def solve(token: str, count: int, size: int, difficulty: int):
    solutions = []
    for i in range(count):                      # i 从 0 到 49，共 50 个解
        b = (token + str(i + 1) + "d").encode()  # 挑战串 + 序号 + "d"
        target = prng(b, difficulty)            # 目标前缀（3 位十六进制）
        salt = prng(b[:-1], size)               # 参与哈希的盐（32 位）
        sol = 0
        while True:
            h = hashlib.sha256((salt + str(sol)).encode()).hexdigest()  # 算哈希
            if h.startswith(target):            # 哈希前 3 位等于目标 → 找到解
                break
            sol += 1
        solutions.append(sol)
    return solutions


if __name__ == "__main__":
    token = "在这里填第1步拿到的 token"
    solutions = solve(token, 50, 32, 3)
    print(solutions)
```

**运行**：

```bash
python3 solver.py
```

**你应该看到**：一串 50 个数字，类似：

```
[2016, 1481, 2905, 314, 3812, ...]
```

**为什么必须用脚本、为什么每个解是从 0 开始试**：
- 服务器要求的解是"让 sha256 哈希结果前 3 位等于目标值"的某个数字。哈希是"单向"的，没法反推，只能一个个数字试。从 0 开始 +1 试，试到命中为止。
- `target` 是 3 位十六进制，总共 16^3 = 4096 种可能，所以平均试 4096 次就中一个。
- 50 个解就是约 20 万次 sha256 计算，Python 几秒内算完。

**避坑提醒**：
- 每次请求 challenge，token 都**不一样**，所以第 2 步的 `token` 必须是第 1 步刚刚拿到的那一个，不能从旧记录里抄。
- 把第 1 步和第 2 步写成"一起跑"，避免 token 过期（challenge 有效期 2 分钟）。后面附录有"一条龙脚本"可以直接用。

---

### 第 3 步：兑换"验证令牌"（Redeem）

把第 1 步的 `token`（挑战串）和第 2 步算出的 50 个解，一起发给服务器，换一个"验证令牌"（captcha_token）。

**命令**（把尖括号里的内容替换成真实值，50 个解用逗号分隔）：

```bash
curl -sS -X POST "https://monkeycode-ai.com/api/v1/public/captcha/redeem" \
  -H "Content-Type: application/json" \
  -d '{"token":"43ce4764277ae4ba70863b01b","solutions":[2016,1481,2905,314,3812]}'
```

**你应该看到**：

```json
{"expires":1786027346792,"token":"f72aea19:f838bc60c32abd1","success":true}
```

`token` 字段（形如 `xxxxx:yyyyy` 中间有冒号）就是**验证令牌**，下一步登录要用。

**避坑提醒（非常重要）**：
- 验证令牌是**一次性**的：用一次就作废。所以兑换成功后必须**立刻**执行第 4 步登录，不能等。
- 如果 `solutions` 数量不对（少于 50 个）或答案算错，会返回 `success:false` 和错误信息，需要重新走第 1 步拿新 token 再算。

---

### 第 4 步：密码登录，拿到登录 Cookie

**命令**（替换邮箱、密码、验证令牌）：

```bash
curl -sS -X POST "https://monkeycode-ai.com/api/v1/users/password-login" \
  -H "Content-Type: application/json" \
  -d '{"email":"253254457@qq.com","password":"000000aaa","captcha_token":"f72aea19:f838bc60c32abd1"}' \
  -c cookies.txt \
  -o login.json

cat login.json
```

> 参数说明：`-c cookies.txt` = 把服务器返回的登录 Cookie 存进 `cookies.txt`；`-o login.json` = 把返回内容存进 `login.json`，方便看。

**你应该看到**（`login.json` 内容，`code` 是 0 就代表成功）：

```json
{"code":0,"message":"success","data":{"id":"019e2f1a-d7f3-7d08-ae84-0000644b2497","name":"显眼包银角大王","email":"253254457@qq.com","role":"individual","status":"active","is_blocked":false,"has_password":true}}
```

同时，`cookies.txt` 里会有类似这样一行（就是我们的通行证）：

```
monkeycode_ai_session	b613b6c0-5aac-4286-8f19-eaf49bf483f7
```

**避坑提醒**：
- 网上/代码注释里说密码要传 MD5，**实际不用**，直接传明文就行（前端页面也是传明文）。
- 如果没带 `captcha_token` 或令牌已用过，会返回 `403`，消息是"禁止访问"。这就是典型的"验证码没弄对"，回到第 1 步重来。
- 邮箱或密码错误，会返回 `code != 0` 或 401。

---

### 第 5 步：查询今日额度（核心目标）

**命令**（`-b cookies.txt` = 自动带上刚才存的 Cookie）：

```bash
curl -sS "https://monkeycode-ai.com/api/v1/users/wallet" -b cookies.txt -H "Accept: application/json"
```

**你应该看到**：

```json
{"code":0,"message":"success","data":{"id":"00000000-0000-0000-0000-000000000000","balance":143117,"daily_token_balance":21790963,"daily_token_limit":30000000}}
```

**结果解读**（这就是你要的"今日额度"）：

| 字段 | 本次值 | 大白话 |
|------|--------|--------|
| `daily_token_balance` | 21790963 | **今日剩余额度**：今天还能用 2179 万个 tokens |
| `daily_token_limit` | 30000000 | 今日上限：今天总共 3000 万个 tokens |
| `balance` | 143117 | 积分余额，单位"分"，`143117 / 1000 = 143.117` 元 |
| `code` | 0 | 0 = 成功，其他值 = 失败 |

**数据怎么自我核对**：`今日已用 = 上限 - 剩余 = 30000000 - 21790963 = 8209037`，约 820.9 万 tokens。如果这个数字对得上，说明数据是对的。

**避坑提醒**：
- 不带 Cookie 或 Cookie 过期，返回 `401 Unauthorized`。Cookie 有效期 30 天，过期就重新登录。
- 换一个账号查，就换一个 `cookies.txt`（或先把旧的删掉）。Cookie 和账号是一一对应的。

---

### 附：一条龙脚本（推荐偷懒直接用）

把上面 5 步合成一个脚本，存为 `one_shot.py`，运行一次输出登录 Cookie：

```python
import hashlib, json, urllib.request, sys

BASE = "https://monkeycode-ai.com"

def fnv1a32(data):
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def prng(seed, length):
    state = fnv1a32(seed); out = []
    while sum(len(x) for x in out) < length:
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        out.append("%08x" % state)
    return "".join(out)[:length]

def solve(token, count, size, difficulty):
    sols = []
    for i in range(count):
        b = (token + str(i + 1) + "d").encode()
        target = prng(b, difficulty); salt = prng(b[:-1], size)
        sol = 0
        while not hashlib.sha256((salt + str(sol)).encode()).hexdigest().startswith(target):
            sol += 1
        sols.append(sol)
    return sols

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

email, password = sys.argv[1], sys.argv[2]
ch = post("/api/v1/public/captcha/challenge", {})
sols = solve(ch["token"], ch["challenge"]["c"], ch["challenge"]["s"], ch["challenge"]["d"])
tok = post("/api/v1/public/captcha/redeem", {"token": ch["token"], "solutions": sols})
login = post("/api/v1/users/password-login", {"email": email, "password": password, "captcha_token": tok["token"]})
print(json.dumps(login, ensure_ascii=False))
```

**运行**：

```bash
python3 one_shot.py 253254457@qq.com 000000aaa
```

> 脚本会自己完成 挑战→求解→兑换→登录，最后打印用户信息。之后你可以打开脚本，把返回的 Cookie 手动存进 `cookies.txt`，也可以自己改造脚本把登录响应里的 Set-Cookie 解析出来。

---

## 五、第二部分：把正在进行的任务切换成 glm-4.7 模型

总流程 3 步：

```
① 查任务列表，找到"正在进行的任务"和它的 ID → ② 安装 WebSocket 工具 → ③ 写脚本连上任务发"switch_model"指令
```

### 第 1 步：查任务列表，找到目标任务

**命令**（记得带登录 Cookie）：

```bash
curl -sS "https://monkeycode-ai.com/api/v1/users/tasks?limit=10" -b cookies.txt -H "Accept: application/json" -o tasks.json
cat tasks.json
```

**你应该看到**：一段较长的 JSON，里面有一个 `tasks` 数组。每个任务长这样（我们只需要看几个字段）：

```json
{"id": "8f5df044-6437-4930-8bea-5dd08036b128", "status": "processing", "model": {"id": "99219247-...", "model": "monkeycode-basic/deepseek-v4-flash", ...}}
```

**怎么挑出"正在进行的任务"**：
- `status` 是 `processing` 就是正在进行的（`finished` 是已结束，`error` 是报错）。
- 记下它的 `id`（UUID 格式，一串 36 位字符）。本例目标任务的 id 是 `8f5df044-6437-4930-8bea-5dd08036b128`。
- 同时记下它现在的模型（本例是 `monkeycode-basic/deepseek-v4-flash`，id=`99219247-...`），切换后你会看到变化。

**我们要切到的目标模型**：`monkeycode-basic/glm-4.7`，它的 id 是 **`c2e2d76b-ac3a-4945-8ad6-e6f78a6ccd93`**。

> 这个 id 怎么来的？在 `/api/v1/users/models`（查询当前账号可用模型列表）里找 `model` 等于 `monkeycode-basic/glm-4.7` 的那一条，抄它的 `id`。示例命令：
>
> ```bash
> curl -sS "https://monkeycode-ai.com/api/v1/users/models?limit=100" -b cookies.txt | grep -o '"model":"[^"]*glm-4.7[^"]*"[^}]*"id":"[^"]*"'
> ```

**避坑提醒**：
- `glm-4.7` 在平台里叫 `monkeycode-basic/glm-4.7`（带前缀），**不要**用裸 `glm-4.7`（那个是另一个 id，也不推荐用）。
- 这个模型当前被平台标成了"隐藏"（is_hidden=true），所以网页下拉菜单里看不到它，但**接口仍然可以切换过去**。这属于正常现象。

---

### 第 2 步：安装 Python 的 WebSocket 库

切换模型走的是 WebSocket 长连接，Python 需要装一个第三方库 `websocket-client`。

**命令**：

```bash
pip install --break-system-packages websocket-client
```

**为什么加 `--break-system-packages`**：新版 Python 默认禁止往系统目录装第三方包，加上这个参数才允许装。如果你用的是虚拟环境（venv）可以不用这个参数，但对"技术一般"的人来说，直接全局装最简单。

**验证装好了**：

```bash
python3 -c "import websocket; print('ok')"
```

看到 `ok` 就说明成功。

---

### 第 3 步：写脚本连接任务并切换模型

保存为 `switch_model.py`：

```python
import base64, json, time, uuid, websocket

TASK_ID = "8f5df044-6437-4930-8bea-5dd08036b128"      # 第1步查到的任务 id
COOKIE = "monkeycode_ai_session=b613b6c0-5aac-4286-8f19-eaf49bf483f7"  # 登录拿到的 Cookie
MODEL_ID = "c2e2d76b-ac3a-4945-8ad6-e6f78a6ccd93"     # monkeycode-basic/glm-4.7

WS_URL = f"wss://monkeycode-ai.com/api/v1/users/tasks/control?id={TASK_ID}"

ws = websocket.create_connection(WS_URL, header=[f"Cookie: {COOKIE}"], timeout=30)
print("connected")

payload = {"request_id": str(uuid.uuid4()), "model_id": MODEL_ID, "load_session": True}
data_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
ws.send(json.dumps({"type": "call", "kind": "switch_model", "data": data_b64}))
print("sent switch_model")

deadline = time.time() + 30
while time.time() < deadline:
    msg = json.loads(ws.recv())
    print("recv:", msg.get("type"), msg.get("kind"))
    if msg.get("type") == "call-response" and msg.get("kind") == "switch_model":
        resp = json.loads(base64.b64decode(msg["data"]))
        print("switch_model result:", json.dumps(resp, ensure_ascii=False))
        print("SUCCESS" if resp.get("success") else "FAILED")
        break

ws.close()
```

**运行**：

```bash
python3 switch_model.py
```

**你应该看到**（最后的成功标志）：

```
connected
recv: call-response switch_model
switch_model result: {"id": "...", "request_id": "...", "success": true, "session_id": "ses_...", "model": {"id": "c2e2d76b-...", "model": "monkeycode-basic/glm-4.7", ...}}
SUCCESS
```

`"success": true` 就是切换成功了。

**为什么每条字段这么写**（对应前端代码里的原样逻辑）：
- `type: "call"`：表示这是一条"请求指令"
- `kind: "switch_model"`：指令类型是"切换模型"
- `data`：把真正要传的参数（请求编号 + 目标模型 id + 是否恢复会话）做成了 **base64 编码**的字符串。前端也是这么编码的，所以我们也照做。
- `load_session: true`：切换模型时让任务恢复原来的上下文（对话历史）。如果传 `false`，任务会以全新上下文重跑。

**避坑提醒**：
- 连不上常见原因：**Cookie 没带对**或已过期（回到第一部分重新登录）；任务 id 写错。
- `recv` 可能先收到一条非 `call-response` 的消息（比如心跳 `ping` 或 `task-event`），脚本会跳过，等到 `switch_model` 的响应为止。这正常，不是卡死。
- 如果你收到 `"success": false`，把返回的 `message` / `error` 记下来，多半是"模型对当前任务不可用"或"任务已结束不能切"。

### 第 4 步：验证切换生效

再查一次任务列表，确认任务模型已经变成 glm-4.7：

```bash
curl -sS "https://monkeycode-ai.com/api/v1/users/tasks?limit=10" -b cookies.txt | grep -A2 "8f5df044"
```

**你应该看到**任务里 `"model": "monkeycode-basic/glm-4.7"`，同时 `status` 仍是 `processing`。

---

## 六、排查错误工具箱（遇到问题先来这里）

### 6.1 看 HTTP 状态码（一上来先看这个）

| 状态码 | 意思 | 常见原因 |
|--------|------|----------|
| 200 | 成功 | 正常 |
| 401 | 未登录 | Cookie 没带 / 过期 → 重新登录 |
| 403 | 禁止访问 | 验证码没通过（登录时）或权限不足 |
| 404 | 找不到 | 网址拼错 / 接口路径不对 |
| 500 | 服务器出错 | 请求参数不对，把完整请求发给平台方 |

想看详细请求过程，给 curl 加 `-v`：

```bash
curl -v -sS "https://monkeycode-ai.com/api/v1/users/wallet" -b cookies.txt
```

`-v` 会打印"发出的请求头"和"收到的响应头"，对排查"Cookie 到底带没带上"特别有用。

### 6.2 排查命令速查表

```bash
# 1) 查登录状态（能返回用户信息说明 Cookie 有效）
curl -sS "https://monkeycode-ai.com/api/v1/users/wallet" -b cookies.txt

# 2) 看 cookies.txt 里到底存了什么
cat cookies.txt

# 3) 看登录响应全文（确认 code=0）
cat login.json

# 4) 检查验证码挑战内容
cat challenge.json

# 5) 列出账号可用模型（找 glm-4.7 的 id）
curl -sS "https://monkeycode-ai.com/api/v1/users/models?limit=100" -b cookies.txt | grep '"model"'

# 6) 列出任务（确认任务 id 和 status）
curl -sS "https://monkeycode-ai.com/api/v1/users/tasks?limit=10" -b cookies.txt | grep -E '"id"|"status"|"model"'

# 7) 查看订阅套餐（plan 决定默认模型）
curl -sS "https://monkeycode-ai.com/api/v1/users/subscription" -b cookies.txt
```

### 6.3 最常踩的坑汇总

| 坑 | 现象 | 解决办法 |
|----|------|----------|
| 验证码令牌一次性 | 第二次登录 403 | 每次登录都要重新走"挑战→求解→兑换→登录" |
| challenge 过期 | 2 分钟内不兑换就失效 | 把步骤 1-4 写成一个脚本一次跑完 |
| Cookie 与账号不对应 | 拿 A 的 Cookie 查 B 的数据 | 每账号单独存一份 cookies.txt |
| 忘记带 Cookie | 401 | curl 加 `-b cookies.txt` |
| 密码传了 MD5 | 登录失败 | 直接传明文 |
| 任务已结束再切换 | success=false | 只能切"进行中"的任务 |
| 用错模型 id | 切换失败或切到别的模型 | 从 models 接口抄 `monkeycode-basic/glm-4.7` 的 id |

---

## 七、本指南用到的"高级工具/功能"逐个说明

> 这一段是写给"只有基本功能"的 Agent 看的。本指南用到了几个超出"普通文件读写"的能力，如果你在别的环境里没这些能力，按下面说明照做即可。

### 7.1 命令行（终端）执行能力

本指南几乎所有步骤都要敲命令（curl、python3、pip、git）。如果你的 Agent 只能读写文件不能执行命令，那这份文档没法执行——需要先在环境里开通"执行终端命令"的能力。

### 7.2 `curl`：命令行请求接口

就是"用命令发网络请求"。所有 `curl -sS ... "网址"` 的写法都是"请求这个网址"。上面每个步骤都给了完整命令，直接复制粘贴即可。

### 7.3 Python 脚本（PoW 验证码求解）

登录验证码不是图片而是一道哈希数学题，必须写 Python 脚本暴力求解。文档里 `solver.py` / `one_shot.py` 是完整可用的，**直接保存运行即可**，不需要理解 `fnv1a32`、`prng` 这些函数原理。它们是对平台开源代码里 `go-cap` 库算法的复刻，保证结果一致。

### 7.4 `pip install --break-system-packages`

安装 Python 第三方库的命令。新版 Linux 的 Python 会拦截"往系统目录装包"，`--break-system-packages` 是放开限制的参数。如果你的 Python 报错提示"externally-managed-environment"，就加这个参数。

### 7.5 WebSocket（长连接通信）

网页正常的请求是"一问一答"（HTTP），WebSocket 是"先连一根持续的水管，双方随时发消息"。切换正在运行的任务模型只能用 WebSocket。我们用 `websocket-client` 这个库，脚本 `switch_model.py` 已把"连上 → 发指令 → 收结果"全部写好。

### 7.6 图片理解工具（本指南定位截图时用到）

如果你拿到了"截图"但只能看到文件路径、看不到图内容，可以借助"图片理解/OCR"能力让程序读图并把里面文字提取出来。本指南在定位"默认模型 glm-4.7"时，就是靠工具把用户截图里的模型选择框文字识别出来，才知道截图界面长什么样。属于辅助能力，不影响上面命令的执行。

### 7.7 git 提交文档到 GitHub

```bash
# 1) 把远程仓库克隆到本地
git clone https://github.com/liliangxing/docs.git
cd docs

# 2) 把你写好的文档放进这个目录（复制进去）

# 3) 提交并推送
git add "文档名.md"
git commit -m "docs: 新增 MonkeyCode 额度查询与任务模型切换指南"
git push
```

> 首次 push 需要 GitHub 账号授权（Token）。如果提示权限不足，用有写权限的 Token 或个人访问令牌配置远程地址。

---

## 八、常见问题 FAQ

**Q1：为什么登录要这么麻烦，不能直接调 wallet 接口？**
因为 wallet 接口需要登录态（Cookie），而登录必须过验证码。验证码是数学题，不是图片，所以必须用脚本算。

**Q2：`daily_token_balance` 会不会每天变？**
会。它代表"今天剩余额度"，用了就减少；每天重置回上限（3000 万）。例如同一天早中晚查询，数值可能不同。

**Q3：把任务切成 glm-4.7 后，任务会重新跑吗？**
会加载原上下文（因为我们传了 `load_session: true`），任务会继续原来的对话，只是底层模型换成 glm-4.7。

**Q4：切换模型收费吗？**
`monkeycode-basic/glm-4.7` 属于基础档模型，按账号套餐和今日额度规则计费，走 `daily_token_balance` / `balance`。切模型本身不额外收手续费。

**Q5：我照着抄命令为什么还是失败？**
90% 是因为：① Cookie 过期或带错账号；② 验证码令牌用过一次；③ 任务 id 抄错。按"第六节"的排查表逐项核对。

---

## 附：本文档涉及的完整命令清单（复制粘贴版）

```bash
# ========= 第一部分：查询今日额度 =========

# 1. 检查环境
python3 --version && curl --version

# 2. 获取验证码挑战（保存到文件）
curl -sS -X POST "https://monkeycode-ai.com/api/v1/public/captcha/challenge" \
  -H "Content-Type: application/json" -d '{}' -o challenge.json
cat challenge.json

# 3. 写 solver.py（见上文），把 token 填进去
python3 solver.py

# 4. 兑换验证令牌（替换成真实值）
curl -sS -X POST "https://monkeycode-ai.com/api/v1/public/captcha/redeem" \
  -H "Content-Type: application/json" \
  -d '{"token":"<挑战token>","solutions":[<50个数字>]}'

# 5. 登录（替换邮箱密码令牌），保存 Cookie
curl -sS -X POST "https://monkeycode-ai.com/api/v1/users/password-login" \
  -H "Content-Type: application/json" \
  -d '{"email":"253254457@qq.com","password":"000000aaa","captcha_token":"<验证令牌>"}' \
  -c cookies.txt -o login.json
cat login.json

# 6. 查询今日额度（核心）
curl -sS "https://monkeycode-ai.com/api/v1/users/wallet" -b cookies.txt -H "Accept: application/json"

# ========= 第二部分：切换任务模型为 glm-4.7 =========

# 7. 查任务列表，找到 status=processing 的任务 id
curl -sS "https://monkeycode-ai.com/api/v1/users/tasks?limit=10" -b cookies.txt

# 8. 安装 WebSocket 库
pip install --break-system-packages websocket-client

# 9. 写 switch_model.py（见上文，填入任务 id、Cookie、glm-4.7 模型 id）
python3 switch_model.py

# 10. 验证
curl -sS "https://monkeycode-ai.com/api/v1/users/tasks?limit=10" -b cookies.txt | grep -E '"id"|"status"|"model"'
```

---

## 本指南参考的真实数据（2026-08-06 实测）

| 项目 | 值 |
|------|-----|
| 目标接口 | `GET /api/v1/users/wallet` |
| 接口返回 | `code=0`，`balance=143117`，`daily_token_balance=21790963`，`daily_token_limit=30000000` |
| 登录接口 | `POST /api/v1/users/password-login` |
| 验证码接口 | `POST /api/v1/public/captcha/challenge`、`POST /api/v1/public/captcha/redeem` |
| 任务控制（切换模型） | WebSocket `wss://monkeycode-ai.com/api/v1/users/tasks/control?id=<任务id>`，发 `switch_model` 指令 |
| 切换目标模型 | `monkeycode-basic/glm-4.7`（id=`c2e2d76b-ac3a-4945-8ad6-e6f78a6ccd93`） |
| 切换结果 | `success: true`，任务保持 `processing` |
