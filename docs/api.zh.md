# OR-Intern API 文档

所有工具都是异步函数，返回 `(output: str, is_error: bool)` 元组。

工具输出文件写入会话工作区 `outputs/<session_id[:8]>/`，并在对话轮次间持久化。

## 目录

- [核心 OR 工具](#核心-or-工具)
  - [model_builder](#model_builder) — Pyomo 数学建模
  - [cvxpy_builder](#cvxpy_builder) — 凸优化建模 (cvxpy)
  - [robust_builder](#robust_builder) — 鲁棒优化建模
  - [stochastic_builder](#stochastic_builder) — 随机规划建模
  - [problem_templates](#problem_templates) — 标准 OR 问题模板
  - [model_checker](#model_checker) — 模型验证
  - [solver_selector](#solver_selector) — 求解器推荐
  - [solve_job](#solve_job) — 求解执行
  - [validate_solution](#validate_solution) — 解验证
  - [sensitivity_analysis](#sensitivity_analysis) — 灵敏度分析
  - [visualization](#visualization) — 可视化
  - [compare_solvers](#compare_solvers) — 求解器比较
  - [report_generator](#report_generator) — 报告生成
  - [or_papers](#or_papers) — 多源论文搜索
  - [data_handler](#data_handler) — 数据加载
  - [research](#research) — 子代理研究
- [基础设施工具](#基础设施工具)
  - [plan_tool](#plan_tool) — 任务规划
  - [notify](#notify) — 外部通知
  - [bash / read / write / edit](#bash--read--write--edit) — 文件系统操作

---

## 核心 OR 工具

### model_builder

从自然语言描述生成 Pyomo 数学模型。支持 LP、MIP、二进制、整数、SOS、指示器约束、分段函数。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `description` | string | ✅ | 问题描述，例如 "maximize 3x+2y s.t. x+y<=10" |
| `solver` | string | | 求解器名称（默认：highs） |
| `filename` | string | | 输出文件名（例如 "model_v1.py"）。省略时自动版本化 |

**返回**：模型文件路径、问题类型、变量数量、约束数量

**示例**：
```
description: "maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0"
filename: "model_production.py"
→ 模型文件: outputs/a3f7b2c1/model_production.py
```

---

### cvxpy_builder

生成 cvxpy 凸优化模型代码。支持 LP、QP、SOCP、SDP，自动进行 DCP 合规性检查。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `description` | string | ✅ | 问题描述 |
| `solver` | string | | 求解器：ECOS、SCS、OSQP、MOSEK（默认：ECOS） |
| `filename` | string | | 输出文件名。省略时自动版本化 |

---

### robust_builder

生成鲁棒优化模型。支持箱型和椭球型不确定性集。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `description` | string | ✅ | 问题描述（含不确定性参数） |
| `uncertainty_set` | string | | "box" 或 "ellipsoidal"（默认：box） |
| `gamma` | number | | 不确定性预算（默认：1.0） |
| `solver` | string | | 求解器（默认：highs） |
| `filename` | string | | 输出文件名 |

---

### stochastic_builder

生成两阶段随机规划模型（SAA）。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `description` | string | ✅ | 问题描述（含不确定性参数） |
| `n_scenarios` | integer | | 场景数量（默认：100） |
| `solver` | string | | 求解器（默认：highs） |
| `filename` | string | | 输出文件名 |

---

### problem_templates

列出/匹配/生成 15 个标准 OR 问题模板。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `operation` | string | | "list"、"match"、"generate"（默认：list） |
| `template_name` | string | | 模板名称（generate 时必填），例如 tsp、knapsack、transportation |
| `description` | string | | 问题描述（match 时必填） |
| `params` | object | | 模板参数 |
| `solver` | string | | 求解器（默认：highs） |
| `filename` | string | | 输出文件名 |

---

### model_checker

验证 Pyomo 模型文件的语法、导入、变量、目标函数、约束、求解器兼容性。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `model_path` | string | ✅ | 模型文件路径 |
| `run_import_test` | boolean | | 是否运行导入测试（默认：true） |

**返回**：验证结果（错误/警告列表）

---

### solver_selector

根据问题类型推荐最佳求解器。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `description` | string | ✅ | 问题描述 |
| `prefer_open_source` | boolean | | 优先选择开源求解器（默认：true） |

**返回**：推荐求解器、类型（开源/商业）、推荐理由、Pyomo 用法

---

### solve_job

执行优化求解，实时监控进度（gap、bound、nodes）。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `operation` | string | | "run"（执行）或 "status"（检查可用求解器） |
| `model_path` | string | ✅(run) | Pyomo 模型文件路径 |
| `solver` | string | | 求解器（默认：highs） |
| `timeout` | integer | | 超时时间（秒）（默认：300） |
| `stream_progress` | boolean | | 实时进度报告（默认：true） |

**返回**：状态、目标值、Gap、下界/上界、求解时间、变量值

**示例**：
```
model_path: "outputs/a3f7b2c1/model.py"
solver: "highs"
→ ## 求解结果
  状态: OPTIMAL
  目标值: 30.0
  Gap: 0
  x = 10.0, y = 0.0
```

---

### validate_solution

验证解的可行性。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `model_path` | string | ✅ | 模型文件路径 |
| `solution` | object | | 解的变量值，例如 {"x": 10, "y": 0} |

**返回**：FEASIBLE/INFEASIBLE、违反约束数量、绑定约束列表

---

### sensitivity_analysis

灵敏度分析：影子价格、约减成本、参数分析。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `model_path` | string | ✅ | 模型文件路径 |
| `solver` | string | | 求解器（默认：highs） |
| `operation` | string | | "dual"、"parametric"、"full"（默认：full） |

**返回**：影子价格表、约减成本表、参数分析结果

---

### visualization

生成可视化图表（PNG）。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `chart_type` | string | | "variables"、"sensitivity"、"heatmap"、"pareto"、"all" |
| `variables` | object | | 变量值，例如 {"x": 10, "y": 0} |
| `objective` | number | | 目标函数值 |
| `param_data` | array | | 灵敏度数据 |
| `gap_data` | array | | 求解进度数据 |
| `constraints` | object | | 约束松弛值 |
| `pareto_data` | array | | 帕累托前沿数据 |
| `filename_prefix` | string | | 文件名前缀（例如 "iteration2"）。省略时自动版本化 |

**返回**：图表文件路径（PNG）

---

### compare_solvers

多求解器性能比较。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `model_path` | string | ✅ | 模型文件路径 |
| `solvers` | string | | 逗号分隔的求解器列表（默认：highs,scip,glpk） |
| `timeout` | integer | | 每个求解器的超时时间（默认：60） |

**返回**：比较表（求解器、状态、时间、目标值）

---

### report_generator

生成综合报告（Markdown 或 LaTeX）。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `problem_description` | string | | 问题描述 |
| `objective` | number | | 目标值 |
| `variables` | object | | 变量值 |
| `constraints` | object | | 约束影子价格 |
| `solver` | string | | 求解器名称 |
| `status` | string | | 求解状态 |
| `chart_paths` | array | | 图表路径列表 |
| `format` | string | | "markdown" 或 "latex"（默认：markdown） |
| `filename` | string | | 输出文件名。省略时自动版本化 |

**返回**：报告文件路径

---

### or_papers

多源 OR 论文搜索与分析。支持 arXiv、Semantic Scholar 和 OpenAlex 数据源。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `operation` | string | | "search"（搜索）、"detail"（详情）、"cite"（引用分析） |
| `query` | string | ✅(search) | 搜索关键词 |
| `paper_id` | string | | 论文 ID（用于 detail/cite，支持 arXiv ID、DOI、S2 ID） |
| `max_results` | integer | | 最大结果数（默认：5） |
| `source` | string | | "arxiv"、"semantic_scholar"、"openalex"、"all"（默认：all） |

**返回**：
- search：论文列表（标题、作者、摘要、引用数、链接）
- detail：完整元数据 + 摘要
- cite：引用分析（谁引用了这篇 / 这篇引用了谁）

---

### data_handler

加载 CSV/JSON 数据并转换为 Pyomo 格式。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `operation` | string | | "load"（加载）或 "inspect"（检查结构） |
| `file_path` | string | ✅ | 数据文件路径 |

**返回**：数据结构描述或 Pyomo 兼容代码

---

### research

子代理深度研究。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `query` | string | ✅ | 研究问题 |

**返回**：研究结果摘要

---

## 基础设施工具

### plan_tool

任务规划与跟踪。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `action` | string | | "create"、"update"、"list" |
| `todos` | array | | 任务列表 |

---

### notify

向已配置的通道发送带外通知。

**参数**：
| 参数 | 类型 | 必填 | 描述 |
|------|------|:--:|------|
| `destinations` | array | ✅ | 目标通道名称列表 |
| `message` | string | ✅ | 通知内容 |
| `title` | string | | 标题 |
| `severity` | string | | "info"、"success"、"warning"、"error" |

**返回**：每个通道的发送结果

---

### bash / read / write / edit

文件系统操作，参数与标准 shell 工具一致。
