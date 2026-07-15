# MiMo-Code 项目总览

> **项目定位**：小米开发的终端原生 AI 编程助手，命令行 `mimo` 进入 TUI 界面，通过 LLM 驱动代码编写、文件操作、命令执行、Git 管理等。

---

## 一、技术栈速览

| 类别 | 技术 |
|------|------|
| 包管理器 | Bun 1.3.14（Workspace Monorepo） |
| 构建编排 | Turborepo 2.8.13 |
| 核心语言 | TypeScript 5.8.2 |
| UI 框架 | SolidJS 1.9.10 + @solidjs/router 0.15.4 |
| TUI 渲染 | OpenTUI（@opentui/solid 0.1.101, @opentui/core 0.1.101） |
| Web 构建 | Vite 7.1.4 |
| CSS | Tailwind CSS 4.1.11 |
| HTTP 服务端 | Hono 4.10.7 + hono-openapi |
| AI SDK | Vercel AI SDK 6.0.168 + 20+ 提供商适配器 |
| 错误处理/DI | Effect.ts 4.0.0-beta.48 |
| 数据库 | SQLite + Drizzle ORM 1.0.0-beta.19（FTS5 全文搜索） |
| 桌面端 | Electron（electron-vite + electron-builder） |
| CLI 框架 | yargs |
| 测试 | Bun Test（单元）、Playwright 1.59.1（E2E） |
| Lint | Oxlint 1.60.0 + Prettier |
| 代码高亮 | Shiki 3.20.0 |
| Markdown 渲染 | Marked 17.0.1 |
| 基础设施 | SST 3.18.10（AWS 部署）、Nix Flake |

---

## 二、Monorepo 目录结构

```
MiMo-Code/
├── packages/
│   ├── opencode/          # 核心 CLI/TUI 应用（主要包）
│   ├── app/               # Web 应用（SolidJS SPA，Vite）
│   ├── desktop/           # Electron 桌面封装
│   ├── ui/                # 共享 UI 组件库（185+ 组件）
│   ├── shared/            # 共享工具函数
│   ├── sdk/js/            # JavaScript SDK（OpenAPI 自动生成）
│   ├── console/           # 管理控制台（SolidStart SSR）
│   │   ├── app/           # 控制台 Web 应用
│   │   ├── core/          # 控制台核心逻辑
│   │   ├── function/      # AWS Lambda / SST 函数
│   │   ├── mail/          # 邮件服务
│   │   └── resource/      # 控制台资源/配置
│   ├── plugin/            # 插件系统
│   ├── identity/          # 品牌资源
│   ├── containers/        # Docker 容器定义
│   ├── enterprise/        # 企业平台集成
│   ├── extensions/        # 编辑器扩展
│   ├── function/          # 无服务器函数
│   ├── script/            # 构建/发布脚本
│   ├── slack/             # Slack 集成
│   └── web/               # Web 部署配置
├── sdks/vscode/           # VS Code 扩展
├── docs/                  # 项目文档
├── infra/                 # 基础设施即代码
├── nix/                   # Nix Flake 依赖
├── assets/                # README 图片
├── patches/               # 补丁后的依赖
├── package.json           # Monorepo 根配置
└── turbo.json             # Turborepo 配置（typecheck）
```

---

## 三、核心包：packages/opencode 内部结构

这是整个项目的核心，200+ 源文件，按职责分为 20+ 个模块：

| 模块目录 | 职责 | 关键文件 |
|----------|------|----------|
| `cli/cmd/tui/` | TUI 界面 | `app.tsx`(入口), `routes/session/index.tsx`(会话页3411行), 组件、对话框、主题 |
| `agent/` | Agent 系统 | `agent.ts`(Agent 定义、Effect 服务、提示词生成), build/plan/compose 模式 |
| `session/` | 会话管理 | `session.ts`(CRUD), `prompt.ts`(LLM 请求编排), 消息流、压缩、检查点 |
| `tool/` | 工具系统 | `registry.ts`(工具注册), bash/read/write/edit/glob/grep/task/skill/workflow |
| `provider/` | AI 提供商 | `provider.ts`(1816行，20+ LLM 统一接口), 模型列表、认证 |
| `server/` | HTTP 服务 | `server.ts`(Hono), routes/(会话、配置、文件、权限、SSE) |
| `config/` | 配置系统 | `config.ts`(mimocode.jsonc 解析), Agent 配置、权限、MCP、LSP |
| `storage/` | 数据持久化 | `schema.ts`(Drizzle 模式), SQLite 适配器、JSON 迁移 |
| `memory/` | 记忆系统 | `service.ts`(FTS5 全文搜索), MEMORY.md 协调, 检查点 |
| `skill/` | 技能引擎 | 内置技能(arxiv/pdf/docx/pptx/xlsx 等13个) |
| `workflow/` | 工作流引擎 | `runtime.ts`(沙箱化 JS), compose/deep-research/fact-check |
| `task/` | 任务跟踪 | 树形任务系统(T1, T1.1, T1.2) |
| `project/` | 项目管理 | 项目实例、仓库检测 |
| `lsp/` | LSP 集成 | 语言服务器协议支持 |
| `mcp/` | MCP 协议 | 模型上下文协议客户端 |
| `git/` | Git 集成 | 仓库操作 |
| `control-plane/` | 控制平面 | 工作区管理、团队、SSE |
| `auth/` | 认证 | Xiaomi MiMo OAuth, OpenRouter |
| `plugin/` | 插件系统 | 插件加载与扩展 |
| `ide/` | IDE 集成 | 编辑器桥接 |
| `cron/` | 定时任务 | 定时作业 |
| `share/` | 会话共享 | 会话链接分享 |

---

## 四、多端入口架构

```
用户入口
├── CLI: `mimo` 命令 (packages/opencode/src/index.ts)
│   └── 进入 TUI 界面 (OpenTUI 终端渲染)
├── Web: 浏览器访问 (packages/app/src/entry.tsx)
│   └── SolidJS SPA + Vite，端口 3000
├── Desktop: Electron 应用 (packages/desktop/)
│   ├── src/main/     -- Electron 主进程
│   ├── src/renderer/ -- 渲染进程（Web UI 在原生窗口）
│   └── src/preload/  -- 预加载脚本
└── Console: 管理后台 (packages/console/app/)
    └── SolidStart SSR，通过 FileRoutes 路由

通信桥梁: Hono HTTP 服务器 (packages/opencode/src/server/server.ts)
    提供 REST API 和 SSE 事件流
```

---

## 五、组件树（TUI 界面）

```
App (app.tsx)
  +-- RouteProvider
      +-- Home (routes/home.tsx)
      │     +-- Prompt input (输入框)
      │     +-- Session list (会话列表)
      │     +-- Startup loading
      +-- Session (routes/session/index.tsx) -- 3411行，最大组件
            +-- Sidebar (文件树、路径导航)
            +-- Prompt (聊天输入，带历史/频率/存储)
            +-- Message list (虚拟滚动，Virtua)
            +-- DialogMessage (消息详情)
            +-- DialogTimeline (对话时间线)
            +-- DialogForkFromTimeline (分叉会话)
            +-- DialogSubagent (子Agent管理)
            +-- Question (权限/问题提示)
            +-- Footer (状态栏)
            +-- WorkflowTree (工作流可视化)
            +-- Dialogs: Model, Provider, Agent, Mcp, Command,
                         Theme, Image, Logo, MimoLogin, Workflows,
                         Worktree, Status, Help, SessionList, etc.
```

---

## 六、数据流与架构

### 6.1 请求处理全流程

```
用户输入消息
    |
    v
TUI/Web/Desktop 界面
    | HTTP POST /instance/session
    v
Hono 服务器 (server.ts)
    |
    v
Session.prompt() -- 构建消息上下文
    |-- 读取 MEMORY.md (FTS5 全文搜索)
    |-- 注入检查点
    |-- 载入任务进度
    |-- 拼接会话历史
    |
    v
Agent.generatePrompt() -- 生成 System Prompt
    |
    v
Provider.stream() -- 调用 LLM (Vercel AI SDK streamText)
    |
    v
【工具调用循环】
    LLM 返回 tool_call
        -> ToolRegistry 解析并执行 (bash/read/write/edit/glob/grep/...)
        -> 工具结果作为 tool_result 返回 LLM
        -> LLM 继续思考/调用更多工具
        -> 循环直到 LLM 生成最终文本
    |
    v
消息持久化到 SQLite (session.sql.ts)
    |-- 每条消息 = 角色 + 部分 (text/tool_call/reasoning/file)
    |
    v
流式返回响应 -> SSE 推送到客户端
```

### 6.2 状态管理

| 层 | 技术 | 说明 |
|---|------|------|
| 服务层 | Effect.ts | 依赖注入、错误处理、可观测性 |
| 服务实例 | Agent.Service, Session.Service, Provider.Service, Config, Storage, Memory.Service | 核心业务逻辑 |
| UI 状态 | SolidJS createSignal | 本地 UI 响应式状态 |
| Web 同步 | @tanstack/solid-query | 服务器状态缓存与同步 |
| 跨组件通信 | @solid-primitives/event-bus | 事件总线 |
| 上下文注入 | Context Providers | SDKProvider, SyncProvider, ProjectProvider, ThemeProvider, KeybindProvider |

### 6.3 Hono 服务端路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/instance/session` | POST | 发送消息（流式 AI 响应） |
| `/instance/config` | GET/POST | 读取/写入配置 |
| `/instance/file` | * | 文件操作 |
| `/instance/provider` | GET | LLM 提供商列表 |
| `/instance/project` | GET | 项目信息 |
| `/instance/event` | GET | SSE 事件流 |
| `/instance/bash-interactive` | POST | 交互式终端 |
| `/instance/sync` | POST | 客户端状态同步 |

---

## 七、工具系统

工具注册在 `tool/registry.ts`，LLM 通过 Function Calling 调用：

| 工具 | 功能 |
|------|------|
| bash | 执行 Shell 命令 |
| read | 读取文件内容 |
| write | 写入文件 |
| edit | 精准修改文件 |
| apply_patch | 应用补丁 |
| glob | 文件模式匹配搜索 |
| grep | 内容正则搜索 |
| webfetch | 获取网页内容 |
| websearch | 搜索互联网 |
| task | 创建子任务 |
| skill | 调用技能 |
| workflow | 执行工作流 |
| question | 向用户提问 |
| actor | 子 Agent 调用 |

---

## 八、20+ LLM 提供商

通过 Vercel AI SDK 统一接口 (`provider.ts` 1816行)：

Anthropic, OpenAI, Google (Gemini), MiMo, Groq, DeepSeek, OpenRouter, Bedrock, Vertex, Azure, xAI, Mistral, Cohere, Together, Fireworks, Perplexity, Cerebras, 等。

配置在 `mimocode.jsonc` 中指定模型和 API Key。

---

## 九、记忆系统

三层记忆架构：

1. **MEMORY.md**：项目根目录的 Markdown 文件，Agent 自动记录项目知识
2. **FTS5 全文搜索**：SQLite 内置全文搜索引擎，语义检索记忆
3. **检查点**：会话状态快照，支持恢复到任意历史状态

记忆注入时机：每次 LLM 请求前自动检索相关记忆并注入 Prompt。

---

## 十、UI 组件库（packages/ui）

185+ 个共享组件，按类别分组：

| 类别 | 组件 |
|------|------|
| 基础 | Button, Card, Checkbox, Dialog, Select, Switch, Tabs, TextField, Icon |
| 会话 | MessagePart, SessionTurn, SessionDiff, SessionReview |
| 文件 | File, FileTree, FileSearch, FileIcon |
| Markdown | Markdown 渲染器、流式渲染 |
| 导航 | MessageNav, StickyAccordionHeader |
| 反馈 | Toast, Progress, Spinner, Tooltip |
| 菜单 | ContextMenu, DropdownMenu, Popover |
| 其他 | ResizeHandle, HoverCard |

---

## 十一、已实现的关键功能清单

1. 多 Agent 系统（build/plan/compose 模式 + 动态子 Agent）
2. 持久化记忆（SQLite FTS5 + MEMORY.md + 检查点）
3. 智能上下文管理（自动压缩、预算控制、上下文重建）
4. 树形任务跟踪（T1 -> T1.1 -> T1.2 层级）
5. 工作流引擎（沙箱 JS 执行 compose/deep-research/fact-check）
6. 13 个内置技能（arxiv/pdf/docx/pptx/xlsx 等）
7. 20+ LLM 提供商统一接口
8. 语音输入（TenVAD + MiMo ASR 实时流式）
9. 会话分叉与恢复（时间线分支）
10. LSP 支持（代码分析 + 诊断）
11. MCP 协议集成（外部工具扩展）
12. 完整的终端 UI（OpenTUI 渲染、鼠标、键盘、主题、对话框）
13. Web 界面 + Electron 桌面应用
14. 配置热加载
15. 国际化（中/英文）

---

## 十二、配置文件

| 文件 | 位置 | 用途 |
|------|------|------|
| `mimocode.jsonc` | `.mimocode/` 或 `~/.config/mimocode/` | 主配置：提供商、模型、Agent、权限 |
| `tui.json` | `.mimocode/` 或 `~/.config/mimocode/` | TUI 主题、键盘绑定 |
| `auth.json` | `~/.local/share/mimocode/` | 认证凭证 |
| `turbo.json` | 项目根目录 | Turborepo 任务配置 |
| `package.json` | 项目根目录 | Workspace 定义 + catalog 依赖 |
| `drizzle.config.ts` | `packages/opencode/` | SQLite 模式迁移 |
| `sst.config.ts` | 项目根目录 | AWS 部署（SST） |

---

## 十三、启动与使用

```bash
# 安装依赖
bun install

# TUI 模式（终端界面）
cd packages/opencode
bun run src/index.ts

# Web 模式
cd packages/app
bun run dev
# 访问 http://localhost:3000

# 桌面应用
cd packages/desktop
bun run dev

# 构建
bun run build
```

---

## 十四、关键文件速查

| 文件 | 用途 |
|------|------|
| `packages/opencode/src/index.ts` | CLI 入口，yargs 命令注册 |
| `packages/opencode/src/cli/cmd/tui/app.tsx` | TUI 应用根组件（1329行） |
| `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx` | 会话页面（3411行，最大文件） |
| `packages/opencode/src/agent/agent.ts` | Agent 定义与提示词生成 |
| `packages/opencode/src/provider/provider.ts` | LLM 提供商统一接口（1816行） |
| `packages/opencode/src/session/prompt.ts` | LLM 请求编排 |
| `packages/opencode/src/tool/registry.ts` | 工具注册与发现 |
| `packages/opencode/src/server/server.ts` | Hono HTTP 服务器 |
| `packages/opencode/src/config/config.ts` | 主配置解析 |
| `packages/opencode/src/memory/service.ts` | 记忆系统（FTS5 搜索） |
| `packages/opencode/src/storage/schema.ts` | Drizzle ORM 数据库模式 |
| `packages/opencode/src/workflow/runtime.ts` | 工作流沙箱执行引擎 |
| `packages/app/src/entry.tsx` | Web 应用入口 |
| `packages/app/src/app.tsx` | Web 应用外壳与路由 |
| `packages/desktop/src/renderer/index.tsx` | Electron 渲染进程入口 |
