# 「面评家」MVP 开发计划

> 配套文档:技术方案详见《赛题2_面评家_技术方案_详细版.md》
> 本计划基于 2026-08-30 开源调研结论:**自己开发,复用开源资产**(详见「六、开源复用清单」)。

---

## 〇、结论摘要

- **决策**:不直接用、不基于现有项目改,自己开发。
- **核心理由**:开源项目均为「候选人训练工具」,而面评家是「HR 端初筛工具」(HR 发起 → 免登录链接 → 候选人文字答题 → HR 看报告横向对比),该产品闭环无现成开源;且 offerMaster/AURORA 无 LICENSE,DeepInterview 是巨型语音优先仓库。
- **目标**:6 周内做出可现场演示的完整闭环,答辩叙事 =「自研 LangGraph 状态机 + 动态追问 + 证据引用 + 标准化报告」。

---

## 一、MVP 边界(砍掉 / 保留)

| 技术方案里的项 | 决策 | 理由 |
|---|---|---|
| PostgreSQL | ✅ 砍 → **SQLite** | 单机演示够用,SQLAlchemy 换连接串即可,答辩说"MVP 用 SQLite,生产可切 PG" |
| Qdrant 向量库 | ✅ 砍 | 跑题检测 MVP 用 LLM 判断 + 追问上限兜底,不引入向量库 |
| 语音面试(ASR/TTS) | ✅ 砍 | 方案已写明 MVP 先文字 |
| 差距热力图 / 面试回放 | ✅ 砍(P1) | 时间不够就砍 |
| 多候选人**横向对比表** | ⚠️ 保留(精简版) | 答辩亮点,做最简单表格版 |

**MVP 必须完整闭环**:HR 上传 JD/简历 → 生成考察大纲 → 发起面试 → 候选人免登录答题 → AI 动态追问 → 收尾自动评估 → HR 查看报告。

---

## 二、技术栈定稿

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + Uvicorn |
| 数据 | SQLite + SQLAlchemy |
| Agent 编排 | LangGraph(StateGraph) |
| LLM | DeepSeek(OpenAI 兼容协议,function calling 强制 JSON) |
| 简历解析 | **markitdown**(开源复用,Apache-2.0) |
| 前端 | Vue3 + Vite + Element Plus(候选人页 + HR 后台) |
| 图表 | echarts(雷达图) |
| 部署 | docker compose |

---

## 三、仓库结构(一次建好,后续只填空)

```
Interview-commentator/
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # env 配置(LLM key 等)
│   │   ├── models.py            # SQLAlchemy:jobs/candidates/interviews/interview_messages
│   │   ├── schemas.py           # Pydantic 请求/响应
│   │   ├── db.py                # 引擎 + Session
│   │   ├── llm.py               # DeepSeek client 封装(function calling)
│   │   ├── api/
│   │   │   ├── jobs.py          # POST /api/jobs
│   │   │   ├── candidates.py    # POST /api/candidates
│   │   │   ├── interviews.py    # 发起/答题/拉状态
│   │   │   └── reports.py       # GET report
│   │   └── agents/
│   │       ├── resume_parser.py # markitdown + LLM 抽取 → 结构化简历 JSON
│   │       ├── jd_analyzer.py   # JD → 能力维度清单 JSON
│   │       ├── interviewer/     # ★核心
│   │       │   ├── state.py     # InterviewState(TypedDict)
│   │       │   ├── prompts.py   # 系统 prompt + 输出 JSON schema
│   │       │   └── graph.py     # LangGraph StateGraph(5-6 节点)
│   │       └── evaluator.py     # 评估 Agent → 报告 JSON
│   └── tests/
│       ├── test_state_machine.py
│       ├── test_schema.py
│       └── fixtures/            # 样例简历 / JD / 固定答案脚本
├── frontend/
│   └── src/
│       ├── candidate/           # 候选人面试页(聊天 UI + 进度)
│       └── admin/               # HR 后台(上传/发起/报告)
└── scripts/
    └── make_demo.py             # 一键生成演示数据(5 岗位 + 20 简历 + 预置面试)
```

---

## 四、数据模型(SQLite 版,对齐方案 6.1)

```python
# jobs          岗位(Jd)
#   id / title / jd_text / dimensions(JSONB→TEXT JSON) / created_at
# candidates    候选人
#   id / name / resume_path / resume_text / parsed_resume(JSON)
# interviews    面试
#   id / job_id / candidate_id / status / state(JSON 快照) / report(JSON) / started_at / ended_at
# interview_messages  逐轮留痕
#   id / interview_id / role(agent|candidate) / text / dimension / assess(JSON) / created_at
```

---

## 五、里程碑(6 周,2-4 人)

### 分工建议
- **A**:数据层 + API + 简历/JD 解析(最独立,先并行)
- **B**:状态机 + 面试官 Agent(核心,投入最大)
- **C**:评估 Agent + 前端(候选人页 + 后台)
- **D(可兼职)**:部署 + 演示数据 + 答辩材料

### W1 — 数据层 + 简历解析 + JD 分析
- [x] 4 张表 + SQLite 初始化
- [x] `resume_parser`:markitdown 转文本 → LLM 抽结构化 JSON(方案 4.1 schema)
- [x] `jd_analyzer`:LLM 输出维度清单(方案 4.2 schema)
- ⏳ **验收**:真实 LLM 验收待网络恢复(本地代理 127.0.0.1:7897 未连通)

### W2 — 面试状态机 v1(★技术心脏)
- [x] `state.py`(方案 5.2)+ `graph.py`(方案 5.3 状态转换)
- [x] 单维度问答闭环:提问 → 判断质量 → 追问/推进(mock 测试验证)
- [x] LLM 输出协议(方案 5.5:`{thinking, assess, next_question, action}`)
- [x] **服务端兜底校验**:action 枚举合法 + 轮次上限(max_q_per_dim=3, max_total_q=15)
- ✅ **验收**:状态机冒烟测试 7 例通过;候选人能答、面试官基于回答出下一问(真实 DeepSeek 手动验证待网络恢复)

### W3 — 多维度推进 + API + 候选人前端
- [x] 答题闭环 API:`POST /interviews/{id}/message`(DB 快照恢复 → 状态机推进 → 写回)+ `GET messages` + `GET state`
- [x] 逐维度推进 / 阶段切换状态机支持(测试覆盖 NEXT_DIMENSION;GO_BEHAVIORAL/GO_CANDIDATE_QA 待真实 LLM 验证)
- [ ] 剩余接口:触发评估 `POST /evaluate`(W4)、候选人报告热力图(可选)
- [ ] 候选人页:聊天 UI + 维度进度 + 免登录链接
- ⏳ **验收**:闭环 API 集成测试通过;一场面试自动覆盖全部维度、不越轮次上限(真实 LLM 验证待网络恢复)

### W4 — 评估 Agent + HR 后台
- [x] 评估 Agent:1 次 LLM 调用出报告 JSON(方案 4.5)+ 证据引用原话
- [x] 收尾自动触发评估 + `POST /evaluate` 手动触发;`GET /report` 已可用
- [ ] 报告页:雷达图(echarts)+ 得分 + 建议(前端)
- [ ] HR 后台:上传 → 发起面试 → 查看报告(前端)
- ✅ **验收(后端)**:收尾自动出报告(集成测试断言通过);面试结束报告落库

### W5 — 打磨 + 演示数据 + 横向对比
- [x] `make_demo.py`(5 岗位 + 20 简历 + 预置面试,2026-08-31)
- [ ] 多候选人横向对比表(精简版)
- ✅ **验收**:完整闭环可演示

### W6 — 部署 + README + 答辩材料
- [ ] docker compose 一键起
- [ ] README:架构 + 部署 + **三组验收指标**
- [ ] 演示脚本(方案 11.2)+ 答辩材料
- ✅ **验收**:现场可跑完整演示

---

## 六、开源复用清单(调研结论,2026-08-30)

| 来源 | 复用内容 | 方式 | License |
|---|---|---|---|
| **DeepInterview**(ngoanpv/DeepInterview) | `markitdown` 简历解析 PDF/DOCX→文本 | 直接 `pip install markitdown`,README 注明出处 | ✅ Apache-2.0 |
| **offerMaster**(heatnan/offerMaster) | 追问 prompt 风格(引用原话追问、按知识边界决定推进/深挖) | **只看思路自己重写,不整段复制** | ⚠️ 无 LICENSE 文件 |
| **structured-hiring**(NashiChuang) | 「评分标准即代码」概念(可选) | 吸收进评估 prompt | MIT |

> 关键验收指标(写进 README,答辩用):追问触发率 ≥60% · 评估一致率(3 次跑分极差 ≤1 分)· 单场成本 <¥1。

---

## 七、风险与兜底

| 风险 | 对策 |
|---|---|
| LLM 输出 JSON 解析失败 | function calling + Schema 校验 + 重试 ≤2 次 + 兜底默认问题 |
| 状态机跑飞 | 服务端二次校验 action + 轮次上限;LLM 只做判断,不做流程 |
| 面试质量不稳定 | 高质量系统 prompt + 固定答案回归测试 |
| 候选人跑题/刷题 | 追问上限 + LLM 质量判断 + 报告中证据引用可复核 |
| 前端来不及 | 候选人页先用单 HTML 文件顶住,后台再做 |

---

## 八、当前状态

- [x] 开源调研(已完成)
- [x] MVP 方向决策(已完成)
- [x] 开发计划(本文件)
- [x] git 初始化(2026-08-30,commit `ebdb19d`)
- [x] W1 骨架代码(数据层 + 简历/JD 解析 Agent + API;真实 LLM 验收待网络恢复后跑)
- [x] W2 状态机 v1(commit `67888a4`,mock 冒烟测试 7 例通过)
- [x] W3 API:答题闭环(commit `b035c10`)
- [x] W4 评估 Agent 后端(commit `a5d5968`,收尾自动出报告;12 例离线测试全绿)
- [x] 前端全部完成(候选人页 `dc9dc74` + 后台/报告页 `776ac61`)
- [x] W5:演示数据(make_demo.py)
- [ ] W5:多候选人横向对比 + 打磨
- ⏳ 待办:真实 LLM 端到端验收(本地代理 127.0.0.1:7897 未连通)
