---
name: knowledge-quiz
description: 根据知识库数据文档生成选择题、判断题，通过 Gradio 界面答题，支持错题集、知识点分类学习、学习报告、OCR 识别。
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
version: 3.1.0
---

# Knowledge Quiz Skill

根据输入的知识库数据文档，分析整理后输出为可以作答的选择题、判断题。通过 Gradio 界面进行答题、错题复习、知识点学习、查看学习报告。

## 功能特性

### 核心功能
- **多格式输入**：支持 PDF、Markdown、纯文本、JSON 格式的知识库
- **OCR 支持**：扫描版 PDF 自动识别（PaddleOCR 优先，EasyOCR 备选）
- **OCR 缓存**：Laravel 风格缓存管理，避免重复处理
- **PDF 预览**：快速预览 PDF 内容
- **多题型生成**：自动生成选择题、判断题
- **Gradio 界面**：独立 Web 应用，无需 AI 参与答题

### Gradio 界面

#### 🎯 开始答题
- 按题型筛选（选择题/判断题）
- 按章节筛选
- 按题目数量选择（全部/10题/20题/50题）
- 智能选题：优先选择未答过的题目
- 实时反馈：答题后显示正确答案和知识点

#### ❌ 错题集
- 按章节查看错题列表
- 显示错题关联的知识点
- **薄弱知识点分析**：按错误次数排序，定位需要复习的知识点
- **错题复习**：一键开始错题复习

#### 📖 知识点学习
- **分类查看**：按章节 + 考点分组显示
- **完整显示**：显示知识点完整内容
- **错题关联**：显示每个知识点关联的错题数量
- 关键词搜索

#### 📊 学习报告
- 总体统计（正确率、错题数）
- 章节进度分析
- 薄弱知识点提示

## 使用方法

```bash
# 导入知识库并生成题库
/knowledge-quiz path/to/knowledge.pdf

# 启动 Gradio 界面
/knowledge-quiz --gradio
# 或直接运行
python ~/.knowledge-quiz/quiz_app.py
```

**访问地址**：http://127.0.0.1:7864

## 执行流程

### Step 1: 解析知识库

**目标**：读取并提取知识点结构。

**操作**：
1. 检测输入格式（PDF/MD/TXT/JSON）
2. PDF 文件检测是否有可提取文本层
3. 扫描版 PDF 调用 OCR 模块识别
4. 分析知识点层次结构
5. 生成知识点列表保存到 `knowledge-base.json`

**知识点格式**：
```json
{
  "id": "kp-001",
  "section": "章节名称",
  "topic": "考点名称",
  "title": "知识点标题",
  "content": "详细内容",
  "keywords": ["关键词1", "关键词2"],
  "difficulty": 2
}
```

### Step 2: 生成题目

**目标**：根据知识点生成选择题和判断题。

**操作**：
1. 遍历知识点列表
2. 为每个知识点生成选择题和判断题
3. 保存到 `questions.json`

**题目格式**：
```json
{
  "id": "q-001",
  "type": "choice|judgment",
  "section": "章节名称",
  "topic": "考点名称",
  "knowledge_point_id": "kp-001",
  "question": "题目内容",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "answer": "A",
  "explanation": "答案解析",
  "difficulty": 2
}
```

### Step 3: 启动 Gradio

**目标**：启动 Gradio Web 应用。

**操作**：
```bash
python ~/.knowledge-quiz/quiz_app.py
```

## OCR 模块

### PDF 预览

```bash
# 预览 PDF 前 3 页
python ocr.py input.pdf --preview

# 预览前 10 页
python ocr.py input.pdf --preview --pages 10
```

### OCR 识别

```bash
# OCR 识别并保存
python ocr.py input.pdf -o output.txt

# 输出元数据
python ocr.py input.pdf -o output.txt --json meta.json

# 禁用缓存重新识别
python ocr.py input.pdf -o output.txt --no-cache
```

### 缓存管理

OCR 模块内置 Laravel 风格的缓存管理器：

```python
from ocr import cache

# 存储缓存 (默认 24 小时)
cache.put('key', data, ttl=3600)

# 获取缓存
value = cache.get('key')

# 回调模式
value = cache.remember('key', lambda: expensive_operation())

# 删除缓存
cache.forget('key')

# 清空所有缓存
cache.flush()
```

缓存文件存储在 `~/.knowledge-quiz/cache/` 目录，OCR 结果默认缓存 7 天。

## 数据存储结构

```
~/.knowledge-quiz/
├── knowledge-base.json   # 知识点数据
├── questions.json        # 题库
├── answers.json          # 答题记录
├── cache/                # OCR 缓存
│   └── *.cache
└── quiz_app.py           # Gradio 应用
```

## 注意事项

1. **PDF 解析**：优先提取文本层，扫描版使用 OCR
2. **Gradio 端口**：默认 7864，如被占用需修改
3. **数据备份**：定期备份 `~/.knowledge-quiz/` 目录

## 致谢

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR 识别
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF 处理
- [Gradio](https://github.com/gradio-app/gradio) - Web 界面
