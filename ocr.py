"""
PDF OCR 模块
支持多种 OCR 引擎：PaddleOCR (优先)、EasyOCR (备选)
自动检测并选择可用的引擎
支持 PDF 预览和模型缓存
"""

import json
import subprocess
import sys
import os
import hashlib
import pickle
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timedelta

# ============ 缓存管理 (Laravel-style) ============

class CacheManager:
    """Laravel 风格的缓存管理器"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".knowledge-quiz" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_key}.cache"

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存"""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return default

        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)

            # 检查是否过期
            if data.get('expires_at') and datetime.now() > data['expires_at']:
                self.forget(key)
                return default

            return data.get('value')
        except Exception:
            return default

    def put(self, key: str, value: Any, ttl: int = 86400) -> bool:
        """存储缓存 (默认缓存24小时)"""
        cache_path = self._get_cache_path(key)

        try:
            data = {
                'value': value,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(seconds=ttl)
            }

            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

            return True
        except Exception:
            return False

    def remember(self, key: str, callback, ttl: int = 86400) -> Any:
        """获取缓存，不存在则执行回调并缓存结果"""
        value = self.get(key)

        if value is not None:
            return value

        value = callback()
        self.put(key, value, ttl)
        return value

    def forget(self, key: str) -> bool:
        """删除缓存"""
        cache_path = self._get_cache_path(key)

        if cache_path.exists():
            cache_path.unlink()
            return True

        return False

    def flush(self) -> bool:
        """清空所有缓存"""
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            return True
        except Exception:
            return False

# 全局缓存实例
cache = CacheManager()

# ============ PDF 预览功能 ============

class PDFViewer:
    """PDF 预览查看器"""

    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)
        self.doc = None

    def open(self):
        """打开 PDF 文档"""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {self.pdf_path}")

        try:
            import fitz
            self.doc = fitz.open(self.pdf_path)
            return self
        except ImportError:
            raise ImportError("需要安装 PyMuPDF: pip install pymupdf")

    def close(self):
        """关闭文档"""
        if self.doc:
            self.doc.close()
            self.doc = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_page_count(self) -> int:
        """获取页数"""
        return self.doc.page_count if self.doc else 0

    def get_page_image(self, page_num: int, zoom: float = 1.0) -> Optional[bytes]:
        """获取页面图像 (PNG 格式)"""
        if not self.doc or page_num < 0 or page_num >= self.doc.page_count:
            return None

        page = self.doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        return pix.tobytes("png")

    def get_page_text(self, page_num: int) -> str:
        """获取页面文本"""
        if not self.doc or page_num < 0 or page_num >= self.doc.page_count:
            return ""

        page = self.doc[page_num]
        return page.get_text()

    def get_toc(self) -> List[Dict]:
        """获取目录"""
        if not self.doc:
            return []

        toc = self.doc.get_toc()
        return [{"level": t[0], "title": t[1], "page": t[2]} for t in toc]

    def get_metadata(self) -> Dict:
        """获取元数据"""
        if not self.doc:
            return {}

        meta = self.doc.metadata
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "creation_date": meta.get("creationDate", ""),
            "mod_date": meta.get("modDate", ""),
            "page_count": self.doc.page_count
        }

    def extract_page_as_markdown(self, page_num: int) -> str:
        """提取页面为 Markdown 格式"""
        if not self.doc or page_num < 0 or page_num >= self.doc.page_count:
            return ""

        page = self.doc[page_num]
        text = page.get_text("text")

        # 简单格式化
        lines = text.split('\n')
        formatted = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测可能的标题
            if len(line) < 50 and not line.endswith('。') and not line.endswith('，'):
                if line.startswith('第') and ('章' in line or '节' in line):
                    formatted.append(f"\n## {line}\n")
                elif line.startswith('考点'):
                    formatted.append(f"\n### {line}\n")
                else:
                    formatted.append(line)
            else:
                formatted.append(line)

        return '\n'.join(formatted)

    def preview_pages(self, start: int = 0, end: int = 5) -> str:
        """预览多页内容"""
        if not self.doc:
            return "文档未打开"

        end = min(end, self.doc.page_count)
        preview = []

        for i in range(start, end):
            preview.append(f"\n{'='*50}")
            preview.append(f"第 {i+1} 页")
            preview.append('='*50)
            preview.append(self.get_page_text(i))

        return '\n'.join(preview)

def view_pdf(pdf_path: str, pages: int = 3) -> str:
    """快速预览 PDF"""
    with PDFViewer(Path(pdf_path)) as viewer:
        meta = viewer.get_metadata()
        result = [f"# PDF 预览: {meta.get('title', Path(pdf_path).name)}"]
        result.append(f"\n- 页数: {meta['page_count']}")
        result.append(f"- 作者: {meta.get('author', '未知')}")
        result.append(f"\n{'='*50}")
        result.append(viewer.preview_pages(0, pages))
        return '\n'.join(result)

# ============ OCR 引擎检测 ============

def check_paddleocr_available() -> bool:
    """检查 PaddleOCR 是否可用"""
    try:
        import paddleocr
        return True
    except ImportError:
        return False

def check_easyocr_available() -> bool:
    """检查 EasyOCR 是否可用"""
    try:
        import easyocr
        return True
    except ImportError:
        return False

def check_pymupdf_available() -> bool:
    """检查 PyMuPDF 是否可用"""
    try:
        import fitz
        return True
    except ImportError:
        return False

def install_dependencies(engine: str = "auto") -> bool:
    """安装 OCR 依赖"""
    packages = ["pymupdf", "Pillow"]

    if engine == "paddleocr" or engine == "auto":
        packages.extend(["paddlepaddle", "paddleocr"])
    if engine == "easyocr" or engine == "auto":
        packages.append("easyocr")

    try:
        for pkg in packages:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        return True
    except subprocess.CalledProcessError:
        return False

def get_best_ocr_engine() -> Optional[str]:
    """获取最佳可用的 OCR 引擎"""
    if check_paddleocr_available():
        return "paddleocr"
    if check_easyocr_available():
        return "easyocr"
    return None

# ============ PDF 转图像 ============

def pdf_to_images(pdf_path: Path) -> List:
    """将 PDF 页面转换为图片列表"""
    import fitz
    from PIL import Image
    import io
    import numpy as np

    doc = fitz.open(pdf_path)
    images = []

    for page in doc:
        # 放大2倍提高识别率
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)

        # 转换为 numpy 数组
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        img_array = np.array(img)
        images.append(img_array)

    doc.close()
    return images

# ============ OCR 处理 (带缓存) ============

def ocr_with_paddleocr_cached(images: List, pdf_path: str) -> List[str]:
    """使用 PaddleOCR 进行文字识别 (带缓存)"""
    cache_key = f"ocr_paddleocr_{pdf_path}_{len(images)}"

    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        print("使用缓存的 OCR 结果...")
        return cached_result

    from paddleocr import PaddleOCR

    # 初始化 OCR，使用中英文模型
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

    results = []
    for i, img in enumerate(images):
        print(f"PaddleOCR 处理第 {i+1}/{len(images)} 页...")
        result = ocr.ocr(img, cls=True)

        # 整理识别结果
        page_text = "\n".join([line[1][0] for line in result[0]] if result[0] else [])
        results.append(page_text)

    # 缓存结果 (缓存7天)
    cache.put(cache_key, results, ttl=7*86400)

    return results

def ocr_with_easyocr_cached(images: List, pdf_path: str) -> List[str]:
    """使用 EasyOCR 进行文字识别 (带缓存)"""
    cache_key = f"ocr_easyocr_{pdf_path}_{len(images)}"

    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        print("使用缓存的 OCR 结果...")
        return cached_result

    import easyocr

    # 初始化 OCR，使用中英文模型
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)

    results = []
    for i, img in enumerate(images):
        print(f"EasyOCR 处理第 {i+1}/{len(images)} 页...")
        result = reader.readtext(img)

        # 整理识别结果
        page_text = "\n".join([item[1] for item in result])
        results.append(page_text)

    # 缓存结果 (缓存7天)
    cache.put(cache_key, results, ttl=7*86400)

    return results

def ocr_pdf(pdf_path: str, output_path: Optional[str] = None, use_cache: bool = True) -> Tuple[str, dict]:
    """OCR 识别 PDF 文件"""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    # 检查依赖
    if not check_pymupdf_available():
        print("正在安装 PyMuPDF...")
        install_dependencies("none")

    # 获取最佳 OCR 引擎
    engine = get_best_ocr_engine()

    if engine is None:
        print("未检测到 OCR 引擎，正在安装 EasyOCR...")
        if install_dependencies("easyocr"):
            engine = "easyocr"
        else:
            raise RuntimeError("无法安装 OCR 引擎，请手动安装: pip install easyocr")

    print(f"使用 OCR 引擎: {engine}")

    # 转换 PDF 为图片
    print("正在转换 PDF 页面...")
    images = pdf_to_images(pdf_path)
    print(f"共 {len(images)} 页")

    # 执行 OCR (带缓存)
    if use_cache:
        if engine == "paddleocr":
            texts = ocr_with_paddleocr_cached(images, str(pdf_path))
        else:
            texts = ocr_with_easyocr_cached(images, str(pdf_path))
    else:
        if engine == "paddleocr":
            texts = ocr_with_paddleocr_cached.__wrapped__(images, str(pdf_path))
        else:
            texts = ocr_with_easyocr_cached.__wrapped__(images, str(pdf_path))

    # 合并结果
    full_text = "\n\n".join([f"=== 第{i+1}页 ===\n{text}" for i, text in enumerate(texts)])

    # 保存到文件
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"OCR 结果已保存到: {output_path}")

    # 元数据
    metadata = {
        "pdf_path": str(pdf_path),
        "total_pages": len(images),
        "total_chars": len(full_text),
        "ocr_engine": engine,
        "pages": [{"page": i+1, "chars": len(t)} for i, t in enumerate(texts)]
    }

    return full_text, metadata

# ============ 知识点解析 ============

def parse_knowledge_from_ocr(text: str) -> List[dict]:
    """从 OCR 识别的文字中解析知识点"""
    import re

    knowledge_points = []
    kp_id = 1
    current_section = "默认章节"

    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检测章节标题
        section_patterns = [
            r'^考点\s*\d*\s*(.+)$',
            r'^第[一二三四五六七八九十]+[章节].*?(.+)$',
            r'^[一二三四五六七八九十]+[、.．]\s*(.+)$',
            r'^\d+\.\s*(.+)$',
        ]

        # 检测知识点
        if '：' in line or '——' in line or '－' in line:
            parts = re.split(r'[：——－]', line, 1)
            if len(parts) == 2:
                title = parts[0].strip()
                content = parts[1].strip()

                if len(content) > 5:
                    knowledge_points.append({
                        "id": f"kp-{kp_id:03d}",
                        "section": current_section,
                        "title": title,
                        "content": content,
                        "keywords": [],
                        "difficulty": 1
                    })
                    kp_id += 1

    return knowledge_points

# ============ 命令行入口 ============

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PDF OCR 工具")
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument("-o", "--output", help="输出文本文件路径")
    parser.add_argument("--json", help="输出 JSON 元数据路径")
    parser.add_argument("--preview", action="store_true", help="预览 PDF 内容")
    parser.add_argument("--pages", type=int, default=3, help="预览页数")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存")

    args = parser.parse_args()

    if args.preview:
        # 预览模式
        print(view_pdf(args.pdf_path, args.pages))
    else:
        # OCR 模式
        text, metadata = ocr_pdf(args.pdf_path, args.output, use_cache=not args.no_cache)

        print(f"\nOCR 完成！")
        print(f"总页数: {metadata['total_pages']}")
        print(f"总字符数: {metadata['total_chars']}")
        print(f"使用引擎: {metadata['ocr_engine']}")

        if args.json:
            with open(args.json, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
