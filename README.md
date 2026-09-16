# 知谱智航教学系统 (KnowledgeGraph-Navigator)


基于大模型的知识图谱教学平台，支持文档解析、知识图谱构建、个性化学习路径推荐与智能问答。

## 验收与测试

- 图谱关系支持 `prerequisite`、`related_to`、`part_of`；课程教师可在课程详情的“修正关系”中手动新增、删除关系，先修与包含关系会校验环路。
- 抽取验收集为 `backend/tests/fixtures/extraction_eval.json`，执行 `python tests/evaluate_extraction.py` 产出知识点精确率、召回率和 F1。RAG 验收集为 `backend/tests/fixtures/rag_eval.json`。启动服务并设置 `RAG_EVAL_TOKEN` 后执行 `python tests/evaluate_rag.py`，产出响应时间、引用命中率和幻觉线索报告。指标必须以报告实测为准。
- 后端启动时执行可重复 SQLite 迁移。抽取任务在后台执行，SQLite 是权威数据源；Neo4j 写入失败会保留待同步标记，教师可重试，不会重抽即删除已有学习进度、笔记和题目。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端框架 | Python FastAPI |
| 大模型 API | DeepSeek API |
| 图数据库 | Neo4j AuraDB |
| RAG 框架 | LangChain |
| 文档解析 | pdfplumber + python-docx |
| 文本预处理 | jieba + re |
| 关系数据库 | SQLite |
| 前端框架 | Vue 3 + Element Plus |
| 图谱可视化 | AntV G6 |
| HTTP 请求 | Axios |
| 状态管理 | Pinia |

## 项目结构

```
KnowledgeGraph-Navigator/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 应用入口
│   ├── requirements.txt     # Python 依赖
│   └── app/
│       ├── api/             # API 路由
│       ├── core/            # 配置与数据库连接
│       ├── services/        # 业务逻辑
│       ├── models/          # 数据模型
│       └── utils/           # 工具函数
├── frontend/                # Vue 3 前端
│   └── src/
│       ├── views/           # 页面
│       ├── components/      # 公共组件
│       ├── api/             # 接口调用
│       └── router/          # 路由
├── docs/                    # 项目文档
├── 开发文档.md               # 接口文档与开发规范
├── .env.example             # 环境变量模板
└── README.md
```

## 快速开始

### 环境要求

- Python 3.13
- Node.js 18+
- Neo4j AuraDB 实例

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env       # 编辑 .env 填入实际配置
python main.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 功能模块

1. **用户认证** — JWT 注册 / 登录 / 角色管理
2. **课程与图谱管理** — 课程 CRUD、文档上传、知识自动抽取
3. **学习进度追踪** — 知识点掌握标记、进度统计
4. **个性化路径推荐** — 基于拓扑排序的学习路径
5. **智能问答** — 基于 RAG 的知识检索与回答

## Git 规范

- 分支：`main`
- 提交格式：`<type>(<scope>): <subject>`
  - `feat` 新功能 | `fix` Bug修复 | `docs` 文档 | `refactor` 重构 | `perf` 性能优化
