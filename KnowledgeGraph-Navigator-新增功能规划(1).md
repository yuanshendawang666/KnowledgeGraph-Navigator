# 知谱智航 — 新增功能规划

> 创建日期：2026-08-10
> 基于当前版本（v1.0 全部完成）进行功能扩展

---

## 当前已实现 vs 待新增 对照

| # | 功能 | 当前状态 | 目标 |
|---|---|---|---|
| 1 | 用户推荐 | 仅课程级推荐（拓扑排序 + 进度 → Top5） | 增加个人画像（专业 + 掌握度 + 学习风格）→ 多维度推荐 |
| 2 | 知识点关系类型 | 3 种（prerequisite / related_to / part_of） | ✅ 已达标，可增加 UI 端的可视化区分 |
| 3 | 智能对话历史 | 无（每次问答独立） | 多轮对话上下文 + 历史记录持久化 |
| 4 | OCR | 无（仅 pdfplumber + python-docx） | 支持扫描件 / 图片文字识别 |
| 5 | 学习进度评判 | 手动标记（not_started / in_progress / mastered） | AI 对话式自动评判掌握度 |
| 6 | 学习笔记 | 无 | 用户自建笔记，关联知识点 |
| 7 | 知识点详情 | 仅图谱节点展示 | 点击节点 → 独立详情页（定义/例题/关联/笔记） |
| 8 | AI 出题 | 已有 quiz 模块混在练习中 | 独立为单独模块，教师可管理题库 |
| 9 | 班级系统 | 无 | 教师创建班级、批量管理学生 |

---

## 一、用户推荐增强

**目标**：根据用户专业背景、知识掌握情况、学习行为，给出个性化学习路径与策略建议。

### 1.1 新增数据

| 字段 | 说明 |
|---|---|
| `User.major` | 用户专业（计算机科学 / 数学 / 物理 等） |
| `User.grade` | 年级 |
| `User.learning_goal` | 学习目标（应试 / 兴趣 / 考研 等） |
| `LearningBehavior` 表 | 记录学习时长、答题正确率趋势、薄弱知识点 |

### 1.2 推荐维度

```
推荐引擎
├── 知识缺口分析：Neo4j 拓扑 → 先修未掌握节点
├── 难度梯度匹配：基于用户当前掌握率推荐合适难度
├── 学习节奏建议：基于行为数据推荐每日学习量
├── 关联拓展：已掌握 A → 推荐相关知识点 B、C
└── 专业路径：根据专业匹配推荐学习路线
```

### 1.3 实现要点

- **后端**：新增 `recommender_v2.py`，整合用户画像 + 行为数据 + 图谱拓扑
- **API**：`GET /api/learning/recommend-v2/{course_id}` 返回带理由的推荐列表
- **前端**：推荐卡片展示"为什么推荐"，含置信度与预计学习时长

---

## 二、知识点关系类型可视化

**目标**：系统已支持 3 种关系类型，前端图谱需用不同线型/颜色区分。

### 2.1 已支持的关系类型

| 关系类型 | 英文标识 | 含义 | 图谱可视化 |
|---|---|---|---|
| 先修关系 | `prerequisite` | A 是 B 的前置知识 | 🔴 红色有向箭头 |
| 相关关系 | `related_to` | A 与 B 相互关联 | 🔵 蓝色虚线 |
| 包含关系 | `part_of` | A 是 B 的子知识点 | 🟢 绿色实线 |

### 2.2 实现要点

- **AntV G6** 自定义边样式：不同 `edge.type` → 不同颜色 + 线型 + 箭头
- **图例**：图谱左下角增加关系图例 Legend
- **筛选器**：可按关系类型筛选显示

---

## 三、智能对话历史

**目标**：QA 问答支持多轮对话上下文，并可查看历史对话记录。

### 3.1 新增数据模型

```python
class ChatSession(Base):
    id: int                    # 会话 ID
    user_id: int               # 用户
    course_id: int             # 关联课程
    title: str                 # 会话标题（自动生成）
    created_at: datetime
    updated_at: datetime

class ChatMessage(Base):
    id: int
    session_id: int            # 所属会话
    role: str                  # user / assistant
    content: str               # 消息内容
    references: JSON           # RAG 引用来源
    created_at: datetime
```

### 3.2 功能点

- 多轮对话：发送最近 N 轮上下文给 DeepSeek
- 会话管理：新建 / 切换 / 删除 / 重命名会话
- 历史搜索：按关键词搜索历史消息
- 导出：对话导出为 Markdown / PDF

### 3.3 API

| 端点 | 说明 |
|---|---|
| `POST /api/qa/sessions` | 新建会话 |
| `GET /api/qa/sessions` | 会话列表 |
| `GET /api/qa/sessions/{id}/messages` | 消息历史 |
| `DELETE /api/qa/sessions/{id}` | 删除会话 |
| `POST /api/qa/ask` | 发送消息（增加 `session_id` 参数） |

---

## 四、OCR 文档识别

**目标**：支持扫描件 PDF / 图片上传，识别其中文字并纳入知识提取流水线。

### 4.1 技术方案

| 方案 | 适用场景 | 优缺点 |
|---|---|---|
| **PaddleOCR**（推荐） | 中文扫描件、手写体 | 中文识别率高、离线部署、免费 |
| Tesseract | 印刷体英文 | 中文效果一般 |
| 百度 OCR API | 高精度需求 | 需付费、需联网 |

### 4.2 流水线集成

```
上传文件 → 类型检测 → [文字型] → pdfplumber / python-docx
                     → [扫描型] → OCR 引擎 → 文字提取
                     → [图片型] → OCR 引擎 → 文字提取
       → 统一文本 → DeepSeek 知识提取 → Neo4j 写入
```

### 4.3 实现要点

- **后端**：新增 `ocr.py` 服务，封装 PaddleOCR
- **文件类型检测**：判断 PDF 是否为扫描版（无嵌入文字层）
- **前端**：上传时支持拖入图片（PNG / JPG / TIFF）

---

## 五、AI 对话式学习进度评判

**目标**：不再手动标记掌握状态，通过 AI 对话自动评估学生对知识点的掌握程度。

### 5.1 流程设计

```
学生选择知识点 → AI 发起对话问答（2-5 轮）
    → 学生回答
    → AI 追问深挖
    → AI 综合评判：掌握度 + 薄弱点 + 建议
    → 自动更新 UserKnowledgeProgress
```

### 5.2 评判维度

| 维度 | 说明 |
|---|---|
| 概念理解 | 能否用自己的话解释知识点 |
| 应用能力 | 能否举例或解决简单问题 |
| 关联认知 | 能否说出该知识点与其他的关系 |
| 综合评分 | 0-100 分 → 映射为 not_started / in_progress / mastered |

### 5.3 API

| 端点 | 说明 |
|---|---|
| `POST /api/learning/evaluate/start` | 开始评判对话 |
| `POST /api/learning/evaluate/reply` | 学生回复，AI 追问 / 评判 |
| `GET /api/learning/evaluate/result/{id}` | 获取评判结果 |

---

## 六、学习笔记

**目标**：用户可为知识点创建个人笔记，支持 Markdown 编辑。

### 6.1 数据模型

```python
class Note(Base):
    id: int
    user_id: int
    knowledge_point_id: int   # 关联知识点
    course_id: int             # 关联课程
    title: str
    content: str               # Markdown 格式
    tags: str                  # 逗号分隔标签
    is_public: bool            # 是否公开（教师可设公开笔记）
    created_at: datetime
    updated_at: datetime
```

### 6.2 功能点

- Markdown 编辑器（集成 Cherry Markdown 或 Toast UI Editor）
- 笔记关联知识点（自动获取知识点名称作为标签）
- 公开笔记广场（课程内可见）
- 搜索与筛选（按知识点 / 标签 / 时间）

### 6.3 API

| 端点 | 说明 |
|---|---|
| `POST /api/notes/` | 创建笔记 |
| `GET /api/notes/?kp_id=&course_id=` | 笔记列表 |
| `PUT /api/notes/{id}` | 编辑笔记 |
| `DELETE /api/notes/{id}` | 删除笔记 |
| `GET /api/notes/public/{course_id}` | 公开笔记 |

---

## 七、知识点详情页

**目标**：从图谱中点击节点，进入独立详情页查看更多信息。

### 7.1 详情页内容

```
知识点详情页
├── 基本信息：名称、描述、标签、所属课程
├── 关系图谱子图：该节点 + 1 跳邻居
├── 学习状态：当前用户对该知识点的掌握度
├── AI 生成内容：
│   ├── 详细讲解
│   ├── 典型例题（2-3 道）
│   └── 常见误区
├── 相关笔记：用户自己的笔记 + 公开笔记
├── 关联文档：该知识点来源于哪些文档
└── 操作区：标记掌握 / 开始评判 / 添加笔记 / AI 提问
```

### 7.2 实现要点

- **后端**：`GET /api/knowledge/{id}` 聚合以上所有信息
- **前端**：新增 `KnowledgeDetailView.vue`
- **图谱联动**：`KnowledgeGraph.vue` 节点 click 事件 → 路由跳转详情页

---

## 八、AI 出题独立模块

**目标**：将现有的 quiz 功能抽离为独立模块，增加教师管理能力。

### 8.1 当前状态

> quiz 模块已有：自适应出题（adaptive）、知识点出题、错题本、答题判分。代码位于 `quiz.py`（API） + `PracticeView.vue`（前端）。

### 8.2 独立模块规划

```
AI 出题模块
├── 学生端（已有 PracticeView）
│   ├── 自适应练习
│   ├── 知识点专项
│   └── 错题重练
├── 教师端（新增 TeacherQuizView）
│   ├── 手动创建题目
│   ├── AI 批量生成题目
│   ├── 题目审核 / 编辑
│   └── 题库管理（按知识点分类）
└── 题目模型增强
    ├── 难度标签细化（1-5 星）
    ├── 题目解析（AI 生成解题步骤）
    └── 使用统计（被练习次数 / 正确率）
```

### 8.3 新增 API

| 端点 | 说明 |
|---|---|
| `POST /api/quiz/questions/generate` | AI 批量生成题目（指定知识点 + 数量 + 难度） |
| `GET /api/quiz/questions/?kp_id=&difficulty=` | 题库查询 |
| `PUT /api/quiz/questions/{id}` | 编辑题目 |
| `DELETE /api/quiz/questions/{id}` | 删除题目 |
| `GET /api/quiz/questions/stats` | 题目使用统计 |
| `POST /api/quiz/questions/review` | 批量审核题目 |

### 8.4 前端新页面

- `TeacherQuizView.vue`：题库管理页
- `QuestionEditor.vue`：题目编辑器组件
- 现有 `PracticeView.vue` 保持不变（学生练习入口）

---

## 九、班级系统

**目标**：支持教师创建班级、批量管理学生、查看班级学习情况。

### 9.1 数据模型

```python
class Classroom(Base):
    id: int
    name: str                  # 班级名称
    teacher_id: int            # 教师用户 ID
    description: str
    invite_code: str           # 邀请码（学生加入用）
    created_at: datetime

class ClassroomMember(Base):
    id: int
    classroom_id: int
    student_id: int
    joined_at: datetime

class ClassroomCourse(Base):
    id: int
    classroom_id: int
    course_id: int             # 班级关联课程
```

### 9.2 功能点

- **教师端**
  - 创建 / 管理班级
  - 生成邀请码（学生凭码加入）
  - 查看班级学生列表
  - 班级整体学习统计（各知识点掌握率、平均进度）
  - 批量布置学习任务（指定课程 + 截止日期）
- **学生端**
  - 凭邀请码加入班级
  - 查看班级课程
  - 查看自己在班级中的学习排名（可选）

### 9.3 API

| 端点 | 说明 |
|---|---|
| `POST /api/classrooms/` | 创建班级 |
| `GET /api/classrooms/` | 班级列表（教师看自己的 / 学生看已加入的） |
| `POST /api/classrooms/{id}/join` | 学生加入（需邀请码） |
| `GET /api/classrooms/{id}/members` | 班级成员 |
| `GET /api/classrooms/{id}/stats` | 班级学习统计 |
| `POST /api/classrooms/{id}/tasks` | 布置学习任务 |

---

## 工作量预估

| # | 功能 | 后端工作量 | 前端工作量 | 优先级 |
|---|---|---|---|---|
| 1 | 用户推荐增强 | 中（3-4天） | 小（1-2天） | ⭐⭐⭐ |
| 2 | 关系类型可视化 | — | 小（1天） | ⭐⭐ |
| 3 | 智能对话历史 | 中（2-3天） | 中（2-3天） | ⭐⭐⭐ |
| 4 | OCR | 中（2-3天） | 小（1天） | ⭐⭐⭐ |
| 5 | 对话式学习评判 | 大（4-5天） | 中（2-3天） | ⭐⭐ |
| 6 | 学习笔记 | 小（1-2天） | 中（3-4天） | ⭐⭐⭐ |
| 7 | 知识点详情 | 中（2天） | 中（3-4天） | ⭐⭐⭐ |
| 8 | AI 出题独立模块 | 中（3-4天） | 大（4-5天） | ⭐⭐ |
| 9 | 班级系统 | 大（4-5天） | 大（4-5天） | ⭐⭐ |

> **总预估**：后端约 22-30 天，前端约 20-28 天。建议分 3 个迭代推进。

---

## 建议迭代计划

### 迭代一（优先做，约 2 周）

1. 智能对话历史（#3）
2. 知识点详情页（#7）
3. 学习笔记（#6）

### 迭代二（约 2 周）

4. 用户推荐增强（#1）
5. OCR 文档识别（#4）
6. 关系类型可视化（#2）

### 迭代三（约 2-3 周）

7. AI 出题独立模块（#8）
8. 对话式学习评判（#5）
9. 班级系统（#9）
