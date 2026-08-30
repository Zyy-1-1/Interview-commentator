# 面评家 · AI 结构化面试 Agent

> HR 端初筛工具:HR 上传 JD / 简历 → 生成免登录面试链接 → 候选人文字答题 → AI 动态追问 → 收尾自动评估 → 标准化报告 + 多候选人横向对比。
>
> 核心叙事(答辩):**自研 LangGraph 状态机 + 动态追问 + 证据引用 + 标准化报告**。

---

## 一、产品闭环

```
HR 上传 JD / 简历
      │  JD 分析 Agent → 考察维度清单(带权重)
      ▼
发起面试 → 生成免登录链接 /interview/{id}
      │
候选人 文字答题 ──┐
      │           │ 面试官 Agent(LangGraph 状态机)
      ▼           │  · 判断回答质量 → 追问 / 推进下一维度
动态追问 ◄────────┘  · 服务端兜底:action 校验 + 轮次上限
      │
收尾 → 评估 Agent 一次调用 → 报告 JSON
      ▼
HR 查看报告(雷达图 + 原话证据 + 亮点/风险/二面建议)
      ▼
多候选人横向对比(按岗位分组,深色高亮最高分)
```

## 二、技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + Uvicorn |
| Agent 编排 | **LangGraph**(StateGraph 状态机) |
| LLM | DeepSeek(OpenAI 兼容协议,强制 JSON 输出) |
| 数据 | SQLite + SQLAlchemy(MVP;生产可切 PostgreSQL) |
| 简历解析 | markitdown(开源复用,Apache-2.0)+ PDF/DOCX 解析 |
| 前端 | Vue3 + Vite + vue-router + echarts |
| 部署 | docker compose |

## 三、架构

```
┌──────────── 前端 (Vue3, :5173) ────────────┐
│  candidate/  候选人面试页(聊天 UI + 进度)    │
│  admin/      HR 后台 + 报告页 + 横向对比页    │
└───────────────────┬─────────────────────────┘
                    │ /api(dev 代理 → :8000)
┌───────────────────▼─────────────────────────┐
│ FastAPI (:8000)                              │
│  api/    jobs · candidates · interviews · report │
│  agents/ resume_parser → jd_analyzer        │
│          interviewer/ (LangGraph 状态机)      │
│          evaluator (一次调用出报告)            │
│  llm.py DeepSeek client(chat_text / chat_json)│
│  SQLite + SQLAlchemy(4 张表)                  │
└──────────────────────────────────────────────┘
```

**面试状态机(面试官 Agent)**:LLM 负责「聪明的判断」,状态机负责「流程的可靠性」。
- 一次 `invoke` = 推进一个回合(开场白 / 判断并出下一问 / 收尾);
- 中间状态以 JSON 快照存库(`Interview.state`),异步多轮 = 多次恢复 + invoke;
- 服务端二次校验 action 枚举 + 轮次上限(每维度 ≤3 问,全场 ≤15 问),LLM 出错自动兜底降级,不中断面试。

**可审计性**:逐轮消息(`interview_messages`)留痕,含该轮质量判断(assess),报告证据引用候选**原话**,可复核。

## 四、仓库结构

```
Interview-commentator/
├── docker-compose.yml        # 一键起后端(前端可追加服务)
├── .env.example              # 环境变量样例(复制为 .env 填 Key)
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py / db.py / models.py / schemas.py / llm.py
│   │   ├── api/              # jobs · candidates · interviews · reports
│   │   └── agents/           # resume_parser · jd_analyzer · interviewer/ · evaluator
│   └── tests/                # 12 例离线测试(mock LLM,可离线跑)
├── frontend/
│   ├── vite.config.js        # :5173,/api 代理到 :8000
│   └── src/
│       ├── candidate/        # 候选人面试页
│       ├── admin/            # HR 后台 + 报告页 + 横向对比页
│       ├── api/index.js      # 接口封装
│       └── router/index.js
└── scripts/
    └── make_demo.py          # 一键生成演示数据(5 岗位 + 20 简历 + 5 场面试)
```

## 五、快速开始

### 1. 本地开发

```bash
# 后端
cd backend
cp ../.env.example .env            # 填入 DEEPSEEK_API_KEY
pip install -r requirements.txt    # 代理不通时加 --proxy ""
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端(另开终端)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

- HR 后台:`http://localhost:5173/admin`(创建岗位 → 上传简历 → 发起面试 → 查看报告)
- 候选人链接:后台发起面试后生成 `/interview/{id}`,免登录直接答题
- 横向对比:`http://localhost:5173/admin/comparison`

> Windows 注意:本机 `uvicorn --reload` 不可靠,改后端代码需手动重启进程。

### 2. 生成演示数据(可选)

```bash
python scripts/make_demo.py
```

纯离线生成 5 个岗位 + 20 份简历 + 5 场面试(3 场已完成含报告,2 场进行中),不依赖 LLM,用于演示与验收。会清空并重建四张表。

### 3. Docker 部署

```bash
cp .env.example .env        # 填 DEEPSEEK_API_KEY
docker compose up -d --build
# 后端 :8000(MVP 阶段仅后端;前端用 nginx 反代或 Vite preview)
```

## 六、三组验收指标(答辩用)

| 指标 | 目标 | 验证方式 |
|---|---|---|
| 追问触发率 | ≥60% | 固定答案回归测试,统计回答质量一般时是否触发追问 |
| 评估一致率 | 3 次跑分极差 ≤1 分 | 同一场面试重复评估 3 次,比较维度分极差 |
| 单场成本 | <¥1 | 统计一次完整面试的 DeepSeek token 消耗 |

## 七、API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/jobs` | 创建岗位(自动 JD 分析出维度) |
| GET | `/api/jobs` | 岗位列表 |
| POST | `/api/candidates` | 上传简历(multipart,自动解析) |
| GET | `/api/candidates` | 候选人列表 |
| POST | `/api/interviews` | 发起面试 |
| GET | `/api/interviews` | 面试列表(含岗位/候选人/总分) |
| POST | `/api/interviews/{id}/message` | 候选人答题闭环(空 reply = 开场白) |
| GET | `/api/interviews/{id}/messages` | 逐轮消息(回放/审计) |
| GET | `/api/interviews/{id}/state` | 会话进度快照 |
| POST | `/api/interviews/{id}/evaluate` | 手动触发评估(收尾后已自动) |
| GET | `/api/interviews/{id}/report` | 评估报告 |
| GET | `/api/interviews/comparison` | 多候选人横向对比(按岗位分组) |

## 八、测试

后端离线测试 **12 例全绿**(mock LLM 注入,确定性、可离线、CI 可用):

```bash
cd backend
python -m pytest tests/ -q
```

- `test_state_machine.py`:状态机冒烟 7 例(action 枚举、维度推进、轮次上限、收尾)
- `test_interviews_api.py`:答题闭环 API 集成(含收尾自动出报告断言)
- `test_evaluator.py`:评估 Agent 报告结构

> 策略说明:Agent / 状态机测试一律注入 **mock LLM**(fake 判断器),保证确定性、可离线跑、CI 可用;真实 DeepSeek 仅做手动验收,不写入自动化测试,避免依赖 API Key / token 成本。

## 九、开源复用清单

| 来源 | 复用内容 | License |
|---|---|---|
| [DeepInterview](https://github.com/ngoanpv/DeepInterview) | markitdown 简历解析思路 | Apache-2.0(直接引用) |
| offerMaster | 追问 prompt 风格(仅吸收思路,自研实现) | 无 LICENSE,不复制代码 |
| structured-hiring | 评分标准概念(可选吸收) | MIT |

---

**开发进度**:见《面评家_MVP开发计划.md》。W1–W5 已完成(数据层/状态机/答题闭环/评估/前端/演示数据/横向对比);W6 部署 + 演示材料进行中。
