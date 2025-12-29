import os
import json
import glob
import copy
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# === 配置区域 ===
CONFIG_DIR = "configs"
TOLERANCE_MINUTES = 30
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
ENV_KEY_NAME = "DEVICE_KEYS"
MAX_RETRIES = 3  # 新增: 最大重试次数
RETRY_DELAY = 2  # 新增: 每次重试间隔秒数


def load_secret_keys():
    """
    从环境变量加载 Keys
    支持两种格式:
    1. List: ["key_1", "key_2"] -> 直接追加到任务
    2. Dict: {"iphone": "key_1", "ipad": "key_2"} -> 替换任务中的别名
    """
    keys_str = os.environ.get(ENV_KEY_NAME, "[]")
    try:
        keys = json.loads(keys_str)
        print(f"🔐 已加载 Keys 配置 (类型: {type(keys).__name__})")
        return keys
    except json.JSONDecodeError:
        print(f"⚠️ 警告: 环境变量 {ENV_KEY_NAME} JSON 格式错误")
        return []


def get_current_time(tz_name="Asia/Shanghai"):
    """获取带时区的当前时间"""
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        # 如果时区名错误，回退到系统本地时间（通常是 UTC）
        return datetime.now()


def process_tasks():
    # 1. 加载环境变量中的 Keys
    secret_keys = load_secret_keys()

    config_files = sorted(glob.glob(os.path.join(CONFIG_DIR, "*.json")))
    if not config_files:
        print("💤 没有找到配置文件。")
        return

    files_changed = False

    for config_file in config_files:
        print(f"\n📄 检查任务: {config_file}")

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"   ❌ 读取失败: {e}")
            continue

        # --- 跳过已执行 ---
        if data.get("executed") is True:
            print("   ⏭️ 跳过: 任务已标记为已执行")
            continue

        # --- 时间检查逻辑 ---
        trigger_time_str = data.get("trigger_time")
        tz_name = data.get("timezone", "Asia/Shanghai")  # 默认上海时间

        if not trigger_time_str:
            continue

        try:
            # 解析触发时间并加上时区信息
            trigger_time = datetime.strptime(trigger_time_str, TIME_FORMAT).replace(tzinfo=ZoneInfo(tz_name))
            current_time = get_current_time(tz_name)
        except ValueError as e:
            print(f"   ❌ 时间格式错误: {e}")
            continue

        # === 修改核心逻辑 ===
        # 计算时间差 (当前时间 - 设定时间)
        diff = current_time - trigger_time
        diff_minutes = diff.total_seconds() / 60

        print(f"   ⏳ 设定: {trigger_time} | 当前: {current_time.strftime('%H:%M:%S')}")
        print(f"   ⏳ 延迟: {diff_minutes:.1f} 分钟 (正数表示已到时间，负数表示未到)")

        # 逻辑：
        # 1. diff_minutes >= 0: 表示当前时间已经过了设定时间（不提前触发）
        # 2. diff_minutes <= TOLERANCE_MINUTES: 表示在设定时间后的30分钟内（有效期）
        if 0 <= diff_minutes <= TOLERANCE_MINUTES:
            print("   🚀 准备执行...")

            url = data.get("webhook_url")
            method = data.get("method", "POST").upper()

            # === 🔑 关键步骤：构建 Payload 并注入 Key ===
            # 使用 deepcopy，防止修改 original data 导致 Key 被写回文件
            payload = copy.deepcopy(data.get("body", {}))

            # 确保 device_keys 字段存在
            if "device_keys" not in payload:
                payload["device_keys"] = []

            # 策略 A: Secret 是列表 -> 直接追加
            if isinstance(secret_keys, list):
                if secret_keys:
                    print(f"      注入 {len(secret_keys)} 个 Keys (追加模式)")
                    # 合并去重
                    payload["device_keys"] = list(set(payload["device_keys"] + secret_keys))

            # 策略 B: Secret 是字典 -> 别名替换
            elif isinstance(secret_keys, dict):
                original_list = payload["device_keys"]
                resolved_list = []

                if not original_list and secret_keys:
                    print(f"      配置为空，注入 Secret 中所有 Keys")
                    resolved_list = list(secret_keys.values())
                else:
                    for item in original_list:
                        if item in secret_keys:
                            print(f"      替换别名 '{item}' -> Masked Key")
                            resolved_list.append(secret_keys[item])
                        else:
                            resolved_list.append(item)

                payload["device_keys"] = resolved_list

            # --- 发送请求 (带重试机制) ---
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    print(f"      📡 发送请求... (尝试 {attempt}/{MAX_RETRIES})")

                    if method == 'GET':
                        resp = requests.get(url, params=payload, timeout=20)
                    else:
                        resp = requests.post(url, json=payload, timeout=20)

                    # 判断是否成功 (200-299)
                    if 200 <= resp.status_code < 300:
                        print(f"   ✅ 发送成功! 状态码: {resp.status_code}")
                        success = True
                        break  # 成功了就跳出循环
                    else:
                        print(f"   ⚠️ 失败: 服务器返回 {resp.status_code}")

                except requests.exceptions.RequestException as req_err:
                    print(f"   ❌ 网络请求异常: {req_err}")

                # 如果不是最后一次尝试，则等待后重试
                if attempt < MAX_RETRIES:
                    print(f"      ⏳ 等待 {RETRY_DELAY} 秒后重试...")
                    time.sleep(RETRY_DELAY)

            # --- 最终结果处理 ---
            if success:
                data["executed"] = True
                data["executed_at"] = current_time.strftime(TIME_FORMAT)

                # 回写文件
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

                print("   💾 状态已更新并保存")
                files_changed = True
            else:
                print(f"   ⛔️ 最终失败: 已重试 {MAX_RETRIES} 次，放弃执行")

        else:
            if diff_minutes < 0:
                print("   zzz 时间未到，稍后重试")
            else:
                print(f"   🚫 已过期 (超过 {TOLERANCE_MINUTES} 分钟)，不再执行")

    if files_changed:
        print("\n🏁 有任务状态更新，GitHub Action 将自动 Commit。")
    else:
        print("\n🏁 无状态变更。")


if __name__ == "__main__":
    process_tasks()
