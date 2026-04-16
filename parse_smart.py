#!/usr/bin/env python3
"""
智能解析 PDF 文本
合并相关内容行，生成更完整的知识点
支持内容完整性检测，过滤水印广告
通用化：不限定任何学科领域
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from collections import Counter

# 需要过滤的水印/广告关键词（通用）
WATERMARK_PATTERNS = [
    r'时政公考资料站',
    r'公考资料站',
    r'时政公考资',
    r'时政公考',
    r'时政公老',
    r'时政公',
    r'时政',
    r'卡卡考公',
    r'微信公众号',
    r'放信公众号',
    r'医疗考试',
    r'\d+页\s*===',  # 页码标记
    r'资料立',
    r'资料站',
    r'资料',
    r'专士站',
    r'公共',
    r'公众号',
]

# 不应作为章节标题的短文本黑名单
SECTION_BLACKLIST = {
    '时政', '时政公考', '卡卡考公', '公考', '资料站', '资料立',
    '医学基础必背考点',  # 文档标题不是章节
    '微信公众号', '放信公众号', '资料', '公众号', '公共',
}

def is_watermark(line: str) -> bool:
    """检查是否是水印/广告"""
    for pattern in WATERMARK_PATTERNS:
        if re.search(pattern, line):
            return True
    return False

def clean_line(line: str) -> str:
    """清理行内的水印内容"""
    for pattern in WATERMARK_PATTERNS:
        line = re.sub(pattern, '', line)
    return line.strip()

def is_section_title(line: str, all_lines: List[str] = None) -> bool:
    """
    判断是否为章节标题（保守策略，仅匹配明确的章节名称格式）：
    - 以"学"/"论"/"法"/"理"/"史"等常见学科尾缀结尾，且长度2-6字
    - 不在水印黑名单中
    - 不包含数字或特殊字符
    """
    line = line.strip()
    if not line or len(line) > 8:
        return False

    # 黑名单排除
    if line in SECTION_BLACKLIST:
        return False

    # 必须是纯中文
    if not re.match(r'^[\u4e00-\u9fa5]+$', line):
        return False

    # 太短的（1-2字）不算章节
    if len(line) < 2:
        return False

    # 常见学科/章节标题尾缀（保守匹配）
    section_suffixes = [
        '学', '论', '法', '理', '史',
    ]
    for suffix in section_suffixes:
        if line.endswith(suffix) and len(line) >= 2:
            return True

    return False

def smart_parse(text_file: str) -> Tuple[List[Dict], List[str], List[str]]:
    """智能解析 PDF 文本"""
    with open(text_file, 'r', encoding='utf-8') as f:
        content = f.read()

    knowledge_points = []
    sections = []
    topics = set()
    kp_id = 1

    # 按页分割
    pages = content.split('=== 第')

    current_section = ""
    current_topic = ""
    pending_lines = []

    def flush_pending():
        """保存累积的知识点"""
        nonlocal kp_id, pending_lines

        if not pending_lines:
            return

        # 合并所有行
        full_content = " ".join(pending_lines)
        if len(full_content) < 10:
            pending_lines = []
            return

        # 过滤纯数字、页码等无效内容
        if re.match(r'^[\d\s\-=]+$', full_content):
            pending_lines = []
            return

        # 提取标题（第一行的前部分）
        first_line = pending_lines[0]

        # 尝试提取标题
        title = first_line[:80]
        for sep in ['——', '－', '：', ':', '-']:
            if sep in first_line:
                parts = first_line.split(sep, 1)
                title = parts[0].strip()
                if len(title) < 3:
                    title = first_line[:50]
                break

        # 清理标题
        title = clean_line(title)
        if len(title) < 3:
            pending_lines = []
            return

        # 检查标题是否是有效知识点（不是目录项）
        if re.match(r'^\d+\s*$', title):  # 纯数字
            pending_lines = []
            return

        kp = {
            "id": f"kp-{kp_id:03d}",
            "section": current_section,
            "topic": current_topic if current_topic else "其他",
            "title": title,
            "content": full_content,
            "keywords": extract_keywords(full_content),
            "difficulty": 2
        }
        knowledge_points.append(kp)
        kp_id += 1

        if current_topic and current_topic not in ["未知", "其他", ""]:
            topics.add(current_topic)

        pending_lines = []

    for page_idx, page in enumerate(pages):
        if not page.strip():
            continue

        lines = page.split('\n')

        for line in lines:
            original_line = line
            line = line.strip()

            # 跳过空行、分隔符、页码
            if not line or line.startswith('_') or line.startswith('='):
                continue
            if re.match(r'^\d+$', line):
                continue
            if line.startswith('=== 第'):
                continue

            # 过滤水印/广告
            if is_watermark(line):
                continue

            # 清理行内水印
            line = clean_line(line)
            if not line or len(line) < 3:
                continue

            # 检测章节标题（通用启发式）
            if is_section_title(line):
                flush_pending()
                # 归一化：去掉 OCR 误加的尾缀 "一"、"，" 等
                normalized = re.sub(r'[一，,]$', '', line)
                current_section = normalized
                if current_section not in sections:
                    sections.append(current_section)
                continue

            # 检测考点标题
            topic_match = re.match(r'考点\s*(\d*)\s*[：:]*\s*(.+)', line)
            if topic_match:
                flush_pending()
                current_topic = topic_match.group(2).strip()
                if current_topic:
                    topics.add(current_topic)
                continue

            # 检测数字编号 (1. 2. 等)
            num_match = re.match(r'^(\d+)\.\s*(.+)', line)
            if num_match:
                # 保存之前的累积
                flush_pending()
                # 开始新的知识点
                point_content = num_match.group(2).strip()
                if len(point_content) >= 5:
                    pending_lines.append(point_content)
                continue

            # 检测括号编号 (1) (2)
            bracket_match = re.match(r'^\((\d+)\)\s*(.+)', line)
            if bracket_match:
                point_content = bracket_match.group(2).strip()
                if len(point_content) >= 5:
                    pending_lines.append(point_content)
                continue

            # 其他行：累积到当前知识点
            if len(line) >= 5:
                pending_lines.append(line)

    # 保存最后累积的内容
    flush_pending()

    return knowledge_points, sections, list(topics)

def extract_keywords(text: str) -> List[str]:
    """提取关键词（通用方法，不限定领域）"""
    # 通用模式：从文本结构中提取术语
    patterns = [
        r'[\u4e00-\u9fa5]{2,6}(?=：|:)',          # 冒号前的术语
        r'[\u4e00-\u9fa5]{2,4}(?=\(|（)',          # 括号前的术语
        r'[A-Z][a-zA-Z]+(?=\s|$)',                  # 英文术语
        r'[\u4e00-\u9fa5]{2,4}(?=的|是|为|有)',     # 谓语前的名词
    ]

    keywords = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        keywords.extend(matches[:3])

    # 通用 fallback：提取高频 2-4 字中文词组
    chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
    word_freq = Counter(chinese_words)
    stopwords = {'的是', '了一', '在一', '和一', '以一', '上一', '下一', '中一',
                 '这是', '那个', '这个', '什么', '怎么', '如果', '因为', '所以',
                 '但是', '而且', '或者', '以及', '不是', '没有', '可以', '需要'}
    for word, _ in word_freq.most_common(10):
        if word not in stopwords and word not in keywords and len(word) >= 2:
            keywords.append(word)

    # 去重
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen and len(kw) >= 2:
            seen.add(kw)
            unique.append(kw)

    return unique[:6]

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

def generate_questions(kp: Dict, q_id: int) -> Tuple[List, int]:
    """生成选择题 - 委托给 QuestionGenerator"""
    # 延迟导入避免循环依赖
    from question_generator import QuestionGenerator

    # 单个知识点无法做交叉干扰，用简化版
    content = kp.get('content', '')
    title = kp.get('title', '')
    section = kp.get('section', '')
    topic = kp.get('topic', '')

    if len(content) < 10:
        return [], q_id

    questions = []

    # 数值型
    numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(cm|ml|min|m|mg|mmHg|%|天|小时|次|个|岁|层|种|块)', content)
    if numbers:
        num_value, unit = numbers[0]
        try:
            num = float(num_value)
            correct_opt = f"{num_value}{unit}"
            wrong_values = set()
            if num == int(num):
                offsets = [-2, -1, 1, 2, 3, -3, 5]
                random.shuffle(offsets)
                for off in offsets:
                    w = int(num + off)
                    if w > 0 and w != int(num):
                        wrong_values.add(w)
                    if len(wrong_values) >= 3:
                        break
            else:
                for f in [0.8, 1.2, 1.5, 0.5]:
                    w = round(num * f, 1)
                    if w > 0 and w != num:
                        wrong_values.add(w)
                    if len(wrong_values) >= 3:
                        break
            wrong_list = list(wrong_values)[:3]
            wrong_opts = [f"{w}{unit}" for w in wrong_list]

            all_opts = [correct_opt] + wrong_opts
            random.shuffle(all_opts)
            idx = all_opts.index(correct_opt)
            answer = chr(65 + idx)
            options = [f"{chr(65+i)}. {v}" for i, v in enumerate(all_opts)]

            q_text = f"【{section}】{title}约为多少？"
            questions.append({
                "id": f"q-{q_id:03d}", "type": "choice", "subtype": "numeric",
                "section": section, "topic": topic, "knowledge_point_id": kp['id'],
                "question": q_text, "options": options, "answer": answer,
                "explanation": content, "difficulty": kp.get('difficulty', 2)
            })
            return questions, q_id + 1
        except (ValueError, IndexError):
            pass

    # 通用型：用交叉干扰（从同章节取）
    # 简化版：标题 + 截取内容作为干扰
    correct_desc = content[:150] if len(content) <= 150 else content[:150] + "..."

    # 尝试术语定义格式
    sep_match = re.search(r'[：:——]', content)
    if sep_match:
        pos = sep_match.start()
        term = content[:pos].strip()
        definition = content[pos+1:].lstrip('：:——').strip()
        if len(term) >= 2 and len(definition) >= 8:
            q_text = f"【{section}】{term}是指什么？"
            correct_desc = definition[:150] if len(definition) <= 150 else definition[:150] + "..."
        else:
            q_text = f"【{section}】关于「{title}」，以下哪项描述正确？"
    else:
        q_text = f"【{section}】关于「{title}」，以下哪项描述正确？"

    # 简化干扰项（无法交叉时用改写）
    distractors = [
        title + "的说法有误",
        "以上描述均不准确",
        "该描述需要补充前提条件",
    ]
    all_opts = [correct_desc] + distractors
    random.shuffle(all_opts)
    idx = all_opts.index(correct_desc)
    answer = chr(65 + idx)
    options = [f"{chr(65+i)}. {v}" for i, v in enumerate(all_opts)]

    questions.append({
        "id": f"q-{q_id:03d}", "type": "choice", "subtype": "compare",
        "section": section, "topic": topic, "knowledge_point_id": kp['id'],
        "question": q_text, "options": options, "answer": answer,
        "explanation": content, "difficulty": kp.get('difficulty', 2)
    })

    return questions, q_id + 1

def main():
    print("=" * 60)
    print("智能 PDF 知识点解析")
    print("=" * 60)

    input_path = Path("C:/Users/xfhss/.knowledge-quiz/pdf_pymupdf.txt")

    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}")
        return

    # 解析知识点
    print("\n正在解析知识点...")
    knowledge_points, sections, topics = smart_parse(str(input_path))
    print(f"提取 {len(knowledge_points)} 个知识点")

    # 过滤掉无效知识点
    valid_points = [kp for kp in knowledge_points if kp['section'] and len(kp['content']) >= 10]
    print(f"有效知识点: {len(valid_points)} 个")

    print(f"章节: {sections}")
    print(f"考点数: {len(topics)}")

    # 生成题目
    print("\n正在生成题目...")
    questions = []
    q_id = 1

    for kp in valid_points:
        qs, q_id = generate_questions(kp, q_id)
        questions.extend(qs)

    print(f"生成 {len(questions)} 道题目")

    # 统计
    choice_count = len([q for q in questions if q['type'] == 'choice'])

    section_stats = {}
    for kp in valid_points:
        sec = kp.get('section', '')
        section_stats[sec] = section_stats.get(sec, 0) + 1

    print(f"\n章节分布:")
    for sec, count in section_stats.items():
        print(f"  {sec}: {count} 个知识点")

    print(f"\n题型分布:")
    print(f"  选择题: {choice_count}")

    # 保存知识点
    source_name = input_path.stem
    kb_data = {
        "name": source_name,
        "source": input_path.name,
        "sections": sections,
        "topics": topics,
        "knowledge_points": valid_points,
        "statistics": {
            "total_points": len(valid_points),
            "total_questions": len(questions),
            "by_section": section_stats
        }
    }

    output_path = Path("C:/Users/xfhss/.knowledge-quiz/knowledge-base.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(kb_data, f, ensure_ascii=False, indent=2)
    print(f"\n知识点已保存: {output_path}")

    # 保存题目
    output_path = Path("C:/Users/xfhss/.knowledge-quiz/questions.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    print(f"题目已保存: {output_path}")

    # 显示示例
    print("\n" + "=" * 60)
    print("示例知识点:")
    for kp in valid_points[:3]:
        print(f"\n[{kp['section']}] {kp['topic']}")
        print(f"标题: {kp['title']}")
        print(f"内容: {kp['content'][:100]}...")
        print(f"完整度: {'完整' if is_content_complete(kp['content']) else '不完整'}")

if __name__ == "__main__":
    main()
