# GlmCoder 微服务新需求开发 -- 实战指南

> 场景：已有微服务项目，拿到需求文档，要在现有代码基础上开发新接口。以下是完整操作流程。

---

## 一、准备工作：让 GlmCoder 理解你的项目

### 1.1 启动 GlmCoder 并打开项目

```bash
cd /path/to/your-microservice-project

# 方式一：通过 jar 包启动（推荐）
java -jar glmcoder-1.1.1.jar --server.port=8888

# 方式二：Docker 部署
docker run -d -p 8888:8888 -v $(pwd):/workspace liliangxing/glmcoder:latest
```

浏览器访问 `http://localhost:8888`，在顶部输入框填入项目路径（如 `/workspace`），点击「打开项目」。

### 1.2 编写 MEMORY.md（最关键的一步）

在项目根目录创建 `MEMORY.md`，写入项目的核心信息。GlmCoder 每次对话都会从 FTS5 全文索引中检索并注入 LLM 上下文。

```markdown
# 项目记忆

## 技术栈
- 框架: Spring Boot 3.x / Go Gin / Node.js Express
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
- 缓存统一用 @Cacheable 注解
- 事务用 @Transactional(rollbackFor = Exception.class)
```

**GlmCoder 会自动读取 MEMORY.md 并注入到每次对话的 SystemPrompt 中**，确保 Agent 遵守项目约定。

### 1.3 点击「索引」按钮

打开项目后，右侧代码结构面板会显示类的概要。点击「索引」按钮触发完整的 JavaParser AST 解析，得到每个类的方法签名、参数、行号等详细信息。

---

## 二、需求澄清阶段

### 2.1 粘贴需求文档

在对话输入框中粘贴需求文档内容，例如：

```
请分析以下需求，梳理需要开发的接口和改动点：

## 需求：订单评价功能

### 功能描述
用户下单并确认收货后，可以对订单进行评价，包括评分（1-5星）和文字评价。

### 接口要求
- POST /api/orders/{orderId}/reviews  创建评价
- GET /api/orders/{orderId}/reviews   查询评价
- GET /api/products/{productId}/reviews  查询商品所有评价

### 数据库
新增表 `order_review`:
- id BIGINT PRIMARY KEY
- order_id BIGINT NOT NULL
- user_id BIGINT NOT NULL
- product_id BIGINT NOT NULL
- rating INT NOT NULL (1-5)
- content TEXT
- created_at DATETIME
```

### 2.2 Agent 会做什么

GlmCoder 接收到这段需求后，会自动执行以下操作：

1. **调用 `searchCode`** 搜索 `OrderController`、`OrderService` 等已有代码，理解项目架构
2. **调用 `readFile`** 读取现有 Controller/Service/Entity 的完整代码，学习接口命名规范和参数格式
3. **输出分析结果**，列出：
   - 需要新增的文件（Entity、DTO、Repository、Service、Controller）
   - 需要修改的文件（如果要在现有 OrderController 中加接口）
   - 数据库迁移脚本

你只需要确认 Agent 的分析是否正确，然后让它继续实现。

---

## 三、代码实现阶段

### 3.1 让 Agent 自主实现

确认分析无误后，直接回复：

```
按照你的分析和项目现有编码规范，实现所有改动。
```

Agent 会按顺序执行：
1. **`createFile`** 创建 Entity 类（遵循 JPA/MyBatis-Plus 规范）
2. **`createFile`** 创建 DTO 类（Request/Response）
3. **`createFile`** 创建 Repository/Mapper 接口
4. **`createFile`** 创建 Service 接口和实现类
5. **`readFile`** 读取现有 Controller，分析插入位置
6. **`editFile`** 在 Controller 中精确插入新接口方法
7. **`compileCheckJava`** 编译验证

### 3.2 editFile 精准修改

GlmCoder 的核心修改能力是 **`editFile(oldText, newText)`**，它使用唯一匹配策略：

```
# Agent 会这样修改现有 Controller：
oldText = "    @GetMapping(\"/{id}\")\n    public Result<OrderDTO> getOrder(@PathVariable Long id) {"
newText = "    @GetMapping(\"/{id}\")\n    public Result<OrderDTO> getOrder(@PathVariable Long id) {\n" +
          "        return orderService.getOrder(id);\n" +
          "    }\n\n" +
          "    @PostMapping(\"/{id}/reviews\")\n" +
          "    public Result<ReviewDTO> createReview(@PathVariable Long id, @RequestBody ReviewRequest req) {"
```

如果 `oldText` 不唯一，Agent 会收到匹配位置的列表，自动扩大上下文重新尝试。

### 3.3 编译验证

每次修改后 Agent 自动调用 `compileCheckJava` 验证编译。编译失败时会读取错误日志，定位问题并自动修复。

---

## 四、测试与验证阶段

### 4.1 运行测试

```
请运行项目中的测试，确保新增功能不影响已有功能。
```

Agent 会调用 `runTests` 执行测试：

```
# Agent 自动执行：
mvn test -Dtest="**/OrderControllerTest*,**/ReviewServiceTest*"
```

### 4.2 执行数据库迁移

如果项目使用 Flyway/Liquibase，让 Agent 生成迁移脚本：

```
请为 order_review 表生成 Flyway 迁移脚本，命名为 V1.1__add_order_review.sql
```

### 4.3 代码审查

```
请审查刚才生成的所有代码，检查是否有潜在的 NullPointerException、SQL 注入或并发问题。
```

Agent 会逐文件读取并分析代码质量。

---

## 五、完整对话示例

以下是一次完整的微服务开发对话示例：

```
[用户] 打开项目 /workspace/microservice-platform

[GlmCoder 自动] 索引完成: 128 个类, 563 个方法

[用户] 请分析以下需求并实现:
## 需求：订单评价功能
POST /api/orders/{orderId}/reviews 创建评价
GET /api/orders/{orderId}/reviews  查询评价
GET /api/products/{productId}/reviews  查询商品所有评价

[GlmCoder - 分析阶段]
已分析项目结构，发现：
- 订单模块: order-service/ 端口 8082
- 现有 OrderController 有 GET/POST/PUT/DELETE 四个接口
- 使用 JPA + Result<T> 统一返回格式
- 需要新增:
  1. OrderReview Entity (order-service/src/main/java/.../entity/)
  2. ReviewDTO (common/src/main/java/.../dto/)
  3. ReviewRepository (order-service/.../repository/)
  4. ReviewService (order-service/.../service/)
  5. 修改 OrderController 添加两个新接口
  6. ProductController 添加一个接口 (product-service/)

[用户] 分析正确，请实现所有改动。

[GlmCoder - 实现阶段]
1. createFile: OrderReview.java (Entity, 含 JPA 注解和字段校验)
2. createFile: ReviewDTO.java (含 @Valid 校验)
3. createFile: ReviewRepository.java (继承 JpaRepository)
4. createFile: ReviewService.java (接口 + 实现类)
5. readFile: OrderController.java (行号 1-58)
6. editFile: OrderController.java (在 getOrder 后插入 createReview)
7. compileCheckJava: order-service/ 编译通过
8. readFile: ProductController.java (行号 1-42)
9. editFile: ProductController.java (在末尾插入 getProductReviews)
10. compileCheckJava: product-service/ 编译通过

全部改动完成，共新增 4 个文件，修改 2 个文件。

[用户] 请进行代码审查和安全检查。

[GlmCoder - 审查阶段]
代码审查结果:
- ReviewService.createReview 缺少事务注解，已添加 @Transactional
- rating 字段缺少 @Min(1) @Max(5) 校验，已修复
- SQL 注入风险: 无，使用 JPA 参数化查询
- 并发问题: 无，仅涉及新增数据，无更新竞争

已修复 2 个问题，重新编译通过。
```

---

## 六、进阶技巧

### 6.1 分步确认

对于复杂需求，建议分步确认：

```
先创建 Entity 和 DTO，等我确认后再继续。
```

### 6.2 参考已有代码

指定参考模板，让 Agent 模仿实现：

```
参考 OrderService 的实现方式，创建 ReviewService。风格保持一致。
```

### 6.3 批量生成

对于 CRUD 接口，一次生成所有文件：

```
参考 UserController + UserService 的完整模式，
为 Product 模块生成 Controller + Service + Repository + Entity + DTO。
```

### 6.4 上下文压缩

当对话超过 20 轮时，GlmCoder 会自动触发 L2 压缩，将前 10 轮对话总结写入 `.monkeycode/MEMORY.md`，防止上下文溢出。也可以在对话中说：

```
请总结当前进度，写入 MEMORY.md。
```

### 6.5 Bash 安全

GlmCoder 的 Bash 工具会自动拦截危险命令（`rm -rf`、`chmod 777`、`git push --force` 等），确保执行安全。

---

## 七、常见问题

### Q: Agent 修改了不需要改的代码怎么办？

A: GlmCoder 的 SystemPrompt 明确要求"一次只修改与当前任务直接相关的代码"。如果出现多余改动，可以用 `git diff` 查看，手动回退不需要的部分。

### Q: editFile 提示 "oldText 不唯一" 怎么办？

A: Agent 会自动处理 -- 它会根据返回的匹配位置列表，选取更长的上下文重新尝试。这是正常的自动修正流程。

### Q: 多模块项目如何指定编译范围？

A: 在对话中说 "只编译 order-service 模块"，Agent 会执行 `mvn compile -pl order-service`。

### Q: 如何让 Agent 遵守特定的编码规范？

A: 把规范写入 `MEMORY.md` 的「编码规范」章节，GlmCoder 会自动遵守。也可以创建 `CLAUDE.md` 文件，内容会自动注入到 SystemPrompt。

### Q: 对话太长导致上下文丢失怎么办？

A: GlmCoder 有两个自动机制：
- **L1 压缩**：工具返回结果超过 500 行自动截断
- **L2 压缩**：对话超过 20 轮自动总结写入 MEMORY.md，后续对话自动加载

---

## 八、总结

| 阶段 | 操作 | 关键工具 |
|------|------|---------|
| 准备 | 写 MEMORY.md + 索引项目 | `open` + `index` |
| 分析 | 粘贴需求文档，让 Agent 分析 | `searchCode` `readFile` |
| 实现 | 确认方案，让 Agent 全自动实现 | `createFile` `editFile` `compileCheckJava` |
| 验证 | 运行测试，代码审查 | `runTests` `executeBash` |
| 提交 | git commit + push | `executeBash` |
