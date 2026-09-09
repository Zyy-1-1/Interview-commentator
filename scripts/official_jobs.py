#!/usr/bin/env python
"""official_jobs.py — 官方精选岗位数据(多行业,真实公司/岗位/薪资梯度)。

数据来源(2026-09 检索,岗位结构与薪资区间取自):
- 互联网:腾讯 join.qq.com、字节 jobs.bytedance.com、华为 career.huawei.com 2027 届校招公告;
  薪资取牛客/小林coding 25-26 届开奖口径。
- 能源央企:国家电网 zhaopin.sgcc.com.cn、中国石化 job.sinopec.com 2026 招聘公告。
- 金融:工行/建行 2027 校招公告、中金 cicc.zhiye.com。
- 制造/新能源:比亚迪、宁德时代 2027 校招简章(高校就业网转载)。
- 快消:宝洁 careers.pg.com.cn、联合利华 UFLP 简章。
- 医药:恒瑞、药明康德 2026 校招。
- 游戏:米哈游、网易游戏雷火 2027 校招。
- 建筑:中建三局 2026 校招简章。
- 财会:普华永道 pwccn.com 校招(专业不限)。

维度(dimensions)结构与 app/agents/jd_analyzer 输出一致:
  {name, type(hard|soft), weight, keywords[], probe(None|"STAR")}
面试流程依赖此字段,故离线预写,不调用 LLM。
薪资 salary_min/max 单位:千元/月;salary_months 为年薪月数。
"""

OFFICIAL_JOBS = [
    # ============ 互联网 / 技术 ============
    {
        "title": "后台开发工程师(C++/Go)",
        "company": "腾讯",
        "category": "技术研发", "education": "本科",
        "salary_min": 24, "salary_max": 40, "salary_months": 15,
        "recruit_type": "校招", "majors": "计算机 / 软件工程 / 通信工程",
        "location": "深圳 / 广州 / 上海",
        "jd_text": (
            "负责腾讯亿级用户产品的后端服务设计与研发,支撑高并发、高可用架构;"
            "熟悉 C++/Go 之一及常用数据结构与算法,具备 MySQL、Redis、消息队列实战经验;"
            "能独立完成模块设计与性能调优,有良好的协作与工程素养。计算机及相关专业优先。"
        ),
        "dimensions": [
            {"name": "编程语言与基础", "type": "hard", "weight": 0.28, "keywords": ["C++", "Go", "数据结构", "算法"], "probe": None},
            {"name": "高并发与系统设计", "type": "hard", "weight": 0.27, "keywords": ["高并发", "缓存", "消息队列", "分布式"], "probe": None},
            {"name": "数据库与存储", "type": "hard", "weight": 0.15, "keywords": ["MySQL", "Redis", "索引", "分库分表"], "probe": None},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["协作", "推动", "对齐"], "probe": "STAR"},
            {"name": "学习与成长", "type": "soft", "weight": 0.15, "keywords": ["自驱", "复盘", "新技术"], "probe": "STAR"},
        ],
    },
    {
        "title": "大模型算法工程师",
        "company": "字节跳动",
        "category": "算法AI", "education": "硕士",
        "salary_min": 35, "salary_max": 60, "salary_months": 15,
        "recruit_type": "校招", "majors": "计算机 / 人工智能 / 数学 / 电子信息",
        "location": "北京 / 上海 / 杭州",
        "jd_text": (
            "参与大模型预训练、微调与推理优化,落地搜索/推荐/生成等场景;"
            "扎实的机器学习功底,熟悉 PyTorch 与 Transformer 体系,有 LLM 相关项目或论文优先;"
            "具备优秀的问题分析与快速实验能力。硕士及以上,计算机/AI/数学等相关专业。"
        ),
        "dimensions": [
            {"name": "机器学习基础", "type": "hard", "weight": 0.25, "keywords": ["深度学习", "Transformer", "优化", "泛化"], "probe": None},
            {"name": "大模型与训练", "type": "hard", "weight": 0.3, "keywords": ["LLM", "微调", "RLHF", "推理优化"], "probe": None},
            {"name": "工程实现", "type": "hard", "weight": 0.15, "keywords": ["Python", "PyTorch", "分布式训练"], "probe": None},
            {"name": "问题抽象与实验", "type": "soft", "weight": 0.15, "keywords": ["分析", "假设", "迭代"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["协作", "表达"], "probe": "STAR"},
        ],
    },
    {
        "title": "AI 算法工程师(社招)",
        "company": "华为",
        "category": "算法AI", "education": "硕士",
        "salary_min": 25, "salary_max": 40, "salary_months": 12,
        "recruit_type": "社招", "majors": "计算机 / 通信 / 数学 / 自动化",
        "location": "深圳 / 杭州 / 东莞",
        "jd_text": (
            "面向昇腾/华为云 AI 平台,负责视觉、语音或大模型方向的算法研发与工程化落地;"
            "熟练掌握 Python/C++,熟悉主流深度学习框架,有 1 年以上相关经验;"
            "具备良好的团队协作与抗压能力。硕士优先,计算机/通信/数学等相关专业。"
        ),
        "dimensions": [
            {"name": "算法与建模", "type": "hard", "weight": 0.3, "keywords": ["CV", "NLP", "模型优化", "调参"], "probe": None},
            {"name": "工程与落地", "type": "hard", "weight": 0.25, "keywords": ["Python", "C++", "部署", "性能"], "probe": None},
            {"name": "领域经验", "type": "hard", "weight": 0.15, "keywords": ["项目", "业务", "方案"], "probe": "STAR"},
            {"name": "协作与抗压", "type": "soft", "weight": 0.15, "keywords": ["跨团队", "攻坚", "沟通"], "probe": "STAR"},
            {"name": "责任心", "type": "soft", "weight": 0.15, "keywords": ["交付", "质量"], "probe": "STAR"},
        ],
    },
    {
        "title": "游戏客户端开发工程师",
        "company": "米哈游",
        "category": "技术研发", "education": "本科",
        "salary_min": 20, "salary_max": 35, "salary_months": 16,
        "recruit_type": "校招", "majors": "计算机 / 数字媒体技术 / 数学",
        "location": "上海",
        "jd_text": (
            "负责二次元开放世界游戏的客户端功能与渲染表现开发,基于 Unity/自研引擎;"
            "扎实的 C#/C++ 与计算机图形学基础,熟悉性能优化与内存管理;"
            "热爱游戏,有良好的审美与细节追求,团队协作意识强。计算机/数媒等专业优先,不限。"
        ),
        "dimensions": [
            {"name": "编程与引擎", "type": "hard", "weight": 0.28, "keywords": ["C#", "Unity", "C++", "脚本"], "probe": None},
            {"name": "图形与性能", "type": "hard", "weight": 0.25, "keywords": ["渲染", "Shader", "优化", "内存"], "probe": None},
            {"name": "数据结构算法", "type": "hard", "weight": 0.12, "keywords": ["算法", "数据结构"], "probe": None},
            {"name": "游戏理解与审美", "type": "soft", "weight": 0.17, "keywords": ["玩家视角", "体验", "细节"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.18, "keywords": ["跨职能", "策划美术", "协作"], "probe": "STAR"},
        ],
    },
    # ============ 制造 / 新能源 ============
    {
        "title": "电池材料研发工程师",
        "company": "宁德时代",
        "category": "制造研发", "education": "硕士",
        "salary_min": 18, "salary_max": 30, "salary_months": 12,
        "recruit_type": "校招", "majors": "材料科学 / 化学 / 电化学 / 能源动力",
        "location": "宁德 / 上海 / 江苏溧阳",
        "jd_text": (
            "从事动力电池正负极、电解液等材料的研发与性能优化,支撑产品迭代;"
            "材料/化学/电化学等相关专业硕士及以上,熟悉材料表征与电化学测试方法;"
            "具备实验设计、数据分析与跨部门协作能力。"
        ),
        "dimensions": [
            {"name": "材料与电化学基础", "type": "hard", "weight": 0.3, "keywords": ["锂电池", "电化学", "表征", "SEM/XRD"], "probe": None},
            {"name": "实验设计与分析", "type": "hard", "weight": 0.25, "keywords": ["实验", "数据", "失效分析", "DOE"], "probe": None},
            {"name": "工程落地", "type": "hard", "weight": 0.15, "keywords": ["工艺", "量产", "良率"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["跨部门", "项目"], "probe": "STAR"},
            {"name": "学习与钻研", "type": "soft", "weight": 0.15, "keywords": ["文献", "自驱"], "probe": "STAR"},
        ],
    },
    {
        "title": "机械设计工程师",
        "company": "比亚迪",
        "category": "制造研发", "education": "本科",
        "salary_min": 10, "salary_max": 16, "salary_months": 12,
        "recruit_type": "校招", "majors": "机械工程 / 车辆工程 / 机械设计制造",
        "location": "深圳 / 西安 / 长沙",
        "jd_text": (
            "负责汽车零部件/整机的结构设计、出图与试制跟进,参与工艺优化;"
            "机械/车辆工程等相关专业,熟练使用 SolidWorks/CATIA 等三维设计软件;"
            "具备扎实的工程图学基础与动手实践意识,团队协作良好。"
        ),
        "dimensions": [
            {"name": "结构设计", "type": "hard", "weight": 0.3, "keywords": ["SolidWorks", "公差", "机构", "强度"], "probe": None},
            {"name": "工程图学与材料", "type": "hard", "weight": 0.25, "keywords": ["制图", "材料", "工艺"], "probe": None},
            {"name": "项目与试制", "type": "hard", "weight": 0.15, "keywords": ["样件", "验证", "改进"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["工艺", "质量", "配合"], "probe": "STAR"},
            {"name": "踏实责任心", "type": "soft", "weight": 0.15, "keywords": ["细致", "交付"], "probe": "STAR"},
        ],
    },
    # ============ 能源央企 ============
    {
        "title": "电气工程师(变电检修方向)",
        "company": "国家电网",
        "category": "电力能源", "education": "本科",
        "salary_min": 8, "salary_max": 14, "salary_months": 12,
        "recruit_type": "校招", "majors": "电气工程及其自动化 / 电力系统",
        "location": "省会及地市供电单位",
        "jd_text": (
            "从事变电站设备运行、检修与缺陷处理,保障电网安全稳定;"
            "电工类专业(电气工程及其自动化等)本科及以上,通过大学英语四级;"
            "认同央企文化,能适应一线生产与应急值守,责任心与纪律性强。"
        ),
        "dimensions": [
            {"name": "电力系统专业知识", "type": "hard", "weight": 0.32, "keywords": ["变电", "一次设备", "继电保护", "安规"], "probe": None},
            {"name": "设备检修与运维", "type": "hard", "weight": 0.23, "keywords": ["巡视", "缺陷", "试验"], "probe": None},
            {"name": "安全与规范意识", "type": "hard", "weight": 0.15, "keywords": ["安全", "制度", "流程"], "probe": "STAR"},
            {"name": "纪律与责任心", "type": "soft", "weight": 0.15, "keywords": ["值守", "应急", "踏实"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["班组", "配合"], "probe": "STAR"},
        ],
    },
    {
        "title": "石油化工工艺研发工程师",
        "company": "中国石化",
        "category": "电力能源", "education": "硕士",
        "salary_min": 10, "salary_max": 18, "salary_months": 12,
        "recruit_type": "校招", "majors": "化学工程 / 石油工程 / 应用化学",
        "location": "北京 / 茂名 / 镇海",
        "jd_text": (
            "参与炼化装置工艺优化与新技术研发,支撑节能降耗与产品质量提升;"
            "化工/石化/应用化学等相关专业硕士及以上,具备扎实的实验与工艺分析能力;"
            "良好的文档表达与团队协作。"
        ),
        "dimensions": [
            {"name": "化工工艺基础", "type": "hard", "weight": 0.3, "keywords": ["反应工程", "分离", "催化", "流程"], "probe": None},
            {"name": "实验与数据分析", "type": "hard", "weight": 0.25, "keywords": ["实验", "表征", "优化"], "probe": None},
            {"name": "安全环保", "type": "hard", "weight": 0.15, "keywords": ["HSE", "规范", "风险"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["团队", "汇报"], "probe": "STAR"},
            {"name": "学习钻研", "type": "soft", "weight": 0.15, "keywords": ["技术", "自驱"], "probe": "STAR"},
        ],
    },
    # ============ 金融 ============
    {
        "title": "星辰管培生(科技菁英方向)",
        "company": "中国工商银行",
        "category": "金融", "education": "本科",
        "salary_min": 12, "salary_max": 18, "salary_months": 12,
        "recruit_type": "校招", "majors": "计算机 / 软件工程 / 电子信息 / 数学(部分不限)",
        "location": "各省市分行 / 总行科技部",
        "jd_text": (
            "面向全行数字化转型的金融科技人才培养项目,轮岗参与系统开发、数据分析与信息安全;"
            "本科及以上,毕业时间符合当届要求,计算机类优先、综合类岗位专业不限;"
            "学习能力强,具备良好的沟通与团队协作。每人可申报多家机构。"
        ),
        "dimensions": [
            {"name": "科技基础", "type": "hard", "weight": 0.28, "keywords": ["编程", "数据库", "数据分析", "信息安全"], "probe": None},
            {"name": "业务理解", "type": "hard", "weight": 0.2, "keywords": ["金融业务", "需求", "场景"], "probe": "STAR"},
            {"name": "逻辑与学习", "type": "hard", "weight": 0.17, "keywords": ["结构化", "自学"], "probe": None},
            {"name": "沟通协作", "type": "soft", "weight": 0.2, "keywords": ["团队", "表达"], "probe": "STAR"},
            {"name": "职业稳定性", "type": "soft", "weight": 0.15, "keywords": ["责任心", "认同"], "probe": "STAR"},
        ],
    },
    {
        "title": "投资银行部分析师",
        "company": "中金公司",
        "category": "金融", "education": "硕士",
        "salary_min": 30, "salary_max": 50, "salary_months": 12,
        "recruit_type": "校招", "majors": "金融 / 经济 / 会计 / 法律(硕士,顶尖院校)",
        "location": "北京 / 上海 / 深圳",
        "jd_text": (
            "参与 IPO、再融资、并购等投行项目的尽职调查、材料撰写与客户沟通;"
            "国内外顶尖院校硕士,金融/经济/会计/法律等专业,财务功底与英文能力扎实;"
            "CPA/CFA 通过部分科目优先,能承受高强度出差与项目节奏。"
        ),
        "dimensions": [
            {"name": "财务与估值", "type": "hard", "weight": 0.28, "keywords": ["财务分析", "估值", "三张表", "建模"], "probe": None},
            {"name": "资本市场知识", "type": "hard", "weight": 0.22, "keywords": ["IPO", "合规", "行业研究"], "probe": None},
            {"name": "尽职调查与写作", "type": "hard", "weight": 0.15, "keywords": ["底稿", "报告", "严谨"], "probe": "STAR"},
            {"name": "沟通与抗压", "type": "soft", "weight": 0.2, "keywords": ["客户", "协调", "强度"], "probe": "STAR"},
            {"name": "成就动机", "type": "soft", "weight": 0.15, "keywords": ["自驱", "目标"], "probe": "STAR"},
        ],
    },
    # ============ 财会 / 咨询 ============
    {
        "title": "审计助理(A1)",
        "company": "普华永道",
        "category": "财会审计", "education": "本科",
        "salary_min": 11, "salary_max": 14, "salary_months": 12,
        "recruit_type": "校招", "majors": "不限(财会 / 审计 / 金融 / 理工均可)",
        "location": "北京 / 上海 / 广州 / 深圳",
        "jd_text": (
            "参与年报审计与专项鉴证项目,执行函证、抽凭、底稿编制等程序;"
            "本科及以上,专业不限,欢迎财会、金融及理工背景,细致负责;"
            "良好的 Excel 与英文读写、沟通表达,能适应项目出差与忙季节奏。"
        ),
        "dimensions": [
            {"name": "财务与审计基础", "type": "hard", "weight": 0.3, "keywords": ["会计准则", "审计程序", "底稿", "内控"], "probe": None},
            {"name": "数据与工具", "type": "hard", "weight": 0.18, "keywords": ["Excel", "抽样", "核对"], "probe": None},
            {"name": "细致与严谨", "type": "hard", "weight": 0.14, "keywords": ["复核", "准确"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.2, "keywords": ["客户", "团队", "表达"], "probe": "STAR"},
            {"name": "抗压与学习", "type": "soft", "weight": 0.18, "keywords": ["忙季", "成长", "考证"], "probe": "STAR"},
        ],
    },
    # ============ 市场 / 供应链 ============
    {
        "title": "品牌管理培训生(Brand Builder)",
        "company": "宝洁 P&G",
        "category": "市场营销", "education": "本科",
        "salary_min": 16, "salary_max": 22, "salary_months": 14,
        "recruit_type": "校招", "majors": "不限(商科 / 文科 / 理工均可)",
        "location": "广州",
        "jd_text": (
            "负责品牌营销策略制定与生意增长,统筹产品、渠道、传播落地;"
            "本科及以上,专业不限,具备领导力、商业敏感度与数据分析能力;"
            "通过宝洁八大问式行为面试,英语良好,能适应快节奏。"
        ),
        "dimensions": [
            {"name": "商业分析与洞察", "type": "hard", "weight": 0.25, "keywords": ["市场", "数据", "增长", "用户"], "probe": None},
            {"name": "品牌与营销思维", "type": "hard", "weight": 0.22, "keywords": ["定位", "创意", "传播"], "probe": None},
            {"name": "领导力", "type": "soft", "weight": 0.2, "keywords": ["影响", "带团队", "担当"], "probe": "STAR"},
            {"name": "沟通表达", "type": "soft", "weight": 0.18, "keywords": ["提案", "协作"], "probe": "STAR"},
            {"name": "学习敏锐度", "type": "soft", "weight": 0.15, "keywords": ["快速", "复盘"], "probe": "STAR"},
        ],
    },
    {
        "title": "供应链管理培训生",
        "company": "联合利华",
        "category": "供应链制造", "education": "硕士",
        "salary_min": 15, "salary_max": 22, "salary_months": 13,
        "recruit_type": "校招", "majors": "物流 / 工业工程 / 食品 / 机械制造 / 电气",
        "location": "上海 / 合肥 / 天津",
        "jd_text": (
            "三年轮岗制培养,覆盖计划、采购、制造与物流配送全链路,推进智能制造;"
            "硕士及以上,供应链/工业工程/食品/机械等理工背景优先;"
            "具备数据分析、项目管理与跨部门沟通能力,英语良好。"
        ),
        "dimensions": [
            {"name": "供应链专业知识", "type": "hard", "weight": 0.28, "keywords": ["计划", "库存", "物流", "采购"], "probe": None},
            {"name": "数据与优化", "type": "hard", "weight": 0.22, "keywords": ["Excel", "建模", "改善"], "probe": None},
            {"name": "项目推进", "type": "hard", "weight": 0.15, "keywords": ["落地", "协同", "交付"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.2, "keywords": ["跨部门", "工厂"], "probe": "STAR"},
            {"name": "学习成长", "type": "soft", "weight": 0.15, "keywords": ["轮岗", "自驱"], "probe": "STAR"},
        ],
    },
    # ============ 医药 ============
    {
        "title": "药物研发研究员(制剂方向)",
        "company": "恒瑞医药",
        "category": "医药研发", "education": "硕士",
        "salary_min": 12, "salary_max": 20, "salary_months": 12,
        "recruit_type": "校招", "majors": "药剂学 / 药学 / 制药工程 / 化学",
        "location": "连云港 / 上海 / 苏州",
        "jd_text": (
            "负责药物制剂处方设计、工艺开发与质量研究,支撑新药申报;"
            "药剂/药学/化学等相关专业硕士及以上,熟悉制剂实验与表征方法;"
            "严谨的科研素养与文献能力,良好的团队协作。"
        ),
        "dimensions": [
            {"name": "制剂专业知识", "type": "hard", "weight": 0.3, "keywords": ["处方", "工艺", "稳定性", "溶出"], "probe": None},
            {"name": "实验与分析能力", "type": "hard", "weight": 0.25, "keywords": ["表征", "数据", "方法开发"], "probe": None},
            {"name": "法规与质量", "type": "hard", "weight": 0.15, "keywords": ["GMP", "申报", "规范"], "probe": None},
            {"name": "科研严谨", "type": "soft", "weight": 0.15, "keywords": ["文献", "复现", "细致"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["团队", "跨部门"], "probe": "STAR"},
        ],
    },
    {
        "title": "生物分析研究员",
        "company": "药明康德",
        "category": "医药研发", "education": "硕士",
        "salary_min": 12, "salary_max": 18, "salary_months": 12,
        "recruit_type": "校招", "majors": "生物学 / 药学 / 生物化学 / 分析化学",
        "location": "上海 / 苏州",
        "jd_text": (
            "在 CXO 平台承担药物生物分析项目方法开发与样本检测,交付客户研究数据;"
            "生物/药学/分析化学相关专业硕士及以上,熟悉 LC-MS/MS 或免疫分析方法;"
            "项目制快节奏,需要良好的时间管理与沟通协作能力。"
        ),
        "dimensions": [
            {"name": "生物分析方法", "type": "hard", "weight": 0.3, "keywords": ["LC-MS", "ELISA", "方法验证", "药代"], "probe": None},
            {"name": "实验操作与数据", "type": "hard", "weight": 0.25, "keywords": ["规范", "图谱", "处理"], "probe": None},
            {"name": "项目交付", "type": "hard", "weight": 0.15, "keywords": ["进度", "质量", "客户"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["团队", "跨部门"], "probe": "STAR"},
            {"name": "抗压与细心", "type": "soft", "weight": 0.15, "keywords": ["节奏", "准确"], "probe": "STAR"},
        ],
    },
    # ============ 游戏策划 ============
    {
        "title": "游戏系统策划",
        "company": "网易游戏(雷火)",
        "category": "产品策划", "education": "本科",
        "salary_min": 15, "salary_max": 25, "salary_months": 14,
        "recruit_type": "校招", "majors": "不限(中文 / 数字媒体 / 数学 / 心理等)",
        "location": "杭州 / 广州",
        "jd_text": (
            "负责游戏玩法系统设计、数值与规则搭建,撰写策划文档并跟进实现;"
            "本科及以上,专业不限,热爱游戏且有大量深度游戏经历;"
            "优秀的逻辑思维、文案表达与跨职能沟通能力,会用 Excel/原型工具。"
        ),
        "dimensions": [
            {"name": "系统与规则设计", "type": "hard", "weight": 0.28, "keywords": ["玩法", "数值", "系统", "体验"], "probe": None},
            {"name": "逻辑与数据", "type": "hard", "weight": 0.22, "keywords": ["数值表", "平衡", "分析"], "probe": None},
            {"name": "文案与表达", "type": "hard", "weight": 0.15, "keywords": ["文档", "沟通", "叙事"], "probe": None},
            {"name": "游戏理解", "type": "soft", "weight": 0.2, "keywords": ["玩家视角", "竞品", "拆解"], "probe": "STAR"},
            {"name": "团队协作", "type": "soft", "weight": 0.15, "keywords": ["程序美术", "推进"], "probe": "STAR"},
        ],
    },
    # ============ 土木建筑 ============
    {
        "title": "土建工程师(施工方向)",
        "company": "中建三局",
        "category": "土木建筑", "education": "本科",
        "salary_min": 8, "salary_max": 12, "salary_months": 12,
        "recruit_type": "校招", "majors": "土木工程 / 工程管理 / 建筑工程",
        "location": "全国项目(以城市为中心)",
        "jd_text": (
            "负责项目现场施工组织、进度与质量安全管控,参与技术交底;"
            "土木/工程管理等相关专业本科及以上,能接受项目驻场与流动;"
            "踏实肯干、责任心与执行力强,具备良好的沟通协调。"
        ),
        "dimensions": [
            {"name": "专业技术", "type": "hard", "weight": 0.3, "keywords": ["结构", "施工图", "规范", "测量"], "probe": None},
            {"name": "施工组织与进度", "type": "hard", "weight": 0.22, "keywords": ["计划", "协调", "现场"], "probe": None},
            {"name": "质量安全", "type": "hard", "weight": 0.15, "keywords": ["验收", "隐患", "交底"], "probe": "STAR"},
            {"name": "执行与吃苦", "type": "soft", "weight": 0.18, "keywords": ["驻场", "抗压", "踏实"], "probe": "STAR"},
            {"name": "沟通协作", "type": "soft", "weight": 0.15, "keywords": ["班组", "监理", "配合"], "probe": "STAR"},
        ],
    },
    # ============ 实习(覆盖实习类型)============
    {
        "title": "数据分析实习生(日常实习)",
        "company": "字节跳动",
        "category": "数据分析", "education": "本科",
        "salary_min": 3, "salary_max": 5, "salary_months": 12,
        "recruit_type": "实习", "majors": "统计 / 数学 / 计算机 / 经济学(在读)",
        "location": "北京 / 上海",
        "jd_text": (
            "支持业务团队的数据提取、清洗与看板搭建,产出分析小报告;"
            "在读本科/硕士,熟练 SQL 与 Excel,了解 Python 优先;"
            "细心、沟通顺畅,每周到岗 4 天以上,实习 3 个月起。日薪 300-450 元。"
        ),
        "dimensions": [
            {"name": "SQL 与数据处理", "type": "hard", "weight": 0.32, "keywords": ["SQL", "清洗", "取数", "埋点"], "probe": None},
            {"name": "统计与分析", "type": "hard", "weight": 0.25, "keywords": ["指标", "漏斗", "归因"], "probe": None},
            {"name": "工具表达", "type": "hard", "weight": 0.15, "keywords": ["Excel", "看板", "Python"], "probe": None},
            {"name": "沟通与细心", "type": "soft", "weight": 0.15, "keywords": ["对接", "准确"], "probe": "STAR"},
            {"name": "学习意愿", "type": "soft", "weight": 0.13, "keywords": ["主动", "成长"], "probe": "STAR"},
        ],
    },
]
