#!/usr/bin/env python3
"""
囍上媒捎 - 自动化查询近期登录会员（高效版）
查询条件：1个月内登录过App，年龄33-43岁，地区佛山/广州（工作地为主）

用法：
    python3 search_recent_members_v2.py

输出：
    /data/user/work/recent_members_v2.json  - 原始筛选结果
    /data/user/work/recent_members_report_v2.md - Markdown报告
"""
import json
import time
import base64
import urllib.request
import urllib.error
import urllib.parse
import ssl
import hashlib
import os
from datetime import datetime, timedelta
from Crypto.Cipher import AES

# ==================== 配置 ====================
BASE_URL = "https://admin-app.xsms-club.com"
ACCESS_KEY = "HnsivOH8EfmTA7sS1Klm"
ACCESS_SECRET = "OH2u7BE6d10DHLtG9SsrFkBYOmHlr9dHQSkUv5IjL2s2T2sI2m"
SIGN_PASSPHRASE = "1234567890"
AES_KEY = "xsms123456789000"
AES_IV = "xsms000123456789"
PHONE = "150****0897"
PASSWORD = "123456"
USER_AGENT = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"

CONFIG = {
    "sex": "1",
    "ageStart": "33",
    "ageEnd": "43",
    "cities": ["广州市", "佛山市"],
    "login_days": 30,
}

OUTPUT_DIR = "/data/user/work"

# ==================== 加密/签名工具 ====================
def cryptojs_aes_encrypt(plaintext, passphrase):
    salt = os.urandom(8)
    d = b''; di = b''
    while len(d) < 48:
        di = hashlib.md5(di + passphrase.encode('utf-8') + salt).digest()
        d += di
    key, iv = d[:32], d[32:48]
    data = plaintext.encode('utf-8')
    pad = 16 - (len(data) % 16)
    data += bytes([pad]) * pad
    enc = AES.new(key, AES.MODE_CBC, iv).encrypt(data)
    return base64.b64encode(b'Salted__' + salt + enc).decode('utf-8')

def aes_ecb_encrypt(plaintext, key):
    data = plaintext.encode('utf-8')
    pad = 16 - (len(data) % 16)
    data += bytes([pad]) * pad
    return base64.b64encode(AES.new(key.encode('utf-8'), AES.MODE_ECB).encrypt(data)).decode('utf-8')

def aes_cbc_decrypt(ct, key, iv):
    dec = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8')).decrypt(base64.b64decode(ct))
    pad = dec[-1]
    # 服务端把 UTF-8 字节误当作 latin-1 字符再编码，需要反向修复
    return dec[:-pad].decode('utf-8').encode('latin-1').decode('utf-8')

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def make_headers(access_token="", user_id=""):
    timestamp = str(int(time.time() * 1000))
    sig = base64.b64encode(cryptojs_aes_encrypt(timestamp, SIGN_PASSPHRASE).encode('utf-8')).decode('utf-8')
    return {
        "Content-Type": "application/json",
        "accessToken": access_token,
        "userId": str(user_id) if user_id else "",
        "accessKey": ACCESS_KEY,
        "accessSecret": ACCESS_SECRET,
        "timestamp": timestamp,
        "signature": sig,
        "User-Agent": USER_AGENT,
    }

def api_get(path, access_token, user_id, params=None, retries=3, timeout=45):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=make_headers(access_token, user_id), method='GET')
        try:
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ""
            try:
                return json.loads(body) if body else {"error": body, "code": e.code}
            except:
                return {"error": body, "code": e.code}
        except Exception as e:
            last_err = str(e)
            print(f"  请求失败({attempt+1}/{retries}): {last_err}")
            time.sleep(2 ** attempt)
    return {"error": last_err}

def api_post(path, body, access_token="", user_id=""):
    url = BASE_URL + path
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                 headers=make_headers(access_token, user_id), method='POST')
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=20) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else ""
        try:
            return json.loads(body) if body else {"error": body, "code": e.code}
        except:
            return {"error": body, "code": e.code}
    except Exception as e:
        return {"error": str(e)}

def decrypt_response(resp):
    if not resp or 'data' not in resp:
        return resp
    data = resp['data']
    if data is None:
        return resp
    if isinstance(data, str) and len(data) > 20:
        try:
            inner = json.loads(aes_cbc_decrypt(data, AES_KEY, AES_IV))
            if isinstance(inner, dict) and 'code' in inner:
                return inner
            resp['data'] = inner
        except Exception as e:
            print(f"解密失败: {e}")
    return resp

# ==================== 登录 ====================
def login():
    token_resp = api_get("/upms/api/access/token", "", "")
    if not token_resp or token_resp.get('code') != 0:
        raise Exception(f"获取令牌失败: {token_resp}")
    access_token = token_resp['data']['token']

    encrypted_password = aes_ecb_encrypt(PASSWORD, AES_KEY)
    login_resp = api_post("/xsms/api/member/login/password",
                          {"phone": PHONE, "password": encrypted_password},
                          access_token, "")
    if not login_resp or login_resp.get('code') != 0:
        raise Exception(f"登录失败: {login_resp}")
    user_id = login_resp['data']['id']
    nickname = login_resp['data'].get('nickname', '')
    print(f"登录成功: {nickname} (ID: {user_id})")
    return access_token, user_id, login_resp['data']

# ==================== 按城市分页查询 ====================
def fetch_city_members(access_token, user_id, city):
    all_records = []
    page = 1
    size = 500
    params = {
        "sex": CONFIG['sex'],
        "ageStart": CONFIG['ageStart'],
        "ageEnd": CONFIG['ageEnd'],
        "workCity": city,
        "current": str(page),
        "size": str(size),
    }
    first_resp = decrypt_response(api_get("/xsms/api/member/query/list", access_token, user_id, params))
    if not first_resp or first_resp.get('code') != 0:
        raise Exception(f"查询 {city} 失败: {first_resp}")
    data = first_resp.get('data', {})
    total = data.get('total', 0)
    pages = data.get('pages', 1)
    records = data.get('records', [])
    all_records.extend(records)
    print(f"  {city} 第1页/{pages}页，本页{len(records)}条，累计{len(all_records)}/{total}条")

    for page in range(2, pages + 1):
        params['current'] = str(page)
        resp = decrypt_response(api_get("/xsms/api/member/query/list", access_token, user_id, params))
        if not resp or resp.get('code') != 0:
            print(f"  {city} 第{page}页/{pages}页查询失败: {resp}")
            continue
        records = resp.get('data', {}).get('records', [])
        all_records.extend(records)
        print(f"  {city} 第{page}页/{pages}页，本页{len(records)}条，累计{len(all_records)}/{total}条")
        time.sleep(0.3)
    return all_records, total

# ==================== 本地过滤 ====================
def parse_datetime(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None

def member_logged_in_recently(member, days):
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    login_time = parse_datetime(member.get('loginTime'))
    active_time = parse_datetime(member.get('activeTime'))
    best = None
    for t in [login_time, active_time]:
        if t and t >= cutoff:
            if best is None or t > best:
                best = t
    return best is not None, best.strftime("%Y-%m-%d %H:%M:%S") if best else None

def filter_members(records):
    filtered = []
    seen_ids = set()
    one_month_ago = (datetime.now() - timedelta(days=CONFIG['login_days'])).strftime("%Y-%m-%d")
    print(f"\n开始过滤：1个月内登录 (>= {one_month_ago})，去重...")
    for m in records:
        mid = m.get('id')
        if not mid or mid in seen_ids:
            continue
        recent, recent_time = member_logged_in_recently(m, CONFIG['login_days'])
        if not recent:
            continue
        seen_ids.add(mid)
        m['_recent_login'] = recent_time
        filtered.append(m)
    return filtered

# ==================== 获取附加信息 ====================
def fetch_member_home(access_token, user_id, member_id):
    resp = decrypt_response(api_get("/xsms/api/member/personal/home", access_token, user_id,
                                    params={"memberId": member_id}))
    if resp and resp.get('code') == 0:
        return resp.get('data', {})
    return {}

def fetch_member_moments(access_token, user_id, member_id):
    resp = decrypt_response(api_get("/xsms/api/memberMoment/getMemberMomentList", access_token, user_id,
                                    params={"memberId": member_id, "current": 1, "size": 50}))
    if resp and resp.get('code') == 0:
        data = resp.get('data', {})
        if isinstance(data, dict):
            return data.get('records', [])
    return []

def enrich_members(access_token, user_id, members):
    for i, m in enumerate(members, 1):
        mid = m.get('id')
        try:
            home = fetch_member_home(access_token, user_id, mid)
            m['_photos'] = home.get('memberImageList', []) or []
            moments = fetch_member_moments(access_token, user_id, mid)
            m['_moments'] = moments
            print(f"  [{i}/{len(members)}] ID {mid} 照片{len(m['_photos'])}张 动态{len(moments)}条")
            time.sleep(0.15)
        except Exception as e:
            print(f"  [{i}/{len(members)}] ID {mid} 获取附加信息失败: {e}")
            m['_photos'] = []
            m['_moments'] = []

# ==================== 生成报告 ====================
def safe_val(m, key, default="N/A"):
    val = m.get(key)
    return val if val not in [None, "", "null"] else default

def render_member(m):
    lines = []
    lines.append(f"### {safe_val(m, 'nickname')}\n")
    lines.append("")
    lines.append("| 属性 | 值 |")
    lines.append("|------|------|")
    lines.append(f"| 会员ID | {safe_val(m, 'id')} |")
    lines.append(f"| 昵称 | {safe_val(m, 'nickname')} |")
    lines.append(f"| 性别 | {'男' if str(m.get('sex')) == '0' else '女' if str(m.get('sex')) == '1' else '未知'} |")
    lines.append(f"| 年龄 | {safe_val(m, 'age')} |")
    lines.append(f"| 手机号 | {safe_val(m, 'phone')} |")
    lines.append(f"| 居住省份 | {safe_val(m, 'residProvince')} |")
    lines.append(f"| 居住城市 | {safe_val(m, 'residCity')} |")
    lines.append(f"| 居住区域 | {safe_val(m, 'residArea')} |")
    lines.append(f"| 工作省份 | {safe_val(m, 'workProvince')} |")
    lines.append(f"| 工作城市 | {safe_val(m, 'workCity')} |")
    lines.append(f"| 工作区域 | {safe_val(m, 'workArea')} |")
    lines.append(f"| 最后登录 | {safe_val(m, 'loginTime')} |")
    lines.append(f"| 活跃时间 | {safe_val(m, 'activeTime')} |")
    lines.append(f"| 注册时间 | {safe_val(m, 'createTime')} |")
    lines.append(f"| 职业 | {safe_val(m, 'occupation')} |")
    lines.append(f"| 身高 | {safe_val(m, 'height')}cm |")
    lines.append(f"| 学历 | {safe_val(m, 'education')} |")
    lines.append(f"| 婚姻状况 | {safe_val(m, 'marriageType')} |")
    lines.append(f"| 头像 | ![]({safe_val(m, 'image')}) |")
    lines.append("")

    photos = m.get('_photos', [])
    lines.append(f"#### 照片 ({len(photos)}张)")
    if photos:
        for idx, photo in enumerate(photos, 1):
            url = photo.get('imageUrl') if isinstance(photo, dict) else str(photo)
            lines.append(f"{idx}. ![]({url})")
    else:
        lines.append("暂无照片")
    lines.append("")

    moments = m.get('_moments', [])
    lines.append(f"#### 动态 ({len(moments)}条)")
    if moments:
        for idx, moment in enumerate(moments, 1):
            content = moment.get('content', '') if isinstance(moment, dict) else str(moment)
            create_time = moment.get('createTime', '') if isinstance(moment, dict) else ''
            lines.append(f"{idx}. **{content[:80]}{'...' if len(content) > 80 else ''}**")
            if create_time:
                lines.append(f"   - 发布时间: {create_time}")
    else:
        lines.append("暂无动态")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)

def generate_report(members, total_queried, operator):
    now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    one_month_ago = (datetime.now() - timedelta(days=CONFIG['login_days'])).strftime("%Y-%m-%d")
    lines = []
    lines.append("# 囍上媒捎 · 佛山广州会员查询报告")
    lines.append("")
    lines.append(f"> 查询时间: {now}")
    lines.append(f"> 操作人: {operator.get('nickname', '')} (ID: {operator.get('id', '')})")
    lines.append(f"> 查询条件: 1个月内登录过App，年龄33-43岁，地区佛山/广州")
    lines.append("")
    lines.append("## 查询概览")
    lines.append("")
    lines.append("| 项目 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 查询会员总数 | {total_queried} |")
    lines.append(f"| 符合条件会员 | {len(members)} |")
    lines.append("")
    lines.append("## 筛选条件")
    lines.append("")
    lines.append(f"- **年龄范围**: {CONFIG['ageStart']}-{CONFIG['ageEnd']}岁")
    lines.append(f"- **地区**: {', '.join(CONFIG['cities'])} (工作地为主，同时显示居住地)")
    lines.append(f"- **登录时间**: 1个月内 (>= {one_month_ago})")
    lines.append(f"- **判定依据**: loginTime 或 activeTime 任一在1个月内即算有效")
    lines.append("")
    lines.append("## 会员详情")
    lines.append("")
    for m in members:
        lines.append(render_member(m))
    return "\n".join(lines)

# ==================== 主流程 ====================
def main():
    print("=" * 60)
    print("  囍上媒捎 - 自动化查询近期登录会员（高效版）")
    print("=" * 60)
    access_token, user_id, operator = login()

    all_records = []
    total_queried = 0
    print("\n[1] 分页获取广州、佛山 33-43 岁会员...")
    for city in CONFIG['cities']:
        print(f"\n查询 {city}...")
        records, total = fetch_city_members(access_token, user_id, city)
        all_records.extend(records)
        total_queried += total
        time.sleep(0.5)
    print(f"\n共获取 {len(all_records)} 条记录（去重前），覆盖 {total_queried} 人次")

    print("\n[2] 本地过滤1个月内登录的会员...")
    filtered = filter_members(all_records)
    # 按最近登录时间倒序
    filtered.sort(key=lambda x: x.get('_recent_login') or '', reverse=True)
    print(f"符合条件会员: {len(filtered)} 人")

    print("\n[3] 获取会员照片和动态...")
    enrich_members(access_token, user_id, filtered)

    print("\n[4] 生成报告...")
    report_md = generate_report(filtered, total_queried, operator)
    report_path = os.path.join(OUTPUT_DIR, "recent_members_report_v2.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_md)
    print(f"Markdown报告已保存: {report_path}")

    json_path = os.path.join(OUTPUT_DIR, "recent_members_v2.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "query_time": datetime.now().isoformat(),
            "operator": {"id": operator.get('id'), "nickname": operator.get('nickname')},
            "config": CONFIG,
            "total_queried": total_queried,
            "matched_count": len(filtered),
            "members": filtered,
        }, f, ensure_ascii=False, indent=2)
    print(f"JSON数据已保存: {json_path}")

    print("\n" + "=" * 60)
    print(f"  完成：共找到 {len(filtered)} 位符合条件的会员")
    print("=" * 60)

if __name__ == "__main__":
    main()
