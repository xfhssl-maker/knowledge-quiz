"""
PDF OCR 模块
支持多种 OCR 引擎：MinerU API (优先)、PaddleOCR、EasyOCR
自动检测并选择可用的引擎
支持 PDF 预览和模型缓存

OCR 引擎优先级：
1. MinerU API - 高精度文档解析，支持公式/表格/多语言，输出 Markdown/JSON
2. PaddleOCR - 高精度中英文 OCR
3. EasyOCR - 多语言支持
"""

import json
import subprocess
import sys
import os
import hashlib
import pickle
import time
import requests
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timedelta

# ============ 配置管理 ============

# API Token 存储路径（用户数据目录，不会上传到 git）
CONFIG_DIR = Path.home() / ".knowledge-quiz"
CONFIG_FILE = CONFIG_DIR / "config.json"

def get_mineru_token() -> Optional[str]:
    """获取 MinerU API Token"""
    # 1. 先检查环境变量
    token = os.environ.get("MINERU_API_TOKEN")
    if token:
        return token

    # 2. 检查配置文件
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("mineru_api_token")
        except Exception:
            pass

    return None

def set_mineru_token(token: str) -> bool:
    """保存 MinerU API Token 到用户数据目录"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            pass

    config["mineru_api_token"] = token

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# ============ 缓存管理 (Laravel-style) ============

class CacheManager:
    """Laravel 风格的缓存管理器"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CONFIG_DIR / "cache"
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

def check_rapidocr_available() -> bool:
    """检查 RapidOCR 是否可用"""
    try:
        from rapidocr_onnxruntime import RapidOCR
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

def check_mineru_api_available() -> bool:
    """检查 MinerU API 是否可用（需要配置 Token）"""
    return get_mineru_token() is not None

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
    """获取最佳可用的 OCR 引擎

    优先级：MinerU API > PaddleOCR > RapidOCR > EasyOCR
    """
    if check_mineru_api_available():
        return "mineru_api"
    if check_paddleocr_available():
        return "paddleocr"
    if check_rapidocr_available():
        return "rapidocr"
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

# ============ MinerU API 处理 ============

MINERU_API_URL = "https://mineru.net/api/v4/extract/task"
MINERU_RESULT_URL = "https://mineru.net/api/v4/extract/task/{task_id}"

def ocr_with_mineru_api_url(pdf_url: str, output_path: Optional[str] = None, model_version: str = "vlm") -> Tuple[str, dict]:
    """使用 MinerU API 通过 URL 进行 PDF 解析

    直接使用在线 URL 提交任务，适用于文件已上传到云存储的情况。

    Args:
        pdf_url: PDF 文件的在线 URL
        output_path: 输出文件路径（可选）
        model_version: 模型版本 (vlm/ocr)

    Returns:
        (markdown_text, metadata): 解析后的 Markdown 文本和元数据
    """
    token = get_mineru_token()
    if not token:
        raise ValueError("MinerU API Token 未配置。请运行: python ocr.py --set-token YOUR_TOKEN")

    print(f"MinerU API 正在解析: {pdf_url}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # 提交解析任务
    data = {
        "url": pdf_url,
        "model_version": model_version
    }

    response = requests.post(MINERU_API_URL, headers=headers, json=data)

    if response.status_code != 200:
        raise RuntimeError(f"MinerU API 请求失败: {response.status_code} - {response.text}")

    result = response.json()

    if result.get("code") != 0:
        raise RuntimeError(f"MinerU API 错误: {result.get('message', 'Unknown error')}")

    task_id = result.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"未获取到任务 ID: {result}")

    print(f"任务已提交，task_id: {task_id}")
    print("等待处理完成...")

    # 轮询任务状态
    max_wait = 600  # 最大等待时间 10 分钟
    start_time = time.time()

    while time.time() - start_time < max_wait:
        status_url = MINERU_RESULT_URL.format(task_id=task_id)
        status_response = requests.get(status_url, headers=headers)

        if status_response.status_code != 200:
            raise RuntimeError(f"查询任务状态失败: {status_response.text}")

        status_data = status_response.json()
        task_state = status_data.get("data", {}).get("state", "")

        if task_state == "done":
            break
        elif task_state in ("failed", "error"):
            err_msg = status_data.get("data", {}).get("err_msg", "Unknown error")
            raise RuntimeError(f"任务处理失败: {err_msg}")

        print(f"任务状态: {task_state or 'processing'}，等待中...")
        time.sleep(5)

    # 获取结果
    result_data = status_data.get("data", {})

    # 获取结果 ZIP 文件
    zip_url = result_data.get("full_zip_url")

    if not zip_url:
        raise RuntimeError(f"未获取到结果文件 URL: {result_data}")

    print(f"下载结果文件...")
    zip_response = requests.get(zip_url)
    if zip_response.status_code != 200:
        raise RuntimeError(f"下载结果失败: {zip_response.status_code}")

    # 解压 ZIP 获取 Markdown
    import zipfile
    import io

    markdown_text = ""
    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
        md_files = [f for f in zf.namelist() if f.endswith('.md')]
        if md_files:
            with zf.open(md_files[0]) as f:
                markdown_text = f.read().decode('utf-8')
        else:
            raise RuntimeError(f"ZIP 中未找到 Markdown 文件: {zf.namelist()}")

    # 构建元数据
    metadata = {
        "pdf_url": pdf_url,
        "task_id": task_id,
        "total_chars": len(markdown_text),
        "ocr_engine": "mineru_api",
        "model_version": model_version
    }

    # 保存到文件
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_text)
        metadata["output_file"] = str(output_path)
        print(f"结果已保存到: {output_path}")

    print(f"MinerU API 解析完成，共 {len(markdown_text)} 字符")
    return markdown_text, metadata

def ocr_with_mineru_api(pdf_path: str, output_path: Optional[str] = None, model_version: str = "vlm") -> Tuple[str, dict]:
    """使用 MinerU API 进行 PDF 解析

    MinerU API 是 OpenDataLab 提供的高精度文档解析服务，支持：
    - 公式、表格识别
    - 多栏布局、跨页表格合并
    - 109 种语言 OCR
    - 输出 Markdown / JSON 格式

    注意：MinerU 云端 API (mineru.net) 仅支持通过 URL 提交任务。
    对于本地文件，本函数会：
    1. 先尝试用 PyMuPDF 提取文本层
    2. 如果有文本层，直接返回
    3. 如果没有文本层（扫描版），回退到 PaddleOCR/EasyOCR

    Args:
        pdf_path: PDF 文件路径
        output_path: 输出文件路径（可选）
        model_version: 模型版本 (vlm/ocr)

    Returns:
        (markdown_text, metadata): 解析后的 Markdown 文本和元数据
    """
    token = get_mineru_token()
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    # 检查缓存
    cache_key = f"mineru_api_{pdf_path}_{pdf_path.stat().st_size}"
    cached = cache.get(cache_key)
    if cached:
        print("使用缓存的 OCR 结果...")
        return cached.get('text', ''), cached.get('metadata', {})

    print(f"处理本地 PDF: {pdf_path}")
    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    print(f"文件大小: {file_size_mb:.2f} MB")

    # MinerU 云端 API 不支持直接上传本地文件
    # 策略：先检查 PDF 是否有可提取的文本层
    if check_pymupdf_available():
        print("检查 PDF 文本层...")
        try:
            import fitz
            doc = fitz.open(pdf_path)
            total_text = ""
            page_count = doc.page_count

            for i in range(page_count):
                page = doc[i]
                text = page.get_text()
                total_text += text

            doc.close()

            # 如果有足够的文本内容，直接使用文本层
            if len(total_text.strip()) > 100:
                print(f"检测到文本层 ({len(total_text)} 字符)，直接提取...")
                full_text = format_pdf_text(str(pdf_path))

                metadata = {
                    "pdf_path": str(pdf_path),
                    "total_pages": page_count,
                    "total_chars": len(full_text),
                    "ocr_engine": "pymupdf_text_layer",
                    "source": "text_layer"
                }

                # 保存到文件
                if output_path:
                    output_path = Path(output_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(full_text)
                    metadata["output_file"] = str(output_path)
                    print(f"结果已保存到: {output_path}")

                # 缓存结果
                cache.put(cache_key, {"text": full_text, "metadata": metadata}, ttl=7*86400)

                print(f"文本提取完成，共 {len(full_text)} 字符")
                return full_text, metadata
            else:
                print("未检测到文本层（扫描版 PDF），将使用本地 OCR 引擎...")

        except Exception as e:
            print(f"文本层提取失败: {e}")

    # 没有文本层或提取失败，使用本地 OCR
    # 选择最佳可用的本地 OCR 引擎
    local_engine = None
    if check_paddleocr_available():
        local_engine = "paddleocr"
    elif check_rapidocr_available():
        local_engine = "rapidocr"
    elif check_easyocr_available():
        local_engine = "easyocr"
    else:
        print("未检测到本地 OCR 引擎，正在安装 RapidOCR...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "rapidocr_onnxruntime", "-q"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            local_engine = "rapidocr"
        except:
            raise RuntimeError(
                f"无法处理此 PDF 文件。\n"
                f"MinerU 云端 API 不支持直接上传本地文件。\n"
                f"请安装本地 OCR 引擎：pip install rapidocr_onnxruntime 或 pip install paddleocr\n"
                f"或者将 PDF 上传到云存储获取公开 URL，然后使用 ocr_with_mineru_api_url()"
            )

    # 使用本地 OCR 引擎处理
    print(f"使用本地 OCR 引擎: {local_engine}")

    if not check_pymupdf_available():
        print("正在安装 PyMuPDF...")
        install_dependencies("none")

    # 转换 PDF 为图片
    print("正在转换 PDF 页面...")
    images = pdf_to_images(pdf_path)
    print(f"共 {len(images)} 页")

    # 执行 OCR (带缓存)
    if local_engine == "paddleocr":
        texts = ocr_with_paddleocr_cached(images, str(pdf_path))
    elif local_engine == "rapidocr":
        texts = ocr_with_rapidocr_cached(images, str(pdf_path))
    else:
        texts = ocr_with_easyocr_cached(images, str(pdf_path))

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
        "ocr_engine": local_engine,
        "source": "local_ocr",
        "pages": [{"page": i+1, "chars": len(t)} for i, t in enumerate(texts)]
    }

    # 缓存结果
    cache.put(cache_key, {"text": full_text, "metadata": metadata}, ttl=7*86400)

    print(f"OCR 完成，共 {len(full_text)} 字符")
    return full_text, metadata


def format_pdf_text(pdf_path: str) -> str:
    """格式化 PDF 文本层内容"""
    import fitz

    doc = fitz.open(pdf_path)
    all_text = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
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

        page_text = '\n'.join(formatted)
        all_text.append(f"=== 第{page_num + 1}页 ===\n{page_text}")

    doc.close()
    return '\n\n'.join(all_text)

# ============ 本地 OCR 处理 (带缓存) ============

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

def ocr_with_rapidocr_cached(images: List, pdf_path: str) -> List[str]:
    """使用 RapidOCR 进行文字识别 (带缓存)

    RapidOCR 是基于 ONNX Runtime 的轻量级 OCR，不需要 GPU 或深度学习框架。
    """
    cache_key = f"ocr_rapidocr_{pdf_path}_{len(images)}"

    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        print("使用缓存的 OCR 结果...")
        return cached_result

    from rapidocr_onnxruntime import RapidOCR

    # 初始化 OCR
    ocr = RapidOCR()

    results = []
    for i, img in enumerate(images):
        print(f"RapidOCR 处理第 {i+1}/{len(images)} 页...")

        # RapidOCR 接受 numpy 数组或文件路径
        result, elapse = ocr(img)

        # 整理识别结果
        # result 格式: [[box, text, confidence], ...]
        if result:
            page_text = "\n".join([item[1] for item in result])
        else:
            page_text = ""
        results.append(page_text)

    # 缓存结果 (缓存7天)
    cache.put(cache_key, results, ttl=7*86400)

    return results

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

def ocr_pdf(pdf_path: str, output_path: Optional[str] = None, use_cache: bool = True, engine: Optional[str] = None) -> Tuple[str, dict]:
    """OCR 识别 PDF 文件

    Args:
        pdf_path: PDF 文件路径
        output_path: 输出文本文件路径（可选）
        use_cache: 是否使用缓存
        engine: 指定 OCR 引擎 (mineru_api/paddleocr/easyocr)，默认自动选择

    Returns:
        (text, metadata): 解析后的文本和元数据
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    # 如果未指定引擎，自动选择最佳引擎
    if engine is None:
        engine = get_best_ocr_engine()

    if engine is None:
        print("未检测到 OCR 引擎，正在安装 EasyOCR...")
        if install_dependencies("easyocr"):
            engine = "easyocr"
        else:
            raise RuntimeError("无法安装 OCR 引擎，请手动安装或配置 MinerU API Token")

    print(f"使用 OCR 引擎: {engine}")

    # MinerU API 使用独立的处理流程
    if engine == "mineru_api":
        full_text, metadata = ocr_with_mineru_api(str(pdf_path), output_path)
        return full_text, metadata

    # 其他引擎需要 PyMuPDF
    if not check_pymupdf_available():
        print("正在安装 PyMuPDF...")
        install_dependencies("none")

    # 转换 PDF 为图片
    print("正在转换 PDF 页面...")
    images = pdf_to_images(pdf_path)
    print(f"共 {len(images)} 页")

    # 执行 OCR (带缓存)
    if engine == "paddleocr":
        texts = ocr_with_paddleocr_cached(images, str(pdf_path))
    elif engine == "rapidocr":
        texts = ocr_with_rapidocr_cached(images, str(pdf_path))
    else:
        texts = ocr_with_easyocr_cached(images, str(pdf_path))

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

# ============ 命令行入口 ============

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PDF OCR 工具 - 支持 MinerU API/PaddleOCR/EasyOCR")
    parser.add_argument("pdf_path", nargs="?", help="PDF 文件路径")
    parser.add_argument("-o", "--output", help="输出文本文件路径")
    parser.add_argument("--json", help="输出 JSON 元数据路径")
    parser.add_argument("--preview", action="store_true", help="预览 PDF 内容")
    parser.add_argument("--pages", type=int, default=3, help="预览页数")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存")
    parser.add_argument("-e", "--engine", choices=["mineru_api", "paddleocr", "rapidocr", "easyocr", "auto"],
                        default="auto", help="指定 OCR 引擎 (默认自动选择)")
    parser.add_argument("--set-token", metavar="TOKEN", help="设置 MinerU API Token")
    parser.add_argument("--show-token", action="store_true", help="显示当前配置的 MinerU API Token")
    parser.add_argument("--clear-cache", action="store_true", help="清空所有缓存")

    args = parser.parse_args()

    # 处理 Token 相关命令
    if args.set_token:
        if set_mineru_token(args.set_token):
            print("MinerU API Token 已保存到:", CONFIG_FILE)
        else:
            print("保存 Token 失败")
        exit(0)

    if args.show_token:
        token = get_mineru_token()
        if token:
            print(f"MinerU API Token: {token[:20]}...{token[-10:]}")
        else:
            print("未配置 MinerU API Token")
        exit(0)

    if args.clear_cache:
        cache.flush()
        print("缓存已清空")
        exit(0)

    # 需要 PDF 文件路径
    if not args.pdf_path:
        parser.print_help()
        exit(1)

    if args.preview:
        # 预览模式
        print(view_pdf(args.pdf_path, args.pages))
    else:
        # OCR 模式
        engine = None if args.engine == "auto" else args.engine
        text, metadata = ocr_pdf(args.pdf_path, args.output, use_cache=not args.no_cache, engine=engine)

        print(f"\nOCR 完成！")
        print(f"总页数: {metadata.get('total_pages', 'N/A')}")
        print(f"总字符数: {metadata['total_chars']}")
        print(f"使用引擎: {metadata['ocr_engine']}")

        if args.json:
            with open(args.json, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
