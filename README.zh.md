# OR-Intern

**一个用于运筹学的 AI 智能体——从描述到求解，一次对话完成。**

<p align="center">
  <img src="https://img.shields.io/badge/版本-1.0.0-blue?style=flat-square" alt="版本">
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/测试-477%20通过-brightgreen?style=flat-square" alt="测试">
  <img src="https://img.shields.io/badge/许可证-Apache%202.0-yellow?style=flat-square" alt="许可证">
  <img src="https://img.shields.io/badge/PRs-欢迎-orange?style=flat-square" alt="PRs 欢迎">
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>中文</strong>
</p>

---

## ✨ 亮点特性

| 特性 | 说明 |
|------|------|
| 🤖 **6阶段质量门** | 自动工作流：建模 → 求解 → 验证 → 分析 → 可视化 → 报告 |
| 🔧 **20个内置工具** | model_builder、solver_selector、sensitivity_analysis、visualization 等 |
| 🚀 **多求解器支持** | HiGHS（默认）、SCIP、Gurobi、CPLEX，支持自动回退 |
| 📊 **丰富输出** | 生成模型（Python/CVXPY）、图表、敏感性分析报告、PDF 报告 |
| 💾 **会话管理** | 撤销、压缩、恢复会话，持久化工作区 |
| 🌐 **多LLM后端** | 通过 LiteLLM 支持 Qwen、Claude、GPT |

---

## 🚀 快速开始

### 1. 安装

```bash
git clone https://github.com/your-org/or-intern.git
cd or-intern
uv sync
```

### 2. 配置

```bash
# 复制配置模板
cp config.example.yaml config.yaml
cp .env.example .env

# 编辑 .env 添加你的 API 密钥
# OPENAI_API_KEY=sk-your-key-here
```

### 3. 运行

```bash
# 交互模式
uv run or-intern

# 无头模式（单次问题求解）
uv run or-intern "求解：maximize 3x+2y s.t. x+y<=10, x>=0, y>=0"
```

---

## 🏗️ 系统架构

```mermaid
graph TD
    A[用户输入] --> B[智能体循环]
    B --> C[LLM<br>Qwen/Claude/GPT via LiteLLM]
    C --> D[工具路由]
    D --> E[基础设施工具]
    D --> F[OR 核心工具]
    D --> G[分析工具]
    
    E --> E1[bash, read, write]
    E --> E2[edit, plan_tool]
    E --> E3[notify_tool]
    
    F --> F1[model_builder]
    F --> F2[cvxpy_builder]
    F --> F3[robust_builder]
    F --> F4[solver_selector]
    F --> F5[solve_job]
    F --> F6[validate_solution]
    F --> F7[problem_templates]
    F --> F8[or_papers]
    F --> F9[data_handler]
    
    G --> G1[sensitivity]
    G --> G2[visualization]
    G --> G3[report_gen]
    G --> G4[compare_solvers]
    
    style A fill:#e1f5ff
    style B fill:#fff3e0
    style C fill:#f3e5f5
    style D fill:#e8f5e8
```

### 6阶段质量门工作流

```
┌─────────────────────────────────────────────────────────────────┐
│  阶段 1：建模     → model_builder / cvxpy_builder / robust      │
├─────────────────────────────────────────────────────────────────┤
│  阶段 2：求解     → solver_selector + solve_job                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ OPTIMAL, gap≈0  → 继续                                  │   │
│  │ gap>5% / 慢     → 切换求解器（最多3次尝试）              │   │
│  │ INFEASIBLE      → 诊断冲突                              │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  阶段 3：验证     → validate_solution                          │
├─────────────────────────────────────────────────────────────────┤
│  阶段 4：分析     → sensitivity_analysis                       │
├─────────────────────────────────────────────────────────────────┤
│  阶段 5：可视化   → visualization                              │
├─────────────────────────────────────────────────────────────────┤
│  阶段 6：报告     → report_generator                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ 配置

### 配置文件

| 文件 | 用途 | 版本控制 |
|------|------|----------|
| `config.yaml` | 模型、求解器、会话设置 | ✅ 可提交 |
| `.env` | API 密钥、密钥 | ❌ 已忽略 |

### 示例 `config.yaml`

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

### 配置搜索顺序

1. `OR_INTERN_CONFIG` 环境变量（显式路径）
2. `./config.yaml`（当前目录）
3. `~/.config/or-intern/config.yaml`（用户配置目录）

### 环境变量

在 config.yaml 中使用 `$VAR`、`${VAR}` 或 `${VAR:-default}` 语法引用环境变量。

```bash
# .env — 仅密钥
OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=your-key
# SLACK_BOT_TOKEN=xoxb-your-token
```

---

## 📁 项目结构

```
or-intern/
├── agent/
│   ├── main.py              # CLI 入口（交互模式 + 无头模式）
│   ├── config.py            # 配置（嵌套 YAML + Pydantic）
│   ├── core/                # 智能体引擎
│   │   ├── agent_loop.py    # 主智能体循环
│   │   ├── session.py       # 会话管理
│   │   ├── doom_loop.py     # 无限循环检测
│   │   └── telemetry.py     # 会话遥测与工作区跟踪
│   ├── context_manager/     # 上下文压缩 + 工作区注入
│   ├── messaging/           # 通知子系统（Slack 等）
│   ├── tools/               # 20 个工具实现
│   │   ├── model_builder.py # 生成 OR 模型
│   │   ├── solve_job.py     # 执行求解器
│   │   ├── _output_dir.py   # 工作区目录管理
│   │   └── ...
│   └── prompts/             # 系统提示词（YAML/Jinja2）
├── config.example.yaml      # 配置模板
├── .env.example             # 密钥模板
├── tests/                   # 477 个测试（单元 + 集成 + 回归）
├── outputs/                 # 每会话工作区（gitignore）
├── session_logs/            # 会话轨迹（gitignore）
├── pyproject.toml
└── README.md
```

---

## 🧪 测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 仅单元测试
uv run pytest tests/unit/ -v

# 基准测试（端到端）
uv run pytest tests/benchmarks/ -v

# 回归测试（128 个测试，15 个维度）
uv run pytest tests/benchmarks/test_regression.py -v

# 完整流水线测试
uv run pytest tests/benchmarks/ -v -k "FullPipeline"
```

---

## 💡 使用示例

### 示例 1：简单线性规划

```bash
uv run or-intern "求解：maximize 3x+2y s.t. x+y<=10, x>=0, y>=0"
```

**输出：**
```
## Phase 1: Model
✅ 模型已生成：maximize 3x + 2y, 约束：x + y <= 10

## Phase 2: Solve
✅ 最优解：x = 10, y = 0, 最优值 = 30

## Phase 3-6
[自动完成验证、灵敏度分析、可视化、报告]
```

### 示例 2：半导体物料缺料预测（真实业务场景）

```bash
# 准备数据文件（CSV格式）
# test_data/materials.csv - 物料主数据
# test_data/production_plan.csv - 生产计划
# test_data/bom.csv - 物料清单

uv run or-intern "请帮我分析半导体物料的缺料风险。数据文件在 test_data/ 目录下"
```

**系统自动完成：**
1. **数据加载** - 读取 CSV 文件（物料、BOM、生产计划）
2. **模型构建** - 生成 MRP 优化模型（Pyomo）
3. **求解计算** - 使用 HiGHS 求解，识别缺料风险
4. **结果验证** - 验证约束满足，目标可行
5. **可视化** - 生成库存趋势图、风险热力图、补货建议图
6. **报告生成** - 输出完整的分析报告

**输出文件：**
```
outputs/2026-06-04_xxxxxxxx/
├── report.md                    # 完整分析报告
├── material_shortage_model.py   # MRP 优化模型
├── shortage_analysis_result.json # 分析结果数据
├── inventory_trend.png          # 库存趋势图
├── shortage_heatmap.png         # 缺料风险热力图
├── reorder_suggestions.png      # 补货建议图
└── supplier_pie.png             # 供应商成本占比
```

**分析结果摘要：**
| 优先级 | 物料 | 补货量 | 最晚下单 | 成本 |
|:------:|:-----|:------:|:--------:|:----:|
| 紧急 | 硅晶圆 | 6,660 | 第1周 | ¥169,830 |
| 紧急 | 金属靶材 | 618 | 第1周 | ¥27,810 |
| 重要 | 刻蚀气体 | 2,756 | 第2周 | ¥23,426 |

### 示例 3：使用论文搜索（复杂问题）

```bash
uv run or-intern "我想用分布鲁棒优化方法处理供应链中的需求不确定性。
请先搜索相关论文，了解最新方法，然后构建模型并求解。"
```

**系统会：**
1. 使用 `or_papers` 搜索 arXiv 上的相关论文
2. 使用 `research` 子代理进行深入研究
3. 使用 `stochastic_builder` 构建随机规划模型
4. 完成完整的 6 阶段工作流

---

## 📚 文档

- [API 文档](docs/api.zh.md) | [API Documentation (English)](docs/api.md)
- [构建 OR 智能体](docs/blog-building-an-or-agent.zh.md) | [Building an OR Agent (English)](docs/blog-building-an-or-agent.md)

---

## 🤝 贡献指南

欢迎贡献！以下是你能帮助的方式：

1. **报告 Bug** - 提交 Issue 并附上复现步骤
2. **建议功能** - 在讨论区分享你的想法
3. **提交 PR** - Fork、创建分支、提交更改
4. **改进文档** - 帮助文档更清晰易懂

### 添加新工具

1. 在 `agent/tools/` 创建工具文件（如 `my_tool.py`）
2. 定义 `MY_TOOL_SPEC`（JSON Schema）和 `my_tool_handler`（异步函数）
3. 使用 `get_workspace_dir(session)` 获取工作区目录
4. 在 `agent/core/tools.py` 的 `create_builtin_tools()` 中注册
5. 在 `agent/prompts/system_prompt.yaml` 中添加描述
6. 在 `tests/unit/` 中添加单元测试

---

## 📄 许可证

Apache 2.0 - 详见 [LICENSE](LICENSE)

---

<p align="center">
  由 OR-Intern 团队 ❤️ 制作
</p>
