# 使用 MiMo-Code 开发微服务新需求 -- 实战指南

> 场景：有一个已有微服务项目，拿到了需求文档，要在现有代码基础上开发新接口。以下是完整的操作流程。

---

## 一、准备工作：让 MiMo-Code 理解你的项目

### 1.1 进入项目目录启动

```bash
cd /path/to/your-microservice-project
mimo
```

MiMo-Code 会在当前目录启动 TUI 界面，自动检测项目类型和结构。

### 1.2 编写 MEMORY.md（最关键的一步）

在项目根目录创建或编辑 `MEMORY.md`，写入项目的核心信息。MiMo-Code 的 FTS5 全文搜索引擎会在每次对话时自动检索并注入。

```markdown
# 项目记忆

## 技术栈
- 框架: Spring Boot 3.x / Go Gin / Node.js Express / ...
- 数据库: MySQL 8.0 + Redis
- 消息队列: Kafka / RabbitMQ
- 注册中心: Nacos / Consul
- RPC: Dubbo / gRPC / Feign

## 项目结构
- user-service/     -- 用户服务（端口 8081）
- order-service/    -- 订单服务（端口 8082）
- gateway/          -- API 网关（端口 8080）
- common/           -- 公共模块（DTO、工具类）

## 编码规范
- Controller -> Service -> Repository 三层架构
- 统一返回格式: Result<T> { code, message, data }
- 异常统一用 GlobalExceptionHandler 处理
- 数据库操作使用 MyBatis-Plus / JPA

## 已有接口模式
- GET /api/users/{id} -> UserController.getUser()
- POST /api/users -> UserController.createUser()
- 分页查询统一用 PageRequest + PageResult

## 注意事项
- 所有接口需要 @Auth 注解做权限校验
- 敏感操作要记录操作日志 @OperationLog
- 禁止在 Controller 层写业务逻辑
```

### 1.3 提供需求文档

将需求文档放在项目内，MiMo-Code 可以直接读取：

```bash
# 放在项目根目录或 docs/ 下
docs/requirements/user-login-history.md
docs/requirements/order-statistics.md
```

---

## 二、第一步：用 plan 模式分析需求和现有代码

按 `Tab` 切换到 **plan** Agent 模式。plan 模式只有只读权限（read、grep、glob 等），不会修改代码，适合先做分析。

### 对话示例

```
我在 docs/requirements/user-login-history.md 中有新的需求文档。
请先读取这个文档，然后分析：
1. 我需要在哪些服务中新增代码？
2. 需要新增哪些文件（Controller、Service、Repository、DTO）？
3. 需要修改哪些现有文件？
4. 这个需求跟我现有的代码模式一致吗？如果不一致，请指出差异。

请先全面阅读相关代码，然后给出分析报告。不要修改任何代码。
```

MiMo-Code 会：
1. 用 `read` 工具读取需求文档
2. 用 `glob` / `grep` 搜索相关服务代码
3. 用 `read` 阅读现有的 Controller、Service、Entity
4. 输出一份结构化的分析报告

### 设置 Goal

分析完之后，设置明确的任务目标：

```
/goal 完成用户登录历史记录功能的后端开发：
1. 新增 login_history 数据库表
2. 新增 LoginHistory entity/DTO
3. 新增 LoginHistoryController (记录查询接口)
4. 修改 UserController.login() 添加记录逻辑
5. 编译通过，所有现有测试不失败
```

`/goal` 的作用：设置后，MiMo-Code 会用一个独立的 judge 模型在后台验证每个步骤是否满足 goal 的要求，任务达到 goal 时会自动停止。

---

## 三、第二步：用 build 模式逐步实现

按 `Tab` 切换回 **build** Agent 模式，开始写代码。

### 3.1 任务自动拆解

直接告诉 MiMo-Code 你的目标，它会自动拆解为树形任务：

```
请开始实现。按照以下顺序逐个完成：
```

MiMo-Code 会自动生成任务树：
```
T1: 创建 login_history 数据库表
  T1.1: 编写 DDL 脚本
  T1.2: 执行并验证
T2: 创建 Entity 和 DTO
  T2.1: 创建 LoginHistory entity
  T2.2: 创建 LoginHistoryDTO
T3: 实现 Repository 层
  T3.1: 创建 LoginHistoryRepository
T4: 实现 Service 层
  T4.1: 创建 LoginHistoryService
T5: 实现 Controller 层
  T5.1: 创建 LoginHistoryController
T6: 修改登录逻辑
  T6.1: 修改 UserController.login() 添加记录逻辑
T7: 编译验证
  T7.1: 编译通过
  T7.2: 运行测试
```

### 3.2 逐个任务推进

```
先做 T1：创建数据库表
```

MiMo-Code 会：
1. 查找项目中现有的 DDL 脚本位置和命名规范
2. 参照现有表结构创建新表的 DDL
3. 确认表结构符合项目规范

```
继续 T2：创建 Entity 和 DTO
```

MiMo-Code 会：
1. 先 `read` 一个现有 Entity（如 `User.java`）了解代码模式
2. 按相同模式创建 `LoginHistory.java`
3. 复用项目已有的注解、基类、工具类

### 3.3 遇到问题时

```
编译报错了，LoginHistoryRepository 找不到。请检查 import 引用的路径是否正确。
```

MiMo-Code 会：
1. 读取报错文件
2. 读取项目结构确定正确的包路径
3. 用 `edit` 工具精确修复 import

---

## 四、Compose 模式：大需求的完整解决方案

对于跨多个服务、步骤繁多的大需求，用 **Compose** 模式会更合适。

### 4.1 什么是 Compose 模式

Compose 是 spec 驱动的编排模式。MiMo-Code 会先在 `docs/compose/` 下生成：
- `plans/` -- 实现计划
- `reports/` -- 进度报告

然后按计划逐步执行，每步完成后自动生成报告。

### 4.2 使用方式

按 `Tab` 切换到 **compose** Agent，然后：

```
我需要根据 docs/requirements/order-statistics.md 开发订单统计功能。
这个需求涉及 order-service（查询接口）和 gateway（路由配置）。
请使用 Compose 模式规划整个实现流程。
```

MiMo-Code 会：
1. 读取需求文档
2. 分析涉及的所有服务
3. 生成分步骤的 Plan
4. 按 Plan 逐步实现
5. 每步完成后生成 Report

### 4.3 自定义 Workflow

如果内置的 compose 流程不满足需求，可以写自定义 Workflow。

在 `.mimocode/workflows/microservice-feature.js`：

```javascript
export const meta = {
  name: "microservice-feature",
  description: "微服务新功能开发流程"
}

export default async function() {
  // Phase 1: 分析现有代码
  const analysis = await agent("请分析项目结构，找到所有相关的 Controller 和 Service")

  // Phase 2: 生成代码
  await pipeline([
    () => agent("创建 Entity 和 DTO"),
    () => agent("创建 Repository"),
    () => agent("创建 Service"),
    () => agent("创建 Controller"),
  ])

  // Phase 3: 验证
  await agent("编译并通过所有测试")
}
```

然后在对话中调用：`/microservice-feature`

---

## 五、跨服务开发的推荐流程

对于微服务项目，推荐按以下顺序逐个服务开发：

### 5.1 公共模块优先

```
先在 common 模块中新增 LoginHistoryDTO，其他服务会用到。
```

### 5.2 核心服务其次

```
在 user-service 中实现登录记录的业务逻辑。
```

### 5.3 网关/路由配置最后

```
在 gateway 的路由配置中增加 login-history 接口的路由规则。
```

### 5.4 每完成一个服务就验证

```
编译 user-service 并通过测试。
```

MiMo-Code 会执行 `mvn compile` 或对应构建命令验证。

---

## 六、实用技巧

### 6.1 使用记忆系统

MiMo-Code 会自动记住你的偏好和项目知识。你也可以主动告诉它：

```
/dream
```
将当前对话中的关键知识提取到 MEMORY.md，下次打开项目时 MiMo-Code 会更有上下文。

### 6.2 子 Agent 并行开发

对于多个独立的修改，可以用子 Agent 并行处理：

```
请用子 Agent 并行完成：
1. Agent A: 创建 LoginHistory 相关的 entity 和 dto
2. Agent B: 检查 gateway 路由配置是否需要修改
```

### 6.3 跳过权限提示

在信任 MiMo-Code 的情况下：

```
mimo --dangerously-skip-permissions
```

或设置环境变量：

```bash
export MIMOCODE_DANGEROUSLY_SKIP_PERMISSIONS=1
mimo
```

### 6.4 无头模式（CI/CD 集成）

```bash
mimo run "实现 docs/requirements/xxx.md 中的需求"
```

适合集成到 CI 流程或批量开发。

### 6.5 会话恢复

```bash
mimo --continue    # 恢复上次会话
mimo --session <id> # 恢复指定会话
```

---

## 七、完整实战一例：新增"用户积分"功能

### 7.1 准备

```bash
cd ~/projects/my-microservice
mimo
```

编辑 `MEMORY.md`，加入项目技术栈、代码规范、已有接口模式。

### 7.2 Plan 阶段

```
Tab -> plan 模式
输入: "请读取 docs/requirements/user-points.md，分析需要改动哪些服务和文件，给出分析报告，不要改代码。"
```

MiMo-Code 读取需求文档和现有代码后返回：
- 需改动: user-service, common 模块
- 需新增: Points entity, PointsController, PointsService 等 5 个文件
- 需修改: UserController.register() 添加初始积分

### 7.3 Build 阶段

```
/goal 完成用户积分功能开发，编译通过，测试不失败
Tab -> build 模式
输入: "按分析报告开始实现。"
```

MiMo-Code 逐个完成任务：
```
T1: common/src/main/java/.../PointsDTO.java -- 完成
T2: user-service/.../entity/Points.java -- 完成
T3: user-service/.../repository/PointsRepository.java -- 完成
T4: user-service/.../service/PointsService.java -- 完成
T5: user-service/.../controller/PointsController.java -- 完成
T6: 修改 UserController.register() -- 完成
T7: mvn compile -- 通过
T8: mvn test -- 通过
```

### 7.4 完成

Goal 验证通过，功能开发完成。

---

## 八、配置参考（mimocode.jsonc）

```jsonc
{
  "model": "claude-sonnet-4-5",          // 默认模型，根据需求选合适的
  "small_model": "claude-haiku-4-5",     // 小任务用轻量模型省 token
  "agent": {
    "build": {
      "model": "claude-sonnet-4-5"       // build 用强模型保证代码质量
    },
    "plan": {
      "model": "claude-haiku-4-5"        // plan 分析用轻量模型即可
    }
  },
  "permission": {
    "edit": { "**": "ask" },             // 修改文件前询问确认
    "bash": {
      "mvn *": "allow",                  // Maven 命令自动允许
      "git *": "allow",                  // Git 命令自动允许
      "docker *": "ask"                  // Docker 操作需要确认
    }
  },
  "instructions": "你是一个微服务后端开发专家。代码风格遵循项目规范。每次修改前先 readFile 确认内容。修改后必须编译验证。"
}
```

---

## 九、关键命令速查

| 命令 | 用途 |
|------|------|
| `mimo` | 启动 TUI |
| `Tab` | 切换 Agent 模式 (build/plan/compose) |
| `/goal <描述>` | 设置任务完成目标 |
| `/dream` | 提取知识到 MEMORY.md |
| `/distill` | 打包可复用工作流 |
| `/rebuild` | 重建上下文（接近 token 上限时） |
| `/voice` | 语音输入模式 |
| `mimo --continue` | 恢复上次会话 |
| `mimo run "..."` | 无头模式，适合 CI/CD |
