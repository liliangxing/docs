# Roo Cline / Kilo Code — Codebase Indexing 完整搭建指南

> **适用环境**：Windows 10 / CatPaw IDE（基于 VS Code）  
> **目标读者**：对命令行不太熟悉、需要手把手指导的同学  
> **最终效果**：让 Roo Cline 和 Kilo Code 插件具备"代码库语义搜索"能力，能根据自然语言描述找到相关代码片段  
> **编写日期**：2026-07-23

---

## 目录

1. [什么是 Codebase Indexing？为什么要配？](#1-什么是-codebase-indexing为什么要配)
2. [整体架构：三个组件的关系](#2-整体架构三个组件的关系)
3. [前置条件检查](#3-前置条件检查)
4. [第一步：下载安装 Qdrant（向量数据库）](#第一步下载安装-qdrant向量数据库)
5. [第二步：下载安装 Ollama（本地 AI 推理引擎）](#第二步下载安装-ollama本地-ai-推理引擎)
6. [第三步：下载 BGE-M3 向量化模型并导入 Ollama](#第三步下载-bge-m3-向量化模型并导入-ollama)
7. [第四步：修改 Roo Cline / Kilo Code 配置文件](#第四步修改-roo-cline--kilo-code-配置文件)
8. [第五步：验证所有服务正常工作](#第五步验证所有服务正常工作)
9. [第六步：启动脚本与日常使用](#第六步启动脚本与日常使用)
10. [踩坑记录与排错命令大全](#踩坑记录与排错命令大全)
11. [附录：所有涉及的文件路径速查表](#附录所有涉及的文件路径速查表)

---

## 1. 什么是 Codebase Indexing？为什么要配？

### 大白话解释

想象你有一个超大的代码库（几万个文件），你想问 AI："帮我找到处理航班排班的代码在哪"。

如果没有 Codebase Indexing，AI 只能看你当前打开的文件，或者一个一个文件去翻，效率很低。

有了 Codebase Indexing 后，AI 会：
1. 把你所有代码文件"读懂"，转成一组数字（叫"向量"）
2. 把这些向量存到一个"向量数据库"里
3. 你提问时，AI 把你的问题也转成向量，然后在数据库里找最相似的代码

**就像给整个代码库建了一个"智能索引"，AI 能秒搜到相关代码。**

### 为什么不用 DeepSeek API 做向量化？

| 方案 | 优点 | 缺点 |
|------|------|------|
| DeepSeek API | 不用本地装东西 | **不支持 embedding 端点！** 调用 `/v1/embeddings` 返回 404 |
| Ollama 本地模型 | 免费、离线可用、速度快 | 需要下载安装、占用一点内存 |

> **结论**：DeepSeek API 只支持聊天（chat），不支持向量化（embedding）。所以必须用本地 Ollama + BGE-M3 模型来生成向量。

---

## 2. 整体架构：三个组件的关系

```
你的代码文件
     │
     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Ollama     │────▶│   Qdrant     │◀────│  Roo Cline  │
│ (BGE-M3模型) │     │ (向量数据库)  │     │ / Kilo Code │
│ 生成向量      │     │ 存储和搜索向量 │     │ 插件前端     │
└─────────────┘     └─────────────┘     └─────────────┘
  localhost:11434     localhost:6333       CatPaw IDE
```

### 三个组件各自的职责

| 组件 | 职责 | 通俗比喻 |
|------|------|----------|
| **Ollama + BGE-M3** | 把文字转成数字向量 | "翻译官"——把代码翻译成机器能比较的数字 |
| **Qdrant** | 存储向量，支持相似度搜索 | "图书馆"——把翻译好的数字存起来，能快速查找 |
| **Roo Cline / Kilo Code** | 调度以上两个组件 | "读者"——提问、获取搜索结果 |

---

## 3. 前置条件检查

### 3.1 检查已安装的 Roo Cline 插件

```powershell
# 检查 Roo Cline 插件是否已安装
dir "C:\Users\HI\.catpawai\extensions\rooveterinaryinc.roo-cline-3.53.0\package.json"
```

> **为什么检查这个？** 确保插件已正确安装，后面的配置文件才能被插件读取。

### 3.2 检查已安装的 Kilo Code 插件

```powershell
dir "C:\Users\HI\.catpawai\extensions\kilocode.kilo-code-7.4.11\package.json"
```

### 3.3 检查 PowerShell 可用

```powershell
# 打开 PowerShell（在 CatPaw 的终端里，或者 Win+R 输入 powershell）
$PSVersionTable.PSVersion
```

> **为什么要用 PowerShell？** Windows 自带，不用额外安装。所有命令都在 PowerShell 里执行。

---

## 第一步：下载安装 Qdrant（向量数据库）

### 1.1 下载 Qdrant

Qdrant 是一个开源的向量数据库，用来存储和搜索代码的向量表示。

```powershell
# 下载 Qdrant Windows 版（约 30MB 压缩包）
# 注意：必须加 --ssl-no-revoke，否则 SSL 证书检查会失败
curl.exe -L --ssl-no-revoke -o "C:\Users\HI\Downloads\qdrant-x86_64-pc-windows-msvc.zip" "https://github.com/qdrant/qdrant/releases/download/v1.13.2/qdrant-x86_64-pc-windows-msvc.zip"
```

> **⚠️ 避坑：为什么要加 `--ssl-no-revoke`？**  
> 公司网络/防火墙可能会拦截 SSL 证书吊销检查（CRYPT_E_REVOCATION_OFFLINE 错误），加上这个参数跳过吊销检查即可正常下载。这是 curl 特有的参数，不影响安全性。

### 1.2 解压 Qdrant

```powershell
# 创建 Qdrant 目录
New-Item -ItemType Directory -Force -Path "C:\Users\HI\qdrant"

# 用 PowerShell 解压（不用装额外工具）
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead("C:\Users\HI\Downloads\qdrant-x86_64-pc-windows-msvc.zip")
foreach ($entry in $zip.Entries) {
    $destPath = Join-Path "C:\Users\HI\qdrant" $entry.FullName
    $destDir = Split-Path $destPath -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
}
$zip.Dispose()

# 验证解压成功
Test-Path "C:\Users\HI\qdrant\qdrant.exe"
# 应该输出 True
```

> **⚠️ 避坑：为什么不用 `ExtractToDirectory`？**  
> PowerShell 的 `ExtractToDirectory` 方法在处理某些 zip 文件时会报错 "Invalid cast from 'System.Boolean' to 'System.Text.Encoding'"。改用 `ExtractToFile` 逐个文件解压更可靠。

### 1.3 启动 Qdrant

```powershell
# 启动 Qdrant 服务（后台运行，监听 6333 端口）
Start-Process -FilePath "C:\Users\HI\qdrant\qdrant.exe" -WorkingDirectory "C:\Users\HI\qdrant" -WindowStyle Hidden

# 等待 5 秒让服务启动
Start-Sleep -Seconds 5

# 验证 Qdrant 是否在运行
Invoke-RestMethod -Uri "http://localhost:6333/healthz" -Method Get
# 应该返回健康状态
```

> **为什么 WorkingDirectory 要设为 qdrant 目录？**  
> Qdrant 默认在当前目录下创建 `storage` 文件夹来存储数据。如果不设 WorkingDirectory，数据可能存到别的地方。

### 1.4 验证 Qdrant 版本

```powershell
# 查看 Qdrant 版本信息
Invoke-RestMethod -Uri "http://localhost:6333/" -Method Get
# 应该返回类似：{"title":"qdrant - vector search engine","version":"1.13.2",...}
```

---

## 第二步：下载安装 Ollama（本地 AI 推理引擎）

### 2.1 下载 Ollama 安装包

Ollama 是一个本地运行 AI 模型的工具，类似"本地版 OpenAI API"，但不需要联网。

```powershell
# 下载 Ollama 安装包（约 1.4GB，耐心等待）
curl.exe -L --ssl-no-revoke -o "C:\Users\HI\Downloads\OllamaSetup.exe" "https://ollama.com/download/OllamaSetup.exe"
```

> **⚠️ 注意：这个文件很大（约 1.4GB），下载可能需要 20-40 分钟。**  
> 可以用以下命令检查下载进度：
> ```powershell
> (Get-Item 'C:\Users\HI\Downloads\OllamaSetup.exe').Length
> # 完整文件大约 1426451968 字节（约 1.4GB）
> ```

### 2.2 静默安装 Ollama

```powershell
# 静默安装（不会弹出安装向导窗口）
Start-Process -FilePath "C:\Users\HI\Downloads\OllamaSetup.exe" -ArgumentList "/VERYSILENT" -Wait -PassThru | Select-Object ExitCode
```

> **⚠️ 避坑：为什么用 `/VERYSILENT` 而不是 `/S`？**  
> `/S` 参数在某些情况下会导致安装卡住（UAC 弹窗被阻塞）。`/VERYSILENT` 更可靠，不会弹出任何窗口。

### 2.3 验证安装

```powershell
# 检查 Ollama 是否安装到默认路径
Test-Path "C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe"
# 应该返回 True
```

### 2.4 启动 Ollama 服务

```powershell
# 启动 Ollama 服务（监听 11434 端口）
Start-Process -FilePath "C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden

# 等待 5 秒
Start-Sleep -Seconds 5

# 验证 Ollama 是否在运行
Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get
# 应该返回 {"models":[]}（空模型列表）
```

> **为什么要先启动 Ollama 服务？**  
> Ollama 有两种用法：① 作为后台服务运行（`ollama serve`），② 直接执行命令（如 `ollama pull`）。先用 `serve` 启动后台服务，后面才能通过 API 调用它。

---

## 第三步：下载 BGE-M3 向量化模型并导入 Ollama

### 3.1 为什么不能直接 `ollama pull`？

正常情况下，Ollama 下载模型只需要一条命令：
```powershell
ollama pull nomic-embed-text
```

**但在公司网络环境下，这会失败！** 因为 Ollama 的模型仓库托管在 Cloudflare 上，公司防火墙会拦截 Cloudflare 的连接（报错 `wsarecv: An existing connection was forcibly closed by the remote host`）。

> **⚠️ 避坑：Ollama 官方模型仓库网络不通**  
> `ollama pull` 从 `registry.ollama.ai` 下载模型，实际文件存在 Cloudflare R2 存储上。公司网络会阻断到 Cloudflare 的连接，导致下载失败。解决方案是从国内镜像站（ModelScope）下载 GGUF 文件，然后手动导入 Ollama。

### 3.2 从 ModelScope 下载 BGE-M3 GGUF 文件

BGE-M3 是智源研究院（BAAI）开发的多语言向量化模型，支持 100+ 种语言（包括中文），生成 1024 维向量。比 nomic-embed-text 对中文代码的理解更好。

```powershell
# 从 ModelScope 下载 BGE-M3 Q4_K_S 量化版本（约 404MB）
# Q4_K_S 是量化等级，在质量和大小之间取了平衡
curl.exe --ssl-no-revoke -L -o "C:\Users\HI\bge-m3-Q4_K_S.gguf" "https://modelscope.cn/models/Xorbits/bge-m3-gguf/resolve/master/bge-m3-Q4_K_S.gguf"
```

> **为什么选 Q4_K_S 而不是更大的 Q8 或 F16？**  
> - Q4_K_S（404MB）：质量够用，体积小，加载快  
> - Q8_0（605MB）：质量更好，但大 50%，加载慢  
> - F16（1104MB）：最高质量，但太大了，没必要  
> 对于代码搜索来说，Q4_K_S 完全够用。

> **为什么用 ModelScope 而不是 HuggingFace？**  
> HuggingFace（huggingface.co）在国内被墙，hf-mirror.com 镜像也不稳定（连接被重置）。ModelScope（modelscope.cn）是阿里达摩院的模型平台，国内直连速度稳定。

### 3.3 检查下载是否完整

```powershell
# 检查文件大小
(Get-Item "C:\Users\HI\bge-m3-Q4_K_S.gguf").Length
# 应该大约是 423655584 字节（约 404MB）
```

### 3.4 创建 Ollama Modelfile

Modelfile 是 Ollama 识别的模型配置文件，告诉 Ollama 用哪个 GGUF 文件创建模型。

```powershell
# 创建 Modelfile
@'
FROM ./bge-m3-Q4_K_S.gguf

PARAMETER temperature 0

PARAMETER num_ctx 8192
'@ | Out-File -Encoding utf8 "C:\Users\HI\Modelfile.bge-m3"
```

> **每行是什么意思？**
> - `FROM ./bge-m3-Q4_K_S.gguf`：指定 GGUF 模型文件路径（相对于 Modelfile 所在目录）
> - `PARAMETER temperature 0`：温度设为 0，保证每次生成的向量完全一致（确定性输出）
> - `PARAMETER num_ctx 8192`：上下文窗口 8192 token，能处理较长的代码片段

### 3.5 导入模型到 Ollama

```powershell
# 切换到 GGUF 文件所在目录（因为 Modelfile 里的路径是相对的）
Set-Location "C:\Users\HI"

# 用 Modelfile 创建 Ollama 模型
& "C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe" create bge-m3 -f "C:\Users\HI\Modelfile.bge-m3"
```

> **⚠️ 避坑：为什么必须先 `Set-Location`？**  
> Modelfile 里写的是 `FROM ./bge-m3-Q4_K_S.gguf`，这是相对路径。如果当前目录不是 `C:\Users\HI`，Ollama 就找不到 GGUF 文件。必须先切换到文件所在目录。

### 3.6 验证模型已导入

```powershell
# 列出 Ollama 中所有模型
& "C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe" list
# 应该看到：
# NAME             ID              SIZE      MODIFIED
# bge-m3:latest    caa4ca854866    423 MB    ...
```

### 3.7 测试 Embedding 功能

```powershell
# 通过 API 测试向量化功能
$body = @{
    model = 'bge-m3'
    prompt = 'Hello, this is a test.'
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:11434/api/embeddings" -Method Post -ContentType "application/json" -Body $body
# 应该返回一个包含 1024 个浮点数的 embedding 数组
```

> **为什么要测试？**  
> 确保模型不仅能加载，还能真正生成向量。如果这一步失败，后面的 Codebase Indexing 也会失败。

---

## 第四步：修改 Roo Cline / Kilo Code 配置文件

### 4.1 配置文件在哪里？

| 插件 | 配置文件路径 |
|------|-------------|
| Roo Cline | `C:\Users\HI\.catpawai\roo-code-settings.json` |
| Kilo Code | `C:\Users\HI\.catpawai\kilo-code-settings.json` |

> **为什么配置文件在 `.catpawai` 目录下？**  
> CatPaw IDE 把用户数据存在 `C:\Users\HI\.catpawai\` 目录（类似 VS Code 的 `.vscode` 目录）。插件的配置文件也存这里。

### 4.2 需要修改的内容

在两个配置文件中，找到 `globalSettings` → `codebaseIndexConfig` 部分，修改为以下内容：

```json
"codebaseIndexConfig": {
    "codebaseIndexEnabled": true,
    "codebaseIndexQdrantUrl": "http://localhost:6333",
    "codebaseIndexEmbedderProvider": "ollama",
    "codebaseIndexEmbedderBaseUrl": "http://localhost:11434",
    "codebaseIndexEmbedderModelId": "bge-m3",
    "codebaseIndexEmbedderModelDimension": 1024,
    "codebaseIndexOpenAiCompatibleBaseUrl": "",
    "codebaseIndexSearchMinScore": 0.0,
    "codebaseIndexSearchMaxResults": 50,
    "codebaseIndexBedrockRegion": "us-east-1",
    "codebaseIndexBedrockProfile": ""
}
```

### 4.3 每个配置项的含义

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `codebaseIndexEnabled` | `true` | 开启 Codebase Indexing 功能 |
| `codebaseIndexQdrantUrl` | `http://localhost:6333` | Qdrant 向量数据库地址 |
| `codebaseIndexEmbedderProvider` | `ollama` | 向量化引擎选择 Ollama（不用 OpenAI） |
| `codebaseIndexEmbedderBaseUrl` | `http://localhost:11434` | Ollama 服务地址 |
| `codebaseIndexEmbedderModelId` | `bge-m3` | 使用的模型名称（必须和 `ollama list` 中一致） |
| `codebaseIndexEmbedderModelDimension` | `1024` | BGE-M3 输出 1024 维向量（**这个值必须和模型实际输出一致！**） |
| `codebaseIndexSearchMinScore` | `0.0` | 搜索最低相似度分数（0 = 不过滤） |
| `codebaseIndexSearchMaxResults` | `50` | 最多返回 50 条搜索结果 |

> **⚠️ 最关键的配置项：`codebaseIndexEmbedderModelDimension`**  
> 这个值必须和模型实际输出的向量维度完全一致。BGE-M3 输出 1024 维，如果填错了（比如填 1536），Qdrant 创建集合时会用错误的维度，后续所有向量化操作都会失败！

### 4.4 用命令行修改配置文件

如果你不想手动编辑 JSON 文件，可以用以下 PowerShell 命令直接修改：

```powershell
# === 修改 Roo Cline 配置 ===
$rooConfig = Get-Content "C:\Users\HI\.catpawai\roo-code-settings.json" -Raw | ConvertFrom-Json
$rooConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderProvider = "ollama"
$rooConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderBaseUrl = "http://localhost:11434"
$rooConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderModelId = "bge-m3"
$rooConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderModelDimension = 1024
$rooConfig.globalSettings.codebaseIndexConfig.codebaseIndexOpenAiCompatibleBaseUrl = ""
$rooConfig | ConvertTo-Json -Depth 10 | Out-File "C:\Users\HI\.catpawai\roo-code-settings.json" -Encoding utf8

# === 修改 Kilo Code 配置（内容一样）===
$kiloConfig = Get-Content "C:\Users\HI\.catpawai\kilo-code-settings.json" -Raw | ConvertFrom-Json
$kiloConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderProvider = "ollama"
$kiloConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderBaseUrl = "http://localhost:11434"
$kiloConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderModelId = "bge-m3"
$kiloConfig.globalSettings.codebaseIndexConfig.codebaseIndexEmbedderModelDimension = 1024
$kiloConfig.globalSettings.codebaseIndexConfig.codebaseIndexOpenAiCompatibleBaseUrl = ""
$kiloConfig | ConvertTo-Json -Depth 10 | Out-File "C:\Users\HI\.catpawai\kilo-code-settings.json" -Encoding utf8
```

### 4.5 验证配置文件

```powershell
# 查看修改后的 Roo Cline 配置
Get-Content "C:\Users\HI\.catpawai\roo-code-settings.json" | ConvertFrom-Json | Select-Object -ExpandProperty globalSettings | Select-Object -ExpandProperty codebaseIndexConfig
```

---

## 第五步：验证所有服务正常工作

### 5.1 一键验证脚本

把以下内容保存为 `C:\Users\HI\verify-setup.ps1`，然后运行：

```powershell
# verify-setup.ps1 — 一键验证所有服务状态

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Codebase Indexing 验证脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Qdrant
Write-Host "[1/4] 检查 Qdrant 向量数据库..." -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod -Uri "http://localhost:6333/healthz" -Method Get
    Write-Host "  ✅ Qdrant 运行正常" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Qdrant 未运行！请执行: Start-Process 'C:\Users\HI\qdrant\qdrant.exe' -WorkingDirectory 'C:\Users\HI\qdrant' -WindowStyle Hidden" -ForegroundColor Red
}
Write-Host ""

# 2. 检查 Ollama
Write-Host "[2/4] 检查 Ollama 服务..." -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get
    Write-Host "  ✅ Ollama 运行正常" -ForegroundColor Green
    if ($r.models) {
        foreach ($m in $r.models) {
            $sizeMB = [math]::Round($m.size / 1024 / 1024, 1)
            Write-Host "     模型: $($m.name) ($sizeMB MB)" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "  ❌ Ollama 未运行！请执行: Start-Process 'C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe' -ArgumentList 'serve' -WindowStyle Hidden" -ForegroundColor Red
}
Write-Host ""

# 3. 测试 Embedding
Write-Host "[3/4] 测试向量化功能..." -ForegroundColor Yellow
try {
    $body = @{ model = 'bge-m3'; prompt = 'test embedding' } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "http://localhost:11434/api/embeddings" -Method Post -ContentType "application/json" -Body $body
    Write-Host "  ✅ 向量化成功！维度: $($r.embedding.Count)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ 向量化失败！请检查 bge-m3 模型是否已导入" -ForegroundColor Red
}
Write-Host ""

# 4. 检查配置文件
Write-Host "[4/4] 检查配置文件..." -ForegroundColor Yellow
$rooPath = "C:\Users\HI\.catpawai\roo-code-settings.json"
if (Test-Path $rooPath) {
    $config = Get-Content $rooPath -Raw | ConvertFrom-Json
    $ci = $config.globalSettings.codebaseIndexConfig
    Write-Host "  Roo Cline 配置:" -ForegroundColor Green
    Write-Host "    Provider: $($ci.codebaseIndexEmbedderProvider)" -ForegroundColor Gray
    Write-Host "    Model: $($ci.codebaseIndexEmbedderModelId)" -ForegroundColor Gray
    Write-Host "    Dimension: $($ci.codebaseIndexEmbedderModelDimension)" -ForegroundColor Gray
    Write-Host "    Qdrant URL: $($ci.codebaseIndexQdrantUrl)" -ForegroundColor Gray
} else {
    Write-Host "  ❌ 配置文件不存在: $rooPath" -ForegroundColor Red
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  验证完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
```

### 5.2 运行验证

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\HI\verify-setup.ps1"
```

预期输出：
```
[1/4] 检查 Qdrant 向量数据库...
  ✅ Qdrant 运行正常

[2/4] 检查 Ollama 服务...
  ✅ Ollama 运行正常
     模型: bge-m3:latest (404 MB)

[3/4] 测试向量化功能...
  ✅ 向量化成功！维度: 1024

[4/4] 检查配置文件...
  Roo Cline 配置:
    Provider: ollama
    Model: bge-m3
    Dimension: 1024
    Qdrant URL: http://localhost:6333
```

---

## 第六步：启动脚本与日常使用

### 6.1 创建一键启动脚本

每次重启电脑后，Qdrant 和 Ollama 不会自动启动。创建一个 bat 文件，双击即可启动两个服务：

```powershell
# 创建启动脚本
@'
@echo off
echo ========================================
echo  启动 Codebase Indexing 服务
echo ========================================
echo.

echo [1/2] 启动 Qdrant 向量数据库...
start "" /B "C:\Users\HI\qdrant\qdrant.exe"
timeout /t 3 /nobreak >nul

echo [2/2] 启动 Ollama AI 引擎...
start "" /B "C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe" serve
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo  所有服务已启动！
echo ========================================
echo   Qdrant:  http://localhost:6333
echo   Ollama:  http://localhost:11434
echo   模型:    bge-m3 (1024 维)
echo ========================================
echo.
pause
'@ | Out-File -Encoding ascii "C:\Users\HI\start-codebase-indexing.bat"
```

> **使用方法**：每次开机后，双击 `C:\Users\HI\start-codebase-indexing.bat` 即可启动所有服务。

### 6.2 在 Roo Cline 中使用 Codebase Search

1. 启动 CatPaw IDE
2. 打开 Roo Cline 插件面板
3. 在对话框中输入你的问题，比如 "找到处理航班配对的代码"
4. Roo Cline 会自动调用 `codebase_search` 工具搜索相关代码

### 6.3 重新索引代码库

如果你修改了配置（比如换了模型），需要重新索引：

1. 在 Roo Cline 设置中找到 "Codebase Indexing"
2. 点击 "Clear Index" 清除旧索引
3. 重新触发索引（通常在打开项目时自动开始）

---

## 踩坑记录与排错命令大全

### 坑 1：DeepSeek API 不支持 Embedding

**错误现象**：
```
Error - Invalid API endpoint. Please check your URL configuration.
```

**原因**：DeepSeek API 的 `/v1/embeddings` 端点返回 404 Not Found。DeepSeek 只支持聊天补全（`/v1/chat/completions`），不支持向量化。

**验证命令**：
```powershell
# 测试 DeepSeek 是否支持 embedding（会返回 404）
$headers = @{
    'Authorization' = 'Bearer sk-a04d8274f404429f9fa416feab039cc9'
    'Content-Type' = 'application/json'
}
$body = @{ model = 'deepseek-chat'; input = 'hello' } | ConvertTo-Json
try {
    Invoke-RestMethod -Uri 'https://api.deepseek.com/v1/embeddings' -Method Post -Headers $headers -Body $body
} catch {
    Write-Host "状态码: $($_.Exception.Response.StatusCode.value__)"
    # 输出: 状态码: 404
}
```

**解决方案**：改用本地 Ollama + BGE-M3 模型做向量化。

---

### 坑 2：Ollama 官方模型仓库网络不通

**错误现象**：
```
Error: max retries exceeded: Get "https://dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com/...":
read tcp 10.95.15.134:52142->172.64.66.1:443: wsarecv: An existing connection was forcibly closed by the remote host.
```

**原因**：`ollama pull` 从 Cloudflare R2 存储下载模型文件，公司防火墙拦截了 Cloudflare 的连接。

**验证命令**：
```powershell
# 尝试从 Ollama 官方仓库下载（会失败）
& "C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe" pull nomic-embed-text
# 等待后查看日志，会看到 connection forcibly closed 错误
```

**解决方案**：从 ModelScope（国内镜像）下载 GGUF 文件，手动导入 Ollama。

---

### 坑 3：HuggingFace 和 hf-mirror.com 下载失败

**错误现象**：
```
curl: (35) Recv failure: Connection was reset
```

**原因**：HuggingFace 在国内被墙，hf-mirror.com 镜像也不稳定。

**验证命令**：
```powershell
# 测试 HuggingFace 连通性（会失败）
curl.exe --ssl-no-revoke -s -o NUL -w "%{http_code}" "https://huggingface.co"
# 输出: 000（连接失败）

# 测试 hf-mirror.com 连通性（页面能打开，但下载大文件会被重置）
curl.exe --ssl-no-revoke -s -o NUL -w "%{http_code}" "https://hf-mirror.com"
# 输出: 200（页面能打开）
# 但下载 GGUF 文件时：
curl.exe --ssl-no-revoke -L -o "test.gguf" "https://hf-mirror.com/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q5_K_M.gguf"
# curl: (35) Recv failure: Connection was reset
```

**解决方案**：使用 ModelScope（modelscope.cn）下载，阿里云的 CDN，国内稳定。

---

### 坑 4：Qdrant 服务未启动

**错误现象**：
```
Error - Invalid API endpoint. Please check your URL configuration.
```

**原因**：Qdrant 没有运行，Roo Cline 连接 `http://localhost:6333` 失败。

> **注意**：这个错误信息和 DeepSeek API 不支持 embedding 时的错误一样！所以需要逐步排查。

**验证命令**：
```powershell
# 检查 Qdrant 是否在运行
try {
    Invoke-RestMethod -Uri "http://localhost:6333/healthz" -Method Get
    Write-Host "Qdrant 正在运行"
} catch {
    Write-Host "Qdrant 未运行！"
}

# 检查 6333 端口是否被占用
netstat -ano | findstr ":6333"
```

**解决方案**：重新启动 Qdrant：
```powershell
Start-Process -FilePath "C:\Users\HI\qdrant\qdrant.exe" -WorkingDirectory "C:\Users\HI\qdrant" -WindowStyle Hidden
```

---

### 坑 5：Ollama 安装时 UAC 弹窗卡住

**错误现象**：使用 `/S` 参数安装 Ollama 时，安装进程一直挂起不结束。

**原因**：`/S` 参数触发了 UAC（用户账户控制）弹窗，但弹窗在后台被阻塞。

**验证命令**：
```powershell
# 检查安装进程是否卡住
Get-Process OllamaSetup* -ErrorAction SilentlyContinue | Select-Object Name, Id
# 如果看到 OllamaSetup 和 OllamaSetup.tmp 进程一直存在，说明卡住了
```

**解决方案**：用 `/VERYSILENT` 参数代替 `/S`：
```powershell
# 先杀掉卡住的进程
Stop-Process -Name "OllamaSetup*" -Force -ErrorAction SilentlyContinue

# 用 VERYSILENT 重新安装
Start-Process -FilePath "C:\Users\HI\Downloads\OllamaSetup.exe" -ArgumentList "/VERYSILENT" -Wait -PassThru | Select-Object ExitCode
```

---

### 坑 6：curl 下载时 SSL 证书错误

**错误现象**：
```
curl: (35) schannel: next InitializeSecurityContext failed: CRYPT_E_REVOCATION_OFFLINE
```

**原因**：Windows 的 curl 使用 Schannel（Windows SSL 库），会检查证书吊销状态（CRL/OCSP）。公司网络可能无法访问吊销检查服务器。

**解决方案**：所有 curl 命令都加 `--ssl-no-revoke` 参数：
```powershell
# 正确写法
curl.exe -L --ssl-no-revoke -o "文件路径" "下载地址"
```

---

### 排错命令速查表

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| Qdrant 是否运行 | `Invoke-RestMethod -Uri "http://localhost:6333/healthz"` | 返回健康状态 |
| Ollama 是否运行 | `Invoke-RestMethod -Uri "http://localhost:11434/api/tags"` | 返回模型列表 |
| Ollama 有哪些模型 | `& "C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe" list` | 列出 bge-m3 |
| Embedding 是否正常 | 见 3.7 节的测试命令 | 返回 1024 维向量 |
| Qdrant 有哪些集合 | `Invoke-RestMethod -Uri "http://localhost:6333/collections"` | 返回集合列表 |
| 配置文件是否正确 | `Get-Content "C:\Users\HI\.catpawai\roo-code-settings.json"` | JSON 格式正确 |
| 检查端口占用 | `netstat -ano \| findstr ":6333"` | 看到 qdrant.exe 的 PID |
| 检查进程 | `Get-Process ollama*,qdrant*` | 看到两个进程 |
| 检查 ModelScope 可达 | `curl.exe --ssl-no-revoke -s -o NUL -w "%{http_code}" "https://modelscope.cn"` | 返回 200 |
| 检查 DeepSeek embedding | 见坑 1 的验证命令 | 返回 404 |

---

## 附录：所有涉及的文件路径速查表

### 程序文件

| 文件 | 路径 | 说明 |
|------|------|------|
| Qdrant 可执行文件 | `C:\Users\HI\qdrant\qdrant.exe` | 向量数据库程序 |
| Ollama 可执行文件 | `C:\Users\HI\AppData\Local\Programs\Ollama\ollama.exe` | AI 推理引擎 |
| BGE-M3 GGUF 模型 | `C:\Users\HI\bge-m3-Q4_K_S.gguf` | 原始模型文件 |
| Ollama Modelfile | `C:\Users\HI\Modelfile.bge-m3` | 模型配置文件 |

### 配置文件

| 文件 | 路径 | 说明 |
|------|------|------|
| Roo Cline 配置 | `C:\Users\HI\.catpawai\roo-code-settings.json` | Roo Cline 插件全局配置 |
| Kilo Code 配置 | `C:\Users\HI\.catpawai\kilo-code-settings.json` | Kilo Code 插件全局配置 |
| CatPaw 用户设置 | `C:\Users\HI\AppData\Roaming\CatPawAI\User\settings.json` | CatPaw IDE 用户设置 |

### 脚本文件

| 文件 | 路径 | 说明 |
|------|------|------|
| 启动脚本 | `C:\Users\HI\start-codebase-indexing.bat` | 双击启动 Qdrant + Ollama |
| 验证脚本 | `C:\Users\HI\verify-setup.ps1` | 一键验证所有服务状态 |

### 下载文件（临时）

| 文件 | 路径 | 说明 |
|------|------|------|
| Qdrant 压缩包 | `C:\Users\HI\Downloads\qdrant-x86_64-pc-windows-msvc.zip` | 可删除 |
| Ollama 安装包 | `C:\Users\HI\Downloads\OllamaSetup.exe` | 可删除 |

---

## 附：完整搭建流程（精简版）

如果你重新搭建，按这个顺序执行即可：

```
1. 下载安装 Qdrant → 启动 → 验证 6333 端口
2. 下载安装 Ollama → 启动 serve → 验证 11434 端口
3. 从 ModelScope 下载 bge-m3-Q4_K_S.gguf（404MB）
4. 创建 Modelfile → ollama create bge-m3 → 验证 ollama list
5. 测试 embedding API → 确认返回 1024 维
6. 修改 roo-code-settings.json 和 kilo-code-settings.json
7. 重启 CatPaw IDE → 在 Roo Cline 中使用 codebase_search
```

---

> **文档版本**：v1.0  
> **最后更新**：2026-07-23  
> **作者**：CatPaw AI 助手  
> **适用版本**：Roo Cline 3.53.0 / Kilo Code 7.4.11 / Qdrant 1.13.2 / Ollama (latest)
