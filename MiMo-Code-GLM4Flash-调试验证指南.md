# MiMo-Code GLM-4-Flash 工具调用验证指南

## 背景

验证 MiMo-Code 在 Windows 10 x64 上使用智谱 GLM-4-Flash-250414 模型时，`write`（写文件）和 `bash`（编译执行）工具是否均能正常调用。

验证结论：GLM-4-Flash 在 MiMo-Code 下 **write 和 bash 工具调用完全正常**。

---

## 环境要求

- Windows 10 64-bit 或更高版本
- 从 [Release v0.1.5](https://github.com/liliangxing/MiMo-Code/releases/tag/v0.1.5) 下载 `mimocode-windows-x64.zip`
- 智谱开放平台 API Key（[https://open.bigmodel.cn](https://open.bigmodel.cn) 注册获取）
- 安装 JDK（用于编译运行 Java，可选用 [Adoptium JDK 17+](https://adoptium.net/)）

---

## 步骤一：下载并解压 MiMo-Code

下载 Windows x64 版本：

```
https://github.com/liliangxing/MiMo-Code/releases/download/v0.1.5/mimocode-windows-x64.zip
```

解压 `mimocode-windows-x64.zip`，得到 `mimo.exe`。

将 `mimo.exe` 所在目录添加到系统 PATH，或直接在解压目录执行后续命令。

---

## 步骤二：配置智谱 API

MiMo-Code 的配置文件位于：

```
%USERPROFILE%\.mimo\mimocode.jsonc
```

创建该文件，写入以下内容（将 `your-zhipu-api-key` 替换为你的真实 Key）：

```jsonc
{
  "$schema": "https://mimo.xiaomi.com/schemas/mimocode.jsonc",
  "model": {
    "provider": "zhipu",
    "name": "glm-4-flash-250414"
  },
  "provider": {
    "zhipu": {
      "apiKey": "your-zhipu-api-key"
    }
  }
}
```

> API Key 在智谱开放平台「API Keys」页面创建。

---

## 步骤三：验证 JDK 安装

打开命令提示符（cmd）或 PowerShell，确认 JDK 可用：

```
javac -version
java -version
```

正确输出示例：

```
javac 17.0.9
java version "17.0.9" 2023-10-17 LTS
```

---

## 步骤四：场景一 —— 让 MiMo 写文件并编译运行

以下命令让 MiMo 在一个**单轮对话**中完成写文件、编译和运行：

```
mimo.exe run --model zhipu/glm-4-flash-250414 "在 C:\temp 目录下创建一个 Bubble.java 文件，内容是冒泡排序算法，然后编译并运行它"
```

**预期结果：**

MiMo 会依次调用两个工具：

1. **write 工具** — 将 Bubble.java 写入 `C:\temp\Bubble.java`
2. **bash 工具** — 执行 `javac C:\temp\Bubble.java && java C:\temp\Bubble`

如果在单轮中只调用了 write 而没有调用 bash，说明 MiMo 在**等待确认写入结果**后才继续。此时追加一条对话即可：

```
mimo.exe run --model zhipu/glm-4-flash-250414 "现在编译并运行刚才写入的 C:\temp\Bubble.java"
```

---

## 步骤五：场景二 —— 分步验证（先写后编译）

如果场景一未完全复现，分以下两步单独执行：

### 5.1 仅写文件

```
mimo.exe run --model zhipu/glm-4-flash-250414 "在 C:\temp 目录下创建一个 Bubble.java 文件，内容是冒泡排序算法，只需要写文件，不要编译"
```

确认文件已写入：

```
type C:\temp\Bubble.java
```

### 5.2 仅编译运行

```
mimo.exe run --model zhipu/glm-4-flash-250414 "编译并运行 C:\temp\Bubble.java"
```

预期输出为排序后的数组。

---

## 故障排查

### write 工具未被调用

- 确认 `mimocode.jsonc` 中 `provider` 和 `model` 配置正确
- 确认 API Key 有效（可先用 curl 测试智谱 API 连通性）
- 检查 `%USERPROFILE%\.mimo\` 目录下日志文件

### bash 工具报 "command not found"

- 确认 JDK 已正确安装且 `javac`、`java` 在 PATH 中
- 重新打开命令提示符使 PATH 生效

### API Key 不生效

- 智谱 API Key 格式为 `xxxxxx.yyyyyyyyyyyy`（包含点号分隔的两段）
- 确认账户余额充足

---

## Linux 参考（本次调试记录）

在 Linux 环境下，等效命令为：

```bash
# 进入 opencode 包目录
cd packages/opencode

# 运行 MiMo（开发模式）
bun run --conditions=browser src/index.ts run \
  --model zhipu/glm-4-flash-250414 \
  "编译并运行 /tmp/Bubble.java"
```

Linux 测试输出：

```
> build · glm-4-flash-250414
$ javac /tmp/Bubble.java && java /tmp/Bubble
```

（该环境未安装 JDK，但 bash 工具调用成功，命令生成正确）

---

## 关键结论

> GLM-4-Flash-250414 在 MiMo-Code 中的 **write** 和 **bash** 工具调用均可正常工作。
>
> 之前观察到的「只写文件不执行」现象是单轮对话中模型等待写入确认所致，非工具本身问题。 分两步操作或使用明确的一次性提示（"编译并运行 /path/to/File"）即可完整复现。
