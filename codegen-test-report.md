# 编码 Agent 自然语言理解 × 项目探索 × 代码生成能力对比测试

> **测试目标**：在**同一个模型**（glm-4-flash）下，比较不同工具理解自然语言需求、探索项目结构、生成代码的能力。
>
> **测试方法**：搭建一个 7 文件 308 行的 Java 图书馆系统项目，用同一个需求文档驱动，比较产出的代码质量。

---

## 测试项目结构

```
codegen-test/
├── src/
│   ├── model/
│   │   ├── Book.java              (id, title, author, isbn, publishedYear)
│   │   └── Member.java            (id, name, email)
│   ├── service/
│   │   ├── BookService.java       (接口: addBook, findBookById, listAllBooks)
│   │   ├── BookServiceImpl.java   (实现: 使用 DataStore<Book>)
│   │   └── MemberService.java     (接口: registerMember, findMemberById, listAllMembers)
│   └── store/
│       ├── DataStore.java         (泛型接口: save, findById, findAll, deleteById)
│       └── impl/
│           └── InMemoryDataStore.java  (HashMap 实现)
```

## 测试需求

在现有系统上添加借书还书功能，具体要求 4 条：
1. Book.java 加 `borrowed` + `borrowedByMemberId` 字段
2. BookService.java 加 `borrowBook(memberId, bookId)` + `returnBook(bookId)` 方法
3. 创建 MemberServiceImpl.java（遵循 BookServiceImpl 的模式）
4. BookServiceImpl 实现借还书逻辑（检查书存在、未借出、会员存在）

---

## 测试结果：Aider v0.86.2 + glm-4-flash

### 命令

```bash
cd /workspace/codegen-test
aider --model openai/glm-4-flash \
  --openai-api-base "https://open.bigmodel.cn/api/paas/v4" \
  --api-key "openai=你的key" \
  --yes-always --no-auto-lint \
  --file src/model/Book.java \
  --file src/service/BookService.java \
  --file src/service/impl/BookServiceImpl.java \
  --file src/service/MemberService.java \
  --message "$(cat requirement.txt)"
```

### 代码质量评估

| 需求项 | 完成度 | 代码质量 |
|---|---|---|
| Book.java 加字段 | ✅ 完成 | 字段 + getter/setter + 构造初始化全都正确 |
| BookService.java 加方法 | ✅ 完成 | 接口签名正确 |
| **MemberServiceImpl.java** | **✅ 创建** | **完美遵循 BookServiceImpl 的 DataStore 模式** |
| **borrowBook 实现** | ⚠️ 部分 | 检查书存在+未借出 ✅，但没检查会员是否存在 ❌ |
| **returnBook 实现** | ✅ 完成 | 检查存在+已借出+重置字段，逻辑完整 |
| 依赖注入 | ❌ 缺失 | BookServiceImpl 没有注入 MemberService，borrowBook 无法验证会员 |
| **编译** | **✅ 通过** | **0 错误，可直接运行** |

### 关键发现

**做得好的**：
- ✅ 代码编译零错误
- ✅ 新文件（MemberServiceImpl）完全遵循了现有代码的风格和模式
- ✅ borrowBook/returnBook 的业务逻辑正确（检查借用状态、保存变更）
- ✅ Book.java 的字段和 getter/setter 完整无遗漏

**做得不够的**：
- ❌ 没有把 MemberService 注入到 BookServiceImpl 中（borrowBook 方法无法验证会员是否存在）
- ❌ BookServiceImpl 没有 import `Member`/`MemberService`
- ✅ 但代码仍能编译——因为 borrowBook 虽然用了 memberId 参数，实际只做 `setBorrowedByMemberId(memberId)`，没调用 MemberService 的校验方法，所以编译不报错，**只是逻辑不完整**

---

## 对比分析：换成 Roo-Code 会怎样

由于 glm-4-flash 的工具调用遵从度较低（见第 14 章验证），无法直接运行 Roo-Code CLI 做同样测试。但从架构设计上分析：

### Roo-Code 的优势（如果有强工具调用模型）

| 能力 | Aider | Roo-Code（概念上） |
|---|---|---|
| 项目探索 | ❌ 用户必须手动 `--file` 添加 | ✅ 模型自己 `listFilesRecursive` → `readFile` |
| 上下文选择 | ❌ 用户决定加哪些文件 | ✅ 模型自主决定哪些文件相关 |
| 多文件编辑 | ✅ 一次性改多文件 | ✅ 逐个工具调用编辑 |
| 编译验证 | ❌ 不会自动编译 | ✅ `execute_command` 触发编译 |
| 自动修复 | ⚠️ `--auto-lint` 有限 | ✅ 5 层重试机制 |

### 关键差异

**Aider 的核心问题**：
- 用户必须自己决定哪些文件需要加入上下文
- 如果漏加了关键文件（比如这个测试里漏了 `store/DataStore.java`），模型还能工作
- 但模型**不会主动探索**项目，不知道有什么文件可用
- 不会自动执行编译命令验证

**Roo-Code 的核心优势**：
- 模型可以自己 `listFilesRecursive` 看项目结构
- 模型可以自己决定读哪些文件来理解上下文
- Agent 循环会推动模型执行命令和修复错误
- 更适合**不了解项目结构**时的探索式开发

---

## 结论

| 场景 | 更适合的工具 | 原因 |
|---|---|---|
| **已知项目结构**，有明确文件要改 | Aider | 精准编辑，代码质量好 |
| **不了解项目**，需要先探索再改 | Roo-Code | 模型自主探索 + agent 循环 |
| **需要自动编译验证** | Roo-Code | execute_command + 5 层修复 |
| **纯文件编辑**（不改逻辑） | Aider | 编辑格式更精准 |
| **大项目、多文件** | Roo-Code | 模型自主决定上下文 |
| **小项目、少量文件** | Aider | 启动快，用户手动加文件 |

**对你场景的建议**：你的需求是"扔一堆 Java + XML + PDF 进去让模型看懂再改"——这属于**不了解项目结构**的场景，Roo-Code 的自主探索能力更适合。但如果换成你先把关键文件加好、需求写清楚，Aider 的编辑质量也很高。
