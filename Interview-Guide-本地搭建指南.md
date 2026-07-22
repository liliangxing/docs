# Interview Guide 本地搭建完全指南

> **适用人群**：对命令行不熟悉、想一步步跑起来的开发者。  
> **文档说明**：本文记录从零开始搭建 Interview Guide（AI 智能面试官平台）的完整过程，**包含踩坑记录和排查命令**。

---

## 目录

- [一、项目简介](#一项目简介)
- [二、准备工作：Fork + 克隆项目](#二准备工作fork--克隆项目)
- [三、环境搭建](#三环境搭建)
  - [3.1 安装 Java（重要踩坑）](#31-安装-java重要踩坑)
  - [3.2 准备 Node.js 和 pnpm](#32-准备-nodejs-和-pnpm)
  - [3.3 Docker 启动基础设施](#33-docker-启动基础设施)
- [四、后端启动](#四后端启动)
  - [4.1 配置环境变量](#41-配置环境变量)
  - [4.2 编译后端](#42-编译后端)
  - [4.3 启动后端开发服务器](#43-启动后端开发服务器)
  - [4.4 验证后端启动成功](#44-验证后端启动成功)
- [五、前端启动](#五前端启动)
  - [5.1 安装依赖](#51-安装依赖)
  - [5.2 启动前端开发服务器](#52-启动前端开发服务器)
  - [5.3 验证前端](#53-验证前端)
- [六、构建发布产物](#六构建发布产物)
  - [6.1 构建可执行 JAR](#61-构建可执行-jar)
  - [6.2 构建前端 dist](#62-构建前端-dist)
- [七、常见问题与排查](#七常见问题与排查)
  - [7.1 Java 版本不匹配](#71-java-版本不匹配)
  - [7.2 Gradle 命令找不到](#72-gradle-命令找不到)
  - [7.3 Docker 容器未启动](#73-docker-容器未启动)
  - [7.4 pnpm 原生模块构建失败](#74-pnpm-原生模块构建失败)
  - [7.5 前端代理不到后端](#75-前端代理不到后端)
  - [7.6 Vite 拒绝外部域名访问](#76-vite-拒绝外部域名访问)
  - [7.7 JAR 文件无法运行](#77-jar-文件无法运行)
- [八、调试命令速查表](#八调试命令速查表)
- [九、搭建小结](#九搭建小结)

---

## 一、项目简介

Interview Guide 是一个**智能 AI 面试官平台**，技术栈如下：

| 层面 | 技术 | 说明 |
|------|------|------|
| 后端 | Spring Boot 4.1 + Java 21 | REST API，端口 8080 |
| AI 框架 | Spring AI 2.0 | 对接多种 LLM（默认阿里云百炼） |
| 数据库 | PostgreSQL 16 + pgvector | 向量数据库，支持 RAG 知识库 |
| 缓存/队列 | Redis 7 + Redisson | 消息队列 + 缓存 |
| 对象存储 | RustFS（开发）/ MinIO（生产） | S3 兼容接口 |
| 前端 | React 18 + TypeScript + Vite | 端口 5173 |
| 构建工具 | Gradle 8.14（后端）/ pnpm（前端） | — |

项目源码地址：`https://github.com/liliangxing/interview-guide`

---

## 二、准备工作：Fork + 克隆项目

### 2.1 Fork 项目

在 GitHub 上打开原项目 `Snailclimb/interview-guide`，点击右上角 Fork 按钮，将项目 Fork 到自己的账号 `liliangxing/interview-guide`。

### 2.2 克隆到本地

```bash
# 克隆项目到本地
git clone https://github.com/liliangxing/interview-guide.git

# 进入项目目录
cd interview-guide
```

> **提示**：如果你使用的是 GitHub Token 认证（而不是 SSH Key），可以用带 Token 的 URL：
> ```bash
> git clone https://你的Token@github.com/liliangxing/interview-guide.git
> ```

---

## 三、环境搭建

### 3.1 安装 Java（重要踩坑）

这是整个搭建过程中**最容易出问题的地方**，请仔细阅读。

#### 为什么需要 Java 21？

项目的 `app/build.gradle` 中配置了 toolchain：

```groovy
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}
```

这意味着**编译和运行都需要 Java 21**。如果你用 Java 17 去运行编译好的 JAR 包，会报错：

```
Unsupported class file major version 65
```

> **大白话**：Java 21 编译出来的 .class 文件版本号是 65，Java 17 只认到 61，所以它不认识这些文件，直接报错。

#### 系统自带的 Java 是 17 还是 21？

先看看系统里装了什么：

```bash
# 查看已安装的 Java 版本
java -version

# 查看 Java 安装位置
which java
```

本环境的输出：

```
openjdk version "17.0.17" 2026-04-20
```

系统自带了 Java 17。**但 Java 21 可以通过 Gradle 自动下载！**

#### Gradle 工具链自动下载 JDK 21

项目的 `settings.gradle` 中配置了 **foojay-resolver**：

```groovy
plugins {
    id 'org.gradle.toolchains.foojay-resolver-convention' version '0.9.0'
}
```

这个插件的作用是：当你运行 `./gradlew compileJava` 时，如果 Gradle 发现系统里没有 Java 21，它会**自动从网络下载**一个 JDK 21 放到 Gradle 的缓存目录。

下载后的位置：

```
/root/.gradle/jdks/eclipse_adoptium-21-amd64-linux.2/
```

里面有完整的 Java 21 环境，可以这样验证：

```bash
# 查看 Gradle 自动下载的 JDK 21 版本
/root/.gradle/jdks/eclipse_adoptium-21-amd64-linux.2/bin/java -version
```

输出：

```
openjdk version "21.0.11" 2026-04-21 LTS
```

> **大白话**：你不用手动安装 Java 21，只要确保系统有 Java 17 作为"引导 JDK"，然后 Gradle 会自动帮你下载和管理 Java 21。省心！

#### 关键结论

| 场景 | 需要的 Java 版本 | 说明 |
|------|---------------|------|
| 运行 Gradle 命令 | Java 17（系统自带即可） | Gradle 自身用 17 就能跑 |
| 编译后端代码 | Java 21（Gradle 自动下载） | 通过 foojay-resolver 自动获取 |
| 运行 JAR 包 | Java 21（需手动指定路径） | 必须用 Java 21 的 java 命令 |

### 3.2 准备 Node.js 和 pnpm

```bash
# 检查 Node.js 版本（需要 18+）
node -v

# 检查 pnpm 是否安装
which pnpm
# 如果没有安装 pnpm：
npm install -g pnpm
```

### 3.3 Docker 启动基础设施

后端依赖三样东西：数据库、Redis、对象存储。项目提供了开发用的 Docker 编排文件，一键搞定。

```bash
# 启动开发环境的依赖服务（PostgreSQL + Redis + RustFS）
docker compose -f docker-compose.dev.yml up -d
```

这个命令会做什么：
- 启动 **PostgreSQL 16**（含 pgvector 扩展），端口 5432，密码 `password`
- 启动 **Redis 7**，端口 6379
- 启动 **RustFS**（S3 兼容对象存储），端口 9000

```bash
# 验证容器是否都在运行
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

期望看到三个容器状态都是 `Up` 和 `healthy`：

| 容器名 | 端口 |
|--------|------|
| interview-postgres | 5432 |
| interview-redis | 6379 |
| interview-rustfs | 9000 |

如果某个容器没有 `healthy`，检查日志：

```bash
# 查看某个容器的详细日志
docker logs interview-postgres
```

---

## 四、后端启动

### 4.1 配置环境变量

项目根目录有一个 `.env.example` 模板文件，需要复制一份：

```bash
# 复制环境变量模板
cp .env.example .env
```

`.env` 文件中的关键配置：

```bash
# 数据库配置（要与 docker-compose.dev.yml 保持一致）
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=interview_guide
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379

# AI 百炼 API Key（需要去阿里云百炼平台申请）
# 注意：不填真实 Key 的话，AI 功能（语音面试、简历分析、知识库问答）会报 401 错误
AI_BAILIAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **避坑提醒**：`POSTGRES_PASSWORD` 必须和 `docker-compose.dev.yml` 中配置的密码一致，否则后端连不上数据库。

### 4.2 编译后端

```bash
# 编译后端 Java 代码（只编译不运行）
./gradlew :app:compileJava
```

如果编译成功，输出类似：

```
BUILD SUCCESSFUL in 5s
```

> **大白话**：`./gradlew` 是 Gradle 的包装脚本（Gradle Wrapper），它会自动下载正确版本的 Gradle，你不需要预先安装 Gradle。

如果遇到权限问题，先给 gradlew 加执行权限：

```bash
chmod +x gradlew
```

### 4.3 启动后端开发服务器

```bash
# 加载 .env 中的环境变量，然后启动 Spring Boot
export $(grep -v '^#' .env | xargs) && ./gradlew :app:bootRun
```

> **大白话**：`grep -v '^#' .env` 是过滤掉 `.env` 文件中以 `#` 开头的注释行，`xargs` 是把这些键值对转成环境变量。然后 `./gradlew :app:bootRun` 启动 Spring Boot 内嵌的 Tomcat 服务器。

启动过程大约需要 **30-40 秒**（第一次会慢一些，后续有缓存会快），你会在日志里看到：

```
Started App in 32.243 seconds (process running for 33.414)
```

### 4.4 验证后端启动成功

```bash
# 检查健康状态
curl http://localhost:8080/actuator/health
```

期望输出：

```json
{"status":"UP"}
```

还可以打开 Swagger 文档页面查看所有 API：

```bash
# 浏览器访问：
http://localhost:8080/swagger-ui.html
```

或者用 curl 验证：

```bash
# 检查 Swagger 页面是否能正常访问（返回 200）
curl -s -o /dev/null -w "HTTP状态码: %{http_code}\n" http://localhost:8080/swagger-ui.html
```

---

## 五、前端启动

### 5.1 安装依赖

```bash
# 进入前端目录
cd frontend

# 安装依赖
pnpm install
```

`pnpm install` 可能会遇到原生模块需要构建的提示。这是因为项目依赖了 `@swc/core`、`esbuild`、`protobufjs` 等需要本地编译的包。运行以下命令批准构建：

```bash
pnpm approve-builds
```

> **大白话**：pnpm 出于安全考虑，会阻止某些包的自动构建脚本。`approve-builds` 就是告诉 pnpm "这些包是安全的，让它们构建吧"。

### 5.2 启动前端开发服务器

```bash
# 在 frontend 目录下启动 Vite 开发服务器
pnpm run dev
```

启动成功后输出：

```
  VITE v5.4.21  ready in 418 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.92.92:5173/
```

### 5.3 验证前端

浏览器访问 `http://localhost:5173/`，你应该能看到 **"AI智能面试官 - 简历分析"** 的页面标题。

用 curl 验证后端 API 代理是否正常工作：

```bash
# 通过前端的 /api 代理访问后端健康检查
curl http://localhost:5173/api/actuator/health
```

如果返回 `{"status":"UP"}`，说明前端到后端的代理链路通了。

> **原理说明**：前端 Vite 配置了 `/api` 反向代理到 `http://localhost:8080`（后端），所以访问 `localhost:5173/api/xxx` 会自动转发到后端。这样浏览器就不会遇到跨域问题。

`vite.config.ts` 中的代理配置：

```typescript
server: {
  host: '0.0.0.0',
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://localhost:8080',  // 转发到后端
      changeOrigin: true,
    },
  },
}
```

---

## 六、构建发布产物

### 6.1 构建可执行 JAR

```bash
# 在项目根目录执行
./gradlew :app:bootJar
```

构建完成后，JAR 文件位于：

```
app/build/libs/app-0.0.1-SNAPSHOT.jar
```

查看文件大小：

```bash
ls -lh app/build/libs/app-0.0.1-SNAPSHOT.jar
# 输出: -rw-r--r-- 1 root root 219M ... app-0.0.1-SNAPSHOT.jar
```

> **大白话**：219M 看起来很大，因为这是 Spring Boot 的 "Fat JAR"，把 Tomcat 服务器、所有依赖库、以及项目代码都打在一个包里了。好处是拿到任何装了 Java 21 的机器上都能直接跑。

### 6.2 构建前端 dist

```bash
cd frontend

# 生产构建
pnpm run build
```

构建产物在 `frontend/dist/` 目录下，是一堆 HTML/CSS/JS 文件，可以直接部署到 Nginx。

---

## 七、常见问题与排查

### 7.1 Java 版本不匹配

**症状**：运行 JAR 时报错 `Unsupported class file major version 65`

```bash
# 错误示例
java -jar app/build/libs/app-0.0.1-SNAPSHOT.jar
# Error: LinkageError occurred while loading main class interview.guide.App
# java.lang.UnsupportedClassVersionError: ... class file version 65.0
```

**原因**：你用 Java 17 去运行 Java 21 编译的东西了。

**解决**：用 Gradle 下载的 JDK 21 来运行：

```bash
# 用 Gradle 缓存的 JDK 21 来运行
/root/.gradle/jdks/eclipse_adoptium-21-amd64-linux.2/bin/java -jar app/build/libs/app-0.0.1-SNAPSHOT.jar

# 或者设置环境变量指向 JDK 21
export JAVA_HOME=/root/.gradle/jdks/eclipse_adoptium-21-amd64-linux.2
$JAVA_HOME/bin/java -jar app/build/libs/app-0.0.1-SNAPSHOT.jar
```

### 7.2 Gradle 命令找不到

**症状**：执行 `gradlew` 时报 `/bin/sh: ./gradlew: not found`

**原因**：当前工作目录不在项目根目录，或者脚本没有执行权限。

**解决**：

```bash
# 方法1：用 -p 参数指定项目目录
/workspace/interview-guide/gradlew -p /workspace/interview-guide :app:bootRun

# 方法2：先 cd 进去再执行
cd /workspace/interview-guide && ./gradlew :app:bootRun

# 方法3：如果提示权限不足
chmod +x gradlew
```

### 7.3 Docker 容器未启动

**症状**：后端启动时报 `Connection refused` 连不上数据库/Redis。

```bash
# 先确认容器是否在运行
docker ps --format "table {{.Names}}\t{{.Status}}"

# 如果容器没有 healthy 标志，查看日志
docker logs interview-postgres
docker logs interview-redis

# 如果需要重启容器
docker compose -f docker-compose.dev.yml restart
```

### 7.4 pnpm 原生模块构建失败

**症状**：`pnpm install` 后运行 `pnpm run dev` 报找不到模块。

**原因**：`@swc/core`、`esbuild` 等原生模块需要编译，但被 pnpm 阻止了。

**解决**：

```bash
cd frontend
pnpm approve-builds
```

### 7.5 前端代理不到后端

**症状**：访问 `http://localhost:5173/api/xxx` 返回 502 或连接失败。

**排查步骤**：

```bash
# 1. 确认后端是否在运行
curl http://localhost:8080/actuator/health

# 2. 确认 Vite 代理配置
# 查看 frontend/vite.config.ts 中的 proxy 配置
grep -A5 "proxy:" frontend/vite.config.ts

# 3. 如果后端没启动，先启动后端再试
```

### 7.6 Vite 拒绝外部域名访问

**症状**：通过域名访问前端时看到：
```
Blocked request. This host ("xxx.monkeycode-ai.online") is not allowed.
```

**原因**：Vite 默认只允许 `localhost` 访问，需要配置 `allowedHosts`。

**解决**：在 `frontend/vite.config.ts` 的 `server` 配置中添加：

```typescript
server: {
  host: '0.0.0.0',
  port: 5173,
  allowedHosts: ['.monkeycode-ai.online'],  // 添加这行
  proxy: {
    '/api': {
      target: 'http://localhost:8080',
      changeOrigin: true,
    },
  },
}
```

然后重启前端开发服务器。

> **大白话**：`allowedHosts` 是一个安全白名单，`.monkeycode-ai.online` 前面的点表示"所有以 `.monkeycode-ai.online` 结尾的域名都放行"。

### 7.7 JAR 文件无法运行

> 见 [7.1 Java 版本不匹配](#71-java-版本不匹配)，本质是同一个问题。

---

## 八、调试命令速查表

以下是搭建和调试过程中的常用命令，按场景分类：

### 进程与端口

```bash
# 查看所有监听的端口
ss -tlnp

# 只看关心的端口
ss -tlnp | grep -E ':(8080|5173|5432|6379)'

# 查看 Java 进程
ps aux | grep java
```

### Docker

```bash
# 启动开发基础设施
docker compose -f docker-compose.dev.yml up -d

# 查看运行中的容器
docker ps

# 查看容器日志
docker logs interview-postgres

# 进入容器内部调试
docker exec -it interview-postgres psql -U postgres -d interview_guide

# 停止并清理所有容器
docker compose -f docker-compose.dev.yml down
```

### Gradle

```bash
# 查看 Gradle 使用的 JDK 路径
./gradlew -q javaToolchains

# 只看编译（不启动）
./gradlew :app:compileJava

# 编译 + 运行
./gradlew :app:bootRun

# 构建可执行 JAR
./gradlew :app:bootJar

# 查看已下载到缓存的 JDK
ls /root/.gradle/jdks/
```

### 后端调试

```bash
# 健康检查
curl http://localhost:8080/actuator/health

# 检查 Swagger 是否可用
curl -o /dev/null -w "%{http_code}" http://localhost:8080/swagger-ui.html

# 查看 Spring Boot 所有端点
curl http://localhost:8080/actuator
```

### 前端调试

```bash
# 安装依赖
pnpm install

# 批准原生模块构建
pnpm approve-builds

# 启动开发服务器
pnpm run dev

# 生产构建
pnpm run build

# 检查构建产物大小
du -sh frontend/dist
```

---

## 九、搭建小结

搭建 Interview Guide 的核心流程就四步：

```
1. Docker 启动基础设施 → 2. 配置 .env → 3. ./gradlew :app:bootRun → 4. pnpm run dev
```

最容易踩的坑是 **Java 版本不匹配**——记住：编译和运行 JAR 都需要 Java 21，但 Gradle 的 foojay-resolver 会自动帮你下载管理。

整个项目跑起来后，浏览器打开 `http://localhost:5173` 就能看到 AI 智能面试官界面。AI 功能（简历分析、语音面试等）需要配置真实的阿里云百炼 API Key，否则相关接口会返回 401 错误。
