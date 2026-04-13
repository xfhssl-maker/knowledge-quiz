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
version: 3.3.0
---

# Knowledge Quiz Skill

根据输入的知识库数据文档，分析整理后输出为可以作答的选择题、判断题。通过 Gradio 界面进行答题、错题复习、知识点学习、查看学习报告。

## 功能特性

### 核心功能
- **多格式输入**：支持 PDF、Markdown、纯文本、JSON 格式的知识库
- **OCR 支持**：多引擎支持，MinerU (优先)、PaddleOCR、EasyOCR
- **OCR 缓存**：Laravel 风格缓存管理，避免重复处理
- **PDF 预览**：快速预览 PDF 内容
- **多题型生成**：自动生成选择题、判断题
- **智能题目生成**：内容完整性检测，避免生成残缺题目
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
- **卡片式显示**：每个知识点独立卡片，美观清晰
- **分类查看**：按章节 + 考点分组显示
- **完整显示**：显示知识点完整内容
- **错题关联**：显示每个知识点关联的错题数量
- **难度星级**：可视化显示知识点难度
- **关键词标签**：突出显示医学关键词

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

**访问地址**：http://127.0.0.1:7866

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

**目标**：根据知识点智能生成选择题和判断题。

**操作**：
1. 遍历知识点列表
2. 检测知识点内容完整性
3. 根据内容完整度智能选择题型
4. 保存到 `questions.json`

**内容完整性检测**：

```python
def is_content_complete(content: str) -> bool:
    """检查内容是否完整"""
    # 内容太短
    if len(content) < 15:
        return False

    # 检查是否有明显的截断迹象
    incomplete_patterns = [
        r'包括[^）]*$',      # 以"包括"结尾但没有完整列表
        r'[（(][^）)]*$',   # 括号未闭合
        r'[—\-－:：]$',     # 以分隔符结尾
        r'[0-9]+\s*$',      # 以数字结尾（可能截断）
        r'[上下去左右内外]$', # 以方位词结尾（可能截断）
    ]

    for pattern in incomplete_patterns:
        if re.search(pattern, content):
            return False

    return True
```

**智能题目生成策略**：

| 条件 | 生成题型 | 说明 |
|------|---------|------|
| 内容完整 + 有数值 | 数值选择题 | 提取数值生成四选一 |
| 内容完整 + 内容较长 | 判断型选择题 | 选项A为正确描述 |
| 内容不完整 | 仅判断题 | 避免选项内容残缺 |

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

## 知识点卡片式显示

Gradio 界面中的知识点学习采用卡片式布局：

```python
CARD_STYLE = """
<style>
    .kp-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }

    .kp-card:hover {
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }

    .kp-card .kp-number {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .kp-card .kp-keyword {
        background: #ede9fe;
        color: #6d28d9;
        padding: 4px 10px;
        border-radius: 15px;
    }

    .kp-card .kp-wrong {
        background: #fef2f2;
        color: #dc2626;
        padding: 4px 10px;
        border-radius: 15px;
    }
</style>
"""
```

**卡片元素**：
- 圆形编号徽章（渐变紫色）
- 知识点标题（加粗）
- 内容区域（浅灰背景）
- 难度星级（金色星星）
- 关键词标签（紫色）
- 错题警告（红色）

## OCR 模块

### 支持的 OCR 引擎

| 引擎 | 优先级 | 说明 |
|------|--------|------|
| MinerU API | 高 | OpenDataLab 云端 API，需配置 Token，支持 URL 方式提交 |
| PyMuPDF 文本层 | 中 | 提取 PDF 内置文本层，速度快 |
| PaddleOCR | 中 | 高精度中英文识别（需要 Python 3.10-3.13） |
| RapidOCR | 中 | 轻量级 OCR，基于 ONNX Runtime，兼容性好 |
| EasyOCR | 低 | 多语言支持，备选方案 |

### MinerU API 配置

MinerU 云端 API (mineru.net) 提供高精度文档解析服务，需要配置 API Token：

```bash
# 配置 Token（保存到 ~/.knowledge-quiz/config.json）
python ocr.py --set-token YOUR_MINERU_API_TOKEN

# 查看当前 Token
python ocr.py --show-token
```

**注意**：MinerU 云端 API 仅支持通过 URL 提交任务，不支持直接上传本地文件。

对于本地 PDF 文件，系统会自动：
1. 先检查 PDF 是否有可提取的文本层
2. 如果有文本层，直接提取
3. 如果没有文本层（扫描版），回退到本地 OCR 引擎

### PDF 预览

```bash
# 预览 PDF 前 3 页
python ocr.py input.pdf --preview

# 预览前 10 页
python ocr.py input.pdf --preview --pages 10
```

### OCR 识别

```bash
# 自动选择最佳引擎
python ocr.py input.pdf -o output.txt

# 指定使用特定引擎
python ocr.py input.pdf -o output.txt -e paddleocr
python ocr.py input.pdf -o output.txt -e easyocr

# 输出元数据
python ocr.py input.pdf -o output.txt --json meta.json

# 禁用缓存重新识别
python ocr.py input.pdf -o output.txt --no-cache
```

### 使用 MinerU API 处理在线 PDF

```python
from ocr import ocr_with_mineru_api_url

# 通过 URL 处理在线 PDF
text, metadata = ocr_with_mineru_api_url(
    "https://example.com/document.pdf",
    output_path="output.md"
)
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
├── parse_smart.py        # 智能解析脚本
└── quiz_app.py           # Gradio 应用
```

## 常见问题及解决方案

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 选择题选项内容残缺 | 知识点内容不完整 | 使用 `is_content_complete()` 检测，不完整时只生成判断题 |
| 知识点显示不全 | 内容截断 | 卡片式布局显示完整内容 |
| 界面无变化 | 旧进程未终止 | 终止旧进程后重启，或更换端口 |
| PDF 解析乱码 | 编码问题 | 使用 pdfplumber 并指定 utf-8 编码 |
| OCR 识别不完整 | 扫描版 PDF 质量 | 多行合并解析，累积内容到知识点 |

## 注意事项

1. **PDF 解析**：优先提取文本层，扫描版使用 OCR
2. **Gradio 端口**：默认 7866，如被占用需修改
3. **数据备份**：定期备份 `~/.knowledge-quiz/` 目录
4. **内容完整性**：生成题目前检测内容完整性，避免残缺题目

## 致谢

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR 识别
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF 处理
- [Gradio](https://github.com/gradio-app/gradio) - Web 界面
