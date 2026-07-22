# Roo-Code 智谱GLM与DeepSeek完整配置指南

> **文档说明**：本文档详细记录了在 CatPawAI（VS Code变体）中配置 Roo Code 插件使用智谱 GLM 和 DeepSeek AI 模型的完整过程。包括所有成功和失败的命令、调试方法以及常见问题解决方案。

> **适用人群**：对命令行不太熟悉，希望按步骤操作的开发者

> **文档版本**：v1.0  
> **最后更新**：2026年7月21日  
> **作者**：Roo Code 配置项目

---

## 📋 目录

- [一、环境准备](#一环境准备)
- [二、智谱 GLM 配置](#二智谱-glm-配置)
  - [2.1 获取智谱 API Key](#21-获取智谱-api-key)
  - [2.2 创建配置文件](#22-创建配置文件)
  - [2.3 查找 Roo Code 配置存储位置](#23-查找-roo-code-配置存储位置)
  - [2.4 下载 sqlite3 工具](#24-下载-sqlite3-工具)
  - [2.5 读取当前配置](#25-读取当前配置)
  - [2.6 写入配置到数据库](#26-写入配置到数据库)
  - [2.7 验证配置](#27-验证配置)
- [三、模型测试与切换](#三模型测试与切换)
  - [3.1 测试 glm-4.5 模型（失败案例）](#31-测试-glm-45-模型失败案例)
  - [3.2 测试其他智谱模型](#32-测试其他智谱模型)
  - [3.3 切回免费模型 glm-4-flash-250414](#33-切回免费模型-glm-4-flash-250414)
- [四、DeepSeek V4 Flash 配置](#四deepseek-v4-flash-配置)
  - [4.1 获取 DeepSeek API Key](#41-获取-deepseek-api-key)
  - [4.2 查询可用模型列表](#42-查询可用模型列表)
  - [4.3 测试 DeepSeek API](#43-测试-deepseek-api)
  - [4.4 更新配置为 DeepSeek](#44-更新配置为-deepseek)
- [五、常见错误与调试](#五常见错误与调试)
  - [5.1 余额不足错误](#51-余额不足错误)
  - [5.2 Git 克隆速度慢问题](#52-git-克隆速度慢问题)
  - [5.3 SQLite 写入格式错误](#53-sqlite-写入格式错误)
  - [5.4 配置不生效问题](#54-配置不生效问题)
- [六、命令速查表](#六命令速查表)
- [七、配置文件参考](#七配置文件参考)

---

## 一、环境准备

### 1.1 检查 CatPawAI 安装

首先确认 CatPawAI 已安装并且 Roo Code 插件已加载：

```powershell
# 查看 CatPawAI 目录结构
Get-ChildItem "C:\Users\HI\.catpawai\extensions" -ErrorAction SilentlyContinue

# 预期输出包含：
# rooveterinaryinc.roo-cline-3.54.0
```

### 1.2 查找配置文件位置

CatPawAI 的用户配置和数据存储在以下位置：

```powershell
# 查看全局存储目录
Get-ChildItem "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage" -ErrorAction SilentlyContinue

# 关键文件：
# state.vscdb - VS Code 状态数据库（包含 Roo Code 配置）
```

### 1.3 Roo Code 配置存储机制

**为什么需要这样配置？**

Roo Code 插件将配置存储在两个地方：

| 存储位置 | 作用 | 数据库键名 |
|---------|------|-----------|
| **SecretStorage** | 存储 API Key 等敏感信息 | `roo_cline_config_api_config` |
| **GlobalState** | 存储配置元数据 | `RooVeterinaryInc.roo-cline` |

由于 CatPawAI 是 VS Code 的变体，使用相同的存储机制。我们需要直接操作 `state.vscdb` SQLite 数据库来写入配置。

---

## 二、智谱 GLM 配置

### 2.1 获取智谱 API Key

登录 [智谱开放平台](https://open.bigmodel.cn) 获取 API Key。

**测试用的 API Key（示例）：**
```
d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4
```

### 2.2 创建配置文件

首先创建 Roo Code 的自动导入配置文件：

```powershell
# 创建配置文件
$settingsPath = "C:\Users\HI\.catpawai\roo-code-settings.json"

@'
{
  "providerProfiles": {
    "currentApiConfigName": "zhipu-glm",
    "apiConfigs": {
      "zhipu-glm": {
        "id": "zhipu-glm-config-001",
        "apiProvider": "openai",
        "openAiApiKey": "d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4",
        "openAiBaseUrl": "https://open.bigmodel.cn/api/paas/v4/",
        "openAiModelId": "glm-4-flash-250414",
        "openAiCustomModelInfo": {
          "maxTokens": 16000,
          "contextWindow": 128000,
          "supportsImages": false,
          "supportsComputerUse": false,
          "supportsPromptCache": false
        },
        "openAiStreamingEnabled": true,
        "rateLimitSeconds": 0,
        "consecutiveMistakeLimit": 6,
        "todoListEnabled": true
      }
    },
    "modeApiConfigs": {
      "code": "zhipu-glm-config-001",
      "architect": "zhipu-glm-config-001",
      "ask": "zhipu-glm-config-001",
      "debug": "zhipu-glm-config-001"
    },
    "migrations": {
      "rateLimitSecondsMigrated": true,
      "openAiHeadersMigrated": true,
      "consecutiveMistakeLimitMigrated": true,
      "todoListEnabledMigrated": true,
      "claudeCodeLegacySettingsMigrated": true
    }
  },
  "globalSettings": {}
}
'@ | Out-File -FilePath $settingsPath -Encoding UTF8 -NoNewline

Write-Output "配置文件已创建: $settingsPath"
```

### 2.3 查找 Roo Code 配置存储位置

```powershell
# 查找 state.vscdb 数据库文件
$dbPath = "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb"
Test-Path $dbPath

# 预期输出：True
```

### 2.4 下载 sqlite3 工具

由于 Windows 默认没有安装 sqlite3，需要下载：

```powershell
# 下载 SQLite 工具
curl.exe --ssl-no-revoke -L -o "C:\temp\sqlite-tools.zip" `
    "https://www.sqlite.org/2024/sqlite-tools-win-x64-3460000.zip" `
    --connect-timeout 15 2>&1

# 解压工具
Expand-Archive -Path "C:\temp\sqlite-tools.zip" `
    -DestinationPath "C:\temp\sqlite-tools" -Force 2>&1

# 验证安装
Test-Path "C:\temp\sqlite-tools\sqlite3.exe"
```

**输出示例：**
```
HTTP_CODE:200
SIZE:2636732
TIME:15.234567s
True
```

### 2.5 读取当前配置

使用 sqlite3 读取 Roo Code 的当前配置：

```powershell
# 查看所有 Roo 相关的配置键
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "SELECT key FROM ItemTable WHERE key LIKE '%roo%' OR key LIKE '%cline%';" 2>&1
```

**预期输出：**
```
RooVeterinaryInc.roo-cline
```

读取完整的 globalState：

```powershell
# 读取 Roo Code 的 globalState
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "SELECT value FROM ItemTable WHERE key = 'RooVeterinaryInc.roo-cline';" 2>&1 | `
    Out-File -FilePath "C:\temp\roo-state.json" -Encoding UTF8

# 查看关键配置字段
$json = Get-Content "C:\temp\roo-state.json" -Raw | ConvertFrom-Json
Write-Output "当前 API 配置名称: $($json.currentApiConfigName)"
Write-Output "API 配置列表:"
$json.listApiConfigMeta | Format-Table -AutoSize
```

### 2.6 写入配置到数据库

#### 步骤 1：写入 SecretStorage（API Key）

```powershell
# 创建 secret 配置文件
$secretPath = "C:\temp\roo-secret.json"

@'
{
  "currentApiConfigName":"zhipu-glm",
  "apiConfigs":{
    "default":{
      "id":"opax6wx3d4a",
      "apiProvider":"openrouter",
      "openRouterModelId":"claude-sonnet-4.5",
      "rateLimitSeconds":0,
      "consecutiveMistakeLimit":6,
      "todoListEnabled":true
    },
    "zhipu-glm":{
      "id":"zhipu001",
      "apiProvider":"openai",
      "openAiApiKey":"d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4",
      "openAiBaseUrl":"https://open.bigmodel.cn/api/paas/v4/",
      "openAiModelId":"glm-4-flash-250414",
      "openAiCustomModelInfo":{
        "maxTokens":16000,
        "contextWindow":128000,
        "supportsImages":false,
        "supportsComputerUse":false,
        "supportsPromptCache":false
      },
      "openAiStreamingEnabled":true,
      "rateLimitSeconds":0,
      "consecutiveMistakeLimit":6,
      "todoListEnabled":true
    }
  },
  "modeApiConfigs":{
    "code":"zhipu001",
    "architect":"zhipu001",
    "ask":"zhipu001",
    "debug":"zhipu001"
  },
  "migrations":{
    "rateLimitSecondsMigrated":true,
    "openAiHeadersMigrated":true,
    "consecutiveMistakeLimitMigrated":true,
    "todoListEnabledMigrated":true,
    "claudeCodeLegacySettingsMigrated":true
  }
}
'@ | Out-File -FilePath $secretPath -Encoding UTF8 -NoNewline

# 写入数据库
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-secret.json') WHERE key = 'roo_cline_config_api_config';" 2>&1

Write-Output "Exit code: $LASTEXITCODE"
```

**输出：**
```
Exit code: 0
```

#### 步骤 2：更新 GlobalState（元数据）

```powershell
# 读取当前 globalState
$json = Get-Content "C:\temp\roo-state.json" -Raw | ConvertFrom-Json

# 添加智谱配置元数据
$json.listApiConfigMeta = @(
    @{name="default"; id="opax6wx3d4a"; apiProvider="openrouter"; modelId="claude-sonnet-4.5"},
    @{name="zhipu-glm"; id="zhipu001"; apiProvider="openai"; modelId="glm-4-flash-250414"}
)
$json | Add-Member -NotePropertyName "currentApiConfigName" -NotePropertyValue "zhipu-glm" -Force

# 写回文件
$json | ConvertTo-Json -Depth 10 | Out-File "C:\temp\roo-state-updated.json" -Encoding UTF8

# 更新数据库
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-state-updated.json') WHERE key = 'RooVeterinaryInc.roo-cline';" 2>&1

Write-Output "Exit code: $LASTEXITCODE"
```

**输出：**
```
Exit code: 0
```

#### 步骤 3：设置自动导入路径

```powershell
# 读取当前 settings.json
$settingsPath = "C:\Users\HI\AppData\Roaming\CatPawAI\User\settings.json"
$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json

# 添加自动导入配置
$settings | Add-Member -NotePropertyName "roo-cline.autoImportSettingsPath" -NotePropertyValue "C:\Users\HI\.catpawai\roo-code-settings.json" -Force

# 写回文件
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

Write-Output "自动导入路径已设置"
```

### 2.7 验证配置

#### 验证 1：检查数据库写入

```powershell
# 验证 secret 写入
Write-Output "=== Secret 验证 ==="
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "SELECT substr(value, 1, 100) FROM ItemTable WHERE key = 'roo_cline_config_api_config';" 2>&1

# 验证 globalState 写入
Write-Output ""
Write-Output "=== GlobalState 验证 ==="
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "SELECT substr(value, 1, 200) FROM ItemTable WHERE key = 'RooVeterinaryInc.roo-cline';" 2>&1
```

#### 验证 2：测试智谱 API 连通性

```powershell
# 创建测试 JSON 文件
@'
{
  "model": "glm-4-flash-250414",
  "messages": [
    {"role": "user", "content": "Say hello in one word"}
  ]
}
'@ | Out-File "C:\temp\zhipu-test.json" -Encoding UTF8 -NoNewline

# 测试 API
curl.exe --ssl-no-revoke -s -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" `
    -H "Content-Type: application/json" `
    -H "Authorization: Bearer d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4" `
    -d "@C:\temp\zhipu-test.json" `
    --connect-timeout 15 2>&1
```

**成功输出示例：**
```json
{
  "choices": [{
    "finish_reason": "stop",
    "index": 0,
    "message": {
      "content": "Hi",
      "role": "assistant"
    }
  }],
  "created": 1784600692,
  "id": "2026072110245263edba08861142d1",
  "model": "glm-4-flash-250414",
  "object": "chat.completion",
  "request_id": "2026072110245263edba08861142d1",
  "usage": {
    "completion_tokens": 3,
    "prompt_tokens": 10,
    "total_tokens": 13
  }
}
```

#### 验证 3：创建 HelloWorld.java 测试

```powershell
# 创建 Java 文件
@'
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello World from Zhipu GLM!");
    }
}
'@ | Out-File "C:\temp\CREW_Kernel_PAED\docs\HelloWorld.java" -Encoding UTF8 -NoNewline

# 编译并运行
cmd /c "set JAVA_HOME=D:\software\Java\jdk1.8.0_202 && set PATH=%JAVA_HOME%\bin;%PATH% && cd /d C:\temp\CREW_Kernel_PAED\docs && javac HelloWorld.java && java HelloWorld"
```

**成功输出：**
```
Hello World from Zhipu GLM!
```

#### 重新加载 CatPawAI

配置完成后，需要重新加载 CatPawAI 窗口让配置生效：

1. 按 `Ctrl+Shift+P`
2. 输入 `Developer: Reload Window`
3. 按 `Enter`

或者从命令面板选择：`Developer: Reload Window`

---

## 三、模型测试与切换

### 3.1 测试 glm-4.5 模型（失败案例）

#### 更新配置为 glm-4.5

```powershell
# 读取配置文件
$settingsPath = "C:\Users\HI\.catpawai\roo-code-settings.json"
$json = Get-Content $settingsPath -Raw | ConvertFrom-Json

# 修改模型 ID
$json.providerProfiles.apiConfigs."zhipu-glm".openAiModelId = "glm-4.5"

# 写回文件
$json | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

Write-Output "配置已更新为 glm-4.5"
```

#### 测试 glm-4.5

```powershell
# 更新测试 JSON
@'
{
  "model": "glm-4.5",
  "messages": [
    {"role": "user", "content": "Say hello in one word"}
  ]
}
'@ | Out-File "C:\temp\zhipu-test-45.json" -Encoding UTF8 -NoNewline

# 测试 API
curl.exe --ssl-no-revoke -s -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" `
    -H "Content-Type: application/json" `
    -H "Authorization: Bearer d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4" `
    -d "@C:\temp\zhipu-test-45.json" `
    --connect-timeout 15 2>&1
```

**失败输出示例：**
```json
{
  "error": {
    "code": "1113",
    "message": "余额不足或无可用资源包,请充值。"
  }
}
```

#### 同步更新数据库配置

```powershell
# 创建新的 secret 配置
$secretPath = "C:\temp\roo-secret.json"
@'
{
  "currentApiConfigName":"zhipu-glm",
  "apiConfigs":{
    "zhipu-glm":{
      "id":"zhipu001",
      "apiProvider":"openai",
      "openAiApiKey":"d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4",
      "openAiBaseUrl":"https://open.bigmodel.cn/api/paas/v4/",
      "openAiModelId":"glm-4.5",
      "openAiCustomModelInfo":{
        "maxTokens":16000,
        "contextWindow":128000,
        "supportsImages":false,
        "supportsComputerUse":false,
        "supportsPromptCache":false
      },
      "openAiStreamingEnabled":true,
      "rateLimitSeconds":0,
      "consecutiveMistakeLimit":6,
      "todoListEnabled":true
    }
  }
}
'@ | Out-File -FilePath $secretPath -Encoding UTF8 -NoNewline

# 写入数据库
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-secret.json') WHERE key = 'roo_cline_config_api_config';" 2>&1

# 更新 globalState
$json = Get-Content "C:\temp\roo-state.json" -Raw | ConvertFrom-Json
$json.listApiConfigMeta = @(
    @{name="zhipu-glm"; id="zhipu001"; apiProvider="openai"; modelId="glm-4.5"}
)
$json.currentApiConfigName = "zhipu-glm"
$json | ConvertTo-Json -Depth 10 | Out-File "C:\temp\roo-state-updated.json" -Encoding UTF8

C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-state-updated.json') WHERE key = 'RooVeterinaryInc.roo-cline';" 2>&1
```

### 3.2 测试其他智谱模型

由于 `glm-4.5` 余额不足，测试其他可用模型：

```powershell
# 测试 glm-4-flash
@'{"model":"glm-4-flash","messages":[{"role":"user","content":"hi"}]}'@ | Out-File "C:\temp\zhipu-test-flash.json" -Encoding UTF8 -NoNewline
curl.exe --ssl-no-revoke -s -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" -H "Content-Type: application/json" -H "Authorization: Bearer d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4" -d "@C:\temp\zhipu-test-flash.json" --connect-timeout 15 2>&1

# 测试 glm-4-plus
@'{"model":"glm-4-plus","messages":[{"role":"user","content":"hi"}]}'@ | Out-File "C:\temp\zhipu-test-plus.json" -Encoding UTF8 -NoNewline
curl.exe --ssl-no-revoke -s -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" -H "Content-Type: application/json" -H "Authorization: Bearer d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4" -d "@C:\temp\zhipu-test-plus.json" --connect-timeout 15 2>&1

# 测试 glm-4
@'{"model":"glm-4","messages":[{"role":"user","content":"hi"}]}'@ | Out-File "C:\temp\zhipu-test-4.json" -Encoding UTF8 -NoNewline
curl.exe --ssl-no-revoke -s -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" -H "Content-Type: application/json" -H "Authorization: Bearer d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4" -d "@C:\temp\zhipu-test-4.json" --connect-timeout 15 2>&1
```

**测试结果汇总：**

| 模型 | 状态 | 说明 |
|------|------|------|
| `glm-4-flash-250414` | ✅ 可用 | 免费，之前已配好 |
| `glm-4-flash` | ✅ 可用 | 免费 |
| `glm-4.5` | ❌ 余额不足 | 需充值 |
| `glm-4` | ❌ 余额不足 | 需充值 |
| `glm-4-plus` | ❌ 余额不足 | 需充值 |
| `glm-4-air` | ❌ 余额不足 | 需充值 |
| `glm-4-flashx` | ❌ 余额不足 | 需充值 |

### 3.3 切回免费模型 glm-4-flash-250414

```powershell
# 读取配置
$settingsPath = "C:\Users\HI\.catpawai\roo-code-settings.json"
$json = Get-Content $settingsPath -Raw | ConvertFrom-Json

# 改回免费模型
$json.providerProfiles.apiConfigs."zhipu-glm".openAiModelId = "glm-4-flash-250414"

# 写回文件
$json | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

Write-Output "已改回 glm-4-flash-250414"
```

同步更新数据库：

```powershell
# 更新 secret
@'
{
  "currentApiConfigName":"zhipu-glm",
  "apiConfigs":{
    "zhipu-glm":{
      "id":"zhipu001",
      "apiProvider":"openai",
      "openAiApiKey":"d7640538c3f245a59b3a1d1bf9862d47.mcOUKUYV9o6OY2n4",
      "openAiBaseUrl":"https://open.bigmodel.cn/api/paas/v4/",
      "openAiModelId":"glm-4-flash-250414",
      "openAiCustomModelInfo":{
        "maxTokens":16000,
        "contextWindow":128000,
        "supportsImages":false,
        "supportsComputerUse":false,
        "supportsPromptCache":false
      },
      "openAiStreamingEnabled":true,
      "rateLimitSeconds":0,
      "consecutiveMistakeLimit":6,
      "todoListEnabled":true
    }
  }
}
'@ | Out-File -FilePath "C:\temp\roo-secret.json" -Encoding UTF8 -NoNewline

C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-secret.json') WHERE key = 'roo_cline_config_api_config';" 2>&1

# 更新 globalState
$json = Get-Content "C:\temp\roo-state.json" -Raw | ConvertFrom-Json
$json.listApiConfigMeta = @(
    @{name="default"; id="opax6wx3d4a"; apiProvider="openrouter"; modelId="claude-sonnet-4.5"},
    @{name="zhipu-glm"; id="zhipu001"; apiProvider="openai"; modelId="glm-4-flash-250414"}
)
$json.currentApiConfigName = "zhipu-glm"
$json | ConvertTo-Json -Depth 10 | Out-File "C:\temp\roo-state-updated.json" -Encoding UTF8

C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-state-updated.json') WHERE key = 'RooVeterinaryInc.roo-cline';" 2>&1

Write-Output "配置已改回 glm-4-flash-250414"
```

---

## 四、DeepSeek V4 Flash 配置

### 4.1 获取 DeepSeek API Key

登录 [DeepSeek 开放平台](https://platform.deepseek.com) 获取 API Key。

**测试用的 API Key（示例）：**
```
你的DeepSeek_API密钥
```

### 4.2 查询可用模型列表

```powershell
# 查询 DeepSeek 模型列表
curl.exe --ssl-no-revoke -s "https://api.deepseek.com/v1/models" `
    -H "Authorization: Bearer 你的DeepSeek_API密钥" `
    --connect-timeout 15 2>&1
```

**成功输出示例：**
```json
{
  "data": [
    {
      "id": "deepseek-v4-flash",
      "object": "model",
      "owned_by": "deepseek"
    },
    {
      "id": "deepseek-v4-pro",
      "object": "model",
      "owned_by": "deepseek"
    }
  ],
  "object": "list"
}
```

### 4.3 测试 DeepSeek API

```powershell
# 创建测试文件
@'
{
  "model": "deepseek-v4-flash",
  "messages": [
    {"role": "user", "content": "Say hello in one word"}
  ]
}
'@ | Out-File "C:\temp\deepseek-test.json" -Encoding UTF8 -NoNewline

# 测试 API
curl.exe --ssl-no-revoke -s -X POST "https://api.deepseek.com/v1/chat/completions" `
    -H "Content-Type: application/json" `
    -H "Authorization: Bearer 你的DeepSeek_API密钥" `
    -d "@C:\temp\deepseek-test.json" `
    --connect-timeout 15 2>&1
```

**测试结果：**
```json
{
  "error": {
    "message": "Insufficient Balance",
    "type": "unknown_error",
    "param": null,
    "code": "invalid_request_error"
  }
}
```

### 4.4 更新配置为 DeepSeek

#### 步骤 1：更新配置文件

```powershell
# 读取配置
$settingsPath = "C:\Users\HI\.catpawai\roo-code-settings.json"
$json = Get-Content $settingsPath -Raw | ConvertFrom-Json

# 更新为 DeepSeek 配置
$json.providerProfiles.currentApiConfigName = "deepseek"
$json.providerProfiles.apiConfigs = @{
    "deepseek" = @{
        "id" = "deepseek-config-001"
        "apiProvider" = "openai"
        "openAiApiKey" = "你的DeepSeek_API密钥"
        "openAiBaseUrl" = "https://api.deepseek.com/v1"
        "openAiModelId" = "deepseek-v4-flash"
        "openAiCustomModelInfo" = @{
            "maxTokens" = 8192
            "contextWindow" = 64000
            "supportsImages" = $false
            "supportsComputerUse" = $false
            "supportsPromptCache" = $false
        }
        "openAiStreamingEnabled" = $true
        "rateLimitSeconds" = 0
        "consecutiveMistakeLimit" = 6
        "todoListEnabled" = $true
    }
}
$json.providerProfiles.modeApiConfigs = @{
    "code" = "deepseek-config-001"
    "architect" = "deepseek-config-001"
    "ask" = "deepseek-config-001"
    "debug" = "deepseek-config-001"
}

# 写回文件
$json | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

Write-Output "配置已更新为 DeepSeek"
```

#### 步骤 2：更新数据库 Secret

```powershell
# 创建 DeepSeek secret 配置
@'
{
  "currentApiConfigName":"deepseek",
  "apiConfigs":{
    "default":{
      "id":"opax6wx3d4a",
      "apiProvider":"openrouter",
      "openRouterModelId":"claude-sonnet-4.5",
      "rateLimitSeconds":0,
      "consecutiveMistakeLimit":6,
      "todoListEnabled":true
    },
    "deepseek":{
      "id":"deepseek-config-001",
      "apiProvider":"openai",
      "openAiApiKey":"你的DeepSeek_API密钥",
      "openAiBaseUrl":"https://api.deepseek.com/v1",
      "openAiModelId":"deepseek-v4-flash",
      "openAiCustomModelInfo":{
        "maxTokens":8192,
        "contextWindow":64000,
        "supportsImages":false,
        "supportsComputerUse":false,
        "supportsPromptCache":false
      },
      "openAiStreamingEnabled":true,
      "rateLimitSeconds":0,
      "consecutiveMistakeLimit":6,
      "todoListEnabled":true
    }
  },
  "modeApiConfigs":{
    "code":"deepseek-config-001",
    "architect":"deepseek-config-001",
    "ask":"deepseek-config-001",
    "debug":"deepseek-config-001"
  },
  "migrations":{
    "rateLimitSecondsMigrated":true,
    "openAiHeadersMigrated":true,
    "consecutiveMistakeLimitMigrated":true,
    "todoListEnabledMigrated":true,
    "claudeCodeLegacySettingsMigrated":true
  }
}
'@ | Out-File -FilePath "C:\temp\roo-secret.json" -Encoding UTF8 -NoNewline

# 写入数据库
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-secret.json') WHERE key = 'roo_cline_config_api_config';" 2>&1

Write-Output "Secret 已更新"
```

#### 步骤 3：更新 GlobalState

```powershell
# 读取当前 globalState
$json = Get-Content "C:\temp\roo-state.json" -Raw | ConvertFrom-Json

# 添加 DeepSeek 配置元数据
$json.listApiConfigMeta = @(
    @{name="default"; id="opax6wx3d4a"; apiProvider="openrouter"; modelId="claude-sonnet-4.5"},
    @{name="deepseek"; id="deepseek-config-001"; apiProvider="openai"; modelId="deepseek-v4-flash"}
)
$json.currentApiConfigName = "deepseek"

# 写回文件
$json | ConvertTo-Json -Depth 10 | Out-File "C:\temp\roo-state-updated.json" -Encoding UTF8

# 更新数据库
C:\temp\sqlite-tools\sqlite3.exe "C:\Users\HI\AppData\Roaming\CatPawAI\User\globalStorage\state.vscdb" `
    "UPDATE ItemTable SET value = readfile('C:/temp/roo-state-updated.json') WHERE key = 'RooVeterinaryInc.roo-cline';" 2>&1

Write-Output "GlobalState 已更新"
```

#### DeepSeek 配置汇总

| 配置项 | 值 |
|--------|------|
| Provider | `openai`（OpenAI 兼容模式） |
| Base URL | `https://api.deepseek.com/v1` |
| API Key | `你的DeepSeek_API密钥` |
| Model | `deepseek-v4-flash` |
| Context Window | 64,000 |
| Max Output Tokens | 8,192 |

**验证结果：**

| 检查项 | 结果 |
|--------|------|
| API Key 有效性 | ✅ 有效（能获取模型列表） |
| 模型 `deepseek-v4-flash` | ✅ 存在（另有 `deepseek-v4-pro`） |
| 聊天接口调用 | ❌ `Insufficient Balance`（余额不足） |

---

## 五、常见错误与调试

### 5.1 余额不足错误

#### 智谱错误

**错误信息：**
```json
{
  "error": {
    "code": "1113",
    "message": "余额不足或无可用资源包,请充值。"
  }
}
```

**原因：**
- API Key 账户没有该模型的资源包或余额

**解决方案：**
1. 登录 [智谱开放平台](https://open.bigmodel.cn) 检查余额
2. 充值或购买对应模型的资源包
3. 或切换到免费模型（如 `glm-4-flash-250414`）

#### DeepSeek 错误

**错误信息：**
```json
{
  "error": {
    "message": "Insufficient Balance",
    "type": "unknown_error",
    "code": "invalid_request_error"
  }
}
```

**解决方案：**
1. 登录 [DeepSeek 平台](https://platform.deepseek.com) 检查余额
2. 充值账户
3. 配置已写入，充值后即可直接使用，无需再改配置

### 5.2 Git 克隆速度慢问题

#### 问题现象

```powershell
git clone https://github.com/liliangxing/Roo-Code.git "D:\workspace\Roo-Code"
```

执行后长时间无响应或下载速度极慢（几 KB/s）。

#### 调试步骤

```powershell
# 1. 检查 GitHub 连接
curl.exe --ssl-no-revoke -s -o NUL -w "HTTP_CODE:%{http_code} TIME:%{time_total}s" `
    "https://github.com/liliangxing/Roo-Code" --connect-timeout 10

# 2. 检查 git 进程状态
$proc = Get-Process -Name "git" -ErrorAction SilentlyContinue
$proc | Select-Object Id,ProcessName,CPU,WorkingSet64

# 3. 检查网络连接
Get-NetTCPConnection -OwningProcess $proc.Id -ErrorAction SilentlyContinue | `
    Select-Object LocalPort,RemoteAddress,RemotePort,State
```

#### 解决方案

**方案 1：使用浅克隆**

```powershell
git clone --depth 1 https://github.com/liliangxing/Roo-Code.git "D:\workspace\Roo-Code"
```

**方案 2：增大 HTTP 缓冲区**

```powershell
git -c http.postBuffer=524288000 clone --depth 1 `
    https://github.com/liliangxing/Roo-Code.git "D:\workspace\Roo-Code"
```

**方案 3：下载 ZIP 并初始化（推荐）**

```powershell
# 停止慢速 git 进程
Stop-Process -Name "git" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Remove-Item "D:\workspace\Roo-Code" -Recurse -Force -ErrorAction SilentlyContinue

# 下载 ZIP
curl.exe --ssl-no-revoke -L -o "D:\workspace\Roo-Code-main.zip" `
    "https://codeload.github.com/liliangxing/Roo-Code/zip/refs/heads/main" `
    --connect-timeout 15

# 解压
Expand-Archive -Path "D:\workspace\Roo-Code-main.zip" `
    -DestinationPath "D:\workspace" -Force

# 重命名目录
Rename-Item "D:\workspace\Roo-Code-main" "Roo-Code"

# 初始化为 git 仓库
Set-Location "D:\workspace\Roo-Code"
git init
git config user.email "user@example.com"
git config user.name "User"
git add -A
git commit -m "Initial commit from main branch"
git branch -M main
git remote add origin https://github.com/liliangxing/Roo-Code.git
```

### 5.3 SQLite 写入格式错误

#### 问题现象

写入数据库后，读取发现 JSON 格式错误（缺少双引号）。

#### 错误原因

```powershell
# 错误写法：直接在命令行嵌入 JSON
$json = '{"currentApiConfigName":"zhipu-glm",...}'
$escaped = $json -replace "'","''"
sqlite3 ... "INSERT OR REPLACE ... VALUES ('$escaped');"
```

PowerShell 或 cmd.exe 会解析双引号，导致 JSON 格式被破坏。

#### 解决方案

```powershell
# 正确写法：使用文件 + readfile()
$json | ConvertTo-Json -Depth 10 | Out-File "C:\temp\roo-secret.json" -Encoding UTF8

sqlite3 ... "UPDATE ItemTable SET value = readfile('C:/temp/roo-secret.json') WHERE key = '...';"
```

### 5.4 配置不生效问题

#### 问题现象

配置已写入数据库，但 Roo Code 仍然使用旧配置。

#### 调试步骤

```powershell
# 1. 检查数据库写入是否成功
sqlite3 state.vscdb "SELECT substr(value, 1, 200) FROM ItemTable WHERE key = 'roo_cline_config_api_config';"

sqlite3 state.vscdb "SELECT substr(value, 1, 200) FROM ItemTable WHERE key = 'RooVeterinaryInc.roo-cline';"

# 2. 检查 currentApiConfigName 是否正确
```

#### 解决方案

**重新加载窗口**

1. 按 `Ctrl+Shift+P`
2. 输入 `Developer: Reload Window`
3. 按 `Enter`

**手动选择配置**

如果重载后仍看到旧配置，可以在 Roo Code 面板中手动选择：
1. 打开 Roo Code 面板
2. 点击设置图标
3. 在 Provider 下拉菜单中手动选择配置

---

## 六、命令速查表

### 基本操作

| 操作 | 命令 |
|------|------|
| 检查 sqlite3 | `where sqlite3` 或 `Get-Command sqlite3` |
| 下载 sqlite3 | `curl -L -o sqlite-tools.zip "https://www.sqlite.org/..."` |
| 查看数据库键 | `sqlite3 state.vscdb "SELECT key FROM ItemTable;"` |
| 读取配置 | `sqlite3 state.vscdb "SELECT value FROM ItemTable WHERE key = '...';"` |

### 智谱 API 测试

| 操作 | 命令 |
|------|------|
| 测试 glm-4-flash | `curl -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" -H "Authorization: Bearer KEY" -d @test.json` |
| 查询模型 | 使用智谱开放平台控制台查看 |

### DeepSeek API 测试

| 操作 | 命令 |
|------|------|
| 查询模型列表 | `curl "https://api.deepseek.com/v1/models" -H "Authorization: Bearer KEY"` |
| 测试 chat | `curl -X POST "https://api.deepseek.com/v1/chat/completions" -H "Authorization: Bearer KEY" -d @test.json` |

### Git 操作

| 操作 | 命令 |
|------|------|
| 浅克隆 | `git clone --depth 1 URL` |
| 增大缓冲区 | `git -c http.postBuffer=524288000 clone URL` |
| 下载 ZIP | `curl -L -o file.zip "https://codeload.github.com/..."` |

---

## 七、配置文件参考

### Roo Code 配置文件格式

```json
{
  "providerProfiles": {
    "currentApiConfigName": "config-name",
    "apiConfigs": {
      "config-name": {
        "id": "unique-id",
        "apiProvider": "openai",
        "openAiApiKey": "your-api-key",
        "openAiBaseUrl": "https://api.example.com/v1",
        "openAiModelId": "model-name",
        "openAiCustomModelInfo": {
          "maxTokens": 16000,
          "contextWindow": 128000,
          "supportsImages": false,
          "supportsComputerUse": false,
          "supportsPromptCache": false
        },
        "openAiStreamingEnabled": true,
        "rateLimitSeconds": 0,
        "consecutiveMistakeLimit": 6,
        "todoListEnabled": true
      }
    },
    "modeApiConfigs": {
      "code": "config-name",
      "architect": "config-name",
      "ask": "config-name",
      "debug": "config-name"
    },
    "migrations": {
      "rateLimitSecondsMigrated": true,
      "openAiHeadersMigrated": true,
      "consecutiveMistakeLimitMigrated": true,
      "todoListEnabledMigrated": true,
      "claudeCodeLegacySettingsMigrated": true
    }
  },
  "globalSettings": {}
}
```

### 数据库结构

| 键名 | 类型 | 说明 |
|------|------|------|
| `roo_cline_config_api_config` | JSON (Secret) | 存储完整的 provider profiles（含 API Key） |
| `RooVeterinaryInc.roo-cline` | JSON (GlobalState) | 存储扩展全局状态（含配置元数据） |

---

## 附录：重要提示

### 关于余额不足

- **智谱 API**：免费模型（`glm-4-flash-250414`, `glm-4-flash`）通常有限额，付费模型需要充值
- **DeepSeek API**：所有模型都需要充值，API Key 本身有效但需要余额才能调用

### 配置写入位置

1. **`roo-code-settings.json`**：`C:\Users\HI\.catpawai\roo-code-settings.json`（自动导入配置）
2. **SecretStorage**：`state.vscdb` 中的 `roo_cline_config_api_config` 键（实际配置）
3. **GlobalState**：`state.vscdb` 中的 `RooVeterinaryInc.roo-cline` 键（配置元数据）
4. **CatPawAI settings.json**：`C:\Users\HI\AppData\Roaming\CatPawAI\User\settings.json`（自动导入路径）

### 重新加载窗口

配置完成后，**必须**重新加载 CatPawAI 窗口才能让配置生效：
```
Ctrl+Shift+P → Developer: Reload Window
```

---

## 文档历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-07-21 | 初始版本，完整记录智谱 GLM 和 DeepSeek 配置过程 |

---

**文档结束**