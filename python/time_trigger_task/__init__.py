import os
import copy
import time
from datetime import datetime
import pytz
from time_trigger_task import task_io

# === 配置区域 ===
CONFIG_DIR = "configs"
TOLERANCE_MINUTES = 30
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
ENV_KEY_NAME = "DEVICE_KEYS"
MAX_RETRIES = 3
RETRY_DELAY = 2


def load_secret_keys():
    """从环境变量加载 Keys"""
    import json
    keys_str = os.environ.get(ENV_KEY_NAME, "[]")
    try:
        keys = json.loads(keys_str)
        print(f"🔐 已加载 Keys 配置 (类型: {type(keys).__name__})")
        return keys
    except json.JSONDecodeError:
        print(f"⚠️ 警告: 环境变量 {ENV_KEY_NAME} JSON 格式错误")
        return []


def get_current_time(tz_name="Asia/Shanghai"):
    try:
        tz = pytz.timezone(tz_name)
        return datetime.now(tz)
    except Exception:
        print(f"⚠️ 时区 '{tz_name}' 无效，使用 UTC")
        return datetime.now(pytz.utc)


def process_tasks():
    secret_keys = load_secret_keys()
    # ✅ 调用 Rust: 极速扫描文件列表
    config_files = task_io.list_configs(CONFIG_DIR)

    if not config_files:
        print("💤 没有找到配置文件。")
        return
    files_changed = False
    for config_file in config_files:
        print(f"\n📄 检查任务: {config_file}")
        try:
            # ✅ 调用 Rust: 安全读取并解析 JSON
            data = task_io.read_config(config_file)
        except Exception as e:
            print(f"   ❌ (Rust内核) 读取失败: {e}")
            continue
        if data.get("executed") is True:
            print("   ⏭️ 跳过: 任务已标记为已执行")
            continue

        trigger_time_str = data.get("trigger_time")
        tz_name = data.get("timezone", "Asia/Shanghai")
        if not trigger_time_str:
            continue
        try:
            target_tz = pytz.timezone(tz_name)
            naive_trigger_time = datetime.strptime(
                trigger_time_str, TIME_FORMAT)
            trigger_time = target_tz.localize(naive_trigger_time)
            current_time = get_current_time(tz_name)
        except ValueError as e:
            print(f"   ❌ 时间格式错误: {e}")
            continue
        diff = current_time - trigger_time
        diff_minutes = diff.total_seconds() / 60
        print(
            f"   ⏳ 设定: {trigger_time} | 当前: {current_time.strftime('%H:%M:%S')}")
        print(f"   ⏳ 延迟: {diff_minutes:.1f} 分钟")
        if 0 <= diff_minutes <= TOLERANCE_MINUTES:
            print("   🚀 准备执行...")

            url = data.get("webhook_url")
            method = data.get("method", "POST").upper()
            payload = copy.deepcopy(data.get("body", {}))

            if "device_keys" not in payload:
                payload["device_keys"] = []

            # --- 注入 Key 逻辑 (保持 Python 处理灵活性) ---
            if isinstance(secret_keys, list) and secret_keys:
                print(f"      注入 {len(secret_keys)} 个 Keys (追加模式)")
                payload["device_keys"] = list(
                    set(payload["device_keys"] + secret_keys))
            elif isinstance(secret_keys, dict):
                original_list = payload["device_keys"]
                resolved_list = []
                if not original_list and secret_keys:
                    print("      配置为空，注入 Secret 中所有 Keys")
                    resolved_list = list(secret_keys.values())
                else:
                    for item in original_list:
                        if item in secret_keys:
                            print(f"      替换别名 '{item}' -> Masked Key")
                            resolved_list.append(secret_keys[item])
                        else:
                            resolved_list.append(item)
                payload["device_keys"] = resolved_list

            # --- 发送请求 (替换为 Rust 绑定) ---
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    print(
                        f"      📡 (Rust内核) 发送请求... (尝试 {attempt}/{MAX_RETRIES})")

                    # ✅ 调用 Rust: 发送 HTTP 请求
                    # 参数: method, url, payload, timeout(秒)
                    # 返回: (status_code, body_text)
                    status_code, resp_text = task_io.send_request(
                        method,
                        url,
                        payload,
                        20  # timeout
                    )

                    if 200 <= status_code < 300:
                        print(f"   ✅ 发送成功! 状态码: {status_code}")
                        success = True
                        break
                    else:
                        print(f"   ⚠️ 失败: 服务器返回 {status_code}")
                        # 可选: 打印返回内容帮助调试
                        # print(f"      响应: {resp_text[:100]}...")

                except Exception as req_err:
                    # Rust 抛出的 PyConnectionError 等异常会在这里被捕获
                    print(f"   ❌ (Rust内核) 网络异常: {req_err}")

                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

            if success:
                data["executed"] = True
                data["executed_at"] = current_time.strftime(TIME_FORMAT)
                try:
                    # ✅ 调用 Rust: 将更新后的数据写回磁盘
                    task_io.save_config(config_file, data)
                    print("   💾 状态已更新并保存 (Rust内核)")
                    files_changed = True
                except Exception as e:
                    print(f"   ❌ (Rust内核) 保存失败: {e}")
            else:
                print(f"   ⛔️ 最终失败")
        else:
            if diff_minutes < 0:
                print("   zzz 时间未到")
            else:
                print(f"   🚫 已过期 (超过 {TOLERANCE_MINUTES} 分钟)")
    if files_changed:
        print("\n🏁 有状态更新。")
    else:
        print("\n🏁 无状态变更。")


if __name__ == "__main__":
    process_tasks()
