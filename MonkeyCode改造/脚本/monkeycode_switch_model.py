#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MonkeyCode 批量切换「进行中会话」默认模型 工具
================================================

用途
----
把一组 MonkeyCode (https://monkeycode-ai.com) 账号里「正在进行(processing)」的会话，
其默认模型切换为目标模型（默认 monkeycode-basic/glm-4.7）。

原理（来自 docs 仓库 MonkeyCode改版 搭建指南）
---------------------------------------------
1. 登录：PoW 验证码求解 (fnv1a32 + prng + sha256) -> redeem 兑换令牌 -> password-login 拿 session cookie
2. 查询：GET /api/v1/users/tasks 找出 status=processing 的任务
3. 查模型：GET /api/v1/users/models 找出目标模型(model_id)
4. 切换：通过 WebSocket 控制通道发送
        - 先 send kind="restart" 唤醒休眠(hibernated)的任务、建立 stream
        - 再 send kind="switch_model"（带 model_id, load_session=True）
   注意：文章示例假设任务本就活跃；实际休眠任务直接 switch 会 500 "stream not found"，
        必须先 restart 再 switch（本脚本已内置此逻辑）。

依赖
----
    pip install websocket-client
    Python 3.8+

运行方式
--------
方式一（推荐，密码不落盘）：用环境变量传入账号密码
    export MONKEY_PASSWORD='你的密码'
    python3 monkeycode_switch_model.py 253254457@qq.com 3053595006@qq.com 919055362@qq.com

方式二：直接把账号写进下方 ACCOUNTS 列表（或命令行参数），密码用脚本里 PASSWORD 默认值。

目标模型可用环境变量覆盖：
    MONKEY_TARGET_MODEL='monkeycode-basic/glm-4.7'

安全提示
--------
本文件提交到公开仓库时，PASSWORD 默认值已替换为占位符 123456，真实密码请通过
环境变量 MONKEY_PASSWORD 传入，切勿把真实密码提交进版本库。
"""

import base64
import hashlib
import json
import os
import sys
import time
import uuid
import http.cookiejar
import urllib.request
import websocket

BASE = "https://monkeycode-ai.com"

# ---- 可配置项 -------------------------------------------------------------
# 默认密码为占位符；真实密码请通过环境变量 MONKEY_PASSWORD 覆盖（推荐）。
PASSWORD = os.environ.get("MONKEY_PASSWORD", "123456")
TARGET_NAME = os.environ.get("MONKEY_TARGET_MODEL", "monkeycode-basic/glm-4.7")
# 休眠任务 restart 后等待 stream 建立的时间（秒）
RESTART_WAIT = 12
# WebSocket 收消息超时（秒）
WS_TIMEOUT = 60

# 默认账号列表（命令行传入则覆盖）；占位密码时这些账号需配合真实 MONKEY_PASSWORD
ACCOUNTS = [
    "253254457@qq.com",
    "3053595006@qq.com",
    "919055362@qq.com",
]


# ---- PoW 验证码求解 -------------------------------------------------------
def fnv1a32(data):
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def prng(seed, length):
    state = fnv1a32(seed)
    out = []
    while sum(len(x) for x in out) < length:
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        out.append("%08x" % state)
    return "".join(out)[:length]


def solve(token, count, size, difficulty):
    sols = []
    for i in range(count):
        b = (token + str(i + 1) + "d").encode()
        target = prng(b, difficulty)
        salt = prng(b[:-1], size)
        sol = 0
        while not hashlib.sha256((salt + str(sol)).encode()).hexdigest().startswith(target):
            sol += 1
        sols.append(sol)
    return sols


# ---- HTTP 封装 ------------------------------------------------------------
def post(cj, path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)).open(req, timeout=30) as r:
        return json.loads(r.read().decode())


def get(cj, path):
    req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
    with urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)).open(req, timeout=30) as r:
        return json.loads(r.read().decode())


def cookie_header(cj):
    return "Cookie: " + "; ".join("%s=%s" % (c.name, c.value) for c in cj)


# ---- 登录 -----------------------------------------------------------------
def login(email):
    cj = http.cookiejar.CookieJar()
    ch = post(cj, "/api/v1/public/captcha/challenge", {})
    sols = solve(ch["token"], ch["challenge"]["c"], ch["challenge"]["s"], ch["challenge"]["d"])
    tok = post(cj, "/api/v1/public/captcha/redeem", {"token": ch["token"], "solutions": sols})
    resp = post(cj, "/api/v1/users/password-login",
                {"email": email, "password": PASSWORD, "captcha_token": tok["token"]})
    session = next((c.value for c in cj if c.name == "monkeycode_ai_session"), None)
    return cj, session, resp


# ---- 查询模型 id ----------------------------------------------------------
def find_target_model_id(cj):
    d = get(cj, "/api/v1/users/models")
    best = None
    for m in d["data"]["models"]:
        if m["model"] == TARGET_NAME:
            return m["id"]
        if TARGET_NAME.split("/")[-1] in m["model"]:  # 容错：按短名匹配
            best = m["id"]
    return best


# ---- 查询 processing 任务 -------------------------------------------------
def processing_tasks(cj):
    d = get(cj, "/api/v1/users/tasks?limit=50")
    return [t for t in d["data"]["tasks"] if t["status"] == "processing"]


# ---- WebSocket 控制通道：restart + switch_model ----------------------------
def switch_task(cj, task_id, model_id):
    ws = websocket.create_connection(
        "wss://monkeycode-ai.com/api/v1/users/tasks/control?id=%s" % task_id,
        header=[cookie_header(cj)], timeout=WS_TIMEOUT)
    # 1) restart 唤醒休眠任务、建立 stream
    ws.send(json.dumps({"type": "call", "kind": "restart",
                        "data": base64.b64encode(json.dumps({"request_id": str(uuid.uuid4())}).encode()).decode()}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("type") == "call-response" and msg.get("kind") == "restart":
            print("    restart success=%s" % json.loads(base64.b64decode(msg["data"])).get("success"))
            break
        elif msg.get("type") == "ping":
            continue
    time.sleep(RESTART_WAIT)
    # 2) switch_model 切换模型
    ws.send(json.dumps({"type": "call", "kind": "switch_model",
                        "data": base64.b64encode(json.dumps(
                            {"request_id": str(uuid.uuid4()), "model_id": model_id, "load_session": True}).encode()).decode()}))
    deadline = time.time() + 50
    result = None
    while time.time() < deadline:
        try:
            msg = json.loads(ws.recv())
        except Exception as e:
            print("    recv err:", e)
            break
        if msg.get("type") == "call-response" and msg.get("kind") == "switch_model":
            result = json.loads(base64.b64decode(msg["data"]))
            break
    ws.close()
    return result


# ---- 主流程 ---------------------------------------------------------------
def main():
    accounts = sys.argv[1:] or ACCOUNTS
    print("目标模型: %s | 待处理账号数: %d" % (TARGET_NAME, len(accounts)))

    for email in accounts:
        print("\n===== 账号 %s =====" % email)
        try:
            cj, session, login_resp = login(email)
            name = (login_resp.get("data") or {}).get("name")
            print("  登录成功 name=%s session=%s" % (name, (session or "")[:8]))
            model_id = find_target_model_id(cj)
            print("  目标模型 model_id=%s" % model_id)
            if not model_id:
                print("  !! 未找到目标模型，跳过")
                continue
            tasks = processing_tasks(cj)
            print("  processing 任务数=%d: %s" % (len(tasks), [(t["id"][:8], t["model"]["model"]) for t in tasks]))
            for t in tasks:
                if t["model"]["model"] == TARGET_NAME:
                    print("  任务 %s 已是 %s，跳过" % (t["id"][:8], TARGET_NAME))
                    continue
                print("  切换任务 %s: %s -> %s" % (t["id"][:8], t["model"]["model"], TARGET_NAME))
                res = switch_task(cj, t["id"], model_id)
                if res:
                    print("  结果 success=%s model=%s" % (res.get("success"), (res.get("model") or {}).get("model")))
                else:
                    print("  结果 无响应")
            # 验证
            print("  --- 验证 ---")
            for t in processing_tasks(cj):
                print("  %s | %s | %s" % (t["id"][:8], t["status"], t["model"]["model"]))
        except Exception as e:
            print("  !! 账号处理失败:", e)
    print("\n===== 全部完成 =====")


if __name__ == "__main__":
    main()
