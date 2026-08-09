# MonkeyCode 批量切换会话模型 · 脚本

把一组 MonkeyCode 账号里「正在进行 (processing)」的会话，默认模型切换为目标模型（默认 `monkeycode-basic/glm-4.7`）。

配套原理文档见同级：`../MonkeyCode-额度查询与任务模型切换-搭建指南.md`

## 文件
- `monkeycode_switch_model.py` —— 单文件、自包含。登录（PoW 验证码）→ 查 processing 任务 → 查目标模型 → WebSocket `restart` 唤醒休眠任务 → `switch_model` 切换。

## 依赖
```bash
pip install websocket-client
# Python 3.8+
```

## 运行
方式一（推荐，密码不落盘，用环境变量）：
```bash
export MONKEY_PASSWORD='你的密码'
python3 monkeycode_switch_model.py 253254457@qq.com 3053595006@qq.com 919055362@qq.com
```

方式二（不改环境变量，直接改脚本顶部 `ACCOUNTS` 列表；密码走 `PASSWORD` 默认值）：
```bash
python3 monkeycode_switch_model.py
```

可选环境变量：
- `MONKEY_PASSWORD` —— 账号密码（默认占位 `123456`，请务必覆盖）
- `MONKEY_TARGET_MODEL` —— 目标模型名（默认 `monkeycode-basic/glm-4.7`）

命令行参数会覆盖脚本里的 `ACCOUNTS` 默认列表。

## 行为说明
- 对每个账号：登录 → 取目标模型 model_id → 列出所有 `processing` 任务。
- 已是目标模型的任务自动跳过（幂等，可重复跑）。
- **休眠 (hibernated) 任务必须先 `restart` 建立 stream，再 `switch_model`**，否则服务端报 500 `stream not found`。脚本已内置「先 restart 再 switch」逻辑。
- 切换后回查任务列表做校验并打印。

## 安全
- 提交到仓库的版本中 `PASSWORD` 默认值为占位符 `123456`，**真实密码请通过环境变量 `MONKEY_PASSWORD` 传入，不要写死进文件/提交进版本库**。
- 登录仅用于本次会话，session cookie 不落盘。
