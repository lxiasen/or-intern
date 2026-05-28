# AGENTS.md — OR-Intern 开发指南

## 项目概述

OR-Intern 是一个运筹优化（Operations Research）领域的 AI Agent，能从自然语言描述自动生成数学模型、调用求解器、验证解、进行灵敏度分析、生成可视化图表和报告。

**一句话愿景**：让每一个运筹优化问题，从描述到求解，只需要一次对话。

## 架构

```
User Input → Agent Loop → LLM (qwen/claude/gpt via LiteLLM)
                    ↓
              Tool Router (18 tools)
                    ↓
    ┌── Infrastructure ──┬── OR Core ──┬── Analysis ──┐
    │ bash, read, write, │ model_builder,  │ sensitivity, │
    │ edit, plan_tool    │ solver_selector, │ visualization,│
    │                    │ solve_job,       │ report_gen,   │
    │                    │ validate_solution,│ compare_solvers│
    │                    │ or_papers,       │               │
    │                    │ data_handler     │               │
    └─────────────────────┴────────────────┴───────────────┘
```

### 分层

| 层 | 目录 | 说明 |
|----|------|------|
| CLI 入口 | `agent/main.py` | 交互模式 + 无头模式 |
| Agent 引擎 | `agent/core/` | agent_loop、session、doom_loop、approval_policy |
| 上下文管理 | `agent/context_manager/` | 压缩策略、求解日志摘要 |
| 工具层 | `agent/tools/` | 18 个工具实现 |
| 系统提示 | `agent/prompts/system_prompt.yaml` | 6 阶段质量门控工作流 |
| 配置 | `configs/cli_config.json` | 模型、求解器、审批策略 |
| 测试 | `tests/` | unit + integration + benchmarks |

## 关键设计决策

### 1. 6 阶段质量门控工作流

System prompt 强制 LLM 走完所有阶段：

```
Phase 1: MODEL     → model_builder
Phase 2: SOLVE     → solver_selector + solve_job
  ┌── Quality Gate ──┐
  │ OPTIMAL, gap≈0   │→ 继续
  │ gap>5% / 慢      │→ 换求解器(最多3次)
  │ INFEASIBLE       │→ 诊断冲突
  └──────────────────┘
Phase 3: VALIDATE  → validate_solution
Phase 4: ANALYZE   → sensitivity_analysis
Phase 5: VISUALIZE → visualization
Phase 6: REPORT    → report_generator
```

### 2. 统一输出目录

所有产出文件写入 `outputs/run_<timestamp>/`：
- `model.py` — Pyomo 模型
- `variables.png` — 变量柱状图
- `sensitivity.png` — 灵敏度图
- `report.md` — 完整报告

协调机制：`agent/tools/_output_dir.py` 中的 `get_run_dir()` 使用标记文件。

### 3. 求解器集成

默认使用 HiGHS（开源、快速）。SCIP 作为备选。Gurobi/CPLEX 需要审批。

### 4. Gap/Bound 信息

`solve_job` 返回 Status、Gap、Lower Bound、Upper Bound、Solver Time，供 Quality Gate 决策。

## 开发环境

```bash
# 安装依赖
cd or-intern
uv sync

# 配置 .env
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY

# 运行测试
uv run pytest tests/ -v

# 启动 CLI
uv run or-intern
```

## 添加新工具

1. 在 `agent/tools/` 创建工具文件（如 `my_tool.py`）
2. 定义 `MY_TOOL_SPEC`（JSON Schema 格式）和 `my_tool_handler`（async 函数）
3. 在 `agent/core/tools.py` 的 `create_builtin_tools()` 中注册
4. 在 `agent/prompts/system_prompt.yaml` 的 Available Tools 中添加说明
5. 在 `tests/unit/` 添加单元测试

## 测试

```bash
# 全部测试（45 个）
uv run pytest tests/ -v

# 仅单元测试
uv run pytest tests/unit/ -v

# 仅基准测试（端到端）
uv run pytest tests/benchmarks/ -v

# 仅全流程测试
uv run pytest tests/benchmarks/ -v -k "FullPipeline"
```

## 与 ML-Intern 的关系

OR-Intern 基于 ML-Intern 的 Agent 基础设施（agent_loop、context_manager、doom_loop 等），但：
- 移除了所有 HuggingFace 专属代码
- 替换了 OR 领域工具集（18 个工具）
- 改写了 system prompt（6 阶段质量门控）
- 优化了上下文管理（OR 压缩策略）

详见 `OR-Intern完整实施方案.md`。
