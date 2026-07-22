# Dify + LiteLLM 搭建指南

> 一份写给"命令不熟练但想自己搭"的详细教程

---

## 目录

1. [这个项目是干什么的](#1-这个项目是干什么的)
2. [动手前的准备：装 Docker](#2-动手前的准备装-docker)
3. [解决 Docker Hub 连不上的问题](#3-解决-docker-hub-连不上的问题)
4. [创建项目目录和配置文件](#4-创建项目目录和配置文件)
5. [配置说明（关键！一定要看懂）](#5-配置说明关键一定要看懂)
6. [启动服务](#6-启动服务)
7. [验证服务是否正常](#7-验证服务是否正常)
8. [常见问题排查](#8-常见问题排查)
9. [附录：所有关键文件一览](#9-附录所有关键文件一览)

---

## 1. 这个项目是干什么的

### 大白话解释

现在有很多 AI 大模型，比如 OpenAI 的 GPT-4o、Anthropic 的 Claude。每个公司都有自己的 API（接口），写法不一样、计费方式也不一样。如果你做一个应用要调用多个大模型，每个都要单独对接，非常麻烦。

**LiteLLM** 的作用：它就像是一个"翻译官"或者"总机"。你把所有大模型的账号密码告诉 LiteLLM，然后你的应用只需要用一种统一的格式和 LiteLLM 对话，LiteLLM 会自动帮你转到对应的大模型。

**Dify** 的作用：它是一个可视化 AI 应用搭建平台。你可以在上面拖拖拽拽，做出聊天机器人、知识库问答、工作流自动化等等。

**两者结合**：Dify 通过 LiteLLM 访问大模型，这样你在 Dify 里就能同时使用 OpenAI、Claude 等多个模型，还不用每个都单独配置。

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                      你的浏览器                          │
│                  http://localhost:80                     │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                    Nginx (端口 80)                       │
│                   Dify 前端入口                          │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
┌─────────────┐ ┌──────────┐ ┌──────────┐
│  Dify API   │ │Dify Web  │ │  Worker  │
│  (5001端口) │ │(3000端口)│ │ (后台)   │
└──────┬──────┘ └──────────┘ └──────────┘
       │
       │ 通过 OpenAI 兼容接口调用
       ▼
┌─────────────────────────────────────────────────────────┐
│                 LiteLLM 网关 (端口 4000)                  │
│            "统一把请求转发给不同的大模型"                  │
└──────┬──────────────┬──────────────┬────────────────────┘
       │              │              │
       ▼              ▼              ▼
   ┌──────┐     ┌──────────┐   ┌─────────┐
   │OpenAI│     │Anthropic │   │ Azure   │  ... 更多
   │GPT-4o│     │ Claude   │   │ OpenAI  │
   └──────┘     └──────────┘   └─────────┘
```

---

## 2. 动手前的准备：装 Docker

### 2.1 什么是 Docker？为什么要装它？

Docker 就像是一个"集装箱系统"。它能把软件和这个软件需要的所有东西（代码、运行环境、系统库等等）打包在一起，无论在哪个机器上都能直接跑起来，不用担心环境不一致。

**不用 Docker 的话**：你需要自己装 Python、Node.js、PostgreSQL、Redis、Nginx... 每一样都要配置，版本冲突了还要折腾半天。

**用 Docker 的话**：一条命令，全部搞定。

### 2.2 安装 Docker

```bash
# 第一步：更新系统软件包列表
# "软件包列表"就是系统能装哪些软件的目录，先更新到最新
apt-get update

# 第二步：安装 Docker
# -y 的意思是"遇到确认提示自动回答 yes"，不用你手动按
apt-get install -y docker.io

# 第三步：启动 Docker 服务
# Docker 是一个后台服务，装完要手动启动
systemctl start docker

# 第四步：设置开机自启（下次重启机器不用手动启动）
systemctl enable docker

# 第五步：验证安装是否成功
# 如果没有报错，说明装好了
docker --version
```

### 2.3 安装 Docker Compose v2（重点！避坑指南）

**Docker Compose** 是用来"批量管理多个 Docker 容器"的工具。比如我们的项目有十几个服务（数据库、缓存、网关、前端...），不可能一个一个手动启停，用 Compose 可以一条命令全部管理。

#### 踩坑：为什么不能用系统自带的老版本？

用 `apt-get install docker-compose` 装的是 **v1 老版本**。Dify 的启动配置文件用的是 **v2 语法**（比如 `depends_on` 里写了 `condition: service_healthy`），老版本读不懂会直接报错。

**正确做法**：手动装 v2：

```bash
# 第一步：从 GitHub 下载 Docker Compose v2 的可执行文件
# /usr/local/lib/docker/cli-plugins/ 是专门放插件的位置
mkdir -p /usr/local/lib/docker/cli-plugins

# 下载最新版 docker-compose（注意是 compose 不是 docker-compose，名字不一样）
# v2.24.0 是我们在用的版本，已验证可用
curl -SL "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose

# 第二步：给可执行权限
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 第三步：验证
docker compose version
# 输出应该类似: Docker Compose version v2.24.0
```

**关键区分**：装完后命令是 `docker compose`（中间有空格），不是 `docker-compose`（中间有横杠）。这是 v2 的用法，记住这个区别就不会搞混。

---

## 3. 解决 Docker Hub 连不上的问题

### 3.1 问题是什么？

Docker 的镜像（软件包）存在 Docker Hub 上（地址是 `docker.io`）。但在某些网络环境下，直接连 Docker Hub 可能会遇到：
- 连不上（被墙或网络限制）
- 证书错误（中间人劫持）
- 速度极慢

### 3.2 解决办法：配置镜像加速器

镜像加速器是一台"中转服务器"，它从 Docker Hub 拉取镜像然后转发给你，绕过网络限制。

```bash
# 写配置文件。daemon.json 是 Docker 的核心配置文件
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://mirror.gcr.io",
    "https://dockerhub.timeweb.cloud",
    "https://docker.rainbond.cc"
  ]
}
EOF
# 上面的 << 'EOF' ... EOF 是一种写法，意思是"把中间的内容写入文件"

# 重启 Docker 让配置生效
systemctl restart docker

# 验证配置是否生效
docker info | grep -A5 "Registry Mirrors"
# 如果输出了上面配置的三个地址，说明成功了
```

**为什么配了三个地址？** 这是"备份机制"。Docker 会按顺序尝试，第一个连不上自动换第二个，提高成功率。

---

## 4. 创建项目目录和配置文件

### 4.1 项目结构概览

```
/workspace/dify-stack/          ← 项目根目录
├── .env                        ← 环境变量配置（最关键的文件）
├── docker-compose.yaml         ← Dify 官方服务定义（不需要改）
├── docker-compose.litellm.yml  ← LiteLLM 网关定义（我们写的）
├── litellm/
│   └── config.yaml             ← LiteLLM 模型路由规则（我们写的）
├── start.sh                    ← 一键启动脚本（我们写的）
└── volumes/                    ← 数据持久化存储目录
```

### 4.2 创建项目目录

```bash
# 创建项目根目录
mkdir -p /workspace/dify-stack

# 进入目录（后面的操作都在这里进行）
cd /workspace/dify-stack
```

### 4.3 从 Dify 官方获取 docker-compose.yaml

Dify 官方在 GitHub 上开源了他们的代码，里面自带了一份 `docker-compose.yaml`。我们需要拿过来用。

**注意**：这里不是 clone 整个 Dify 代码仓库（太大），我们只需要那一个配置文件。

```bash
# 从 GitHub 下载官方 docker-compose.yaml（这是核心文件，定义了所有服务）
curl -o docker-compose.yaml \
  "https://raw.githubusercontent.com/langgenius/dify/main/docker/docker-compose.yaml"

# 如果你连 GitHub 也不稳定，可以手动下载后上传到项目目录
```

同时 Dify 官方 compose 文件需要配套的 `.env.example`（模板）和 `nginx` 配置。如果不能直接从 GitHub 下载，需要手动创建这些文件。

**在实际搭建中**，我们直接用 `git clone` 拿了 Dify 官方仓库里的 `docker/` 目录中的所有文件，然后在此基础上加 LiteLLM 的配置。两种方式都可以。

### 4.4 创建 .env 环境变量文件

`.env` 文件是整个项目最重要的配置文件。它里面记录了数据库密码、API Key、服务端口等所有敏感和可变的配置。

```bash
# 复制官方的模板文件作为起点
cp .env.example .env
```

然后编辑 `.env` 文件，修改以下关键配置：

#### 关键配置项解释

| 配置项 | 干什么用的 | 怎么填 |
|--------|-----------|--------|
| `OPENAI_API_BASE` | Dify 把 LLM 请求发到哪 | `http://litellm:4000/v1` |
| `OPENAI_API_KEY` | 访问 LiteLLM 的密码 | `sk-litellm-master-key-change-me` |
| `LITELLM_MASTER_KEY` | LiteLLM 自己的管理员密码 | 改成你自己想的强密码 |
| `LITELLM_UPSTREAM_OPENAI_KEY` | 你真实的 OpenAI API Key | 去 OpenAI 官网拿 |
| `LITELLM_UPSTREAM_ANTHROPIC_KEY` | 你真实的 Anthropic API Key | 去 Anthropic 官网拿 |
| `DB_PASSWORD` | Dify 数据库密码 | 保持默认或改成你自己的 |
| `REDIS_PASSWORD` | Redis 缓存密码 | 保持默认或改成你自己的 |

**最重要的原理**：Dify 不直接连 OpenAI/Anthropic，而是连 LiteLLM。所以：

- `OPENAI_API_BASE` 指向 LiteLLM 的地址：`http://litellm:4000/v1`
- `OPENAI_API_KEY` 是 LiteLLM 的 master key（你设置的密码），不是 OpenAI 的 key
- 真正的 OpenAI/Anthropic API Key 存在 `LITELLM_UPSTREAM_*` 这个变量里，由 LiteLLM 自己使用

> ⚠️ **安全提醒**：`.env` 文件包含敏感信息，已在 `.gitignore` 中排除，不会被提交到 Git。

### 4.5 创建 LiteLLM 网关配置

#### docker-compose.litellm.yml

这个文件定义了两个服务：

1. **litellm**：LiteLLM 网关本身，监听 4000 端口
2. **litellm_db**：LiteLLM 专用的 PostgreSQL 数据库

```bash
mkdir -p /workspace/dify-stack/litellm
```

**为什么要给 LiteLLM 单独配一个数据库？**

LiteLLM 需要存很多东西：虚拟 key 列表、调用日志、速率限制数据等等。不能和 Dify 的业务数据库共用，因为它们的用途完全不一样。Dify 存的是"工作流、知识库、用户数据"，LiteLLM 存的是"API 调用记录、key 管理"。分开存放有两个好处：出了问题互不影响；万一将来 LiteLLM 换数据库，Dify 不受影响。

```bash
cat > /workspace/dify-stack/docker-compose.litellm.yml << 'DOCKEREOF'
version: '3.8'

services:
  litellm:
    image: docker.litellm.ai/berriai/litellm:main-stable
    container_name: litellm
    ports:
      - "4000:4000"
    volumes:
      - ./litellm/config.yaml:/app/config.yaml
    command:
      - "--config=/app/config.yaml"
      - "--port=4000"
    environment:
      DATABASE_URL: "postgresql://llmproxy:dbpassword9090@litellm_db:5432/litellm"
      STORE_MODEL_IN_DB: "True"
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:-sk-litellm-master-key-change-me}
      LITELLM_UPSTREAM_OPENAI_KEY: ${LITELLM_UPSTREAM_OPENAI_KEY:-}
      LITELLM_UPSTREAM_ANTHROPIC_KEY: ${LITELLM_UPSTREAM_ANTHROPIC_KEY:-}
    depends_on:
      litellm_db:
        condition: service_healthy
    healthcheck:
      test:
        - CMD-SHELL
        - python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:4000/health/liveliness')"
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: always
    networks:
      - default

  litellm_db:
    image: postgres:16-alpine
    container_name: litellm_db
    environment:
      POSTGRES_DB: litellm
      POSTGRES_USER: llmproxy
      POSTGRES_PASSWORD: dbpassword9090
    volumes:
      - ./volumes/litellm_db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d litellm -U llmproxy"]
      interval: 1s
      timeout: 5s
      retries: 10
    restart: always
DOCKEREOF
```

**关键配置解读**：

- `${LITELLM_MASTER_KEY:-sk-litellm-master-key-change-me}`：这个写法的意思是"如果 `.env` 里设了 `LITELLM_MASTER_KEY` 就用那个值，否则用后面这个默认值"
- `${LITELLM_UPSTREAM_OPENAI_KEY:-}`：同样逻辑，但默认值是空（没有默认值，必须由用户填入）
- `condition: service_healthy`：意思是"等 litellm_db 的健康检查通过了再启动 litellm"，确保启动顺序正确

#### litellm/config.yaml（模型路由配置）

```bash
cat > /workspace/dify-stack/litellm/config.yaml << 'CONFEOF'
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY

model_list:
  # OpenAI 模型
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/LITELLM_UPSTREAM_OPENAI_KEY
  - model_name: gpt-4o-mini
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/LITELLM_UPSTREAM_OPENAI_KEY
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: openai/gpt-3.5-turbo
      api_key: os.environ/LITELLM_UPSTREAM_OPENAI_KEY

  # Anthropic 模型
  - model_name: claude-sonnet-4-20250514
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/LITELLM_UPSTREAM_ANTHROPIC_KEY
  - model_name: claude-3-5-sonnet-20241022
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/LITELLM_UPSTREAM_ANTHROPIC_KEY

litellm_settings:
  num_retries: 3               # 调用失败后重试3次
  request_timeout: 600         # 单个请求最长等待10分钟
  set_verbose: false
  drop_params: true            # 忽略模型不认识的参数（避免报错）
  success_callback: ["prometheus"]
  failure_callback: ["prometheus"]

router_settings:
  routing_strategy: "latency-based-routing"  # 按延迟选最快的模型
  fallbacks:
    - gpt-4o: ["gpt-4o-mini"]               # gpt-4o 挂了自动切 gpt-4o-mini
    - claude-sonnet-4-20250514: ["gpt-4o"]   # Claude 挂了自动切 GPT
CONFEOF
```

**模型路由配置解读**：

1. **`model_name`**：是暴露给 Dify 用的名字（你可以自定义）
2. **`model`**：是 LiteLLM 内部转发用的名字。格式是 `提供商/模型名`，比如 `openai/gpt-4o` 意思是"用 OpenAI 的格式去调 gpt-4o"
3. **`api_key: os.environ/XXXXX`**：从环境变量读取 API Key。因为 Key 是敏感信息，不能写在配置文件里（会被提交到 Git），所以通过环境变量传进来
4. **`fallbacks`（备用模型）**：主模型不可用时，自动切到备用模型。比如 OpenAI 宕机了，请求自动转给 Anthropic

#### 如何添加新模型

假设你想添加一个 Google 的 Gemini 模型：

```yaml
# 在 model_list 里加一段
- model_name: gemini-pro
  litellm_params:
    model: gemini/gemini-1.5-pro
    api_key: os.environ/LITELLM_UPSTREAM_GEMINI_KEY
```

然后别忘了在 `.env` 里加上 `LITELLM_UPSTREAM_GEMINI_KEY=你的key`。

### 4.6 创建一键启动脚本

```bash
cat > /workspace/dify-stack/start.sh << 'SHEOF'
#!/bin/bash
# 一键启动 LiteLLM + Dify

set -e  # 任何命令出错就立即停止

cd "$(dirname "$0")"

# === 第一步：先启动 LiteLLM（因为它不依赖 Dify 的任何东西）===
echo "正在启动 LiteLLM 网关..."
docker compose -f docker-compose.litellm.yml up -d
# -f 指定用哪个 compose 文件
# up -d 启动服务并在后台运行

# 等待 LiteLLM 就绪
echo "等待 LiteLLM 就绪（最多 60 秒）..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:4000/health/liveliness >/dev/null 2>&1; then
        echo "✓ LiteLLM 已就绪"
        break
    fi
    sleep 2
done

# === 第二步：启动 Dify 全家桶 ===
echo "正在启动 Dify 服务（首次需要下载镜像，可能比较久）..."
docker compose \
    -f docker-compose.yaml \
    -f docker-compose.litellm.yml \
    --profile postgresql \
    --profile weaviate \
    --profile collaboration \
    up -d
# 这里同时用了两个 -f，Docker 会把两个文件合并处理
# --profile 激活哪些可选服务组

# 等待 Dify API 就绪
echo "等待 Dify API 就绪（最多 180 秒）..."
for i in $(seq 1 90); do
    if curl -sf http://localhost:5001/health >/dev/null 2>&1; then
        echo "✓ Dify API 已就绪"
        break
    fi
    sleep 2
done

# 等待 Nginx 就绪
echo "等待前端入口就绪..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:80 >/dev/null 2>&1; then
        echo "✓ Nginx 前端入口已就绪"
        break
    fi
    sleep 2
done

echo ""
echo "===== 全部启动完成 ====="
echo "Dify 控制台: http://localhost:80"
echo "LiteLLM 网关: http://localhost:4000"
SHEOF

# 添加执行权限
chmod +x /workspace/dify-stack/start.sh
```

---

## 5. 配置说明（关键！一定要看懂）

### 5.1 为什么用两个 compose 文件，而不是一个？

Dify 官方的 `docker-compose.yaml` 定义了 Dify 自己需要的所有服务（API、Web、Worker、数据库、Redis、向量数据库等等）。

我们的 `docker-compose.litellm.yml` 定义了 LiteLLM 网关和它的数据库。

**为什么要分开？**
- Dify 的配置文件是官方维护的，你改了它，以后官方更新了你想升级就麻烦了
- LiteLLM 是我们自己加的，单独一个文件，想加想删都方便
- 两个文件通过 `docker compose -f a.yaml -f b.yaml up -d` 合并运行，效果等价于一个文件

### 5.2 `--profile` 是什么？

Dify 的 compose 文件里有些服务打了 `profiles` 标签，意思是"可选服务，需要时才启动"。

```
--profile postgresql     → 启动 PostgreSQL 数据库
--profile weaviate       → 启动 Weaviate 向量数据库
--profile collaboration  → 启动协作模式功能
```

### 5.3 Dify 怎么连上 LiteLLM 的？

核心就两个环境变量：

```
OPENAI_API_BASE=http://litellm:4000/v1
OPENAI_API_KEY=sk-litellm-master-key-change-me
```

**大白话解释**：
- Dify 内置了"以 OpenAI 兼容的方式调用大模型"的功能
- LiteLLM 提供了一个"长得跟 OpenAI 一模一样的接口"
- 所以只要把 Dify 的 API 地址指向 LiteLLM，Dify 就能通过 LiteLLM 调用所有模型了
- `litellm` 是 Docker 服务名（不是 localhost），Docker 内部有 DNS 可以自动解析

### 5.4 LiteLLM 怎么调用真实大模型的？

LiteLLM 的 `config.yaml` 里写了每个模型的"真名"和 API Key。当 Dify 请求"gpt-4o"时：

1. LiteLLM 在自己的 `model_list` 里找到 `gpt-4o`
2. 发现它对应的是 `openai/gpt-4o`
3. 用 `LITELLM_UPSTREAM_OPENAI_KEY` 这个 Key，按 OpenAI 的格式发请求
4. 拿到结果，按 OpenAI 格式返回给 Dify

**整个过程对 Dify 来说**：它只知道自己调了一个叫"gpt-4o"的 OpenAI 模型。实际上这个请求经过了 LiteLLM 的转发和可能的 fallback 处理。

---

## 6. 启动服务

### 6.1 启动所有服务

```bash
# 进入项目目录
cd /workspace/dify-stack

# 方式一：使用一键脚本
./start.sh

# 方式二：手动执行
docker compose \
    -f docker-compose.yaml \
    -f docker-compose.litellm.yml \
    --profile postgresql \
    --profile weaviate \
    --profile collaboration \
    up -d
```

**首次启动** 会比较慢（几分钟到十几分钟），因为 Docker 要下载所有镜像（每个几百 MB）。

### 6.2 查看服务状态

```bash
# 查看所有容器的运行状态
docker compose -f docker-compose.yaml -f docker-compose.litellm.yml --profile postgresql --profile weaviate --profile collaboration ps

# 应该看到所有服务都是 Up 状态（绿色的 running）
```

### 6.3 查看日志

```bash
# 查看所有服务的日志（Ctrl+C 退出）
docker compose -f docker-compose.yaml -f docker-compose.litellm.yml --profile postgresql --profile weaviate --profile collaboration logs -f

# 只看 LiteLLM 的日志
docker compose -f docker-compose.litellm.yml logs litellm

# 只看 Dify API 的日志
docker compose -f docker-compose.yaml logs api
```

### 6.4 停止服务

```bash
# 停止所有服务（数据不会丢，存在 volumes/ 里）
docker compose -f docker-compose.yaml -f docker-compose.litellm.yml --profile postgresql --profile weaviate --profile collaboration down

# 单独停 LiteLLM
docker compose -f docker-compose.litellm.yml down
```

---

## 7. 验证服务是否正常

### 7.1 检查 LiteLLM 是否活着

```bash
# 访问 LiteLLM 健康检查接口
curl http://localhost:4000/health/liveliness

# 如果返回 "I'm alive!" 说明 LiteLLM 正常运行
```

### 7.2 查看 LiteLLM 暴露了哪些模型

```bash
# 用 LiteLLM 的 master key 查询模型列表
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer sk-litellm-master-key-change-me"

# 返回的 JSON 里 data 字段列出了所有配置的模型
# 比如 gpt-4o, gpt-4o-mini, claude-sonnet-4-20250514 等
```

### 7.3 测试 Dify 前端

```bash
# 检查 Dify 前端是否响应
curl -I http://localhost:80

# 如果返回 HTTP/1.1 307 或者 200，说明 Nginx 在正常工作
```

### 7.4 在浏览器中访问

打开浏览器，访问 `http://localhost:80`，你应该看到 Dify 的初始化页面：
1. 首次访问会要求设置管理员邮箱和密码
2. 设置完成后进入 Dify 主界面
3. 在"设置 → 模型提供商"中可以看到通过 LiteLLM 暴露的模型

---

## 8. 常见问题排查

### 8.1 Linux 下装了 Docker 但 docker 命令不能用

```bash
# 这种情况通常是当前用户不在 docker 组里
# 把当前用户加入 docker 组
sudo usermod -aG docker $USER

# 退出终端重新登录，或者执行
newgrp docker
```

### 8.2 Docker Compose v1 报错 "Additional property condition is not allowed"

这说明你用的是 v1 老版本，不认识 v2 的新语法。必须按本文 [2.3 节](#23-安装-docker-compose-v2重点避坑指南) 的方法重装 v2。

### 8.3 镜像下载失败或极慢

参考本文 [第 3 节](#3-解决-docker-hub-连不上的问题)，检查镜像加速器是否配置成功：

```bash
docker info | grep -A5 "Registry Mirrors"
```

如果输出为空，说明没有生效。需要检查 `/etc/docker/daemon.json` 是否正确，然后重启 Docker。

### 8.4 LiteLLM 启动失败，报数据库连接错误

```bash
# 先检查 litellm_db 是否正常
docker compose -f docker-compose.litellm.yml ps

# 如果 litellm_db 还没启动或挂了，重新启动它
docker compose -f docker-compose.litellm.yml restart litellm_db

# 等它启动完成后再重启 litellm
docker compose -f docker-compose.litellm.yml restart litellm
```

### 8.5 Dify 页面能打开但调用模型时报错

99% 是因为 `LITELLM_UPSTREAM_OPENAI_KEY` 或 `LITELLM_UPSTREAM_ANTHROPIC_KEY` 没有填。

```bash
# 检查 .env 里是否填了真实 API Key
grep "LITELLM_UPSTREAM" /workspace/dify-stack/.env

# 如果值是空的，编辑 .env 填上真实 Key，然后重启 LiteLLM
docker compose -f docker-compose.litellm.yml restart litellm
```

### 8.6 端口冲突（4000 或 80 被其他程序占用）

```bash
# 查看谁在用这些端口
ss -tlnp | grep -E ':80|:4000'

# 停止占用的程序后再启动
```

### 8.7 服务启动后总是自动退出

```bash
# 查看具体容器的日志，定位原因
docker compose -f docker-compose.yaml -f docker-compose.litellm.yml logs 容器名

# 常见原因：
# 1. 环境变量缺失
# 2. 依赖的服务没启动
# 3. 数据库迁移失败
```

---

## 9. 附录：所有关键文件一览

### docker-compose.litellm.yml

```yaml
version: '3.8'
services:
  litellm:
    image: docker.litellm.ai/berriai/litellm:main-stable
    container_name: litellm
    ports:
      - "4000:4000"
    volumes:
      - ./litellm/config.yaml:/app/config.yaml
    command:
      - "--config=/app/config.yaml"
      - "--port=4000"
    environment:
      DATABASE_URL: "postgresql://llmproxy:dbpassword9090@litellm_db:5432/litellm"
      STORE_MODEL_IN_DB: "True"
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:-sk-litellm-master-key-change-me}
      LITELLM_UPSTREAM_OPENAI_KEY: ${LITELLM_UPSTREAM_OPENAI_KEY:-}
      LITELLM_UPSTREAM_ANTHROPIC_KEY: ${LITELLM_UPSTREAM_ANTHROPIC_KEY:-}
      LITELLM_UPSTREAM_AZURE_KEY: ${LITELLM_UPSTREAM_AZURE_KEY:-}
      LITELLM_UPSTREAM_AZURE_BASE: ${LITELLM_UPSTREAM_AZURE_BASE:-}
      LITELLM_UPSTREAM_AZURE_VERSION: ${LITELLM_UPSTREAM_AZURE_VERSION:-2024-02-15-preview}
    depends_on:
      litellm_db:
        condition: service_healthy
    healthcheck:
      test:
        - CMD-SHELL
        - python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:4000/health/liveliness')"
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: always
    networks:
      - default
  litellm_db:
    image: postgres:16-alpine
    container_name: litellm_db
    environment:
      POSTGRES_DB: litellm
      POSTGRES_USER: llmproxy
      POSTGRES_PASSWORD: dbpassword9090
    volumes:
      - ./volumes/litellm_db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d litellm -U llmproxy"]
      interval: 1s
      timeout: 5s
      retries: 10
    restart: always
```

### litellm/config.yaml

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY

model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/LITELLM_UPSTREAM_OPENAI_KEY
  - model_name: gpt-4o-mini
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/LITELLM_UPSTREAM_OPENAI_KEY
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: openai/gpt-3.5-turbo
      api_key: os.environ/LITELLM_UPSTREAM_OPENAI_KEY
  - model_name: claude-sonnet-4-20250514
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/LITELLM_UPSTREAM_ANTHROPIC_KEY
  - model_name: claude-3-5-sonnet-20241022
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/LITELLM_UPSTREAM_ANTHROPIC_KEY

litellm_settings:
  num_retries: 3
  request_timeout: 600
  set_verbose: false
  drop_params: true

router_settings:
  routing_strategy: "latency-based-routing"
  fallbacks:
    - gpt-4o: ["gpt-4o-mini"]
    - claude-sonnet-4-20250514: ["gpt-4o"]
```

### start.sh

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

docker compose -f docker-compose.litellm.yml up -d

for i in $(seq 1 30); do
    if curl -sf http://localhost:4000/health/liveliness >/dev/null 2>&1; then break; fi
    sleep 2
done

docker compose \
    -f docker-compose.yaml \
    -f docker-compose.litellm.yml \
    --profile postgresql --profile weaviate --profile collaboration \
    up -d

echo "完成! Dify: http://localhost:80  LiteLLM: http://localhost:4000"
```

### .env 关键部分

```ini
# Dify 连接 LiteLLM 网关
OPENAI_API_BASE=http://litellm:4000/v1
OPENAI_API_KEY=sk-litellm-master-key-change-me

# LiteLLM 管理员密码
LITELLM_MASTER_KEY=sk-litellm-master-key-change-me

# 上游 LLM API Key（填你真实的）
LITELLM_UPSTREAM_OPENAI_KEY=
LITELLM_UPSTREAM_ANTHROPIC_KEY=
LITELLM_UPSTREAM_AZURE_KEY=
LITELLM_UPSTREAM_AZURE_BASE=
LITELLM_UPSTREAM_AZURE_VERSION=2024-02-15-preview

# 数据库和 Redis 密码
DB_PASSWORD=difyai123456
REDIS_PASSWORD=difyai123456

# 向量数据库
VECTOR_STORE=weaviate
WEAVIATE_ENDPOINT=http://weaviate:8080
```

### 启动命令速查

| 操作 | 命令 |
|------|------|
| 启动全部服务 | `docker compose -f docker-compose.yaml -f docker-compose.litellm.yml --profile postgresql --profile weaviate --profile collaboration up -d` |
| 查看服务状态 | `docker compose -f docker-compose.yaml -f docker-compose.litellm.yml --profile postgresql --profile weaviate --profile collaboration ps` |
| 查看日志 | `docker compose -f docker-compose.yaml -f docker-compose.litellm.yml --profile postgresql --profile weaviate --profile collaboration logs -f` |
| 停止全部服务 | `docker compose -f docker-compose.yaml -f docker-compose.litellm.yml --profile postgresql --profile weaviate --profile collaboration down` |
| 单独重启 LiteLLM | `docker compose -f docker-compose.litellm.yml restart litellm` |
| 检查 LiteLLM 健康 | `curl http://localhost:4000/health/liveliness` |
| 列出可用模型 | `curl http://localhost:4000/v1/models -H "Authorization: Bearer sk-litellm-master-key-change-me"` |

---

> 文档版本：v1.0
> 创建日期：2026-06-27
> 适用环境：Linux (Ubuntu/Debian) + Docker Compose v2
