# OR-Intern API 文档

所有工具均为异步函数，返回 `(output: str, is_error: bool)` 元组。

## 目录

- [OR 核心工具](#or-核心工具)
  - [model_builder](#model_builder) — 数学建模
  - [solver_selector](#solver_selector) — 求解器推荐
  - [solve_job](#solve_job) — 求解执行
  - [validate_solution](#validate_solution) — 解验证
  - [sensitivity_analysis](#sensitivity_analysis) — 灵敏度分析
  - [visualization](#visualization) — 可视化
  - [compare_solvers](#compare_solvers) — 求解器对比
  - [report_generator](#report_generator) — 报告生成
  - [or_papers](#or_papers) — 论文搜索
  - [data_handler](#data_handler) — 数据加载
  - [research](#research) — 子 Agent 研究
- [基础设施工具](#基础设施工具)
  - [plan_tool](#plan_tool) — 任务计划
  - [bash](#bash) — 命令执行
  - [read](#read) — 文件读取
  - [write](#write) — 文件写入
  - [edit](#edit) — 文件编辑

---

## OR 核心工具

### model_builder

从自然语言描述生成 Pyomo 数学模型。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `description` | string | ✅ | 问题描述，如 "maximize 3x+2y s.t. x+y<=10" |
| `solver` | string | | 求解器名称（默认: highs） |

**返回**: 模型文件路径、问题类型、变量、约束数量

**示例**:
```
description: "maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0"
→ Model file: outputs/run_*/model.py
```

---

### solver_selector

根据问题类型推荐最佳求解器。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `description` | string | ✅ | 问题描述 |
| `prefer_open_source` | boolean | | 是否优先开源（默认: true） |

**返回**: 推荐求解器、类型（开源/商用）、理由、Pyomo 用法

---

### solve_job

执行优化求解。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `operation` | string | | "run"（执行）或 "status"（检查可用求解器） |
| `model_path` | string | ✅(run) | Pyomo 模型文件路径 |
| `solver` | string | | 求解器（默认: highs） |
| `timeout` | integer | | 超时秒数（默认: 300） |

**返回**: Status、Objective、Gap、Lower/Upper Bound、Solver Time、变量值

**示例**:
```
model_path: "outputs/run_20260527/model.py"
solver: "highs"
→ ## Solve Results
  Status: OPTIMAL
  Objective value: 30.0
  Gap: 0
  x = 10.0, y = 0.0
```

---

### validate_solution

验证解的可行性。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `model_path` | string | ✅ | 模型文件路径 |
| `solution` | object | | 解的变量值，如 {"x": 10, "y": 0} |

**返回**: FEASIBLE/INFEASIBLE、违反数、紧约束列表

---

### sensitivity_analysis

灵敏度分析：影子价格、reduced costs、参数分析。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `model_path` | string | ✅ | 模型文件路径 |
| `solver` | string | | 求解器（默认: highs） |
| `operation` | string | | "dual"、"parametric"、"full"（默认: full） |

**返回**: 影子价格表、reduced costs 表、参数分析结果

---

### visualization

生成可视化图表。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `chart_type` | string | | "variables"、"sensitivity"、"all"（默认: all） |
| `variables` | object | ✅ | 变量值，如 {"x": 10, "y": 0} |
| `objective` | number | | 目标函数值 |
| `param_data` | array | | 灵敏度数据 |
| `gap_data` | array | | 求解进度数据 |

**返回**: 图表文件路径（PNG）

---

### compare_solvers

多求解器性能对比。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `model_path` | string | ✅ | 模型文件路径 |
| `solvers` | string | | 逗号分隔的求解器列表（默认: highs,scip,glpk） |
| `timeout` | integer | | 每个求解器超时（默认: 60） |

**返回**: 对比表（求解器、状态、时间、目标值）

---

### report_generator

生成 Markdown 综合报告。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `problem_description` | string | | 问题描述 |
| `objective` | number | | 目标值 |
| `variables` | object | | 变量值 |
| `constraints` | object | | 约束影子价格 |
| `solver` | string | | 求解器名称 |
| `status` | string | | 求解状态 |
| `chart_paths` | array | | 图表路径列表 |

**返回**: 报告文件路径（Markdown）

---

### or_papers

搜索 arXiv OR 论文。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `query` | string | ✅ | 搜索关键词 |
| `max_results` | integer | | 最大结果数（默认: 5） |
| `source` | string | | "arxiv"、"web"、"both"（默认: arxiv） |

**返回**: 论文列表（标题、作者、摘要、链接）

---

### data_handler

加载 CSV/JSON 数据并转换为 Pyomo 格式。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `operation` | string | | "load"（加载）或 "inspect"（检查结构） |
| `file_path` | string | ✅ | 数据文件路径 |

**返回**: 数据结构描述或 Pyomo 兼容代码

---

### research

子 Agent 深度研究。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `query` | string | ✅ | 研究问题 |

**返回**: 研究结果摘要

---

## 基础设施工具

### plan_tool

任务计划追踪。

**参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `action` | string | | "create"、"update"、"list" |
| `todos` | array | | 任务列表 |

---

### bash / read / write / edit

文件系统操作，参数与标准 shell 工具一致。
