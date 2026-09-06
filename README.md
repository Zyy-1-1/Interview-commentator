# 面评家 · AI 模拟面试官

> 面向**应聘者**的自助闭环:打开首页就是岗位大厅 → 选岗位、上传简历(PDF/DOCX/MD/TXT,最大 10 MB)→ 先看「人岗匹配分析」再决定要不要面 → 挑一位数字人面试官风格(严谨技术官 / 亲和 HR / 压力面)→ 语音提问、文字答题的模拟面试 → 收尾自动输出**个人竞争力报告**(雷达图 + 原话证据 + 强项短板 + 提升建议)。
>
> 岗位侧配套治理:任何人可自助发布招聘信息,官方口令审核通过后才能上架大厅。
>
> 核心叙事(答辩):**自研 LangGraph 状态机 + 动态追问 + 证据引用 + 标准化个人评估报告**;人格化只发生在 prompt 语言层,决策内核不变。

---

## 一、产品闭环

```
岗位大厅(首页,仅展示审核通过的岗位)
      │  选一个岗位 → /apply/{jobId}
      ▼
上传简历(PDF/DOCX/MD/TXT,最大 10 MB)
      │  简历解析 Agent(pdfminer/python-docx → LLM 结构化)
      │  匹配 Agent:简历 × 岗位维度 → 匹配分 + 雷达 + 亮点/缺口
      ▼
看完分析,再决定:换简历 or 开始模拟面试(选定面试官风格)
      │
/interview/{id} 数字人面试官(SVG 形象 + 浏览器 TTS 语音提问)
      │           面试官 Agent(LangGraph 状态机)
应聘者 文字答题 ──┤  · 判断回答质量 → 追问 / 推进下一维度
      ▼           │  · 服务端兜底:action 校验 + 轮次上限
动态追问 ◄────────┘
      │
收尾 → 领取后台评估任务 → 个人竞争力报告 JSON（可查询状态和重试）
      ▼
查看报告 /admin/reports/{id}(雷达图 + 原话证据 + 提升建议)

支线:发布招聘信息 /jobs/submit → 官方审核 /review(口令门控)→ 上架大厅
```

## 二、技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + Uvicorn |
| Agent 编排 | **LangGraph**(StateGraph 状态机) |
| LLM | **千问 DashScope**(qwen-plus,OpenAI 兼容协议,强制 JSON 输出) |
| 数据 | SQLite + SQLAlchemy(MVP;生产可切 PostgreSQL)+ 启动期幂等补列迁移 |
| 简历解析 | pdfminer.six(PDF)+ python-docx(DOCX)提文本 → LLM 结构化抽取 |
| 数字人 | 纯前端 SVG 形象(3 风格外观 + 眨眼/浮动/口型动画),零服务器成本 |
| 语音 | 浏览器 Web Speech API 端侧 TTS(zh-CN,不可用时静默降级纯文字) |
| 前端 | Vue3 + Vite + vue-router + echarts |
| 审核治理 | 岗位 status 工作流(pending/approved/rejected)+ `hmac.compare_digest` 口令校验 |

## 三、架构

```
┌──────────── 前端 (Vue3, :5173) ─────────────────────────┐
│  views/      岗位大厅 / 简历分析页 / 发布招聘 / 官方审核   │
│  candidate/  数字人语音面试页(SVG + TTS + 聊天 UI)      │
│  admin/      个人竞争力报告页(雷达图 + 证据)             │
│  components/DigitalHuman.vue  composables/useSpeech.js   │
└───────────────────┬──────────────────────────────────────┘
                    │ /api(dev 代理 → :8000)
┌───────────────────▼──────────────────────────────────────┐
│ FastAPI (:8000)                                           │
│  api/    jobs(提交/审核/上架)· candidates(上传/match)     │
│          interviews(状态机答题闭环)· report               │
│  agents/ resume_parser · jd_analyzer · matcher            │
│          interviewer/(LangGraph 状态机,style 人格注入)    │
│          evaluator(一次调用出个人评估报告)                 │
│  llm.py  千问 client(chat_text / chat_json)              │
│  SQLite + SQLAlchemy(4 张表 + 幂等补列迁移)               │
└───────────────────────────────────────────────────────────┘
```

**面试状态机(面试官 Agent)**:LLM 负责「聪明的判断」,状态机负责「流程的可靠性」。
- 一次 `invoke` = 推进一个回合(开场白 / 判断并出下一问 / 收尾);
- 中间状态以 JSON 快照存库(`Interview.state`),异步多轮 = 多次恢复 + invoke;
- 服务端二次校验 action 枚举、问题字段和轮次上限；默认每维度最多追问 3 次、全场最多提问 15 次。`MAX_Q_PER_DIM` / `MAX_TOTAL_Q` 必须为正整数，创建面试时保存到状态快照，后续配置变更只影响新会话。模型决策结构异常时使用安全问题兜底；简历字段类型错误返回可重试的 422。
- **三种面试官风格(pro/friendly/pressure)只替换 system prompt 中的人格段**,action 枚举、状态迁移、评估标准完全不变——人格化是语言层,决策是内核。

**可审计性**：逐轮消息（`interview_messages`）保留编号与问题维度。新报告（`schema_version: 2`）的证据必须定位到同一维度、同一条候选人消息；报告页可展开原始问答。维度状态为 `scored`、`not_assessed` 或 `insufficient_evidence`，后两者的 `score` 为 `null`；低分需要实际回答证据。完整覆盖且输入未截断时才返回 `summary_score`，否则为 `null`，另给 `coverage` 与仅代表已覆盖部分的 `assessed_score`。原话校验只能证明出处，评分合理性与公平性仍需真实对照评估。历史缓存报告保留原样并在页面标注未按新规则核验。

**一致性保护**:客户端每次答题携带 `request_id`,网络重试会回放同一结果;数据库使用乐观锁并把状态快照与双侧消息放在同一事务中,避免重复推进或部分写入。

**匿名隐私凭证**:上传简历后服务端只返回一次随机访问令牌,数据库仅保存其 SHA-256;匹配、创建面试、答题、消息和报告接口均需 `X-Candidate-Token`。前端把令牌保存在当前浏览器会话中,无需注册账号。

## 四、仓库结构

```
Interview-commentator/
├── .env.example               # 环境变量样例(复制为 backend/.env)
├── docker-compose.yml        # 一键起后端(前端可追加服务)
├── start_all.bat             # Windows 一键启动前后端
├── backend/
│   ├── requirements.txt / requirements-dev.txt
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py / db.py(补列迁移)/ models.py / schemas.py / llm.py
│   │   ├── api/              # jobs · candidates · interviews
│   │   └── agents/           # resume_parser · jd_analyzer · matcher
│   │                         # interviewer/(含 PERSONAS)· evaluator
│   └── tests/                # 离线测试(mock LLM,可离线跑)
├── frontend/src/
│   ├── views/                # JobHallView · ResumeAnalysisView
│   │                         # JobSubmitView · ReviewView
│   ├── candidate/            # InterviewView(数字人 + TTS)
│   ├── admin/                # ReportView(个人竞争力报告)
│   ├── components/DigitalHuman.vue
│   ├── composables/useSpeech.js
│   └── api/index.js · router/index.js
└── scripts/
    ├── make_demo.py          # 一键生成演示数据(5 岗位 + 20 简历 + 5 场面试)
    └── 演示脚本.md            # 现场演示走查 + 答辩叙事
```

## 五、快速开始

### 1. 创建 Miniconda 环境并安装依赖

```powershell
conda create -n interview-commentator python=3.11 -y
conda activate interview-commentator
pip install -r backend/requirements-dev.txt

cd frontend
npm ci
cd ..
```

### 2. 配置密钥

```bash
copy .env.example backend\.env     # 或 cp .env.example backend/.env
# 编辑 backend/.env:
#   DASHSCOPE_API_KEY=sk-xxx      (阿里云百炼控制台申请)
#   REVIEW_PASSPHRASE=自定口令     (/review 审核页使用)
```

> 显式环境变量优先于 `.env`,便于 CI/Docker 临时覆盖配置。若本机已有同名系统变量,可在当前 PowerShell 中用 `$env:DASHSCOPE_API_KEY='新值'` 覆盖，或清理旧值。

### 3. 本地开发

```bash
# 后端
conda activate interview-commentator
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端(另开终端)
cd frontend
npm ci
npm run dev                        # http://localhost:5173
```

或直接双击 `start_all.bat`(Windows)。

- 首页 = 岗位大厅;简历分析 `/apply/{jobId}`;面试 `/interview/{id}`;报告 `/admin/reports/{id}`
- 发布招聘 `/jobs/submit`;官方审核 `/review`(输入口令)

> Windows 注意:本机 `uvicorn --reload` 不可靠,改后端代码需手动重启进程(重启时自动执行补列迁移)。

### 4. 生成演示数据(可选,纯离线)

```bash
python scripts/make_demo.py
```

5 个岗位 + 20 份简历 + 5 场面试(3 场已完成含报告,2 场进行中)。会清空并重建四张表,完成后会打印带 `#access_token=...` fragment 的本地演示链接;前端读取后立即从地址栏清除。

### 5. Docker 部署（当前仅后端）

```bash
copy .env.example backend\.env    # 填 DASHSCOPE_API_KEY 与 REVIEW_PASSPHRASE
docker compose up -d --build
docker compose ps                  # backend 应显示 healthy
```

容器内数据库固定写入 `/app/data/interview.db` 并挂载命名卷;`backend/.env`、数据库、上传临时文件均不会进入镜像构建上下文。

## 六、三组验收指标(答辩用)

| 指标 | 目标 | 验证方式 |
|---|---|---|
| 追问触发率 | ≥60% | 固定答案回归测试,统计回答质量一般时是否触发追问 |
| 评估一致率 | 3 次跑分极差 ≤1 分 | 同一场面试重复评估 3 次,比较维度分极差 |
| 单场成本 | <¥1 | 一次完整面试的千问 token 消耗(TTS 与数字人均为端侧,零服务器成本) |

## 七、API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/jobs?status=approved` | 岗位大厅;查询 pending/all 需后台请求头 |
| POST | `/api/jobs` | 自助发布招聘,一律 pending 且不触发 LLM |
| POST | `/api/jobs/review/auth` | 校验后台请求头 `X-Review-Passphrase` |
| POST | `/api/jobs/review` | 后台审核;通过时分析 JD 并上架 |
| GET | `/api/jobs/{id}` | 已上架岗位详情;非公开岗位需后台请求头 |
| POST | `/api/jobs/{id}/analyze` | 后台 JD 分析失败重试 |
| POST | `/api/candidates` | 上传简历;响应仅一次返回匿名 `access_token` |
| GET | `/api/candidates/{id}/match/{jobId}` | 人岗匹配分析;需候选人令牌 |
| POST | `/api/interviews` | 发起模拟面试;需候选人令牌 |
| GET | `/api/interviews/{id}` | 面试详情;需候选人令牌 |
| POST | `/api/interviews/{id}/message` | 答题闭环;需令牌,支持幂等 `request_id` |
| GET | `/api/interviews/{id}/messages` | 逐轮消息;需候选人令牌 |
| GET | `/api/interviews/{id}/state` | 会话进度快照;需候选人令牌 |
| GET | `/api/interviews/{id}/report` | 报告及生成状态；需候选人令牌，未生成时 report 为 null |
| POST | `/api/interviews/{id}/evaluate` | 已结束面试补做或重试评估；新任务返回 202，已有报告返回 200 |

报告状态为 `not_started / pending / running / ready / failed`，`can_retry` 表示当前是否可发起评估。收尾请求落库后即安排后台线程评估，页面每 2 秒查询状态。数据库领取与任务编号阻止同一报告并发重复调用及旧任务覆盖新结果。当前使用进程内后台任务：服务重启不会自动恢复未完成任务，超过 120 秒（或模型总预算加 30 秒，取较大值）后可在报告页手动重试；查询状态不会触发模型。多节点部署或大规模队列需要独立任务系统。

模型默认单次网络超时 `LLM_TIMEOUT_SECONDS=25`，多次尝试共享 `LLM_TOTAL_TIMEOUT_SECONDS=75` 秒重试预算（最大 80）；每次请求使用剩余预算收紧超时，鉴权与参数错误不重复请求。网络库的超时不等同于严格的进程执行时限。浏览器请求超时为 90 秒，生成报告已从答题请求中分离。

## 八、测试

后端离线测试默认不会访问真实 LLM;联网用例必须显式开启:

```powershell
conda activate interview-commentator
python -m pytest -q

# 仅手动验收真实千问时运行
$env:RUN_LLM_TESTS='1'
python -m pytest -m llm_live -q
```

- `test_state_machine.py`:状态机冒烟(action 枚举、维度推进、轮次上限、收尾)
- `test_interviews_api.py`:答题闭环 + 风格进 prompt + match 接口
- `test_jobs_api.py`:自助提交 → pending → 口令审核 → 上架全流程
- `test_matcher_and_style.py`:三种人格差异 + 协议不变 + 匹配 Agent
- `test_evaluator.py`:评估报告结构

> 策略:Agent / 状态机测试一律注入 **mock LLM**(fake 判断器),不依赖 API Key;即使 `backend/.env` 里存在 Key,默认测试也不会产生外部调用或费用。

## 九、开源复用清单

| 来源 | 复用内容 | License |
|---|---|---|
| pdfminer.six / python-docx | 简历文档文本提取 | MIT / 各开源协议 |
| [DeepInterview](https://github.com/ngoanpv/DeepInterview) | 简历解析 + LLM 结构化思路(参考,未复制代码;markitdown 因依赖 onnxruntime 未采用) | Apache-2.0 |
| offerMaster | 追问 prompt 风格(仅吸收思路,自研实现) | 无 LICENSE,不复制代码 |
| structured-hiring | 评分标准概念(可选吸收) | MIT |

---

**当前版本**:应聘者自助闭环改版(千问 + 数字人语音 + 岗位审核治理 + 幂等/并发保护)。
