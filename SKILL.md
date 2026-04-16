---
name: knowledge-quiz
description: 根据知识库数据文档生成选择题，通过 Gradio 界面答题，支持错题集、知识点分类学习、学习报告。
type: skill
triggers:
  - /knowledge-quiz
tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
inputs:
  - PDF 文档
  - Markdown 文件
  - 纯文本
  - JSON 数据
outputs:
  - 题目 JSON
  - 知识点 JSON
  - Gradio Web 应用
  - 学习报告
version: 5.0.0
---

# Knowledge Quiz Skill v5.0

根据知识库文档自动生成选择题，通过 Gradio Web 界面进行答题、复习、学习。
支持任意学科领域，不限定医学等特定领域。

## 核心流程

```
OCR → AI 生成知识库 → AI 出题 → Gradio 界面
```

### Step 1: OCR / 文本提取

从 PDF 或其他文档提取文本内容。

```bash
# 支持 PDF 文本层提取
python pipeline.py input.pdf

# 或使用已有的 OCR 结果
python pipeline.py knowledge.txt
```

### Step 2: AI 生成知识库

从提取的文本智能分析并生成结构化知识点。

```python
from kb_generator import KnowledgeBaseGenerator

generator = KnowledgeBaseGenerator()
kb_data = generator.parse_text_content(text, "知识库")
generator.save("knowledge-base.json")
```

**知识点格式**：
```json
{
  "id": "kp-001",
  "section": "基础知识",
  "topic": "核心概念",
  "title": "变量与数据类型",
  "content": "Python 中的变量不需要声明类型，解释器会自动推断。",
  "keywords": ["变量", "数据类型"],
  "difficulty": 2
}
```

### Step 3: AI 出题

根据知识点智能生成选择题。

```python
from question_generator import QuestionGenerator

generator = QuestionGenerator()
questions = generator.generate_from_knowledge_base("knowledge-base.json")
generator.save("questions.json")
```

**选择题格式**：
```json
{
  "id": "q-001",
  "type": "choice",
  "section": "基础知识",
  "topic": "核心概念",
  "question": "【基础知识】关于「变量与数据类型」，以下哪项描述是正确的？",
  "options": ["A. 解释器会自动推断类型", "B. 该说法不正确", "C. 该说法部分正确", "D. 以上都不对"],
  "answer": "A",
  "explanation": "Python 中的变量不需要声明类型，解释器会自动推断。"
}
```

### Step 4: 启动 Gradio 界面

```bash
python quiz_app_v4.py
# 或
python pipeline.py --gradio
```

访问地址：http://127.0.0.1:7866

## 使用方法

### 快速开始

```bash
# 完整流程：导入 PDF → 生成知识库 → 出题 → 启动界面
python pipeline.py knowledge.pdf

# 仅启动界面（使用已有数据）
python pipeline.py --gradio
```

### Gradio 界面功能

| 模块 | 功能 |
|------|------|
| 开始答题 | 按章节筛选，选项完整显示 |
| 错题集 | 错题列表、薄弱知识点分析 |
| 知识点学习 | 按章节查看知识点卡片 |
| 学习报告 | 正确率、进度统计 |

## 文件结构

```
~/.knowledge-quiz/
├── pipeline.py              # 主流程脚本
├── kb_generator.py          # AI 知识库生成器
├── question_generator.py    # AI 题目生成器
├── quiz_app_v4.py           # Gradio 界面 (推荐)
├── parse_smart.py           # 智能文本解析器
├── knowledge-base.json      # 知识库数据
├── questions.json           # 题库数据
├── answers.json             # 答题记录
└── cache/                   # OCR 缓存
```

## 智能出题策略

### 选择题生成

1. **数值型**：提取知识点中的数值，生成四选一
   - 问法：`"关于XX，正确的数值是？"`
   - 选项：正确数值 + 3 个干扰项

2. **定义型**：提取术语和定义
   - 问法：`"XX是什么？"`
   - 选项：正确定义 + 3 个干扰项

3. **内容型**：知识点内容作为正确选项
   - 问法：`"关于XX，以下哪项描述是正确的？"`
   - 选项：正确描述 + 3 个干扰项

4. **简单型**：内容较短时的简化选择题

### 内容完整性检测

```python
def is_content_complete(content: str) -> bool:
    """检测内容是否完整，避免生成残缺题目"""
    if len(content) < 20:
        return False
    # 检查截断迹象
    patterns = [r'包括[^）)]*$', r'[（(][^）)]*$', r'[—\-－:：]$', r'等$']
    for p in patterns:
        if re.search(p, content):
            return False
    return True
```

## 界面特性

### 选项完整显示

选择题按钮动态更新，显示完整选项内容：
- `A. 解释器会自动推断类型`
- `B. 该说法不正确`
- `C. 该说法部分正确`
- `D. 以上都不对`

### 响应式布局

- 题目区域：白色卡片，清晰展示
- 选项按钮：左对齐，大号字体
- 结果反馈：正确绿色/错误红色背景

### 动态章节配色

章节图标和颜色根据数据自动分配，无需硬编码。

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| 选项只显示字母 | 使用 `quiz_app_v4.py`，按钮动态更新 |
| 题目内容残缺 | `is_content_complete()` 检测后跳过 |
| 知识点不完整 | 检查 OCR 结果，必要时重新识别 |
| 端口被占用 | 修改 `server_port=7866` 为其他端口 |

## 依赖

- gradio >= 4.0
- PyMuPDF (可选，PDF 文本提取)
- Python >= 3.8
