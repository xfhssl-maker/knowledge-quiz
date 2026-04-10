# Knowledge Quiz 参考文档

## 目录

1. [系统架构](#系统架构)
2. [数据模型](#数据模型)
3. [题目生成规则](#题目生成规则)
4. [记忆曲线算法](#记忆曲线算法)
5. [Dashboard 组件](#dashboard-组件)
6. [API 参考](#api-参考)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge Quiz Skill                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ 输入解析层    │  │ 题目生成层    │  │ 记忆分析层    │       │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤       │
│  │ • PDF 解析   │  │ • 填空题生成  │  │ • 正确率计算  │       │
│  │ • MD 解析    │  │ • 选择题生成  │  │ • 遗忘曲线    │       │
│  │ • TXT 解析   │  │ • 判断题生成  │  │ • 掌握度分析  │       │
│  │ • JSON 解析  │  │ • 难度评估    │  │ • 错题追踪    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         ↓                  ↓                  ↓               │
│  ┌──────────────────────────────────────────────────┐        │
│  │              数据持久化层                          │        │
│  │  JSON 文件存储 | 增量更新 | 会话管理               │        │
│  └──────────────────────────────────────────────────┘        │
│         ↓                  ↓                  ↓               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ 答题交互      │  │ Web Dashboard │  │ 导出功能      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 数据模型

### 知识点 (Knowledge Point)

```json
{
  "id": "kp-001",
  "title": "变量与数据类型",
  "content": "Python 中的变量不需要声明类型...",
  "keywords": ["变量", "数据类型", "int", "str"],
  "difficulty": 2,
  "source": "knowledge.md",
  "created_at": "2026-04-10T10:00:00Z"
}
```

### 题目 (Question)

```json
{
  "id": "q-001",
  "type": "fill-blank",
  "knowledge_point_id": "kp-001",
  "question": "Python 中的变量不需要声明____，解释器会自动推断。",
  "answer": "类型",
  "options": null,
  "difficulty": 2,
  "tags": ["变量", "基础"],
  "created_at": "2026-04-10T10:05:00Z"
}
```

### 答题记录 (Answer Record)

```json
{
  "id": "ar-001",
  "question_id": "q-001",
  "user_answer": "类型",
  "correct": true,
  "time_spent_ms": 3500,
  "answered_at": "2026-04-10T11:00:00Z",
  "session_id": "session-20260410-001"
}
```

### 记忆分析 (Memory Analysis)

```json
{
  "knowledge_point_id": "kp-001",
  "total_attempts": 5,
  "correct_count": 4,
  "accuracy": 0.8,
  "first_review": "2026-04-10",
  "last_review": "2026-04-12",
  "next_review": "2026-04-19",
  "mastery_level": "良好",
  "forgetting_stage": 2
}
```

---

## 题目生成规则

### 填空题生成

1. **关键词提取**：识别句子中的关键名词、动词、形容词
2. **挖空策略**：
   - 优先挖空专有名词、术语
   - 避免挖空虚词、连接词
   - 每题挖空 1-2 处
3. **答案标准化**：统一大小写、去除多余空格

### 选择题生成

1. **正确答案**：从知识点中提取关键信息
2. **干扰项生成**：
   - 同类但错误的选项
   - 相似概念的混淆项
   - 常见错误理解
3. **选项顺序**：随机打乱，记录正确答案位置

### 判断题生成

1. **陈述转换**：将知识点转为陈述句
2. **错误变体**：
   - 替换关键词为错误值
   - 添加绝对化词语（"必须"、"一定"）
   - 颠倒因果关系
3. **平衡性**：保持正确/错误题目比例约 1:1

---

## 记忆曲线算法

### 艾宾浩斯遗忘曲线

基于经典艾宾浩斯曲线，结合用户答题表现调整：

```python
class ForgettingCurve:
    """遗忘曲线计算器"""

    BASE_INTERVALS = [1, 3, 7, 14, 30]  # 基础复习间隔（天）

    def calculate_next_review(self, correct_streak, accuracy, last_review):
        """
        计算下次复习时间

        Args:
            correct_streak: 连续正确次数
            accuracy: 该知识点总体正确率
            last_review: 上次复习时间

        Returns:
            下次复习日期
        """
        # 基础间隔
        base_days = self.BASE_INTERVALS[min(correct_streak, len(self.BASE_INTERVALS) - 1)]

        # 根据正确率调整
        adjustment = 1.0 + (accuracy - 0.5)  # -0.5 ~ +0.5

        final_days = max(1, int(base_days * adjustment))

        return last_review + timedelta(days=final_days)

    def get_retention_rate(self, days_since_review, difficulty=1):
        """
        计算记忆保持率

        公式: R = e^(-t/S)
        - R: 保持率
        - t: 时间（天）
        - S: 记忆强度（与难度成反比）
        """
        strength = 10 / difficulty  # 难度越高，记忆强度越低
        return math.exp(-days_since_review / strength)
```

### 掌握度评估

| 等级 | 条件 | 说明 |
|------|------|------|
| 未学习 | 答题次数 = 0 | 需要首次学习 |
| 初识 | 正确率 < 50% | 需要加强理解 |
| 学习中 | 50% ≤ 正确率 < 80% | 持续练习 |
| 良好 | 80% ≤ 正确率 < 95% | 定期复习 |
| 掌握 | 正确率 ≥ 95% 且连续正确 ≥ 5 次 | 可延长复习间隔 |

---

## Dashboard 组件

### 1. 总体统计卡片

```
┌─────────────────────────────────────────┐
│  📊 学习概览                             │
├─────────────────────────────────────────┤
│  总题数: 100    已答: 85    正确率: 85%  │
│  今日答题: 20    今日正确: 17 (85%)      │
│  待复习: 15 题                          │
└─────────────────────────────────────────┘
```

### 2. 知识点掌握度雷达图

```javascript
const radarData = {
  labels: ['基础概念', '语法', '数据结构', '算法', '应用'],
  datasets: [{
    label: '掌握度',
    data: [90, 75, 80, 60, 70],
    backgroundColor: 'rgba(54, 162, 235, 0.2)',
    borderColor: 'rgba(54, 162, 235, 1)'
  }]
};
```

### 3. 遗忘曲线预测图

```
记忆保持率
100% │●
 80% │●●
 60% │  ●●
 40% │    ●●
 20% │      ●●
  0% └─────────────────
     1  3  7  14  30 天
```

### 4. 错题列表

```
┌──────────────────────────────────────────────────────┐
│ ❌ 错题记录                                            │
├──────────────────────────────────────────────────────┤
│ 1. [填空] Python 中的变量不需要声明____                │
│    你的答案: 值    正确答案: 类型    错误次数: 2       │
├──────────────────────────────────────────────────────┤
│ 2. [选择] 以下哪个不是 Python 数据类型？              │
│    你的答案: B    正确答案: C    错误次数: 1          │
└──────────────────────────────────────────────────────┘
```

### 5. 复习提醒

```
📅 今日待复习 (2026-04-10)
├── 🔴 紧急: 5 题（已超期）
├── 🟡 今日: 10 题
└── 🟢 未来 3 天: 15 题
```

---

## API 参考

### 命令行接口

```bash
# 创建题库
/knowledge-quiz <file_or_directory>

# 继续学习
/knowledge-quiz --resume [--session <session_id>]

# 查看报告
/knowledge-quiz --report [--format json|html]

# 复习错题
/knowledge-quiz --review-wrong

# 重置进度
/knowledge-quiz --reset [--knowledge-point <id>]
```

### 数据文件接口

```python
# 读取知识点
knowledge_points = read_json('knowledge-points.json')

# 读取题库
questions = read_json('questions.json')

# 记录答案
def record_answer(question_id, user_answer, time_spent_ms):
    record = {
        "id": generate_id(),
        "question_id": question_id,
        "user_answer": user_answer,
        "correct": check_answer(question_id, user_answer),
        "time_spent_ms": time_spent_ms,
        "answered_at": datetime.now().isoformat()
    }
    append_to_json('answers.json', record)

# 获取记忆分析
def get_memory_analysis(knowledge_point_id):
    answers = filter_by_knowledge_point('answers.json', knowledge_point_id)
    return calculate_memory_metrics(answers)
```

---

## 扩展开发

### 添加新题型

1. 在 `SKILL.md` 中定义题型格式
2. 在题目生成逻辑中添加生成函数
3. 更新 Dashboard 渲染逻辑

### 添加新输入格式

1. 创建解析器函数
2. 在输入检测逻辑中添加格式识别
3. 更新文档

### 自定义遗忘曲线

修改 `ForgettingCurve.BASE_INTERVALS` 参数：

```python
# 更激进的复习间隔
BASE_INTERVALS = [1, 2, 4, 7, 15, 30, 60]

# 更保守的复习间隔
BASE_INTERVALS = [0.5, 1, 2, 4, 7, 14, 30]
```
