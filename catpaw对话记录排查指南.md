# CatPaw 对话记录排查与查看指南

> 本文档记录了如何排查 CatPaw IDE 中 AI 对话记录的存储位置，包括成功的步骤和需要避坑的地方。适合对命令行不太熟悉的同学参考。

---

## 一、背景

CatPaw 是美团开发的 AI 编程 IDE（对标 Cursor / Z Code）。在使用过程中，用户与 AI 的对话记录（包括用户发给 AI 的原始消息、AI 的回复、工具调用记录等）会保存在本地。但一开始不确定具体保存在哪里，尤其是在 VSCode 的 `state.vscdb` 数据库中查找 `ItemTable` 表时遇到了问题。

---

## 二、排查过程

### 步骤1：查看 state.vscdb 数据库中有哪些表

**目的**：确认 `state.vscdb` 文件中是否有 `ItemTable` 表。

**命令**（使用 sqlite3 工具）：

```powershell
# 进入 sqlite3 工具所在目录（根据你的实际安装路径调整）
# sqlite3 工具下载地址：https://www.sqlite.org/download.html，选择 sqlite-tools-win32-x64-*.zip

# 查看 state.vscdb 中的所有表名
D:\software\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" ".tables"
```

**输出结果**：
```
ItemTable
```

**结论**：表 `ItemTable` 确实存在。

> ⚠️ **避坑提示**：如果你用的是 PowerShell，直接在命令行中写 SQL 语句时，单引号和双引号的嵌套容易出问题。建议把 SQL 语句用双引号包裹，里面的字符串用单引号。如果还报错，可以把 SQL 写到一个 `.sql` 文件中，然后用 `.read` 命令执行。

---

### 步骤2：查看 ItemTable 中有哪些 key

**目的**：CatPaw 的对话记录可能以某个 key 存储在 `ItemTable` 表中，需要找到对应的 key。

**命令**：
```powershell
# 查看 ItemTable 表中所有的 key（前50条）
D:\software\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" "SELECT key FROM ItemTable LIMIT 50;"
```

> ⚠️ **避坑提示**：在 PowerShell 中执行这个命令时，如果用 `cmd /c` 包裹，SQL 语句中的引号会导致解析错误（报 "incomplete input" 错误）。**解决方案**：不要用 `cmd /c` 包裹，直接在 PowerShell 中调用 sqlite3.exe 即可。

**输出结果**（关键部分）：
```
catpaw-uuid
catpaw.catpaw-core-sankuai
catpaw.catpaw-core-sankuai-sankuai
catpaw.mt-authentication
chat.ChatSessionStore.index
chat.workspaceTransfer
...
```

**结论**：找到了多个 `catpaw` 开头的 key，说明 CatPaw 的数据确实存储在 `state.vscdb` 中。但具体对话记录可能在哪个 key 里？

---

### 步骤3：查看 catpaw 相关 key 的内容

**目的**：查看 `catpaw.catpaw-core-sankuai` 这个 key 存储的内容，看是否是对话记录。

**命令**：
```powershell
# 查看 catpaw.catpaw-core-sankuai 的内容（前500个字符）
D:\software\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" "SELECT substr(value, 1, 500) FROM ItemTable WHERE key = 'catpaw.catpaw-core-sankuai';"
```

**输出结果**：
```
15088040897
```

**结论**：这个 key 存储的是用户工号，不是对话记录。

---

### 步骤4：查看 chat.ChatSessionStore.index 的内容

**目的**：检查 chat 相关的 key 是否存储对话记录。

**命令**：
```powershell
D:\software\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" "SELECT substr(value, 1, 500) FROM ItemTable WHERE key = 'chat.ChatSessionStore.index';"
```

**输出结果**：
```json
{"version":1,"entries":{}}
```

**结论**：chat session store 是空的，对话记录不在这里。

---

### 步骤5：查找 CatPaw 在文件系统中的其他存储位置

**目的**：既然 `state.vscdb` 中没有找到对话记录，说明 CatPaw 可能将对话记录存储在文件系统的其他位置。

**命令**：
```powershell
# 查找 CatPaw 在 globalStorage 目录下的所有文件
cmd /c "dir /s /b C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\ 2>nul | findstr /i catpaw"
```

> ⚠️ **注意**：这个命令执行后，输出被重定向到了一个 log 文件（CatPaw 的终端日志机制），需要用 `read_file` 工具读取输出。如果手动执行，直接在命令行中看输出即可。

---

### 步骤6：在用户主目录下查找 .catpaw 目录（关键发现！）

**目的**：CatPaw 可能在用户主目录下有自己的数据目录。

**命令**：
```powershell
# 查找 C:\Users\HI\.catpaw 目录下的所有文件（排除 .log 文件）
cmd /c "dir /s /b C:\Users\HI\.catpaw\ 2>nul | findstr /i /v \.log"
```

**输出结果**（关键部分）：
```
C:\Users\HI\.catpaw\projects
C:\Users\HI\.catpaw\projects\idec--temp-CREW_Kernel_PAED
C:\Users\HI\.catpaw\projects\idec--temp-CREW_Kernel_PAED\3adbacc9-0ec4-4382-a72a-d8f1d400b1a8
C:\Users\HI\.catpaw\projects\idec--temp-CREW_Kernel_PAED\3adbacc9-0ec4-4382-a72a-d8f1d400b1a8\agent-transcripts
C:\Users\HI\.catpaw\projects\idec--temp-CREW_Kernel_PAED\3adbacc9-0ec4-4382-a72a-d8f1d400b1a8\agent-transcripts\transcript.txt
...
```

**结论**：找到了！CatPaw 的对话记录存储在 `C:\Users\HI\.catpaw\projects\` 目录下。

---

## 三、最终结论：CatPaw 对话记录的存储结构

### 3.1 存储路径

```
C:\Users\{用户名}\.catpaw\projects\{项目路径编码}\{会话UUID}\agent-transcripts\transcript.txt
```

### 3.2 路径各部分说明

| 路径部分 | 说明 | 示例 |
|---------|------|------|
| `C:\Users\{用户名}\.catpaw\` | CatPaw 的根数据目录 | `C:\Users\HI\.catpaw\` |
| `projects\` | 所有项目的对话记录都在这下面 | |
| `{项目路径编码}` | 工作区路径，把 `:` 和 `\` 替换为 `-` | `idec--temp-CREW_Kernel_PAED`（对应 `c:\temp\CREW_Kernel_PAED`） |
| `{会话UUID}` | 每个对话会话对应一个 UUID 文件夹 | `3adbacc9-0ec4-4382-a72a-d8f1d400b1a8` |
| `agent-transcripts\transcript.txt` | 对话记录文本文件 | |

### 3.3 其他子目录

每个会话 UUID 文件夹下还可能包含：
- `agent-tools\` — 工具调用记录
- `terminals\` — 终端命令记录（每条命令一个 `.log` 文件）

### 3.4 如何找到你需要的对话记录

1. 打开 `C:\Users\{你的用户名}\.catpaw\projects\` 目录
2. 找到对应项目的文件夹（文件夹名中包含项目名）
3. 如果有多个 UUID 文件夹（多个对话会话），可以按修改时间排序，最新的就是最近一次对话
4. 打开 `agent-transcripts\transcript.txt` 文件，里面就是完整的对话记录

---

## 四、常用排查命令汇总

### 4.1 查看 state.vscdb 中的表

```powershell
D:\software\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" ".tables"
```

### 4.2 查看 ItemTable 中的所有 key

```powershell
D:\software\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" "SELECT key FROM ItemTable LIMIT 50;"
```

### 4.3 查看某个 key 的内容

```powershell
D:\software\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" "SELECT substr(value, 1, 500) FROM ItemTable WHERE key = 'catpaw.catpaw-core-sankuai';"
```

> **说明**：`substr(value, 1, 500)` 表示只取前500个字符，防止内容太长刷屏。

### 4.4 查找 CatPaw 数据目录

```powershell
# 查找 .catpaw 目录下所有文件（排除日志文件）
cmd /c "dir /s /b C:\Users\HI\.catpaw\ 2>nul | findstr /i /v \.log"
```

### 4.5 查看最近的对话记录文件

```powershell
# 按修改时间倒序列出所有 transcript.txt 文件
cmd /c "dir /s /b /o-d C:\Users\HI\.catpaw\projects\*transcript.txt"
```

---

## 五、避坑总结

### 坑1：PowerShell 中执行 sqlite3 命令的引号问题

**问题**：在 PowerShell 中用 `cmd /c` 包裹 sqlite3 命令时，SQL 语句中的引号会导致解析错误，报 "incomplete input" 或 "Expression after pipe" 错误。

**解决方案**：不要用 `cmd /c` 包裹，直接在 PowerShell 中调用 `sqlite3.exe`，SQL 语句用双引号包裹即可。

```powershell
# ❌ 错误写法（会报错）
cmd /c "D:\software\sqlite-tools\sqlite3.exe "C:\path\to\db.vscdb" "SELECT key FROM ItemTable LIMIT 50;""

# ✅ 正确写法
D:\software\sqlite-tools\sqlite3.exe "C:\path\to\db.vscdb" "SELECT key FROM ItemTable LIMIT 50;"
```

### 坑2：state.vscdb 中找不到对话记录

**问题**：在 `state.vscdb` 的 `ItemTable` 中找到了 `catpaw` 开头的 key，但里面存的是工号等配置信息，不是对话记录。

**原因**：CatPaw 的对话记录不在 VSCode 的 globalStorage 数据库中，而是存储在用户主目录下的 `.catpaw` 文件夹中。

**解决方案**：直接去 `C:\Users\{用户名}\.catpaw\projects\` 目录下查找。

### 坑3：catpaw.catpaw-core-sankuai 不是对话记录

**问题**：看到 `catpaw.catpaw-core-sankuai` 这个 key 名字很像核心数据，以为是对话记录。

**实际**：这个 key 存储的是用户工号（如 `15088040897`），不是对话记录。

---

## 六、sqlite3 工具安装

如果电脑上没有 `sqlite3` 命令，需要手动安装：

1. 访问 https://www.sqlite.org/download.html
2. 下载 `sqlite-tools-win32-x64-*.zip`
3. 解压到任意目录（如 `D:\software\sqlite-tools\`）
4. 使用时用完整路径调用：`D:\software\sqlite-tools\sqlite3.exe`

> 不需要配置环境变量，直接用完整路径调用即可。
