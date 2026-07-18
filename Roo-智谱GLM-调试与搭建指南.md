# Roo-Code 驱动智谱 GLM 调试与搭建指南

> 目标：让 Roo Code 这个插件（coding agent）的 headless CLI（命令行模式）能接上智谱 GLM-4-Flash 模型，用自然语言写 Java、自动编译并运行。同时把调试过程中遇到的真实错误和坑全部记录下来，方便你手动复现。
>
> 适用读者：技术一般、命令不熟，想照着一步步操作的人。

## 背景与结论

**Roo Code** 是一个类似 AI 程序员的 VS Code 插件，自带一个独立的命令行工具 `roo`（通过 `@roo-code/cli` 安装）。所谓 **headless 模式**，就是不需要打开 VS Code 界面，直接在终端用 `roo --print "你的需求"` 就能让 AI 干活。

**智谱 GLM-4-Flash** 是智谱 AI 的轻量模型。它走的是 OpenAI 兼容接口，但有两个"怪脾气"：

1. **拒绝把消息内容（content）传成数组**——它只接受字符串，收到数组会静默返回"消息被截断"，不调用任何工具。
2. **拒绝 strict:true 工具模式**下未归一化的 schema。

Roo Code 原版完全不知道这两个怪脾气，结果每一轮都触发"消息被截断"，模型不调用工具，Roo 误以为模型没用工具，反复重试 → 无限循环 `MODEL_NO_TOOLS_USED` → 任务卡死。

本次修复涉及 **4 个文件**，核心思路：新增两个 provider 钩子，**只在 `openai-compatible` 这个 provider 下**把 content 数组拍平成字符串、把 strict 降级为 false。其它 provider（官方 OpenAI、DeepSeek 等）完全不受影响。

最终端到端跑通：自然语言 → 生成 `Hello.java` → `javac` 编译 → `java` 运行 → 输出 `Hello Roo from Zhipu`。

最终发布：`https://github.com/liliangxing/Roo-Code/releases/tag/v3.53.0-zhipu-fix`

---

## 整体流程图

![Roo Code 智谱调试全流程](images/roo-zhipu/01-flow.png)

---

## 第一部分：环境准备

### 1.1 需要的工具

| 工具 | 作用 | 怎么安装 |
|------|------|----------|
| `git` | 从 GitHub 下载代码 | 一般都自带，没有的话 `apt install git` |
| `node` (v20+) | 运行 Roo CLI | 官网安装，或 `nvm install 20` |
| `pnpm` | Roo 用 pnpm 管理依赖（不是 npm） | `npm install -g pnpm` |
| `gh` (GitHub CLI) | 发布 Release 用 | 见 https://cli.github.com/ |
| Java JDK | 编译运行 Java 示例 | `apt install default-jdk` |

> **为什么用 pnpm 而不是 npm？** Roo Code 是一个 monorepo（多个包在一个仓库里），用 turbo + pnpm 管理。用 `npm install` 会装错依赖结构，后续 `turbo build` 会失败。

### 1.2 验证环境

```bash
node -v          # 预期 v20+（实际 v22 也行）
pnpm -v          # 预期 10+
git --version
java -version    # 预期能跑
```

> **避坑**：如果 `pnpm` 命令找不到，先跑 `npm install -g pnpm`。Roo 不认 npm。

---

## 第二部分：下载代码

### 2.1 克隆 fork 仓库

```bash
mkdir -p /workspace/forks
cd /workspace/forks

git clone https://github.com/liliangxing/Roo-Code.git
cd Roo-Code

# 切到修复所在的分支
git checkout debug-zhipu-java-demo
```

### 2.2 查看提交历史

```bash
git log --oneline -6
```

你会看到：

```
2d063c4 docs: correct Zhipu OpenAI-compatible base URL to api/paas/v4
6fd7168 feat: register 'openai-compatible' as a canonical provider
3257f67 fix: make Roo CLI work with OpenAI-compatible providers (Zhipu/glm)
91f09b9 debug: 智谱 GLM 驱动的自然语言 Java 开发闭环演示
b867ec9 Remove roocode.com web app (#12375)
```

三个关键提交：
- `3257f67`：核心修复（改了 3 个文件）
- `6fd7168`：注册 provider（改了 1 个文件，让类型检查通过）
- `2d063c4`：端点更正文档

> **说明**：如果你要自己从零改，可以在 `b867ec9`（上游原始状态）基础上，照着本指南第四部分手动改这 4 个文件。

---

## 第三部分：安装依赖

### 3.1 执行 pnpm install

```bash
cd /workspace/forks/Roo-Code
pnpm install
```

这一步会下载所有依赖（很多包，耐心等几分钟）。成功后没有报错即可。

### 3.2 检查项目结构

```bash
ls -la
```

重点关注：
- `src/`：主插件代码（修复在这里）
- `src/api/providers/`：各模型 provider 的实现
- `src/api/index.ts`：provider 路由（选择用哪个 handler）
- `packages/types/src/provider-settings.ts`：provider 注册表
- `apps/cli/`：命令行入口
- `src/dist/extension.js`：构建后的打包文件（CLI 实际加载的）

---

## 第四部分：理解修复（重点，4 个文件）

![修改的 4 个文件](images/roo-zhipu/03-files-modified.png)

### 根因图解

![根因与修复](images/roo-zhipu/02-root-cause.png)

### 4.1 文件一：`src/api/providers/base-provider.ts`（新增两个钩子）

这个文件是所有 provider 的父类。我们在里面加两个方法，**默认返回 true**（表示"支持"），让子类可以重写。

```ts
// 默认：支持 strict 工具模式
protected supportsStrictTools(): boolean {
    return true
}

// 默认：支持数组 content
protected supportsContentArray(): boolean {
    return true
}
```

然后在 `convertToolsForOpenAI` 方法里用 `supportsStrictTools()` 判断：

```ts
protected convertToolsForOpenAI(tools: any[] | undefined): any[] | undefined {
    if (!tools) return undefined
    const supportsStrict = this.supportsStrictTools()

    return tools.map((tool) => {
        if (tool.type !== "function") return tool

        // 不支持 strict 的 provider：去掉 strict，但仍然归一化 schema
        if (!supportsStrict) {
            return {
                ...tool,
                function: {
                    ...tool.function,
                    strict: false,
                    parameters: this.convertToolSchemaForOpenAI(tool.function.parameters),
                },
            }
        }
        // 支持 strict 的走原逻辑
        return { ...tool, function: { ...tool.function, strict: !isMcp, ... } }
    })
}
```

> **为什么这么做？** 因为 strict:true 是 OpenAI 官方的功能，很多兼容端点（包括智谱）不认。但默认设成 true，是为了不破坏官方 OpenAI 的行为。子类按需重写。

### 4.2 文件二：`src/api/providers/openai.ts`（重写钩子 + 拍平 content）

这是核心修复。在 `OpenAiHandler` 类里重写两个钩子，**只对 `openai-compatible` 降级**：

```ts
// 只有 openai-compatible 才降级；官方 openai 不受影响
protected override supportsStrictTools(): boolean {
    return this.options.apiProvider !== "openai-compatible"
}

protected override supportsContentArray(): boolean {
    return this.options.apiProvider !== "openai-compatible"
}
```

再加一个把 content 数组拍平成字符串的方法：

```ts
private flattenContentArrays(messages: any[]): any[] {
    // 如果支持数组，直接返回
    if (this.supportsContentArray()) return messages

    // 不支持数组：把纯文本数组拍平成字符串
    return messages.map((msg) => {
        if (msg && Array.isArray(msg.content)
            && msg.content.every((p: any) => p && p.type === "text")) {
            return { ...msg, content: msg.content.map((p: any) => p.text).join("\n\n") }
        }
        return msg   // 含图片的数组不动（保留多模态）
    })
}
```

然后在 `createMessage` 方法的**两条路径**（流式 streaming 和非流式）里，组装完消息后各调用一次：

```ts
convertedMessages = this.flattenContentArrays(convertedMessages)
```

> **为什么拍平？** 智谱 GLM 只接受 content 为字符串。Roo 的 `convertToOpenAiMessages()` 永远把 user 消息拼成数组 `[{type:"text", text:"..."}]`。不拍平，GLM 就静默返回"消息被截断"，不调用工具。
>
> **为什么含图片的不拍平？** 图片必须用数组结构传，拍平会丢图。所以只拍平"全是文本块"的数组。

### 4.3 文件三：`src/api/index.ts`（补 provider 路由）

原来的 `buildApiHandler()` 函数里有个 switch，**没有 `openai-compatible` 分支**。没有匹配的 case 会落到 `default`，用了 Anthropic 的 handler，鉴权直接失败。

```ts
switch (apiProvider) {
    case "openai":
        return new OpenAiHandler({ ...options, apiProvider })
    case "openai-compatible":          // 新增
        return new OpenAiHandler({ ...options, apiProvider })
    // ...其它 case
}
```

> **为什么透传 `apiProvider`？** 因为 `ApiHandlerOptions` 原本把 `apiProvider` 排除掉了（`Omit<ProviderSettings, "apiProvider">`）。handler 拿不到自己的 provider 名，就没法做 `apiProvider !== "openai-compatible"` 的判断。所以我们把它加回来，在构造 handler 时透传进去。
>
> 配套修改 `src/shared/api.ts` 里的 `ApiHandlerOptions` 类型：
> ```ts
> export type ApiHandlerOptions = Omit<ProviderSettings, "apiProvider"> & {
>     apiProvider?: ProviderSettings["apiProvider"]   // 新增可选字段
>     // ...
> }
> ```

### 4.4 文件四：`packages/types/src/provider-settings.ts`（注册 provider）

这个文件是 provider 的"注册表"。如果不在这里登记 `openai-compatible`，TypeScript 类型检查会报错：`'openai-compatible' is not assignable to ProviderName`。

需要改三处：

```ts
// 1. providerNames 数组里加一行
export const providerNames = [
    "anthropic",
    "openai",
    "openai-compatible",    // 新增
    // ...
] as const

// 2. modelIdKeysByProvider 里加映射
export const modelIdKeysByProvider = {
    // ...
    "openai-compatible": "openAiModelId",    // 新增
} as const

// 3. MODELS_BY_PROVIDER 里加条目
export const MODELS_BY_PROVIDER = {
    // ...
    "openai-compatible": { id: "openai-compatible", label: "OpenAI Compatible", models: [] },  // 新增
}
```

> **为什么必须改这个文件？** Roo 用 Zod 做类型校验，`ProviderName` 是从 `providerNames` 数组派生的联合类型。不登记的话，`apiProvider = "openai-compatible"` 类型不合法。而且 git push 前有个 husky 钩子会跑 `turbo check-types`（跨 13 个包做 TypeScript 检查），类型不对会拒绝推送。

---

## 第五部分：重建 extension bundle

改完代码后，必须重新构建 `src/dist/extension.js`，因为 CLI 实际加载的是这个打包文件，不是源码。

### 5.1 用 esbuild 重建

```bash
cd /workspace/forks/Roo-Code/src
node esbuild.mjs
```

### 5.2 成功标志

最后几行：

```
[copyWasms] Copied tree-sitter.wasm to .../dist
[copyWasms] Copied 35 tree-sitter language wasms to .../dist
[copyWasms] Copied 4 esbuild-wasm files to .../dist
[copyLocales] Copied 108 locale files to .../dist/i18n/locales
esbuild exit=0
```

### 5.3 验证修复进了 bundle

```bash
# 检查 flattenContentArrays 在 bundle 里
grep -c "flattenContentArrays" src/dist/extension.js
# 预期：3

# 检查 openai-compatible 在 bundle 里
grep -c "openai-compatible" src/dist/extension.js
# 预期：39（很多引用）
```

> **为什么要检查？** 有时候你改了源码但忘了 rebuild，CLI 加载的还是旧 bundle。grep 确认一下修复确实进了打包文件。

---

## 第六部分：类型检查

### 6.1 运行 check-types

```bash
cd /workspace/forks/Roo-Code
pnpm check-types
```

### 6.2 成功标志

```
Tasks:    10 successful, 10 total
Cached:   10 cached, 10 total
```

### 6.3 如果失败

| 错误 | 原因 | 解决 |
|------|------|------|
| `'openai-compatible' is not assignable to ProviderName` | 没在 provider-settings.ts 注册 | 照第四部分 4.4 改 |
| `Property 'apiProvider' does not exist on type 'ApiHandlerOptions'` | 没改 shared/api.ts | 加上 `apiProvider?:` 字段 |
| 某个包 `Exited with code 1` | 代码语法错误 | 检查括号、引号 |

> **避坑**：check-types 会跨 13 个包检查，一个错就全挂。报错信息会告诉你哪个包出错，照着改。

---

## 第七部分：提交并推送

### 7.1 暂存修改

```bash
cd /workspace/forks/Roo-Code
git add src/api/providers/base-provider.ts
git add src/api/providers/openai.ts
git add src/api/index.ts
git add src/shared/api.ts
git add packages/types/src/provider-settings.ts
git add src/dist/extension.js
```

### 7.2 提交

```bash
git commit -m "fix: make Roo CLI work with OpenAI-compatible providers (Zhipu/glm)"
```

### 7.3 推送

```bash
git push "https://x-access-token:YOUR_GITHUB_PAT@github.com/liliangxing/Roo-Code.git" debug-zhipu-java-demo
```

> **避坑 1**：不要直接 `git push origin`，GitHub 不接受密码。URL 里要带 `x-access-token:<PAT>`。
>
> **避坑 2**：推送时 husky 会自动跑 `turbo check-types`（pre-push 钩子）。如果类型检查没过，push 会被拒绝。看到 `Tasks: 10 successful` 才会继续推。

---

## 第八部分：打包 vsix

### 8.1 构建

```bash
cd /workspace/forks/Roo-Code
pnpm build
```

成功标志：

```
Tasks:    5 successful, 5 total
```

### 8.2 打包

```bash
cd /workspace/forks/Roo-Code/src
pnpm -F roo-cline exec vsce package --no-dependencies --out "../bin/roo-cline-3.53.0-zhipu-fix.vsix"
```

> **为什么用 `pnpm -F roo-cline exec vsce`？** Roo 是 monorepo，`roo-cline` 是主插件包。`-F` 表示"在这个包里执行"。`vsce` 是 VS Code 插件打包工具。
>
> `--out` 指定输出文件名，带 `-zhipu-fix` 后缀，和上游 `roo-cline-3.53.0.vsix` 区分。

### 8.3 成功输出

```
DONE  Packaged: ../bin/roo-cline-3.53.0-zhipu-fix.vsix (1740 files, 29.41 MB)
```

### 8.4 验证包里含修复

```bash
# vsix 里的 extension.js 在 extension/dist/ 路径下
unzip -p bin/roo-cline-3.53.0-zhipu-fix.vsix extension/dist/extension.js | grep -c "flattenContentArrays"
# 预期：2

unzip -p bin/roo-cline-3.53.0-zhipu-fix.vsix extension/dist/extension.js | grep -c "openai-compatible"
# 预期：12
```

> **为什么路径是 `extension/dist/extension.js`？** vsce 打包时会把 `src/` 重命名为 `extension/`。所以包内路径和源码路径不同。

---

## 第九部分：发布到 GitHub Release

### 9.1 登录 gh

```bash
export GH_TOKEN="YOUR_GITHUB_PAT"
echo "$GH_TOKEN" | gh auth login --with-token
```

### 9.2 创建 Release 并上传

```bash
cd /workspace/forks/Roo-Code

gh release create v3.53.0-zhipu-fix \
  --repo liliangxing/Roo-Code \
  --title "Roo Code 3.53.0 — 智谱 GLM / OpenAI 兼容修复版" \
  --target debug-zhipu-java-demo \
  bin/roo-cline-3.53.0-zhipu-fix.vsix
```

### 9.3 如果要替换已有资产

```bash
gh release delete-asset v3.53.0-zhipu-fix roo-cline-3.53.0.vsix --repo liliangxing/Roo-Code --yes
gh release upload v3.53.0-zhipu-fix bin/roo-cline-3.53.0-zhipu-fix.vsix --repo liliangxing/Roo-Code
```

---

## 第十部分：用 Roo CLI 驱动智谱 GLM 实跑

### 10.1 设置环境变量

```bash
export ZHIPU_API_KEY="你的智谱 API Key"
```

### 10.2 准备 prompt 文件

```bash
cat > /tmp/prompt.txt << 'EOF'
用 Java 写一个程序：创建 Hello.java 打印 "Hello Roo from Zhipu"；
用 execute_command 执行 javac Hello.java 编译，再 java Hello 运行；
确认输出 "Hello Roo from Zhipu"，然后调用 attempt_completion 结束任务。
不要用 newTask 委派子任务。
EOF
```

> **为什么 prompt 里要写"不要用 newTask 委派"？** GLM 偶尔会用 `newTask` 工具把任务委派给子智能体，但子任务会回退到默认的 OpenRouter（没 key）导致卡住。这是 Roo CLI 的既有行为，和我们的修复无关。在 prompt 里明确禁止即可。

### 10.3 执行 CLI 命令

```bash
cd /workspace/forks/Roo-Code
node_modules/.bin/tsx apps/cli/src/index.ts --print \
  --provider openai-compatible --api-key "$ZHIPU_API_KEY" \
  --base-url "https://open.bigmodel.cn/api/paas/v4/" \
  --model glm-4-flash-250414 --mode code --oneshot --ephemeral \
  --consecutive-mistake-limit 6 \
  -w roo-java-demo --prompt-file /tmp/prompt.txt
```

### 10.4 命令拆解

![CLI 命令拆解](images/roo-zhipu/06-command-anatomy.png)

| 参数 | 含义 |
|------|------|
| `tsx apps/cli/src/index.ts` | 用 tsx 直接跑 TypeScript 源码（不用先编译） |
| `--print` | 打印模式（headless，不开 UI） |
| `--provider openai-compatible` | 用 OpenAI 兼容 provider |
| `--api-key $ZHIPU_API_KEY` | 智谱 API Key |
| `--base-url` | 智谱端点（必须是 `api/paas/v4`，不是 `api/compat`） |
| `--model glm-4-flash-250414` | 模型名 |
| `--mode code` | 代码模式（适合写代码） |
| `--oneshot` | 单次任务，不追问 |
| `--ephemeral` | 不落盘历史 |
| `--consecutive-mistake-limit 6` | 连续错误上限 6 次，防止无限空转 |
| `-w roo-java-demo` | 工作目录 |
| `--prompt-file` | prompt 文件 |

### 10.5 预期运行过程

```
[Tool Request] newFileCreated   path: Hello.java
[command request]               Command: javac Hello.java
[command request]               Command: java Hello
[command output]                Hello Roo from Zhipu
[assistant] I've completed the task …
[task complete]
MODEL_NO_TOOLS_USED 出现次数 = 0
```

---

## 第十一部分：验证产物

### 11.1 查看生成的文件

```bash
ls -la roo-java-demo/
```

预期看到：

```
Hello.java    (125 B)
Hello.class   (424 B)
```

### 11.2 手动验证

```bash
cd roo-java-demo
cat Hello.java
# 看到 public class Hello { ... System.out.println("Hello Roo from Zhipu"); }

javac Hello.java
java Hello
# 输出：Hello Roo from Zhipu
```

### 11.3 Hello.java 内容

```java
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello Roo from Zhipu");
    }
}
```

> **和 Cline 的区别**：Roo 生成的类名没有带路径问题（比 Cline 表现好一点）。但如果偶尔遇到，照 Cline 指南里的方法，手动把类名改成 `public class Hello` 即可。

---

## 第十二部分：调试排查命令速查表

![调试工具箱](images/roo-zhipu/05-debug-toolkit.png)

### 12.1 确认修复在源码里

```bash
grep -c "flattenContentArrays" src/api/providers/openai.ts
# 预期：3

grep -c "supportsContentArray" src/api/providers/base-provider.ts
# 预期：1

grep -n "openai-compatible" src/api/index.ts
# 预期：看到 case "openai-compatible":

grep -n "openai-compatible" packages/types/src/provider-settings.ts
# 预期：看到三处（providerNames / modelIdKeysByProvider / MODELS_BY_PROVIDER）
```

### 12.2 确认修复在 dist bundle 里

```bash
grep -c "flattenContentArrays" src/dist/extension.js
# 预期：3

grep -c "openai-compatible" src/dist/extension.js
# 预期：39
```

### 12.3 确认修复在 vsix 里

```bash
unzip -p bin/roo-cline-3.53.0-zhipu-fix.vsix extension/dist/extension.js | grep -c "flattenContentArrays"
# 预期：2
```

### 12.4 检查 pre-push 钩子结果

```bash
git push 2>&1 | grep -E "Tasks:|check-types"
# 预期：Tasks: 10 successful, 10 total
```

### 12.5 用 curl 测试智谱端点

```bash
curl -X POST https://open.bigmodel.cn/api/paas/v4/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ZHIPU_API_KEY" \
  -d '{"model":"glm-4-flash-250414","messages":[{"role":"user","content":"hello"}]}'
```

- 返回 `{choices:[...]}` → API Key 和端点 OK
- 返回 `401` → Key 错了
- 返回 `404` → 端点错了（检查是不是用了 `api/compat`）

### 12.6 dump 请求体排查（进阶）

如果模型完全没反应，可以在 `openai.ts` 的 `createMessage` 里临时加一行，把请求体 dump 出来：

```ts
import { writeFileSync } from "fs"
// 在发请求前
writeFileSync("/tmp/roo_req.json", JSON.stringify(requestBody, null, 2))
```

然后用独立脚本回放，逐个字段测试哪个导致问题：

```bash
node replay.js   # 自己写的回放脚本，逐字段 bisect
```

> **这是我实际用的排查手法**：先 dump 真实请求，再用独立 Node 脚本逐步删减字段，最终定位是 content 数组（不是 strict）导致的。

---

## 第十三部分：避坑清单（必须看）

![避坑清单](images/roo-zhipu/04-pitfalls.png)

### 坑 1：MODEL_NO_TOOLS_USED 无限循环

```
[MODEL_NO_TOOLS_USED]
model: "It seems like your message got cut off"
```

**原因**：智谱 GLM 拒绝 content 数组，静默返回非工具回复。

**解决**：确认 `flattenContentArrays()` 被调用，且 `apiProvider` 设为 `openai-compatible`。

### 坑 2：`'openai-compatible' is not assignable to ProviderName`

**原因**：没在 `packages/types/src/provider-settings.ts` 注册 provider。

**解决**：照第四部分 4.4，加三处注册。

### 坑 3：端点用错 `api/compat`

```
返回：{"code":500,"msg":"404 NOT_FOUND","success":false}
```

**原因**：`api/compat` 不是智谱的真实端点（实测和胡编路径返回一样）。

**解决**：用 `https://open.bigmodel.cn/api/paas/v4`。

### 坑 4：git push 认证失败

```
remote: Invalid username or password.
```

**解决**：URL 里带 `x-access-token:<PAT>`。

### 坑 5：newTask 委派导致子任务卡死

**现象**：模型用 `newTask` 委派子任务，子任务回退到 OpenRouter（无 key）→ 401 卡死。

**解决**：在 prompt 里写"不要用 newTask 委派子任务"。这是 Roo CLI 既有行为，非本次修复引入。

---

## 第十四部分：从 GitHub Release 下载安装

### 14.1 下载

```
https://github.com/liliangxing/Roo-Code/releases/tag/v3.53.0-zhipu-fix
```

下载 `roo-cline-3.53.0-zhipu-fix.vsix`。

### 14.2 安装到 VS Code

1. 打开 VS Code
2. Extensions → 右上角 `...` → `Install from VSIX...`
3. 选择下载的 `.vsix` 文件

### 14.3 配置 Roo 使用智谱

1. 打开 Roo 面板
2. Provider 选择 `OpenAI Compatible`
3. 填写：
   - Base URL：`https://open.bigmodel.cn/api/paas/v4`
   - API Key：你的智谱 API Key
   - Model：`glm-4-flash-250414`

---

## 第十五部分：Roo 和 Cline 的对照

| 维度 | Cline | Roo Code |
|------|-------|----------|
| Headless 命令 | `bun apps/cli/dist/index.js` | `tsx apps/cli/src/index.ts --print` |
| 卡点根因 | 弱模型漏 old_text → 硬抛错 | content 数组被拒 + strict 被拒 + provider 路由缺失 |
| 修复手法 | 抛错改返回纠正提示 | 加钩子按 provider 降级 + content 拍平 |
| 改了几个文件 | 1 个 | 4 个 |
| 类型检查 | 无 pre-push 钩子 | husky pre-push `turbo check-types` |
| 端到端结果 | Calculator 写/编译/运行通过 | Hello 写/编译/运行通过 |

---

## 第十六部分：总结

| 步骤 | 关键命令 | 成功标志 |
|------|----------|----------|
| 克隆 | `git clone ... && git checkout debug-zhipu-java-demo` | 分支切换成功 |
| 装依赖 | `pnpm install` | 无报错 |
| 改代码 | 编辑 4 个文件 | grep 到 flattenContentArrays |
| 重建 bundle | `node esbuild.mjs` | `esbuild exit=0` |
| 类型检查 | `pnpm check-types` | `10 successful` |
| 提交推送 | `git commit` / `git push` | GitHub 分支更新 |
| 打包 | `pnpm -F roo-cline exec vsce package` | 生成 `.vsix` |
| 发布 | `gh release upload` | Release 页面出现 vsix |
| 实跑 | `tsx apps/cli/src/index.ts --print ...` | `[task complete]` |
| 验证 | `javac Hello.java && java Hello` | 输出 `Hello Roo from Zhipu` |

整个过程最核心的一点：**不要让兼容性问题变成全局性的硬失败，而是按 provider 精确降级，只对需要的 provider 做适配，其它 provider 一律不动**。这是 Roo 能接上 GLM-4-Flash 的关键。

---

## 附录：完整命令速查

```bash
# 1. 环境
export ZHIPU_API_KEY="你的智谱Key"

# 2. 下载
git clone https://github.com/liliangxing/Roo-Code.git
cd Roo-Code
git checkout debug-zhipu-java-demo

# 3. 依赖
pnpm install

# 4. 验证修复在源码
grep -c "flattenContentArrays" src/api/providers/openai.ts   # 3
grep -c "supportsContentArray" src/api/providers/base-provider.ts  # 1
grep -n "openai-compatible" src/api/index.ts                 # case 存在
grep -n "openai-compatible" packages/types/src/provider-settings.ts  # 三处

# 5. 重建 bundle
cd src && node esbuild.mjs && cd ..
grep -c "flattenContentArrays" src/dist/extension.js        # 3

# 6. 类型检查
pnpm check-types    # 10 successful

# 7. 提交推送（如需自己改）
git add -A
git commit -m "fix: ..."
git push "https://x-access-token:YOUR_GITHUB_PAT@github.com/liliangxing/Roo-Code.git" debug-zhipu-java-demo

# 8. 打包
pnpm build
cd src
pnpm -F roo-cline exec vsce package --no-dependencies --out "../bin/roo-cline-3.53.0-zhipu-fix.vsix"

# 9. 验证包内修复
unzip -p ../bin/roo-cline-3.53.0-zhipu-fix.vsix extension/dist/extension.js | grep -c "flattenContentArrays"  # 2

# 10. 发布
gh release create v3.53.0-zhipu-fix --repo liliangxing/Roo-Code \
  --target debug-zhipu-java-demo \
  bin/roo-cline-3.53.0-zhipu-fix.vsix

# 11. 实跑
echo '用 Java 写 Hello.java 打印 "Hello Roo from Zhipu"，javac 编译后 java 运行，完成后调用 attempt_completion。不要用 newTask 委派。' > /tmp/prompt.txt

node_modules/.bin/tsx apps/cli/src/index.ts --print \
  --provider openai-compatible --api-key "$ZHIPU_API_KEY" \
  --base-url "https://open.bigmodel.cn/api/paas/v4/" \
  --model glm-4-flash-250414 --mode code --oneshot --ephemeral \
  --consecutive-mistake-limit 6 \
  -w roo-java-demo --prompt-file /tmp/prompt.txt

# 12. 验证
cd roo-java-demo
javac Hello.java
java Hello
# => Hello Roo from Zhipu
```

---

> 版本：2026-07-18
> 基于 Roo Code fork `liliangxing/Roo-Code` 分支 `debug-zhipu-java-demo`，提交 `3257f67` + `6fd7168` + `2d063c4` 整理。
