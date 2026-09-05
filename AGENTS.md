# AGENTS.md

## 项目目标

本文件约定本仓库的开发与审查方式。项目「面评家」面向求职者，核心流程为：岗位大厅 → 上传简历 → 人岗匹配分析 → 选择面试官风格 → 多轮模拟面试 → 个人竞争力报告。

参赛方向已确认：AIC 全球校园人工智能算法精英赛 / 算法创新赛 / 赛题 2：AI+软件创新。改进应服务于可运行的核心流程、AI 与业务的结合、可复核的评估和真实使用效果。赛题依据见 [2026 年官方规则](https://www.aicomp.cn/tracks/tracks-2/3792.html)；赛区安排和提交期限需要另行核对。

## 工作方式

- 使用中文沟通和编写项目说明；沿用现有代码命名与格式。
- 开始前检查 `git status --short`，阅读相关源码、测试和 README，保留用户已有改动。
- 按用户当前请求执行：审查时给出证据和优先级；修改时完成实现与必要验证。不要把建议写成已实现功能。
- 优先修复影响核心流程的问题，避免无关重构、批量格式化或为展示堆叠功能。
- 默认使用 `rg` 搜索；排除依赖目录、构建产物、缓存和本地数据。
- 文档、样例、测试桩、真实 LLM 调用和浏览器验收分别报告；不能用 mock 测试证明模型效果、评分公平性或实际成本。

## 代码导航

| 路径 | 职责 |
| --- | --- |
| `backend/app/main.py` | FastAPI 入口、生命周期和路由注册 |
| `backend/app/config.py` | 配置；环境变量优先，`.env` 相对进程工作目录读取 |
| `backend/app/db.py`、`models.py`、`schemas.py` | 数据库会话、启动期补列/索引、数据模型与 API 契约 |
| `backend/app/security.py` | 候选人令牌和审核口令校验 |
| `backend/app/api/` | 岗位、简历、面试与报告接口 |
| `backend/app/llm.py` | DashScope 千问调用、JSON 解析、重试和用量日志 |
| `backend/app/agents/` | JD 分析、简历解析、人岗匹配、报告评估 |
| `backend/app/agents/interviewer/` | LangGraph 回合推进、状态定义、追问与风格提示词 |
| `backend/tests/`、`pytest.ini` | 离线测试、隔离数据和显式启用的 `llm_live` 用例 |
| `frontend/src/views/` | 岗位大厅、简历分析、发布与审核页面 |
| `frontend/src/candidate/InterviewView.vue` | 多轮答题、重试、进度与语音播报 |
| `frontend/src/admin/ReportView.vue` | 候选人竞争力报告；当前目录名不代表仅管理员可用 |
| `frontend/src/api/index.js`、`access.js` | 请求封装、鉴权头与面试令牌的会话存储 |
| `frontend/src/composables/useSpeech.js` | 浏览器 TTS；当前答题输入为文字 |
| `scripts/`、`docs/` | 演示数据、演示脚本和项目文档 |

## 环境与常用命令

后端使用 Python 3.11，前端 CI 使用 Node.js 22。Windows PowerShell 调用 npm 时优先使用 `npm.cmd`。优先复用名为 `interview-commentator` 的 Conda 环境；本机启动脚本支持 `C:\miniconda\envs\interview-commentator\python.exe`，使用前检查路径，其他机器不要依赖该绝对路径。

依赖安装（仅在需要时执行）：

```powershell
# 仓库根目录，先激活项目环境
conda activate interview-commentator
python -m pip install -r backend/requirements-dev.txt
Set-Location frontend
npm.cmd ci
```

本地开发（两个独立终端）：

```powershell
# 后端：从仓库根目录进入 backend，确保配置和 SQLite 相对路径一致
conda activate interview-commentator
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# 前端：从仓库根目录进入 frontend
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1
```

Vite 开发端口为 5173，`/api` 代理到 `http://localhost:8000`。本仓库允许使用 Vite 本地开发。后台启动辅助进程时隐藏窗口，并记录 PID，结束时只停止本次创建的进程。

## 验证要求

- 纯文档修改：核对命令、路径、表述与源码一致，执行 `git diff --check`；无需为文档新增测试。
- 后端行为修改：先跑相关离线用例；涉及鉴权、状态机、事务、评分或公共数据契约时，再运行后端离线测试集。
- 前端行为修改：运行构建，并检查受影响的交互；涉及主流程时覆盖正常、失败、重试、刷新恢复。构建通过不代表页面功能通过。
- 涉及图表：确认条件分支渲染完成后才初始化，重试/重新上传后绑定当前 DOM，并在卸载时销毁实例。

```powershell
# 仓库根目录；排除真实模型用例
python -m pytest -m "not llm_live" -q

# frontend 目录
npm.cmd run build

# 仓库根目录；仅校验配置，避免展开并打印密钥
docker compose config --quiet
git diff --check
```

测试数据库应使用内存库或独立临时目录。若 Windows 的 pytest 缓存/清理发生权限错误，可使用 `-p no:cacheprovider --basetemp <新建且独占的临时目录>`；不要为通过测试清理用户数据。

前端用 `npm.cmd test` 运行 Vue 组件离线回归，覆盖条件渲染、失败重试和图表生命周期；内存 DOM 检查不能代替浏览器端到端验收。目前没有 lint 或浏览器端到端测试脚本。当前 Compose 只包含后端；配置校验、镜像构建、容器运行和整站浏览器验收是不同结果，分别记录。

## 核心行为约束

- 公开岗位提交进入 `pending`；审核与 JD 分析使用管理员鉴权，候选人只能从已上架且具备维度的岗位开始面试。
- 候选人私有接口复用 `security.py`，使用 `X-Candidate-Token`；后台使用 `X-Review-Passphrase`。令牌明文只在创建时返回，数据库保存哈希。
- 面试按硬技能、软素质、候选人提问、收尾推进，并保留全场轮次上限优先结束的行为；边界修改要覆盖相关测试。
- 状态快照和双方消息保持同一事务，保留乐观锁与 `request_id` 重试回放；注意回答归属的是上一问的维度。
- 风格枚举为 `pro`、`friendly`、`pressure`。共享协议不等于实际评分公平；相关结论需要真实对照验证。
- 分数限制、岗位维度和加权总分由服务端校验。修改评分时区分“未考察”“无有效证据”和“回答较差”，保留原话可追溯性。
- 面试结束与报告生成成功分别处理；评估失败需要可见状态和可用重试，不能提前宣称报告已生成。
- LLM 输出按不可信数据处理：JSON 能解析不代表字段类型、证据或评分正确；模型异常应有明确的错误或降级路径。
- 同步文档解析和模型调用不要阻塞异步事件循环。调整重试时检查客户端超时、服务端总耗时与重复调用成本。

## 数据与交付边界

- 默认沿用当前不配置 `.env`、不调用付费 LLM 的工作边界。真实模型测试须由用户明确要求；仅存在 Key 不代表授权调用。
- 不读取或回显本地 `.env` 的内容；不得在代码、日志、截图或提交中记录 Key、审核口令、访问令牌及真实简历/答题内容。
- `scripts/make_demo.py` 会清空并重建演示表。执行前必须已明确授权重置目标数据；优先使用独立临时数据库验证。
- `.agents/` 是已忽略的本地工作目录；共享约定放本文件，正式说明放 `README.md` 或 `docs/`。不要提交 `.env`、数据库、上传文件、依赖和构建缓存。
- 涉及实际行为或启动流程的变更，同步维护相应文档。交付说明包含改动、验证结果、尚未验证部分和后续风险。
- 提交或推送按当前任务授权执行；提交前核对暂存文件与差异，避免夹带无关改动。

文件命名和作用范围参考 [OpenAI 官方 AGENTS.md 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。
