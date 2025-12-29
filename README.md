# ⏰ Time Trigger Task Scheduler

> 基于 GitHub Actions 的定时 Webhook 触发器，采用 **uv** 构建并运行在 **Python 3.14** 环境下。

这个项目旨在利用 GitHub Actions 的 Cron 机制，扫描仓库中的任务配置文件，在指定的时间窗口内触发 Webhook，并自动将执行状态回写到
Git 仓库以防止重复执行。

## 📂 项目结构

```text
.
├── .github/workflows/
│   └── time_trigger.yml  # GitHub Actions 流程配置
├── configs/              # 任务配置文件目录
│   ├── 01_login.json
│   ├── 02_sign.json
│   └── ...
├── main.py               # 核心逻辑脚本
├── pyproject.toml        # uv 项目配置
└── README.md
```

## ⚙️ 任务配置指南

在 `configs/` 目录下创建 `.json` 文件。请务必使用 **数字前缀**（如 `01.json`, `02.json`）以确保执行顺序。

**示例：`configs/01_example.json`**

```json
{
  "trigger_time": "2024-05-20 10:00:00",
  "webhook_url": "https://api.your-service.com/hooks/trigger",
  "method": "POST",
  "body": {
    "task_id": 123,
    "action": "start"
  },
  "executed": false
}
```

| 字段             | 类型      | 说明                                          |
|:---------------|:--------|:--------------------------------------------|
| `trigger_time` | String  | 触发时间 (格式: `YYYY-MM-DD HH:MM:SS`)，系统默认为北京时间。 |
| `webhook_url`  | String  | 需要调用的目标 URL。                                |
| `method`       | String  | HTTP 方法 (`GET` 或 `POST`)，默认为 `POST`。        |
| `body`         | Object  | 请求体 (POST json 数据) 或 查询参数 (GET params)。     |
| `executed`     | Boolean | **系统自动维护**。初始设为 `false`，执行成功后会自动变为 `true`。  |

## 🚀 本地开发与运行

本项目使用 `uv` 管理依赖。

1. **安装 uv** (如果尚未安装):
   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **安装依赖**:
   ```bash
   uv sync
   ```

3. **运行脚本**:
   ```bash
   # 默认使用 pyproject.toml 指定的版本 (>=3.12)
   uv run main.py
   
   # 或者强制使用特定版本测试 (需本地已安装对应 Python)
   uv run --python 3.12 main.py
   ```

## 🤖 GitHub Actions 配置

Workflow 位于 `.github/workflows/time_trigger.yml`。

- **触发频率**: 默认配置为每 **20分钟** 运行一次 (`*/20 * * * *`)。
- **Python 版本**: 强制指定安装 **Python 3.14**。
- **权限**: 需要 Write 权限以提交 `executed` 状态的变更。