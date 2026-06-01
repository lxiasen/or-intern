# OR-Intern

一个用于运筹学的 AI 智能体——自动建模、求解、验证和报告优化问题。

**[English](README.md) | 中文**

## 快速开始

```bash
# 克隆并安装
cd or-intern
uv sync

# 设置 API 密钥（LiteLLM 兼容）
cp .env.example .env
# 编辑 .env 添加 OPENAI_API_KEY

# 配置（可选）
cp config.example.yaml config.yaml

# 交互模式
uv run or-intern

# 无头模式
uv run or-intern "求解：maximize 3x+2y s.t. x+y<=10, x>=0, y>=0"
```

## 架构

```
用户输入 → 智能体循环 → LLM（qwen/claude/gpt via LiteLLM）
                    ↓
              工具路由（20 个工具）
                    ↓
    ┌── 基础设施 ──┬── OR 核心 ──────┬── 分析 ──────┐
    │ bash, read,  │ model_builder,  │ sensitivity, │
    │ write, edit, │ solver_selector,│ visualization,│
    │ plan_tool,   │ solve_job,      │ report_gen,  │
    │ notify_tool  │ validate_solution,│ compare_solvers │
    │              │ cvxpy_builder,  │              │
    │              │ robust_builder, │              │
    │              │ stochastic_builder│             │
    │              │ problem_templates│              │
    │              │ model_checker,  │              │
    │              │ or_papers,      │              │
    │              │ data_handler    │              │
    └──────────────┴────────────────┴──────────────┘
```

## 配置

复制 `config.example.yaml` 到 `config.yaml` 并自定义：

```bash
cp config.example.yaml config.yaml
```

示例配置：

```yaml
model:
  name: openai/qwen3.6-plus
  api_base: ""  # 或 https://your-endpoint/v1
  reasoning_effort: high
  max_iterations: 500

solver:
  default: highs
  timeout: 3600

session:
  save: true
  auto_save_interval: 1
  log_dir: session_logs
  heartbeat_interval: 60

approval:
  yolo_mode: false
  cost_cap_usd: 1.0
  confirm_expensive: true

tool_runtime: local
mcp_servers: {}

messaging:
  enabled: false
  auto_event_types: [approval_required, error, turn_complete]
  destinations: {}
```

环境变量可以在 config.yaml 中使用 `$VAR`、`${VAR}` 或 `${VAR:-default}` 语法引用。
密钥应放在 `.env` 中（参见 `.env.example`）：

```bash
# .env — 仅密钥，无配置
OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=your-key
# SLACK_BOT_TOKEN=xoxb-your-token
```

配置文件搜索顺序：
1. `OR_INTERN_CONFIG` 环境变量（显式路径）
2. `./config.yaml`（当前目录）
3. `~/.config/or-intern/config.yaml`（用户配置目录）

## 测试

```bash
uv run pytest tests/ -v
# 477 个测试，涵盖单元测试 + 集成测试 + 基准测试 + 回归测试
```

## 项目结构

```
or-intern/
├── agent/
│   ├── main.py              # CLI 入口点
│   ├── config.py            # 配置（嵌套 YAML）
│   ├── core/                # 智能体引擎
│   │   ├── agent_loop.py    # 主智能体循环
│   │   ├── approval_policy.py # OR 审批规则
│   │   ├── llm_params.py    # LiteLLM 集成
│   │   ├── telemetry.py     # 会话遥测与工作区跟踪
│   │   ├── session_resume.py # 从日志恢复会话
│   │   └── ...
│   ├── context_manager/     # 上下文压缩 + 工作区注入
│   ├── messaging/           # 通知子系统（Slack 等）
│   ├── tools/               # 20 个工具实现
│   │   ├── model_builder.py
│   │   ├── solve_job.py
│   │   ├── _output_dir.py   # 工作区目录管理
│   │   └── ...
│   └── prompts/             # 系统提示词（YAML/Jinja2）
├── config.example.yaml      # 配置模板
├── .env.example             # 密钥模板
├── tests/                   # 单元测试 + 集成测试 + 回归测试
├── outputs/                 # 每会话工作区（gitignore）
├── session_logs/            # 会话轨迹（gitignore）
├── pyproject.toml
└── README.md
```

## 文档

- [API 文档](docs/api.zh.md) | [API Documentation (English)](docs/api.md)
- [构建 OR 智能体](docs/blog-building-an-or-agent.zh.md) | [Building an OR Agent (English)](docs/blog-building-an-or-agent.md)

## 许可证

Apache 2.0
