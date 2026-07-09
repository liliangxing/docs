# Qwen2.5-0.5B 纯 CPU 本地部署指南

> 适用场景：低配 Linux 服务器（8GB 内存 / 2 核 CPU），用最轻量的模型跑本地对话

---

## 一、为什么是 0.5B

这个文档是 [Qwen3-1.7B 部署指南](./Qwen3-1.7B-本地CPU部署指南.md) 的姊妹篇。在同一台 8GB 内存 / 2 核 CPU 的机器上，先尝试了 1.7B 模型，结论是：

| 模型 | 大小 | 加载时间 | 推理速度（首次） | 长时稳定性 |
|------|------|---------|--------------|-----------|
| Qwen3-1.7B | 1.1GB | 7-8 分钟 | ~7.6 tok/s | 差（Swap 颠簸后掉到 0.03 tok/s） |
| Qwen2.5-0.5B | 468MB | 2 分钟 | ~0.3 tok/s（首次）→ 3-8 tok/s（缓存热后） | 可持续运行 |

**关键结论**：0.5B 模型虽然初始推理慢，但 KV 缓存预热后生成速度可以达到 3-8 tok/s，对 8GB 内存的机器来说是不用升级硬件的唯一选择。

---

## 二、前提条件

以下步骤假设你已经：
1. 照着 [Qwen3-1.7B 部署指南](./Qwen3-1.7B-本地CPU部署指南.md) 完成了前三步（swapfile、llama.cpp 编译、依赖安装）
2. `/opt/llama.cpp/build/bin/llama-server` 已编译好
3. `/swapfile`（2GB）已创建并启用
4. 想换成更小的模型来提升稳定性

如果你是从零开始，推荐先看 1.7B 指南的第四到七节（编译 llama.cpp），再回到本文下载模型。

---

## 三、下载模型

### 3.1 模型选择

| 信息 | 值 |
|------|-----|
| 模型名 | Qwen2.5-0.5B-Instruct |
| 文件名 | `qwen2.5-0.5b-instruct-q4_k_m.gguf` |
| 大小 | 468MB |
| 量化格式 | Q4_K_M（4bit） |
| 官方仓库 | `Qwen/Qwen2.5-0.5B-Instruct-GGUF`（ModelScope） |

> 注意文件名是**全小写**的！这和 unsloth 仓库里 1.7B 的命名习惯不同（unsloth 用大写 Q 开头）。

### 3.2 尝试一：ModelScope CLI 下载（失败）

先用和 1.7B 一样的方式试：

```bash
modelscope download \
  --model Qwen/Qwen2.5-0.5B-Instruct-GGUF \
  --include "*Q4_K_M.gguf*" \
  --local_dir /opt/models
```

**结果**：
```
No files to download
Snapshot ready at /opt/models
```

**排查**：`--include "*Q4_K_M.gguf*"` 没匹配到任何文件。原因是文件名是**小写**的 `q4_k_m`，ModelScope 的通配符**区分大小写**。改成小写模式重试：

```bash
modelscope download \
  --model Qwen/Qwen2.5-0.5B-Instruct-GGUF \
  --include "*q4_k_m.gguf*" \
  --local_dir /opt/models
```

**结果**：这次匹配到了，但它开始**下载所有文件**（含 fp16、q2_k、q3_k_m 等无关的），因为 `--include "*"` 会拉整个目录树。最终超时，下载了一堆 `.incomplete` 残留文件。

**教训**：ModelScope 的 include 参数在大仓库里不太好用。直接改用 curl 下载单文件更可控。

### 3.3 正确做法：curl 直链下载

```bash
# 先清理之前的残留文件
rm -f /opt/models/qwen2.5*.gguf*

# 用 ModelScope 的文件 API 直链下载（单个文件，稳定可控）
curl -L -o /opt/models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  "https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/repo?Revision=master&FilePath=qwen2.5-0.5b-instruct-q4_k_m.gguf"

# 确认下载成功
ls -lh /opt/models/qwen2.5-0.5b-instruct-q4_k_m.gguf
```

**实际输出**：
```
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  468M  100  468M    0     0  2892k      0  0:02:45  0:02:45 --:--:-- 2754k

-rw-r--r-- 1 root root 469M Jul  9 04:30 qwen2.5-0.5b-instruct-q4_k_m.gguf
```

468MB，约 2.9MB/s 下载速度，耗时约 2 分 45 秒。

**URL 解析**：`https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/repo?Revision=master&FilePath=qwen2.5-0.5b-instruct-q4_k_m.gguf` 这条 URL 的各部分含义：
- `Qwen/Qwen2.5-0.5B-Instruct-GGUF` — 仓库名
- `Revision=master` — 分支
- `FilePath=qwen2.5-0.5b-instruct-q4_k_m.gguf` — 文件路径（注意必须和仓库里的文件名完全一致，包括大小写）

如果以后换其他变体（如 Q5_K_M），只需要改 FilePath 参数即可。

---

## 四、启动服务

```bash
/opt/llama.cpp/build/bin/llama-server \
  -m /opt/models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  -t 2 \
  -ngl 0 \
  -c 1024 \
  --mmap \
  --host 0.0.0.0 \
  --port 8080 \
  --temp 0.6 \
  --top-p 0.95 \
  --top-k 20 \
  --repeat-penalty 1.05 \
  --jinja
```

**参数比 1.7B 版本唯一的变化**：`-m` 指向了新模型文件。

**启动日志（重点看加载时间）**：

```
0.00.310 I srv    load_model: loading model 'qwen2.5-0.5b-instruct-q4_k_m.gguf'
0.02.514 W load: control-looking token: 128247 '</s>' was not control-type
2.02.209 I srv    load_model: initializing, n_slots = 4, n_ctx_slot = 1024
2.02.779 I srv  llama_server: model loaded
2.02.779 I srv  llama_server: listening on http://0.0.0.0:8080
```

**对比 1.7B 的加载时间**：
```
7.18.271 I srv  llama_server: model loaded  ← 1.7B 花了 7 分钟
2.02.779 I srv  llama_server: model loaded  ← 0.5B 只花了 2 分钟
```

加载时间从 7 分钟降到 2 分钟，快了约 3.5 倍。模型只有 468MB（1.7B 是 1.1GB），不仅文件小，内存布局计算也轻量得多。

---

## 五、验证推理

```bash
curl -s -X POST "http://127.0.0.1:8080/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-0.5B",
    "messages": [{"role": "user", "content": "用一句话自我介绍"}],
    "max_tokens": 20,
    "temperature": 0.6
  }' | python3 -m json.tool
```

**实际返回**：

```json
{
  "choices": [{
    "message": {
      "content": "我是一个人工智能模型，由阿里云开发和训练的。",
      "role": "assistant"
    }
  }],
  "timings": {
    "prompt_ms": 43337.99,
    "prompt_per_token_ms": 1313.27,
    "predicted_ms": 60791.85,
    "predicted_per_second": 0.33
  }
}
```

**首次调用性能（冷缓存）**：

| 阶段 | 值 | 解读 |
|------|-----|------|
| 提示编码 | 1313 ms/token（0.76 tok/s） | 慢，CPU 上矩阵运算通病 |
| 文本生成 | 3039 ms/token（0.33 tok/s） | 首次极慢，因为内存紧张 |

---

## 六、性能数据：缓存预热后的真实速度

首次调用速度很慢是因为 KV 缓存是空的，且操作系统正在把 llama-server 的页面往 swap 里塞。**多调几次后缓存热了，速度会大幅提升**。

以下是服务器日志记录的连续调用性能：

### 第一次调用（冷启动）
```
prompt eval:    43337 ms / 33 tokens  (1313 ms/token, 0.76 tok/s)
      eval:     60791 ms / 20 tokens  (3039 ms/token, 0.33 tok/s)   ← 极慢
```

### 第二次调用
```
prompt eval:    45118 ms / 30 tokens  (1503 ms/token, 0.66 tok/s)
      eval:     86902 ms / 27 tokens  (3218 ms/token, 0.31 tok/s)   ← 仍然慢，Swap 挤压
```

### 第三次调用（缓存开始热）
```
prompt eval:    32550 ms / 67 tokens  ( 485 ms/token, 2.06 tok/s)
      eval:     11984 ms / 106 tokens ( 113 ms/token, 8.85 tok/s)   ← 质的飞跃！
```

### 第四次调用（缓存全热）
```
prompt eval:    34390 ms / 18 tokens  (1910 ms/token, 0.52 tok/s)
      eval:     62020 ms / 234 tokens ( 265 ms/token, 3.77 tok/s)   ← 稳定可用
```

**关键发现**：
- 最佳状态：106 token 生成只用了 12 秒，每秒生成 **8.85 个 token**
- 稳定状态：234 token 生成用了 62 秒，每秒 **3.77 个 token**
- 提示编码始终是瓶颈（0.5-2.0 tok/s），但生成速度在缓存热后完全可用

**为什么速度波动这么大？**

因为这台机器只有 8GB 内存，opencode 开发环境本身占用了约 400MB，剩余内存刚好够加载模型但不够放 KV 缓存。系统和 llama.cpp 在争抢内存，有时命中 swap 就慢，不命中就快。高配机子（16GB+ 内存）不会有这个问题。

---

## 七、完整命令速查

假设已安装 cmake/build-essential 和 modelscope，llama.cpp 已编译好：

```bash
# ===== 1. 创建 swapfile（8GB 以下必做） =====
fallocate -l 2G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile

# ===== 2. 下载模型（curl 直链） =====
curl -L -o /opt/models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  "https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/repo?Revision=master&FilePath=qwen2.5-0.5b-instruct-q4_k_m.gguf"

# 确认文件大小
ls -lh /opt/models/qwen2.5-0.5b-instruct-q4_k_m.gguf

# ===== 3. 启动服务 =====
/opt/llama.cpp/build/bin/llama-server \
  -m /opt/models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  -t $(nproc) -ngl 0 -c 1024 --mmap \
  --host 0.0.0.0 --port 8080 \
  --temp 0.6 --top-p 0.95 --top-k 20 \
  --repeat-penalty 1.05 --jinja

# ===== 4. 验证 =====
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen2.5-0.5B","messages":[{"role":"user","content":"你好"}],"max_tokens":50}'
```

---

## 八、错误排查

### 错误 1：modelscope download 说 "No files to download"

**现象**：
```
No files to download for Qwen/Qwen2.5-0.5B-Instruct-GGUF@master
Snapshot ready at /opt/models
```

**原因**：`--include "*Q4_K_M.gguf*"` 没有匹配到文件。该仓库的文件名是全小写的 `q4_k_m`，而通配符区分大小写。

**解决**：改用 `--include "*q4_k_m.gguf*"`（全小写），或者直接用 curl 下载单文件。

### 错误 2：ModelScope 把所有文件都下载了

**现象**：`--include "*"` 或宽松的通配符会把 fp16、q2、q3 等所有变体都下载下来。

**解决**：不要用 modelscope CLI。改用 curl 请求 ModelScope 的文件 API：

```bash
curl -L -o 文件名 \
  "https://modelscope.cn/api/v1/models/仓库名/repo?Revision=master&FilePath=文件路径"
```

### 错误 3：首次调用极慢（0.3 tok/s）

**现象**：启动后第一次 API 调用要等很久才有回复。

**原因**：KV 缓存是空的，操作系统在内存不足时会把 llama-server 的部分页面换出到 swap。

**解决**：这不是错误。多调用几次（3-4 次），缓存预热后速度会提升到 3-8 tok/s。如果始终很慢，考虑：
1. 降低上下文 `-c 512`
2. 关闭其他进程腾内存
3. 升级到 16GB 内存（最佳方案）

### 错误 4：服务跑久了被 521

**现象**：Cloudflare 返回 521 错误。

**原因**：llama-server 还在运行，但遇到极长的推理任务（如图中模型在 0.03 tok/s 下推了几百个 token），网络代理认为服务器无响应。

**排查命令**：
```bash
# 检查进程是否还活着
ps aux | grep llama

# 检查端口是否还在监听
python3 -c "import socket; s=socket.socket(); s.settimeout(3); r=s.connect_ex(('127.0.0.1',8080)); print('OK' if r==0 else 'DEAD')"

# 查看最新日志
tail -20 /tmp/terminal_xxx.log

# 查看内存和 Swap 使用
free -h
```

**解决**：重启服务。如果频繁出现，降低 `-c` 参数到 512。

---

## 九、两种模型的适用场景

| 场景 | 推荐模型 |
|------|---------|
| 8GB 内存开发机，偶尔需要 LLM 辅助 | Qwen2.5-0.5B（本文） |
| 16GB+ 内存，需要更聪明的回复 | Qwen3-1.7B（姊妹篇） |
| 32GB+ 内存 / 有 GPU | 建议直接用更大模型 |

0.5B 模型的回答质量不如 1.7B，但它在 8GB 内存机器上可以持续稳定运行，不会因为 Swap 颠簸而崩溃。
