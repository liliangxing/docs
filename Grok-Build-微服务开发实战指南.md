# 使用 Grok Build 开发微服务新需求 -- 实战指南

> 场景：有一个已有微服务项目，拿到了需求文档，要在现有代码基础上开发新接口。以下是使用 Grok Build (`grok`) 的完整操作流程。

---

## 一、准备工作：让 Grok 理解你的项目

### 1.1 安装与启动

```bash
# 安装 Grok Build
curl -fsSL https://x.ai/cli/install.sh | bash

# 进入项目目录启动 TUI
cd /path/to/your-microservice-project
grok
```

Grok 会启动全屏 TUI 界面，自动检测项目类型和代码结构。

### 1.2 创建项目级配置（可选）

在项目根目录创建 `.grok/config.toml`：

```toml
# 允许 Grok 自动执行 Maven/Gradle 命令，减少确认提示
[tools.bash]
auto_approve_patterns = [
    "mvn *",
    "gradle *",
    "git status",
    "git diff",
    "git log *"
]

# 指定模型（可通过环境变量覆盖）
model = "grok-3"

# 启用工作区命令
[settings]
workspace_commands = true
```

### 1.3 编写记忆文件（最关键的一步）

Grok 有 git-backed 记忆系统。在项目根目录创建 `MEMORY.md`：

```markdown
# 项目记忆

## 技术栈
- 框架: Spring Boot 3.3 + MyBatis-Plus
- 数据库: MySQL 8.0 + Redis 7.0
- 消息队列: Kafka 3.6
- 注册中心: Nacos 2.3
- RPC: OpenFeign + Sentinel

## 项目结构
```
user-service/     -- 用户服务 (8081)
order-service/    -- 订单服务 (8082)
product-service/  -- 商品服务 (8083)
gateway/          -- API 网关 (8080)
common/           -- 公共模块 (DTO、工具类、异常处理)
```
common/
├── dto/          -- 数据传输对象
├── enums/        -- 枚举类
├── exception/    -- 异常定义
└── utils/        -- 工具类

user-service/
├── controller/   -- REST 控制器
├── service/      -- 业务逻辑层
├── repository/   -- 数据访问层 (MyBatis-Plus Mapper)
├── entity/       -- 数据库实体
├── dto/          -- 请求/响应 DTO
└── config/       -- 服务配置

## 编码规范
- Controller 只做参数校验和路由，业务逻辑全部在 Service
- 统一返回: Result<T> { code: int, message: string, data: T }
- 全局异常: GlobalExceptionHandler @RestControllerAdvice
- 分页查询: PageRequest { page, size, sort } + PageResult { total, list }
- 所有接口需要 @Auth 注解，权限校验在网关层
- 数据库实体统一继承 BaseEntity { id, createdAt, updatedAt }

## 已有接口模式
- GET    /api/users/{id}       -> UserController.getById()
- POST   /api/users            -> UserController.create(@Valid @RequestBody CreateUserRequest)
- PUT    /api/users/{id}       -> UserController.update(@PathVariable id, @Valid @RequestBody UpdateUserRequest)
- DELETE /api/users/{id}       -> UserController.delete(@PathVariable id)
- GET    /api/users?page=&size= -> UserController.page(PageRequest)

## 注意事项
- 数据库表字段使用下划线命名，实体类使用驼峰命名
- 敏感操作记录操作日志: @OperationLog(module = "user", operation = "create")
- 跨服务调用用 FeignClient，降级用 Sentinel fallback
- 启动前确认 Nacos 已运行，否则服务注册失败
```

### 1.4 放入需求文档

将需求文档放在项目内，Grok 可以直接读取：

```bash
docs/requirements/user-login-history.md
docs/requirements/order-export.md
```

---

## 二、第一步：分析需求和现有代码

### 2.1 让 Grok 全面分析

在 TUI 中输入：

```
请读取 docs/requirements/user-login-history.md 这个需求文档。
然后全面分析我的项目，回答以下问题：
1. 这个需求涉及哪些现有服务？
2. 需要新增哪些文件（Controller/Service/Entity/DTO）？
3. 需要修改哪些现有文件？
4. 新接口的 URL、请求体、响应体应该是什么样的？
5. 跟我现有代码风格一致吗？不一致的地方请指出。

在给出分析报告之前，不要修改任何代码。先用 read_file 全面阅读相关代码。
```

Grok 会依次执行：
1. `read_file` 读取需求文档
2. `glob` 搜索 `**/*Controller.java`、`**/*Service.java` 找到相关代码
3. `grep` 搜索关键类名和方法名
4. `read_file` 逐文件阅读现有 Controller/Service/Entity
5. 输出一份结构化分析报告

### 2.2 查看分析报告

Grok 会返回类似：

```
## 分析报告

### 涉及服务
- user-service: 主要改动，新增登录历史记录
- common: 新增共用 DTO

### 需新增文件 (5个)
1. user-service/entity/LoginHistory.java    -- 数据库实体
2. user-service/dto/LoginHistoryDTO.java    -- 响应 DTO
3. user-service/repository/LoginHistoryMapper.java -- MyBatis Mapper
4. user-service/service/LoginHistoryService.java   -- 业务逻辑
5. user-service/controller/LoginHistoryController.java -- REST 控制器

### 需修改文件 (1个)
1. user-service/service/UserService.java    -- 在 login() 方法末尾添加记录逻辑

### 接口设计
GET /api/users/{userId}/login-history?page=1&size=20
响应: Result<PageResult<LoginHistoryDTO>>

### 数据库变更
CREATE TABLE login_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    login_ip VARCHAR(45),
    login_time DATETIME NOT NULL,
    ...
);
```

---

## 三、第二步：逐步实现

### 3.1 用 todo 工具拆解任务

```
/grok todo 请把上面的分析报告拆解为可执行的任务列表
```

Grok 会调用 `todo` 工具创建树形任务。你也可以手动指定：

```
请按以下顺序逐个完成任务，完成一个之后再开始下一个：

任务 1: 创建数据库表 DDL（放在 user-service/sql/V2__add_login_history.sql）
任务 2: 创建 LoginHistory 实体类
任务 3: 创建 LoginHistoryDTO
任务 4: 创建 LoginHistoryMapper
任务 5: 创建 LoginHistoryService
任务 6: 创建 LoginHistoryController
任务 7: 修改 UserService.login() 添加记录逻辑
任务 8: 编译验证，确保不破坏现有测试

现在开始任务 1。
```

### 3.2 逐个任务推进

Grok 的工作方式：

```
任务 1: 创建 DDL
- Grok 先用 read_file 读取现有的 SQL 迁移文件，了解命名规范和格式
- 然后 create 新文件 user-service/sql/V2__add_login_history.sql
- 内容参照项目已有的表结构风格

任务 2: 创建 Entity
- Grok 先用 read_file 读取现有 Entity (如 User.java)
- 理解 @TableName、@TableId、@TableField 注解的使用方式
- 然后 create LoginHistory.java，完全仿照现有风格

任务 3: 创建 DTO
- Grok 读取现有 DTO 了解命名和结构模式
- 创建 LoginHistoryDTO.java

...
```

### 3.3 关键：Grok 的编辑机制

Grok 使用与 MiMo-Code 相同的 `old_string`/`new_string` 精确替换：
- 修改前必须先 `read_file`
- `old_string` 必须精确匹配（含缩进）
- 不唯一时报错，需要扩大上下文重试
- 找不到时提供最接近的匹配建议

修改 UserService.login() 时，Grok 会：
1. `read_file` UserService.java
2. 找到 `login()` 方法中的 `return` 语句
3. 调用 edit: 在 `return` 前面插入登录记录逻辑

### 3.4 编译验证

```
请编译 user-service 模块，确保没有错误
```

Grok 会执行 `mvn compile -pl user-service -q`，如果有错误会：
1. 读取错误输出
2. 定位出错的文件和行号
3. 用 edit 修复
4. 重新编译验证

---

## 四、高级用法

### 4.1 Worktree 隔离开发

对于大需求，可以创建独立的 git worktree 来隔离开发：

```
/workspace create login-history-feature
```

Grok 会用 CoW (Copy-on-Write) 创建 git worktree，在隔离环境中开发，不影响主分支。完成后合并回去。

### 4.2 并行子 Agent

```
请用子 agent 并行完成：
1. Agent A: 创建 LoginHistory 相关的所有文件 (entity/dto/mapper/service/controller)
2. Agent B: 同时检查 gateway 路由配置是否需要新增路由规则
```

Grok 会 fork 子 agent 并行执行，完成后再合并结果。

### 4.3 跨服务开发

对于涉及多个微服务的需求：

```
请先完成 user-service 的改动（任务 1-7），编译通过后再处理 gateway 的路由配置（任务 8）。

user-service 完成后告诉我，我会手动验证，然后你继续 gateway。
```

### 4.4 Hook 系统 -- 自定义安全检查

在项目 `.grok/hooks/` 下创建安全检查脚本：

```bash
# .grok/hooks/bin/check-branch.sh
#!/bin/bash
# 禁止在 main 分支上直接修改
current_branch=$(git branch --show-current)
if [ "$current_branch" = "main" ]; then
    echo "错误: 不允许在 main 分支上直接修改代码。请创建 feature 分支。"
    exit 1
fi
```

```json
{
  "hooks": [{
    "name": "check-branch",
    "type": "command",
    "command": ".grok/hooks/bin/check-branch.sh",
    "matcher": "edit",
    "events": ["PreToolUse"]
  }]
}
```

这样 Grok 在修改文件前会自动检查分支，防止误改 main。

### 4.5 Headless 模式 -- CI/CD 集成

```bash
# 非交互模式，直接用需求文档驱动开发
grok -p "根据 docs/requirements/user-login-history.md 完成全部开发，编译通过后停止"

# 带进度输出
grok -p "实现登录历史功能" --verbose

# 指定会话 ID 以便后续恢复
grok -p "继续 user-login-history 功能的开发" --session login-history-session
```

---

## 五、完整实战示例：新增"订单导出"功能

### 5.1 准备

```bash
cd ~/projects/my-microservice
grok
```

### 5.2 分析

```
请读取 docs/requirements/order-export.md。
分析涉及的服务和需要新增/修改的文件。
只做分析，不要改代码。
```

Grok 输出：
```
涉及: order-service (导出接口), common (Excel 工具类)
新增: OrderExportController, OrderExportService, ExcelUtil
修改: OrderMapper (新增查询方法)
接口: POST /api/orders/export { startDate, endDate, status }
```

### 5.3 实现

```
拆分任务:
T1: 在 common/util 下创建 ExcelUtil.java
T2: 在 order-service/repository/OrderMapper.java 中新增导出查询方法
T3: 创建 OrderExportService.java
T4: 创建 OrderExportController.java
T5: 编译 order-service 并运行测试

请按顺序完成。
```

Grok 逐步执行，每个任务完成后编译验证：
```
T1: ExcelUtil.java -- 完成，编译通过
T2: OrderMapper.java -- 新增 selectByCondition() 方法，完成
T3: OrderExportService.java -- 完成
T4: OrderExportController.java -- 完成
T5: mvn compile -pl order-service -q -- 通过
    mvn test -pl order-service -q -- 4 tests passed
```

### 5.4 验证

```
请用 curl 写一个测试请求，验证订单导出接口是否正常
```

Grok 会找项目端口配置，构造 curl 命令验证接口。

---

## 六、常用命令速查

| 命令/操作 | 用途 |
|-----------|------|
| `grok` | 启动 TUI |
| `grok -p "task"` | Headless 非交互模式 |
| `grok --continue` 或 `grok -c` | 恢复上次会话 |
| `grok --session <id>` | 恢复指定会话 |
| `Shift+Tab` | 切换 auto-approve 模式 |
| `/workspace create <name>` | 创建隔离 worktree |
| TUI 内直接输入任务描述 | 驱动 Grok 执行 |

## 七、配置参考（.grok/config.toml）

```toml
# 模型选择
model = "grok-3"
small_model = "grok-3-mini"     # 简单任务用轻量模型

# Bash 自动批准（减少确认提示）
[tools.bash]
auto_approve_patterns = [
    "mvn compile*",
    "mvn test*",
    "git status",
    "git diff",
    "git log*",
    "git branch",
    "ls *",
    "cat *"
]

# 工作区设置
[workspace]
enabled = true
auto_checkpoint = true           # 自动创建检查点

# 权限
[permissions]
auto_mode_timeout_minutes = 30  # 自动批准模式有效期

# 记忆
[memory]
auto_sync = true                 # 自动同步 MEMORY.md
```

---

## 八、与 MiMo-Code 的主要差异

| 特性 | Grok Build | MiMo-Code |
|------|-----------|-----------|
| 语言 | Rust | TypeScript (Bun) |
| 多 Agent 模式 | 无显式 build/plan/compose | 有 Tab 切换 build/plan/compose |
| 任务系统 | todo 工具，简单列表 | 树形任务 (T1, T1.1) |
| Worktree | CoW/Btrfs reflinks 高性能 | 普通 git worktree |
| 沙箱 | Landlock/Seatbelt 内核级 | 无 |
| Hook 系统 | PreToolUse/PostToolUse 拦截 | 无独立 hook |
| Sub-agent | 有，可并行 | 有 |
| Goal 系统 | 无独立的 judge 模型 | 有 /goal + judge 验证 |
| 斜杠命令 | 少量内置命令 | 丰富的 /dream /distill /loop 等 |
| 语音输入 | 有 (cpal -> xAI STT) | 有 (TenVAD + MiMo ASR) |
| Mermaid | vendored 引擎，终端渲染 SVG | 无 |
