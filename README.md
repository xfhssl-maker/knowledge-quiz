# Knowledge Quiz

根据知识库数据文档生成选择题、判断题，通过 Gradio 界面答题，支持知识点学习、学习报告、OCR 识别。

## 快速开始

```bash
# 创建题库
/knowledge-quiz path/to/knowledge.pdf

# 启动 Gradio 界面
/knowledge-quiz --gradio
```

## 功能特性

- **AI 创建题库**：从知识库自动生成选择题、判断题
- **Gradio 界面**：独立 Web 应用答题
- **OCR 支持**：自动识别扫描版 PDF（PaddleOCR 优先，EasyOCR 备选）
- **PDF 预览**：快速预览 PDF 内容
- **智能缓存**：Laravel 风格缓存管理，避免重复 OCR 处理

## 支持的输入格式

| 格式 | 说明 |
|------|------|
| `.pdf` | PDF 文档（支持扫描版 OCR） |
| `.md` | Markdown 文件 |
| `.txt` | 纯文本 |
| `.json` | 结构化 JSON 数据 |

## OCR 功能

### PDF 预览

```bash
# 预览 PDF 前 3 页
python ocr.py input.pdf --preview

# 预览 PDF 前 10 页
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
cache.put('key', 'value', ttl=3600)

# 获取缓存
value = cache.get('key')

# 获取或存储 (回调模式)
value = cache.remember('key', lambda: expensive_operation())

# 删除缓存
cache.forget('key')

# 清空所有缓存
cache.flush()
```

缓存文件存储在 `~/.knowledge-quiz/cache/` 目录，OCR 结果默认缓存 7 天。

### 支持的 OCR 引擎

| 引擎 | 优先级 | 说明 |
|------|--------|------|
| PaddleOCR | 高 | 高精度中英文识别 |
| EasyOCR | 中 | 多语言支持 |

## 数据存储

```
~/.knowledge-quiz/
├── knowledge-base.json   # 知识点数据
├── questions.json        # 题库
├── answers.json          # 答题记录
├── cache/                # OCR 缓存
│   └── *.cache
└── quiz_app.py           # Gradio 应用
```

## 详细文档

参见 [SKILL.md](SKILL.md)

## 致谢

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR 识别
- [PaddlePaddle](https://github.com/PaddlePaddle/PaddlePaddle) - 深度学习框架
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - 多语言 OCR
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF 处理
- [Gradio](https://github.com/gradio-app/gradio) - Web 界面
