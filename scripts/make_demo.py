#!/usr/bin/env python
"""make_demo.py — W5 一键生成演示数据(纯离线,不依赖 LLM)。

用法:
    python scripts/make_demo.py

注意:
- 会清空 jobs / candidates / interviews / interview_messages 四张表后重建;
- 推荐在后端未启动时运行;若后端正在运行,请确认没有进行中的请求;
- 演示数据:5 个岗位 + 20 份简历 + 3 场已完成面试(含报告)+ 2 场进行中面试。
"""
import json
import os
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 固定路径:无论从哪个目录调用,都以「后端目录」为基准
# (使 sqlite:///./interview.db 解析到 backend/interview.db,.env 也能被读到)
BACKEND_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from app.agents.interviewer.graph import DEFAULT_CLOSING  # noqa: E402
from app.agents.interviewer.state import (  # noqa: E402
    ACTION_CLOSING,
    PHASE_BEHAVIORAL,
    PHASE_CLOSING,
    PHASE_PROBING,
)
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Candidate, Interview, InterviewMessage, Job  # noqa: E402
from app.security import hash_candidate_token  # noqa: E402

DEMO_ACCESS_TOKEN = "demo-local-access-token"


# ============================================================ 岗位定义
JOBS = [
    {
        "title": "Python 后端开发工程师",
        "jd_text": (
            "负责核心业务后端服务的设计与开发,参与高并发场景优化;"
            "熟悉 Python 及主流 Web 框架,具备 MySQL/Redis 实战经验;"
            "能独立完成模块设计,有良好的沟通协作意识。"
        ),
        "dimensions": [
            {"name": "Python 编程", "type": "hard", "weight": 0.3, "keywords": ["Python", "asyncio", "FastAPI"], "probe": None},
            {"name": "数据库与缓存", "type": "hard", "weight": 0.2, "keywords": ["SQL", "MySQL", "Redis"], "probe": None},
            {"name": "系统设计", "type": "hard", "weight": 0.2, "keywords": ["高并发", "微服务", "消息队列"], "probe": None},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["协作", "沟通"], "probe": "STAR"},
            {"name": "学习能力", "type": "soft", "weight": 0.15, "keywords": ["自驱", "新技术"], "probe": "STAR"},
        ],
    },
    {
        "title": "Web 前端开发工程师(Vue3)",
        "jd_text": (
            "负责产品前端页面的开发与维护,基于 Vue3 生态建设组件库;"
            "熟悉 JavaScript/TypeScript,关注页面性能与工程化;"
            "有良好的审美和跨团队协作能力。"
        ),
        "dimensions": [
            {"name": "Vue3 框架", "type": "hard", "weight": 0.3, "keywords": ["Vue3", "Pinia", "组件化"], "probe": None},
            {"name": "JavaScript/TypeScript", "type": "hard", "weight": 0.25, "keywords": ["JS", "TS", "异步"], "probe": None},
            {"name": "工程化与性能", "type": "hard", "weight": 0.2, "keywords": ["Vite", "优化", "CDN"], "probe": None},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["协作", "需求沟通"], "probe": "STAR"},
            {"name": "学习能力", "type": "soft", "weight": 0.1, "keywords": ["新技术", "自驱"], "probe": "STAR"},
        ],
    },
    {
        "title": "数据分析师",
        "jd_text": (
            "负责业务数据的采集、清洗与分析,产出经营分析报告;"
            "熟练使用 SQL,掌握常用统计与建模方法;"
            "能够把分析结论转化为业务可执行的建议,具备良好的表达能力。"
        ),
        "dimensions": [
            {"name": "SQL 与数据处理", "type": "hard", "weight": 0.3, "keywords": ["SQL", "数据清洗", "埋点"], "probe": None},
            {"name": "统计与建模", "type": "hard", "weight": 0.25, "keywords": ["回归", "A/B", "指标"], "probe": None},
            {"name": "可视化", "type": "hard", "weight": 0.15, "keywords": ["看板", "图表"], "probe": None},
            {"name": "业务理解", "type": "soft", "weight": 0.15, "keywords": ["业务", "增长"], "probe": "STAR"},
            {"name": "沟通表达", "type": "soft", "weight": 0.15, "keywords": ["汇报", "呈现"], "probe": "STAR"},
        ],
    },
    {
        "title": "产品经理",
        "jd_text": (
            "负责产品需求调研、方案设计与迭代推进;"
            "能独立完成 PRD 与原型,关注数据指标和用户价值;"
            "协调研发/设计/运营多方,具备优秀的沟通与优先级判断能力。"
        ),
        "dimensions": [
            {"name": "需求分析与原型", "type": "hard", "weight": 0.25, "keywords": ["需求", "PRD", "原型"], "probe": None},
            {"name": "数据分析", "type": "hard", "weight": 0.2, "keywords": ["指标", "埋点", "转化"], "probe": None},
            {"name": "项目推进", "type": "hard", "weight": 0.2, "keywords": ["排期", "迭代", "验收"], "probe": None},
            {"name": "沟通协作", "type": "soft", "weight": 0.2, "keywords": ["协作", "对齐"], "probe": "STAR"},
            {"name": "逻辑思维", "type": "soft", "weight": 0.15, "keywords": ["结构化", "优先级"], "probe": "STAR"},
        ],
    },
    {
        "title": "测试工程师",
        "jd_text": (
            "负责产品的功能、接口与自动化测试,保障发布质量;"
            "能独立设计测试用例,熟练使用缺陷管理流程;"
            "有良好的质量意识,推动问题闭环。"
        ),
        "dimensions": [
            {"name": "测试用例设计", "type": "hard", "weight": 0.3, "keywords": ["用例", "边界", "场景"], "probe": None},
            {"name": "自动化测试", "type": "hard", "weight": 0.25, "keywords": ["Pytest", "Selenium", "CI"], "probe": None},
            {"name": "缺陷管理", "type": "hard", "weight": 0.15, "keywords": ["Bug", "复现", "回归"], "probe": None},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["协作", "对齐"], "probe": "STAR"},
            {"name": "质量意识", "type": "soft", "weight": 0.15, "keywords": ["质量", "风险"], "probe": "STAR"},
        ],
    },
]


# ============================================================ 候选人定义(20 份简历)
# parsed_resume 结构对齐 app/agents/resume_parser.py 的输出 schema
def _resume(name, age, school, major, education, experience, projects, skills):
    return {
        "basic": {"name": name, "age": age, "school": school, "major": major},
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
    }


CANDIDATES = [
    _resume(
        "张伟", 27, "武汉理工大学", "计算机科学与技术",
        [{"school": "武汉理工大学", "degree": "本科", "major": "计算机科学与技术", "years": "2017-2021"}],
        [{"company": "某电商公司", "role": "Python 后端工程师", "duration": "2021-至今", "summary": "负责订单与用户服务开发,主导网关接口性能优化,QPS 提升约 4 倍。"}],
        [{"name": "网关性能优化", "tech_stack": ["Python", "asyncio", "Redis"], "achievements": "把串行调用改为 asyncio 并发,接口 QPS 由 800 提升至 3000。"}],
        {"programming": ["Python", "SQL"], "tools": ["MySQL", "Redis", "Docker", "K8s"], "soft": ["协作", "自驱"]},
    ),
    _resume(
        "李娜", 24, "中南财经政法大学", "统计学",
        [{"school": "中南财经政法大学", "degree": "硕士", "major": "统计学", "years": "2022-2024"}],
        [{"company": "某零售集团", "role": "数据分析实习生", "duration": "2023-2024", "summary": "负责经营周报与用户留存分析,沉淀漏斗与归因模板。"}],
        [{"name": "流失用户预警", "tech_stack": ["SQL", "Python", "XGBoost"], "achievements": "构建流失预测模型,AUC 0.78,支持运营分层召回。"}],
        {"programming": ["SQL", "Python"], "tools": ["Tableau", "Excel", "Metabase"], "soft": ["表达", "细致"]},
    ),
    _resume(
        "王强", 25, "湖北大学", "软件工程",
        [{"school": "湖北大学", "degree": "本科", "major": "软件工程", "years": "2018-2022"}],
        [{"company": "某 SaaS 公司", "role": "前端开发工程师", "duration": "2022-至今", "summary": "负责后台管理系统前端,基于 Vue3 + Pinia 搭建组件库。"}],
        [{"name": "后台权限中心", "tech_stack": ["Vue3", "Pinia", "TypeScript"], "achievements": "实现动态路由与按钮级权限控制,组件复用率提升 30%。"}],
        {"programming": ["JavaScript", "TypeScript", "Vue"], "tools": ["Vite", "Webpack", "Git"], "soft": ["协作", "耐心"]},
    ),
    _resume(
        "刘洋", 26, "武汉大学", "信息管理",
        [{"school": "武汉大学", "degree": "本科", "major": "信息管理与信息系统", "years": "2018-2022"}],
        [{"company": "某工具类产品", "role": "产品助理", "duration": "2022-至今", "summary": "负责报表模块改版,访谈 8 名业务用户并主导两期迭代上线。"}],
        [{"name": "报表模块改版", "tech_stack": ["Figma", "埋点", "SQL"], "achievements": "制作时长下降 40%,二次使用率提升。"}],
        {"programming": [], "tools": ["Figma", "Axure", "SQL"], "soft": ["沟通", "推动力"]},
    ),
    _resume(
        "陈静", 25, "武汉科技大学", "计算机科学与技术",
        [{"school": "武汉科技大学", "degree": "本科", "major": "计算机科学与技术", "years": "2018-2022"}],
        [{"company": "某金融科技公司", "role": "测试工程师", "duration": "2022-至今", "summary": "负责支付链路功能与回归测试,搭建 Pytest 自动化回归脚本。"}],
        [{"name": "支付链路回归自动化", "tech_stack": ["Pytest", "Selenium"], "achievements": "每日 CI 自动回归,减少 60% 手工回归时间。"}],
        {"programming": ["Python"], "tools": ["Pytest", "Selenium", "Jira"], "soft": ["细致", "责任心"]},
    ),
    _resume(
        "赵磊", 30, "华中科技大学", "软件工程",
        [{"school": "华中科技大学", "degree": "硕士", "major": "软件工程", "years": "2016-2019"}],
        [{"company": "某出行平台", "role": "高级后端工程师", "duration": "2019-至今", "summary": "负责调度系统核心模块,主导微服务拆分与稳定性建设。"}],
        [{"name": "调度服务拆分", "tech_stack": ["Go", "Python", "Kafka"], "achievements": "拆分 6 个微服务,线上可用性提升到 99.99%。"}],
        {"programming": ["Python", "Go"], "tools": ["MySQL", "Redis", "Kafka", "K8s"], "soft": ["领导力", "体系化"]},
    ),
    _resume(
        "孙婷", 23, "武汉理工大学", "数学与应用数学",
        [{"school": "武汉理工大学", "degree": "本科", "major": "数学与应用数学", "years": "2020-2024"}],
        [{"company": "某电商平台", "role": "数据分析师", "duration": "2024-至今", "summary": "负责大促活动复盘与用户分层分析。"}],
        [{"name": "大促复盘体系", "tech_stack": ["SQL", "Python"], "achievements": "建立活动复盘模板,输出 12 期周报。"}],
        {"programming": ["SQL", "Python"], "tools": ["Excel", "PowerBI"], "soft": ["逻辑", "认真"]},
    ),
    _resume(
        "周杰", 22, "华中师范大学", "数字媒体技术",
        [{"school": "华中师范大学", "degree": "本科", "major": "数字媒体技术", "years": "2021-2025"}],
        [],
        [{"name": "社团活动小程序", "tech_stack": ["Vue3", "小程序"], "achievements": "上线服务 300 名社团成员。"}],
        {"programming": ["JavaScript", "Vue"], "tools": ["Vite", "Git"], "soft": ["热情", "好学"]},
    ),
    _resume(
        "吴敏", 28, "中南财经政法大学", "工商管理",
        [{"school": "中南财经政法大学", "degree": "硕士", "major": "工商管理", "years": "2019-2022"}],
        [{"company": "某在线教育公司", "role": "产品经理", "duration": "2022-至今", "summary": "负责学员端学习路径优化,GMV 相关转化提升 15%。"}],
        [{"name": "学习路径优化", "tech_stack": ["埋点", "SQL", "A/B"], "achievements": "通过 A/B 实验优化首页推荐,转化提升 15%。"}],
        {"programming": [], "tools": ["Axure", "SQL"], "soft": ["共情", "推动"]},
    ),
    _resume(
        "郑浩", 22, "湖北工业大学", "信息工程",
        [{"school": "湖北工业大学", "degree": "本科", "major": "信息工程", "years": "2021-2025"}],
        [],
        [{"name": "课程设计测评工具", "tech_stack": ["Python", "pytest"], "achievements": "自动化校验作业,减少人工批改。"}],
        {"programming": ["Python"], "tools": ["pytest", "Git"], "soft": ["严谨", "执行"]},
    ),
    _resume(
        "冯雪", 23, "武汉纺织大学", "计算机科学与技术",
        [{"school": "武汉纺织大学", "degree": "本科", "major": "计算机科学与技术", "years": "2020-2024"}],
        [{"company": "某医疗信息化公司", "role": "后端开发实习", "duration": "2023-2024", "summary": "参与预约挂号服务开发,编写接口文档与单元测试。"}],
        [{"name": "预约挂号服务", "tech_stack": ["Python", "FastAPI"], "achievements": "完成 3 个核心接口开发,测试覆盖率 85%。"}],
        {"programming": ["Python", "SQL"], "tools": ["FastAPI", "MySQL", "Git"], "soft": ["踏实", "钻研"]},
    ),
    _resume(
        "陈晨", 25, "武汉大学", "经济统计学",
        [{"school": "武汉大学", "degree": "本科", "major": "经济统计学", "years": "2019-2023"}],
        [{"company": "某银行信用卡中心", "role": "数据分析", "duration": "2023-至今", "summary": "负责营销转化分析,搭建活动归因看板。"}],
        [{"name": "营销归因看板", "tech_stack": ["SQL", "Metabase"], "achievements": "看板覆盖 80% 营销活动复盘需求。"}],
        {"programming": ["SQL"], "tools": ["Metabase", "Excel"], "soft": ["沟通", "细致"]},
    ),
    _resume(
        "朱俊", 24, "湖北经济学院", "电子商务",
        [{"school": "湖北经济学院", "degree": "本科", "major": "电子商务", "years": "2020-2024"}],
        [{"company": "某本地生活公司", "role": "前端开发", "duration": "2024-至今", "summary": "负责商家端 H5 页面开发与性能优化。"}],
        [{"name": "商家端 H5", "tech_stack": ["Vue3", "Vite"], "achievements": "首屏时间从 3s 降到 1.2s。"}],
        {"programming": ["JavaScript", "Vue"], "tools": ["Vite", "CDN"], "soft": ["合作", "上进"]},
    ),
    _resume(
        "许晴", 29, "华中科技大学", "工业工程",
        [{"school": "华中科技大学", "degree": "硕士", "major": "工业工程", "years": "2017-2020"}],
        [{"company": "某制造业 SaaS", "role": "高级产品经理", "duration": "2020-至今", "summary": "负责排产模块从 0 到 1,客户续费率提升。"}],
        [{"name": "排产模块 0→1", "tech_stack": ["PRD", "SQL"], "achievements": "3 家标杆客户落地,续费率提升 20%。"}],
        {"programming": [], "tools": ["Figma", "SQL"], "soft": ["决策力", "抗压"]},
    ),
    _resume(
        "何伟", 27, "武汉理工大学", "自动化",
        [{"school": "武汉理工大学", "degree": "本科", "major": "自动化", "years": "2017-2021"}],
        [{"company": "某智能硬件公司", "role": "测试工程师", "duration": "2021-至今", "summary": "负责固件发布测试,建立自动化压测脚本。"}],
        [{"name": "固件自动化压测", "tech_stack": ["Python", "pytest"], "achievements": "压测脚本覆盖 40+ 场景,发布风险前置。"}],
        {"programming": ["Python"], "tools": ["pytest", "Jenkins"], "soft": ["沉稳", "靠谱"]},
    ),
    _resume(
        "高翔", 23, "武汉大学", "计算机科学与技术",
        [{"school": "武汉大学", "degree": "本科", "major": "计算机科学与技术", "years": "2021-2025"}],
        [],
        [{"name": "校园二手交易平台", "tech_stack": ["Python", "FastAPI", "Redis"], "achievements": "独立完成 6 个模块,答辩获院级优秀。"}],
        {"programming": ["Python", "SQL"], "tools": ["FastAPI", "Redis"], "soft": ["潜力", "专注"]},
    ),
    _resume(
        "罗莉", 23, "中南财经政法大学", "应用统计",
        [{"school": "中南财经政法大学", "degree": "硕士", "major": "应用统计", "years": "2023-2025"}],
        [],
        [{"name": "招聘数据画像", "tech_stack": ["SQL", "Python"], "achievements": "基于职位/简历特征做匹配度建模。"}],
        {"programming": ["SQL", "Python"], "tools": ["Excel", "Python"], "soft": ["踏实", "敏锐"]},
    ),
    _resume(
        "唐飞", 26, "武汉工程大学", "计算机科学与技术",
        [{"school": "武汉工程大学", "degree": "本科", "major": "计算机科学与技术", "years": "2018-2022"}],
        [{"company": "某游戏公司", "role": "前端开发工程师", "duration": "2022-至今", "summary": "负责运营活动页与数据中心前端。"}],
        [{"name": "数据中心可视化", "tech_stack": ["Vue3", "ECharts"], "achievements": "实现大屏看板,数据刷新延迟 <2s。"}],
        {"programming": ["JavaScript", "TypeScript", "Vue"], "tools": ["ECharts", "Vite"], "soft": ["抗压", "协作"]},
    ),
    _resume(
        "韩梅", 24, "湖北大学", "市场营销",
        [{"school": "湖北大学", "degree": "本科", "major": "市场营销", "years": "2020-2024"}],
        [{"company": "某消费品牌", "role": "产品运营", "duration": "2024-至今", "summary": "负责用户增长活动策划,探索转付费。"}],
        [{"name": "老带新活动", "tech_stack": ["活动埋点", "SQL"], "achievements": "活动带来 800 名新用户。"}],
        {"programming": [], "tools": ["Axure", "SQL"], "soft": ["创意", "共情"]},
    ),
    _resume(
        "曹阳", 23, "武汉理工大学", "软件工程",
        [{"school": "武汉理工大学", "degree": "本科", "major": "软件工程", "years": "2021-2025"}],
        [],
        [{"name": "校园卡系统测试", "tech_stack": ["pytest", "Postman"], "achievements": "覆盖 120 条用例,协助定位 3 个高危缺陷。"}],
        {"programming": ["Python"], "tools": ["pytest", "Postman", "Jira"], "soft": ["耐心", "细致"]},
    ),
]


# ============================================================ 面试定义
# rounds:首条为开场白(agent,无 candidate),其余为 (dim, agent_q, cand_a, quality, issue, evidence)
# 演示用四元/六元组;quality 用于生成报告维度分,evidence 必须来自候选原话。

INTERVIEWS = [
    # ---- 已完成:Python 后端 × 张伟(强,82 分) ----
    {
        "job_title": "Python 后端开发工程师",
        "candidate": "张伟",
        "finished": True,
        "summary_score": 82,
        "suggestion": "与目标岗位匹配度较高,工程实战扎实,重点补强分布式/一致性细节即可",
        "strengths": ["异步编程理解深入,QPS 优化有量化结果", "数据库与缓存设计有实战经验", "系统设计表达结构化,能主动做兜底"],
        "risks": ["分库分表只讲了表拆分,索引与迁移细节未深入", "行为类回答较简短,团队协作细节待观察", "K8s 迁移尚未完全上线"],
        "next_step": ["针对性练习:吃透分布式事务与最终一致性,可做一个小的订单对账项目", "针对性练习:把一次线上事故排查写成完整时间线,练 STAR 表达"],
        "rounds": [
            ("", "你好,我是本次面试的面试官,很高兴见到你。这场面试大约 15 分钟,会围绕你的岗位能力和软素质展开。我们先从你的自我介绍开始吧。", "", 0, "", ""),
            ("Python 编程", "你的简历里提到用 Python 做过接口性能优化,能具体讲讲当时怎么用 asyncio 提升 QPS 的吗?", "当时我们有个查询网关接口 QPS 只有 800,排查发现是串行调用三个外部接口。我改成 asyncio.gather 并发请求,配合信号量限流,并给超时重试加了指数退避,最终 QPS 提升到 3000 左右,还把 requests 换成了 aiohttp。", 9, "", "用 asyncio.gather 并发请求,最终 QPS 提升到 3000 左右"),
            ("数据库与缓存", "聊下数据库,你提到订单表做过分库分表,分表键是怎么选的?有踩过坑吗?", "我们是按用户 ID 哈希分 16 张表,主键用雪花 ID。最早按创建时间分表,导致单表热点和跨月查询,后来改成用户维度。订单详情用 Redis 缓存,缓存穿透时用布隆过滤器兜底。", 8, "分库分表细节可再深挖", "最早按创建时间分表导致单表热点,后来改成用户维度"),
            ("系统设计", "如果让你设计一个秒杀系统,你会怎么拆?", "我会先做静态化走 CDN;入口用 Redis 预扣库存,Lua 脚本保证原子性;扣减成功后发 MQ 异步落订单,订单服务批量消费;热点商品提前预热缓存,再配限流组件保护下游。", 8, "", "用 Redis 预扣库存,Lua 脚本保证原子性"),
            ("系统设计", "如果下游订单服务挂了,消息积压,你会怎么处理?", "先看消费端是不是慢 SQL 或死循环,优先扩容 consumer、改批量消费;积压严重就临时加队列容量,并在恢复后跑对账补偿,保证最终一致。", 8, "未深入聊消息顺序性", "恢复后跑对账补偿,保证最终一致"),
            ("沟通协作", "如果和一个前端同事对接口字段有分歧,对方坚持不改,你会怎么处理?", "我会先拉出双方依赖,把改动影响列成清单;如果确实需要改,我会主动提供适配层降低对方改造成本,并把结论同步到群聊留痕,避免二义性。", 8, "", "主动提供适配层降低对方改造成本,并把结论同步到群聊留痕"),
            ("学习能力", "近一年你主动学了什么新技术,有落地到项目里吗?", "我学了 Go 和 K8s,把 CI 里一段构建脚本用 Go 重写,构建时间缩短了一半;现在在把老服务往 K8s 迁移,准备下季度上生产。", 7, "", "把 CI 里一段构建脚本用 Go 重写,构建时间缩短了一半"),
        ],
    },
    # ---- 已完成:数据分析师 × 李娜(中,72 分) ----
    {
        "job_title": "数据分析师",
        "candidate": "李娜",
        "finished": True,
        "summary_score": 72,
        "suggestion": "匹配度中等偏上,分析思路清晰,建议补强统计建模与业务验证能力",
        "strengths": ["SQL 基础扎实,取数链路清晰", "具备从指标到归因的完整分析思路", "表达有条理,结论先行"],
        "risks": ["建模环节样本量小,模型未经过线上验证", "业务归因偏经验,缺 A/B 或显著性检验", "可视化交互设计经验较少"],
        "next_step": ["针对性练习:独立设计一次完整 A/B 实验(含显著性检验)", "针对性练习:把一个分析结论做成能推动业务落地的完整故事"],
        "rounds": [
            ("", "你好,欢迎参加本次面试。我们大约 15 分钟,先请你做个自我介绍。", "", 0, "", ""),
            ("SQL 与数据处理", "你简历里写过月活漏斗分析,能说说数据是怎么清洗和加工的吗?", "我主要用 SQL 从埋点表取数,先用窗口函数去重会话,再按路径漏斗做 step 关联,异常值按设备维度剔除,最后落到宽表供可视化。", 8, "", "用 SQL 从埋点表取数,先用窗口函数去重会话"),
            ("统计与建模", "你提到用过回归做流失预测,变量和样本是怎么处理的?", "样本取近 90 天活跃用户,正负样本做了降采样平衡;变量先做相关性筛选,再用逻辑回归,效果不稳定就换 XGBoost,用 AUC 评估。", 7, "样本量较小,模型未上线验证", "正负样本做了降采样平衡,用 AUC 评估"),
            ("可视化", "用户流失预警看板你一般怎么设计?", "先定北极星指标,拆成新增/活跃/流失三层,每层放趋势和 Top 原因表,异常点自动标注,方便业务直接定位。", 7, "", "拆成新增/活跃/流失三层,异常点自动标注"),
            ("业务理解", "如果 GMV 连续两周下滑,你会怎么定位?", "先看大盘拆渠道、拆品类,找下滑最大的一块;再对齐运营动作和促销日历,排除活动错位;最后下钻看流量和转化环节。", 7, "归因方法较依赖经验,缺量化验证", "先看大盘拆渠道、拆品类,找下滑最大的一块"),
            ("沟通表达", "给业务方讲一个不友好的结论(比如活动效果差),怎么讲?", "我会先说结论再讲依据,用图配上同类活动基准,同时给出可执行的下一步建议,避免让业务觉得被针对。", 7, "", "先说结论再讲依据,同时给出可执行的下一步建议"),
        ],
    },
    # ---- 已完成:Web 前端 × 王强(偏弱,61 分) ----
    {
        "job_title": "Web 前端开发工程师(Vue3)",
        "candidate": "王强",
        "finished": True,
        "summary_score": 61,
        "suggestion": "匹配度中等,框架使用熟练,但 JS 底层与工程化是主要提升点",
        "strengths": ["框架使用熟练,能落地项目", "具备基础性能优化意识"],
        "risks": ["JS 底层概念停留在记忆层,缺工程佐证", "沟通应对偏被动,缺少主动推动案例", "项目规模偏小,缺复杂交互与性能压力场景"],
        "next_step": ["针对性练习:手写一遍响应式原理与虚拟 DOM diff,理解底层", "针对性练习:独立完成一个小型复杂交互组件,关注性能与工程化"],
        "rounds": [
            ("", "你好,欢迎参加面试。大约 15 分钟,先做个自我介绍吧。", "", 0, "", ""),
            ("Vue3 框架", "你用 Vue3 开发过哪些项目?组件之间状态是怎么管理的?", "做过一个后台管理系统,用的是 Vue3 + Pinia,主要管理用户和权限模块,组件复用用插槽和 props,复杂表单会用动态组件。", 7, "", "用的是 Vue3 + Pinia,组件复用用插槽和 props"),
            ("JavaScript/TypeScript", "聊一下闭包和事件循环,宏任务微任务各举个例?", "闭包就是函数能访问外层作用域的变量;事件循环先执行同步再执行微任务,Promise 是微任务,setTimeout 是宏任务。比如先 log 后 resolve 再 setTimeout。", 6, "解释停留在概念层面,缺少工程场景", "Promise 是微任务,setTimeout 是宏任务"),
            ("JavaScript/TypeScript", "项目里有用过 TypeScript 吗?泛型怎么用的?", "有,接口数据都用类型定义,泛型主要是封装请求函数的时候用,比如把响应包一层 Request 类型。", 6, "泛型使用较浅,未深入类型体操", "泛型主要是封装请求函数的时候用"),
            ("工程化与性能", "首屏加载慢,你会怎么优化?", "会做路由懒加载、图片懒加载,静态资源上 CDN,再用分包和 tree-shaking,必要的话上 SSR 或预渲染。", 7, "", "做路由懒加载、图片懒加载,静态资源上 CDN"),
            ("沟通协作", "一个需求你判断做不了,PM 又催得紧,你怎么处理?", "我会先评估工作量,拆成能快速上线的 MVP,并跟 PM 讲清楚风险和排期,实在不行就拉技术负责人一起对齐。", 6, "应对方式偏被动,缺乏主动推动", "拆成能快速上线的 MVP,并跟 PM 讲清楚风险和排期"),
            ("学习能力", "Vue3 的 Composition API 相比 Options 你更喜欢哪个,为什么?", "我更喜欢 Composition API,逻辑可以按功能组织,抽 hook 复用,Options 写多了 methods 会很长。", 7, "", "逻辑可以按功能组织,抽 hook 复用"),
        ],
    },
    # ---- 进行中:产品经理 × 刘洋 ----
    {
        "job_title": "产品经理",
        "candidate": "刘洋",
        "finished": False,
        "rounds": [
            ("", "你好,欢迎参加产品经理面试。大约 15 分钟,先做个自我介绍。", "", 0, "", ""),
            ("需求分析与原型", "你最近做的一个需求,从洞察到方案是怎么推进的?", "我接手了后台报表模块的改版,先访谈了 8 个业务用户,梳理出 3 类高频场景,再画出低保真原型和业务确认,评审通过后拆成两期排期。", 8, "", ""),
            ("数据分析", "这个改版你怎么定义成功?用什么指标衡量?", "主要看报表制作时长和用户二次使用率,基线先埋点一周,上线后对比使用时长下降比例和留存。", 7, "", ""),
            ("项目推进", "开发说需求范围太大,要在中间砍,你会怎么处理?", "我会把需求按价值和成本排出优先级,砍掉长尾功能,保证核心流程完整,同时跟开发对齐新的排期和验收标准。", 7, "", ""),
        ],
    },
    # ---- 进行中:测试工程师 × 陈静 ----
    {
        "job_title": "测试工程师",
        "candidate": "陈静",
        "finished": False,
        "rounds": [
            ("", "你好,欢迎参加测试工程师面试。大约 15 分钟,先做个自我介绍。", "", 0, "", ""),
            ("测试用例设计", "给你一个登录功能,你会怎么设计测试用例?", "我会分正常流、异常流和边界:正常账号密码、记住我、验证码;异常包括错误密码、空输入、密码长度边界、账号锁定;还要覆盖并发登录和安全性,比如 SQL 注入、XSS。", 8, "", ""),
            ("自动化测试", "你做过自动化测试吗?框架和数据怎么维护?", "用 Pytest + Selenium 做过回归脚本,用例数据抽到 yaml,定位元素用 data-testid,在 CI 里每天定时跑并出报告。", 7, "", ""),
            ("缺陷管理", "提了一个 Bug,开发说不是问题,你怎么办?", "我会先把复现步骤和环境整理清楚,截图录屏,再找开发当面确认,如果确实是需求歧义,就拉产品一起定标准。", 7, "", ""),
        ],
    },
]


# ============================================================ 构建器
def _build_state(interview_id, dimensions, rounds, finished):
    """按真实状态机输出格式构造 Interview.state 快照。"""
    dim_count = {}
    total = 0
    history = [{"role": "agent", "text": rounds[0][1]}]
    last_dim_idx = 0
    for i, r in enumerate(rounds):
        dim, agent_q, cand_a, *_ = r
        if i == 0:
            continue  # 开场白
        history.append({"role": "agent", "text": agent_q})
        history.append({"role": "candidate", "text": cand_a})
        dim_count[dim] = dim_count.get(dim, 0) + 1
        total += 1
        last_dim_idx = next((j for j, d in enumerate(dimensions) if d["name"] == dim), last_dim_idx)

    current_type = dimensions[last_dim_idx].get("type") if dimensions else "hard"
    state = {
        "interview_id": interview_id,
        "phase": (
            PHASE_CLOSING
            if finished
            else PHASE_BEHAVIORAL if current_type == "soft" else PHASE_PROBING
        ),
        "dim_idx": last_dim_idx,
        "dimensions": dimensions,
        "dim_question_count": dim_count,
        "total_questions": total,
        "history": history,
        "max_q_per_dim": 3,
        "max_total_q": 15,
        "pending_verification": [],
        "finished": finished,
    }
    if finished:
        state["action"] = ACTION_CLOSING
        state["closing_message"] = DEFAULT_CLOSING
        state["history"].append({"role": "agent", "text": DEFAULT_CLOSING})
    return state


def _build_report(dimensions, rounds, summary_score, suggestion, strengths, risks, next_step):
    """按评估 Agent 输出格式构造报告;evidence 直接取候选原话,保证可复核。"""
    scores = {}
    evidence = {}
    for i, r in enumerate(rounds):
        dim, agent_q, cand_a, quality, issue, ev = r
        if i == 0:
            continue
        scores.setdefault(dim, quality)
        evidence.setdefault(dim, [])
        if ev:
            evidence[dim].append(ev)
    report_dims = [
        {
            "name": d["name"],
            "score": float(scores.get(d["name"], 0)),
            "evidence": evidence.get(d["name"], []),
        }
        for d in dimensions
    ]
    return {
        "summary_score": summary_score,
        "suggestion": suggestion,
        "dimensions": report_dims,
        "strengths": strengths,
        "risks": risks,
        "next_step_questions": next_step,
    }


def _record_messages(db, interview, dimensions, rounds, finished):
    """按真实留痕逻辑写入 interview_messages。"""
    # 开场白不归属能力维度。
    db.add(
        InterviewMessage(
            interview_id=interview.id,
            role="agent",
            text=rounds[0][1],
            dimension=None,
            assess=None,
        )
    )
    for i, r in enumerate(rounds):
        dim, agent_q, cand_a, quality, issue, ev = r
        if i == 0:
            continue
        assess = {"answered": True, "quality": quality, "issue": issue, "evidence": ev}
        db.add(
            InterviewMessage(
                interview_id=interview.id,
                role="agent",
                text=agent_q,
                dimension=dim,
                assess=None,
            )
        )
        db.add(
            InterviewMessage(
                interview_id=interview.id,
                role="candidate",
                text=cand_a,
                dimension=dim,
                assess=json.dumps(assess, ensure_ascii=False),
            )
        )
    # 已完成面试补一条收尾语,让回放更完整
    if finished:
        db.add(
            InterviewMessage(
                interview_id=interview.id,
                role="agent",
                text=DEFAULT_CLOSING,
                dimension=None,
                assess=None,
            )
        )


def main():
    init_db()
    db = SessionLocal()
    try:
        # 1) 清空(按外键顺序)
        db.query(InterviewMessage).delete()
        db.query(Interview).delete()
        db.query(Candidate).delete()
        db.query(Job).delete()

        # 2) 岗位
        jobs = {}
        for j in JOBS:
            job = Job(title=j["title"], jd_text=j["jd_text"], dimensions=json.dumps(j["dimensions"], ensure_ascii=False))
            db.add(job)
            db.flush()
            jobs[j["title"]] = (job, j["dimensions"])
        db.commit()

        # 3) 候选人
        candidates = {}
        for c in CANDIDATES:
            cand = Candidate(
                name=c["basic"]["name"],
                resume_text=c["experience"][0]["summary"] if c["experience"] else "",
                parsed_resume=json.dumps(c, ensure_ascii=False),
                access_token_hash=hash_candidate_token(DEMO_ACCESS_TOKEN),
            )
            db.add(cand)
            db.flush()
            candidates[c["basic"]["name"]] = cand
        db.commit()

        # 4) 面试
        now = datetime.now()
        created = 0
        demo_interviews = []
        for spec in INTERVIEWS:
            job, dims = jobs[spec["job_title"]]
            cand = candidates[spec["candidate"]]
            finished = spec["finished"]

            iv = Interview(
                job_id=job.id,
                candidate_id=cand.id,
                status="finished" if finished else "probing",
                started_at=now - timedelta(days=1),
                ended_at=now if finished else None,
            )
            db.add(iv)
            db.flush()
            demo_interviews.append((iv.id, finished))

            rounds = spec["rounds"]
            state = _build_state(iv.id, dims, rounds, finished)
            iv.state = json.dumps(state, ensure_ascii=False)
            if finished:
                report = _build_report(
                    dims, rounds,
                    spec["summary_score"], spec["suggestion"],
                    spec["strengths"], spec["risks"], spec["next_step"],
                )
                iv.report = json.dumps(report, ensure_ascii=False)
            _record_messages(db, iv, dims, rounds, finished)
            created += 1

        db.commit()

        total_messages = db.query(InterviewMessage).count()
        total_candidates = db.query(Candidate).count()
        print("演示数据生成完成:")
        print(f"   - 岗位 {len(JOBS)} 个")
        print(f"   - 候选人 {total_candidates} 人")
        print(f"   - 面试 {created} 场(已完成 3 + 进行中 2,消息共 {total_messages} 条)")
        finished_id = next(i for i, finished in demo_interviews if finished)
        ongoing_id = next(i for i, finished in demo_interviews if not finished)
        print("   匿名凭证通过 URL fragment 传入,读取后会自动从地址栏清除:")
        print(
            "   - 已完成报告 "
            f"http://localhost:5173/admin/reports/{finished_id}#access_token={DEMO_ACCESS_TOKEN}"
        )
        print(
            "   - 进行中面试 "
            f"http://localhost:5173/interview/{ongoing_id}#access_token={DEMO_ACCESS_TOKEN}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
