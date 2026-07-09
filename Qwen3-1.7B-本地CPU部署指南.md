# Qwen3-1.7B 纯 CPU 本地部署指南

> 适用场景：无 GPU 的 Linux 服务器，纯 CPU 跑大模型对话

---

## 一、环境要求

| 项目 | 最低要求 | 本文实测环境 |
|------|---------|------------|
| CPU | 2 核 | 2 核 Intel Xeon |
| 内存 | 8GB | 7.8GB |
| 磁盘 | 5GB 可用 | 15GB 可用 |
| Swap | 2GB+ | 2GB（手动创建） |
| GPU | 不需要 | 无 |
| 操作系统 | Linux (Ubuntu/Debian) | Debian 12 |

> *如果你是高配机子（16GB+ 内存、8 核+ CPU），本文所有步骤照样适用，只会更流畅。*

---

## 二、为什么选这个方案

### 2.1 为什么不用 Ollama？

Ollama 自带一套 daemon 进程，本身就要吃掉几百 MB 内存。llama.cpp 是纯 C++ 编译的，没有额外守护进程，内存开销更小。在 8GB 内存的机器上，这几百 MB 可能就是你跑得起来和直接 OOM 的区别。

### 2.2 为什么是 Qwen3-1.7B？

- 1.7B 参数，Q4_K_M 量化后仅 1.1GB，加载到内存后还有余量
- Qwen3 系列中文能力强，支持思考模式（reasoning）
- 9B 及以上模型在 8GB 内存机器上完全跑不起来

### 2.3 为什么是 llama.cpp 而不是其他框架？

- llama.cpp 原生支持 GGUF 格式，CPU 推理优化最好
- 自带 `llama-server`，启动后直接提供 OpenAI 兼容 API
- 自带 Web 聊天界面，零配置开箱即用
- 支持 mmap 按需加载模型，不一次性占满内存

---

## 三、避坑总览（先看这里）

| 坑 | 现象 | 解决 |
|----|------|------|
| hf-mirror 下载被墙 | `SSL_ERROR_SYSCALL` | 改用 ModelScope |
| GitHub 克隆超时 | `timeout` | 用 `ghfast.top` 镜像 |
| 克隆后文件不全 | checkout 失败 | `git checkout -f HEAD` |
| cmake 未安装 | `command not found: cmake` | `apt install cmake build-essential` |
| 编译超时 | 卡住不动 | 只编译需要的目标：`--target llama-server` |
| `--low-vram` 报错 | `invalid argument` | 新版本已废弃，直接去掉 |
| 推理慢得像卡死 | 5 分钟没输出 | 正常，首次提示编码慢，后续生成约 7 tok/s |
| 内存不足 OOM | 进程被杀 | 必须建 swapfile |
| hf-mirror 重定向到 huggingface.co | HTTPS 握手失败 | huggingface.co 被墙，不能用 hf-mirror |

---

## 四、第一步：检查机器资源

首先搞清楚你的机器有多少资源，这会决定后面的参数怎么调。

```bash
# 看磁盘空间
df -h

# 看内存和 Swap
free -h

# 看 CPU 核心数
nproc

# 看有没有 GPU
nvidia-smi 2>/dev/null || echo "没有 GPU"
```

**实际输出（本文环境）：**

```
=== 磁盘 ===
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        20G  4.4G   15G  24% /
=== 内存 ===
               total        used        free      shared  buff/cache   available
Mem:           7.8Gi       7.5Gi       242Mi       768Ki      238Mi       239Mi
Swap:             0B          0B          0B
=== CPU ===
2
=== GPU ===
没有 GPU
```

> *看到没？Swap 是 0！这就是最大的雷。在不加 Swap 的情况下，模型一加载就可能 OOM 被杀。*

---

## 五、第二步：创建 Swapfile（救命步骤）

在内存只有 8GB 的机器上，**必须先建 swapfile**。llama.cpp 虽然用了 mmap 按需加载，但推理时 KV cache 和临时张量仍有内存峰值。Swap 提供兜底保护。

```bash
# 创建 2GB 的 swap 文件
fallocate -l 2G /swapfile

# 设置权限（只有 root 能读写）
chmod 600 /swapfile

# 格式化为 swap
mkswap /swapfile

# 启用 swap
swapon /swapfile

# 确认生效
free -h
```

**实际输出：**

```
Setting up swapspace version 1, size = 2 GiB (2147479552 bytes)
no label, UUID=e3186cfb-bb2f-435e-bf9f-98577cb1f359
               total        used        free      shared  buff/cache   available
Mem:           7.8Gi       7.0Gi       817Mi       768Ki       248Mi       824Mi
Swap:          2.0Gi          0B       2.0Gi
```

> *Swap 一行不再是 0B 了，安全感+1。*

---

## 六、第三步：下载模型

### 6.1 选哪个模型

模型名：**Qwen3-1.7B-Q4_K_M.gguf**

| 字段 | 含义 |
|------|------|
| Qwen3 | 模型系列 |
| 1.7B | 17 亿参数 |
| Q4_K_M | 4-bit 量化，K-quant 方法，Medium 大小 |
| .gguf | llama.cpp 专用格式 |

文件大小约 1.1GB。

### 6.2 下载方式

**重要提示**：不要用 hf-mirror.com！它会重定向到 huggingface.co，而后者的 443 端口在这个环境里被墙了：

```
curl: (35) OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to huggingface.co:443
```

**正确做法：用 ModelScope 下载**

ModelScope 是阿里维护的国内模型仓库，速度稳定且不会被墙。

```bash
# 安装 ModelScope 命令行工具
pip install modelscope

# 下载模型到 /opt/models/ 目录
modelscope download \
  --model unsloth/Qwen3-1.7B-GGUF \
  --include "*Qwen3-1.7B-Q4_K_M.gguf*" \
  --local_dir /opt/models

# 确认文件已下载
ls -lh /opt/models/
```

**实际输出：**

```
Downloading: 100%|██████████| 1/1 [09:01<00:00, 541.51s/file]
Snapshot ready at /opt/models

$ ls -lh /opt/models/
total 1.1G
-rw-r--r-- 1 root root 1.1G Jul  8 14:29 Qwen3-1.7B-Q4_K_M.gguf
```

> *下载了约 9 分钟（2.9 MB/s），文件大小 1.1GB，确认无误。*

### 6.3 备用下载方式

如果你的网络环境 ModelScope 也不行，可以尝试：

```bash
# 方式一：wget 直链（如果 wget 可用）
wget -O /opt/models/Qwen3-1.7B-Q4_K_M.gguf \
  "https://www.modelscope.cn/models/unsloth/Qwen3-1.7B-GGUF/resolve/master/Qwen3-1.7B-Q4_K_M.gguf"

# 方式二：huggingface-cli（仅在海外的机器上用）
pip install huggingface_hub
export HF_ENDPOINT=https://hf-mirror.com   # 国内设镜像
huggingface-cli download unsloth/Qwen3-1.7B-GGUF \
  --include "Qwen3-1.7B-Q4_K_M.gguf" \
  --local_dir /opt/models
```

---

## 七、第四步：编译 llama.cpp

### 7.1 安装编译工具

```bash
apt-get install -y cmake build-essential
```

> *cmake 是 C++ 的构建系统，build-essential 包含 gcc、g++ 等基础编译器。*

### 7.2 克隆源码

GitHub 直连大概率超时，我们走镜像：

```bash
# 用 ghfast.top 镜像克隆（只拉最新版本，--depth 1 省时间）
git clone --depth 1 \
  https://ghfast.top/https://github.com/ggml-org/llama.cpp \
  /opt/llama.cpp
```

**备用镜像地址**（按优先级尝试）：
- `https://ghfast.top/https://github.com/ggml-org/llama.cpp`
- `https://gitclone.com/github.com/ggml-org/llama.cpp`
- `https://hub.fastgit.xyz/ggml-org/llama.cpp`

### 7.3 修复不完整的克隆

**这是个大坑！** 镜像克隆有时文件不全（checkout 失败），表现为 `src/` 目录下只有少数文件。需要手动恢复：

```bash
cd /opt/llama.cpp

# 先看看是不是缺文件
ls src/ | head -5

# 如果只有 CMakeLists.txt 等少数文件，执行恢复
git checkout -f HEAD

# 再次确认（应该看到几十个 .cpp 文件）
ls src/ | head -10
```

**恢复前 vs 恢复后对比：**

```
# 恢复前（只有 1 个文件）：
CMakeLists.txt

# 恢复后（完整的源码）：
CMakeLists.txt
llama-adapter.cpp
llama-adapter.h
llama-arch.cpp
llama-arch.h
llama-batch.cpp
llama-batch.h
llama-chat.cpp
llama-chat.h
llama-context.cpp
```

### 7.4 编译

```bash
cd /opt/llama.cpp
mkdir -p build

# CMake 配置（关掉 BLAS 和 CUDA，纯 CPU 编译）
cmake -S /opt/llama.cpp -B /opt/llama.cpp/build \
  -DGGML_CUDA=OFF

# 只编译我们需要的两个目标（全量编译在 2 核机器上要半小时+）
cmake --build /opt/llama.cpp/build --config Release -j$(nproc) \
  --target llama-cli llama-server
```

**参数说明：**

| 参数 | 含义 | 为什么这样设 |
|------|------|------------|
| `-DGGML_CUDA=OFF` | 不编译 GPU 支持 | 没有显卡，编了白占空间 |
| `--target llama-cli` | 只编译命令行工具 | 用于终端对话测试 |
| `--target llama-server` | 只编译 HTTP 服务 | 提供 Web 界面和 API |
| `-j$(nproc)` | 用全部 CPU 核心并行编译 | 加速编译 |

**编译成功输出：**

```
[100%] Linking CXX executable ../../bin/llama-cli
[100%] Built target llama-cli
[100%] Linking CXX executable ../../bin/llama-server
[100%] Built target llama-server

$ ls -lh /opt/llama.cpp/build/bin/llama-cli /opt/llama.cpp/build/bin/llama-server
-rwxr-xr-x 1 root root 1.2M Jul  8 15:07 llama-cli
-rwxr-xr-x 1 root root  18K Jul  8 15:10 llama-server
```

> *llama-cli 1.2MB、llama-server 18KB（动态链接到共享库），两个都已编译好。*

---

## 八、第五步：先测试模型能不能跑

在正式启动服务前，先用命令行工具快速验证一下。这步可以帮你确认：
1. 模型文件没有损坏
2. 内存够加载模型
3. 推理能正常工作

```bash
/opt/llama.cpp/build/bin/llama-cli \
  -m /opt/models/Qwen3-1.7B-Q4_K_M.gguf \
  -t 2 \
  -ngl 0 \
  -c 512 \
  --mmap \
  --jinja \
  -p "你好" \
  -n 10
```

**参数解释：**

| 参数 | 值 | 为什么 |
|------|----|--------|
| `-m` | 模型路径 | 指向 .gguf 文件 |
| `-t 2` | 2 线程 | 你只有 2 核，多了反而抢资源 |
| `-ngl 0` | 0 层 GPU | 没显卡，全部 CPU 算 |
| `-c 512` | 上下文 512 | 测试用，正式跑可以设 2048 |
| `--mmap` | 内存映射 | **关键参数！** 按需加载模型，不一次占满内存 |
| `--jinja` | 启用 Jinja 模板 | Qwen3 需要这个才能正确渲染对话格式 |
| `-p "你好"` | 提示词 | 模型会从这个输入开始生成 |
| `-n 10` | 最多生成 10 token | 测试而已，不用太多 |

**重要提示**：`--low-vram` 在新版 llama.cpp 中已废弃，不要再加这个参数，否则会报 `invalid argument` 错误。

**实际效果**：在 2 核 CPU 上，模型加载约 2 分钟，生成 10 个 token 可能需要几十秒。这是正常的！因为首次调用需要做大量的 prompt 编码运算。

---

## 九、第六步：启动 llama-server（正式服务）

```bash
/opt/llama.cpp/build/bin/llama-server \
  -m /opt/models/Qwen3-1.7B-Q4_K_M.gguf \
  -t 2 \
  -ngl 0 \
  -c 2048 \
  --mmap \
  --host 0.0.0.0 \
  --port 8080 \
  --temp 0.6 \
  --top-p 0.95 \
  --top-k 20 \
  --repeat-penalty 1.05 \
  --jinja
```

**新增参数说明：**

| 参数 | 含义 | 为什么这样设 |
|------|------|------------|
| `--host 0.0.0.0` | 监听所有网卡 | 允许外部访问，如果只本机用改 `127.0.0.1` |
| `--port 8080` | 服务端口 | 改成你喜欢的 |
| `-c 2048` | 上下文 2048 token | 8GB 内存下 4096 有风险 |
| `--temp 0.6` | 温度 | Qwen3 官方推荐值 |
| `--top-p 0.95` | 核采样 | 同上 |
| `--top-k 20` | Top-K | 同上 |
| `--repeat-penalty 1.05` | 重复惩罚 | 略高于默认值，防止生成内容重复 |

**启动日志（完整）：**

```
warning: no usable GPU found, --gpu-layers option will be ignored
warning: one possible reason is that llama.cpp was compiled without GPU support
warning: consult docs/build.md for compilation instructions
0.00.207.314 I cmn  common_param: common_params_print_info: verbosity = 3
0.00.312.199 I srv    load_model: loading model '/opt/models/Qwen3-1.7B-Q4_K_M.gguf'
0.02.693.559 W load: control-looking token: 128247 '</s>' was not control-type
7.17.843.536 I srv    load_model: initializing, n_slots = 4, n_ctx_slot = 2048, kv_unified = 'true'
7.18.271.326 I srv  llama_server: model loaded
7.18.271.341 I srv  llama_server: listening on http://0.0.0.0:8080
```

> *看到 `model loaded` 和 `listening on http://0.0.0.0:8080` 就表示成功了。但注意加载过程花了 **7 分钟**！在 2 核 CPU 上这是正常的（模型文件 1.1GB，CPU 要计算内存布局和 KV cache）。高配机子这个时间会大幅缩短。*

### 9.1 后台运行

生产环境需要后台运行，用 nohup 或 systemd：

```bash
# 方式一：nohup（简单）
nohup /opt/llama.cpp/build/bin/llama-server \
  -m /opt/models/Qwen3-1.7B-Q4_K_M.gguf \
  -t 2 -ngl 0 -c 2048 --mmap \
  --host 0.0.0.0 --port 8080 \
  --temp 0.6 --top-p 0.95 --top-k 20 \
  --repeat-penalty 1.05 --jinja \
  > /var/log/llama-server.log 2>&1 &

# 方式二：systemd（推荐生产环境）
# 创建 /etc/systemd/system/llama-server.service
```

---

## 十、第七步：验证服务

### 10.1 直接访问 Web 界面

打开浏览器访问 `http://你的IP:8080`，会看到一个聊天界面，直接在浏览器里和模型对话。

### 10.2 用 curl 测试 API

```bash
curl -s -X POST "http://127.0.0.1:8080/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen3-1.7B",
    "messages": [{"role": "user", "content": "用一句话介绍你自己"}],
    "max_tokens": 30,
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20
  }' | python3 -m json.tool
```

**实际返回结果：**

```json
{
  "choices": [
    {
      "finish_reason": "length",
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "",
        "reasoning_content": "嗯，用户让我用一句话介绍自己..."
      }
    }
  ],
  "usage": {
    "completion_tokens": 30,
    "prompt_tokens": 12,
    "total_tokens": 42
  },
  "timings": {
    "prompt_n": 12,
    "prompt_ms": 47102.028,
    "prompt_per_token_ms": 3925.169,
    "prompt_per_second": 0.254,
    "predicted_n": 30,
    "predicted_ms": 3917.192,
    "predicted_per_token_ms": 130.573,
    "predicted_per_second": 7.658
  }
}
```

**性能分析：**

| 阶段 | 速度 | 说明 |
|------|------|------|
| 提示编码 (Prompt Eval) | 3925 ms/token ≈ 0.25 tok/s | **非常慢！** CPU 上的矩阵运算通病 |
| 文本生成 (Token Gen) | 130 ms/token ≈ 7.66 tok/s | 还行，基本可用的速度 |

> *注意：返回的 `content` 为空，`reasoning_content` 有内容——这是 Qwen3 的"思考模式"。模型在生成正式回答前会先推理。如果不喜欢这个行为，加 `"reasoning_effort": "none"` 参数。*

### 10.3 服务器日志中的性能数据

```
9.48.326.794 I slot print_timing:
  id  3 | task 0 | prompt eval time =   47102.03 ms /    12 tokens ( 3925.17 ms per token,     0.25 tokens per second)
9.48.326.827 I slot print_timing:
  id  3 | task 0 |        eval time =    3917.19 ms /    30 tokens (  130.57 ms per token,     7.66 tokens per second)
9.48.326.829 I slot print_timing:
  id  3 | task 0 |       total time =   51019.22 ms /    42 tokens
```

### 10.4 连接客户端

llama-server 提供 OpenAI 兼容 API，意味着你可以用任何支持 OpenAI 的客户端连接：

| 客户端 | Base URL | 备注 |
|--------|----------|------|
| Cherry Studio | `http://IP:8080/v1` | API Key 随便填 |
| Chatbox | `http://IP:8080/v1` | 模型名填 `Qwen3-1.7B` |
| OpenWebUI | `http://IP:8080/v1` | 开源 ChatGPT 替代 |
| 代码调用 | `http://IP:8080/v1` | 直接用 OpenAI SDK |

---

## 十一、性能优化建议

### 11.1 如果机器配置更好

| 配置提升 | 建议调整 |
|----------|---------|
| 4 核+ CPU | `-t` 设为 CPU 核心数 |
| 16GB+ 内存 | `-c 4096` 上下文翻倍，去掉 swapfile |
| 有 NVIDIA GPU | 加 `-ngl 99`（把所有层 offload 到 GPU） |
| 有 Apple Silicon | 用 Metal 后端，重编译时开 `-DGGML_METAL=ON` |

### 11.2 加速 llama.cpp 编译

如果 CPU 核心多（8 核+），建议开启 OpenBLAS 加速矩阵运算：

```bash
# 安装 OpenBLAS
apt-get install -y libopenblas-dev

# 重新 cmake（加 BLAS 支持）
cmake -S /opt/llama.cpp -B /opt/llama.cpp/build \
  -DGGML_CUDA=OFF \
  -DGGML_BLAS=ON \
  -DGGML_BLAS_VENDOR=OpenBLAS

# 增量编译（只编译变化的部分）
cmake --build /opt/llama.cpp/build --config Release -j$(nproc) \
  --target llama-server
```

> *OpenBLAS 是优化过的线性代数库，可以提升推理速度 15-30%。但在 2 核机器上收益很小，建议 4 核以上再开。*

---

## 十二、调试排查过程记录

以下是本文档在低配机器（2 核 / 8GB 内存）上实际部署时遇到的错误和解决过程。这些记录有助于你遇到类似问题时快速定位。

### 错误 1：hf-mirror 下载失败

**现象**：
```bash
curl -L -o model.gguf "https://hf-mirror.com/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf"
# curl: (35) OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to huggingface.co:443
```

**原因**：hf-mirror.com 只是做了前端代理，实际下载时 302 重定向到 huggingface.co，而 huggingface.co 在国内网络环境被墙。

**解决**：改用 ModelScope，它是阿里云国内节点，直连无墙。

### 错误 2：GitHub 克隆超时

**现象**：
```bash
git clone https://github.com/ggml-org/llama.cpp /opt/llama.cpp
# 2 分钟后超时，无输出
```

**排查过程**：
- 尝试直接访问：`curl --connect-timeout 5 https://github.com` → 超时
- 尝试镜像 `gitclone.com` → 超时
- 尝试 `ghfast.top` → 能连上但 checkout 失败

**解决**：用 ghfast.top 镜像克隆后，手动 `git checkout -f HEAD` 恢复不完整的文件。

### 错误 3：克隆后文件不全

**现象**：
```bash
ls /opt/llama.cpp/src/
# 只有 CMakeLists.txt，没有 .cpp 源文件
```

**原因**：git checkout 阶段磁盘 I/O 太慢导致部分文件未写入。

**解决**：
```bash
cd /opt/llama.cpp
git checkout -f HEAD    # -f 强制覆盖，确保所有文件正确检出
```

### 错误 4：cmake 未安装

**现象**：`zsh: command not found: cmake`

**解决**：`apt-get install -y cmake build-essential`

### 错误 5：全量编译超时

**现象**：`cmake --build` 跑了 10 分钟还没结束

**原因**：llama.cpp 全量编译有几百个目标（含 UI、测试、各种工具），2 核编译非常慢。

**解决**：只编译需要的目标：
```bash
cmake --build /opt/llama.cpp/build --config Release -j$(nproc) \
  --target llama-cli llama-server
```

### 错误 6：--low-vram 参数无效

**现象**：
```
error: invalid argument: --low-vram
```

**原因**：llama.cpp 新版本已废弃此参数（mmap 机制已替代其功能）。

**解决**：直接从命令中删除 `--low-vram`。

### 错误 7：推理卡住不动

**现象**：`llama-cli -n 10` 跑了 5 分钟没输出，看起来像死循环。

**排查**：
- 检查进程状态：`ps aux | grep llama` → 进程还在跑（CPU 100%）
- 检查内存：`free -h` → Swap 已使用 419MB，内存几乎耗尽
- 结论：模型确实在推理，但 prompt 编码阶段（首 token）极慢

**实际性能数据**：
```
prompt eval time = 47102.03 ms / 12 tokens (3925.17 ms per token)
       eval time =  3917.19 ms / 30 tokens ( 130.57 ms per token)
```

**解读**：12 个 token 的提示编码花了 47 秒！但 30 个 token 的生成只花了 3.9 秒。所以长提示词会卡很久，但回复的生成速度是可以接受的。

---

## 十三、完整命令速查表

如果你不想看解释，直接复制下面这些命令就能从头搭一套：

```bash
# ===== 1. 创建 swapfile =====
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile

# ===== 2. 安装依赖 =====
apt-get install -y cmake build-essential
pip install modelscope

# ===== 3. 下载模型 =====
modelscope download \
  --model unsloth/Qwen3-1.7B-GGUF \
  --include "*Qwen3-1.7B-Q4_K_M.gguf*" \
  --local_dir /opt/models

# ===== 4. 编译 llama.cpp =====
git clone --depth 1 \
  https://ghfast.top/https://github.com/ggml-org/llama.cpp \
  /opt/llama.cpp
cd /opt/llama.cpp && git checkout -f HEAD
mkdir -p build
cmake -S /opt/llama.cpp -B /opt/llama.cpp/build -DGGML_CUDA=OFF
cmake --build /opt/llama.cpp/build --config Release -j$(nproc) \
  --target llama-cli llama-server

# ===== 5. 测试模型 =====
/opt/llama.cpp/build/bin/llama-cli \
  -m /opt/models/Qwen3-1.7B-Q4_K_M.gguf \
  -t $(nproc) -ngl 0 -c 512 --mmap --jinja \
  -p "你好" -n 10

# ===== 6. 启动服务 =====
/opt/llama.cpp/build/bin/llama-server \
  -m /opt/models/Qwen3-1.7B-Q4_K_M.gguf \
  -t $(nproc) -ngl 0 -c 2048 --mmap \
  --host 0.0.0.0 --port 8080 \
  --temp 0.6 --top-p 0.95 --top-k 20 \
  --repeat-penalty 1.05 --jinja

# ===== 7. 验证 =====
curl -X POST "http://127.0.0.1:8080/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen3-1.7B","messages":[{"role":"user","content":"你好"}],"max_tokens":50}'
```
