#!/usr/bin/env python3
"""
Knowledge Quiz 主流程
整合 OCR → AI 生成知识库 → AI 出题 → 启动界面
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 工作目录
WORK_DIR = Path(__file__).parent.expanduser()
WORK_DIR.mkdir(parents=True, exist_ok=True)

def check_ocr_result(input_path: Path) -> str:
    """检查输入是否需要 OCR 处理"""
    suffix = input_path.suffix.lower()

    # 已经是文本文件
    if suffix in ['.txt', '.md']:
        return input_path.read_text(encoding='utf-8')

    # PDF 文件 - 尝试提取文本层
    if suffix == '.pdf':
        print("📄 检测到 PDF 文件，尝试提取文本...")

        # 使用 PyMuPDF 提取
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(input_path))
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()

            if len(text.strip()) > 100:
                # 保存提取结果
                output_txt = WORK_DIR / f"{input_path.stem}_extracted.txt"
                output_txt.write_text(text, encoding='utf-8')
                print(f"✅ 提取文本层成功: {len(text)} 字符")
                return text
            else:
                print("⚠️ 文本层内容不足，可能需要 OCR")
                return ""
        except ImportError:
            print("⚠️ 未安装 PyMuPDF，无法提取 PDF 文本")
            return ""

    # JSON 文件
    if suffix == '.json':
        data = json.loads(input_path.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return "\n".join([item.get('content', str(item)) for item in data])
        elif isinstance(data, dict):
            return data.get('content', json.dumps(data, ensure_ascii=False))

    return ""

def generate_knowledge_base_with_ai(text: str, source_name: str) -> dict:
    """使用 AI 从文本生成知识库"""
    print("\n" + "="*50)
    print("🤖 AI 生成知识库")
    print("="*50)

    # 使用本地生成器
    from kb_generator import KnowledgeBaseGenerator

    generator = KnowledgeBaseGenerator()
    kb_data = generator.parse_text_content(text, source_name)

    return kb_data

def generate_questions_with_ai(kb_path: Path) -> list:
    """使用 AI 从知识库生成题目"""
    print("\n" + "="*50)
    print("📝 AI 生成题库")
    print("="*50)

    from question_generator import QuestionGenerator

    generator = QuestionGenerator()
    questions = generator.generate_from_knowledge_base(str(kb_path))

    return questions

def save_knowledge_base(kb_data: dict, output_path: Path):
    """保存知识库"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(kb_data, f, ensure_ascii=False, indent=2)

    stats = kb_data.get('stats', {})
    print(f"\n✅ 知识库已保存: {output_path}")
    print(f"   - 知识点: {stats.get('total_points', 0)} 个")
    print(f"   - 章节: {stats.get('total_sections', 0)} 个")
    print(f"   - 考点: {stats.get('total_topics', 0)} 个")

def save_questions(questions: list, output_path: Path):
    """保存题库"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump([q.to_dict() for q in questions], f, ensure_ascii=False, indent=2)

    choice_count = len([q for q in questions if q.type == 'choice'])

    print(f"\n✅ 题库已保存: {output_path}")
    print(f"   - 选择题: {choice_count} 道")

def start_gradio():
    """启动 Gradio 界面"""
    print("\n" + "="*50)
    print("🚀 启动 Gradio 界面")
    print("="*50)
    print("访问地址: http://127.0.0.1:7866")

    import subprocess
    subprocess.run([sys.executable, str(WORK_DIR / "quiz_app_v4.py")])

def main():
    parser = argparse.ArgumentParser(
        description='Knowledge Quiz - 知识库答题系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从 PDF 生成知识库和题库
  python pipeline.py input.pdf

  # 从文本文件生成
  python pipeline.py knowledge.txt

  # 只启动界面（使用现有数据）
  python pipeline.py --gradio

  # 重新生成题库
  python pipeline.py --generate-questions
        """
    )

    parser.add_argument('input', nargs='?', help='输入文件 (PDF/TXT/MD/JSON)')
    parser.add_argument('--gradio', '-g', action='store_true', help='启动 Gradio 界面')
    parser.add_argument('--generate-questions', action='store_true', help='重新生成题库')
    parser.add_argument('--name', '-n', default='知识库', help='知识库名称')
    parser.add_argument('--skip-kb', action='store_true', help='跳过知识库生成（仅生成题目）')
    parser.add_argument('--skip-questions', action='store_true', help='跳过题目生成')

    args = parser.parse_args()

    # 如果只是启动界面
    if args.gradio and not args.input:
        start_gradio()
        return

    # 需要输入文件
    if not args.input and not args.generate_questions:
        parser.print_help()
        print("\n❌ 错误: 请提供输入文件或使用 --gradio 启动界面")
        return

    # 检查输入文件
    if args.input:
        input_path = Path(args.input).expanduser()
        if not input_path.exists():
            print(f"❌ 文件不存在: {input_path}")
            return

        # Step 1: OCR / 提取文本
        print("\n" + "="*50)
        print("📖 步骤 1: 提取文本内容")
        print("="*50)

        text = check_ocr_result(input_path)

        if not text or len(text.strip()) < 50:
            print("❌ 无法提取足够的文本内容")
            print("   如果是扫描版 PDF，请先使用 OCR 工具处理")
            return

        print(f"✅ 提取成功: {len(text)} 字符")

        # Step 2: AI 生成知识库
        if not args.skip_kb:
            kb_data = generate_knowledge_base_with_ai(text, args.name)
            kb_path = WORK_DIR / "knowledge-base.json"
            save_knowledge_base(kb_data, kb_path)
        else:
            print("\n⏭️ 跳过知识库生成")

    # Step 3: AI 生成题目
    kb_path = WORK_DIR / "knowledge-base.json"

    if not args.skip_questions:
        if not kb_path.exists():
            print(f"❌ 知识库文件不存在: {kb_path}")
            print("   请先运行: python pipeline.py input.pdf")
            return

        questions = generate_questions_with_ai(kb_path)
        q_path = WORK_DIR / "questions.json"
        save_questions(questions, q_path)
    else:
        print("\n⏭️ 跳过题目生成")

    # Step 4: 启动界面
    print("\n" + "="*50)
    print("✅ 全部完成！")
    print("="*50)
    print("\n运行以下命令启动答题界面:")
    print("  python pipeline.py --gradio")

if __name__ == '__main__':
    main()
