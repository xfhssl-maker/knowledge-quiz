#!/usr/bin/env python3
"""
智能解析 PDF 文本
合并相关内容行，生成更完整的知识点
支持内容完整性检测，避免生成残缺题目
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

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

        # 提取标题（第一行的前部分）
        first_line = pending_lines[0]

        # 尝试提取标题
        title = first_line[:50]
        for sep in ['——', '－', '：', ':', '-']:
            if sep in first_line:
                parts = first_line.split(sep, 1)
                title = parts[0].strip()
                break

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

            # 检测章节标题
            if line in ['解剖学', '生理学', '药理学', '病理学']:
                flush_pending()
                current_section = line
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
    """提取关键词"""
    medical_terms = [
        '细胞', '组织', '器官', '系统', '神经', '血管', '骨骼', '肌肉',
        '心脏', '肝脏', '肾脏', '肺', '胃', '肠', '血液', '淋巴',
        '激素', '酶', '蛋白', '糖', '脂肪', '代谢', '免疫',
        '炎症', '肿瘤', '感染', '药物', '治疗', '诊断',
        '解剖', '生理', '病理', '药理', '临床', '症状',
        '受体', '递质', '离子', '电位', '渗透压', '血压',
        '呼吸', '循环', '消化', '排泄', '内分泌', '生殖',
        '脊髓', '脑', '反射', '传导', '收缩', '舒张',
        '滤过', '重吸收', '分泌', '合成', '分解',
        '抗生素', '抗菌', '消炎', '镇痛', '镇静', '催眠',
        '毒性', '副作用', '禁忌', '剂量', '浓度',
        '心电图', '体温', '脉搏', '呼吸频率',
        '白细胞', '红细胞', '血小板', '血红蛋白',
        '葡萄糖', '胰岛素', '甲状腺', '肾上腺',
        '青霉素', '头孢', '阿司匹林', '吗啡', '地高辛',
        '静脉', '动脉', '毛细血管', '心房', '心室'
    ]

    keywords = []
    for term in medical_terms:
        if term in text and term not in keywords:
            keywords.append(term)

    return keywords[:6]

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
    """生成题目"""
    questions = []
    content = kp['content']
    title = kp['title']
    section = kp.get('section', '')
    topic = kp.get('topic', '')

    # 检查内容是否完整
    content_complete = is_content_complete(content)

    # 提取数字（带单位）
    numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(cm|ml|min|m|mg|mmHg|%|天|小时|次|个|岁|cm²|ml/min)', content)

    # 生成选择题
    if numbers and content_complete:
        # 有明确数值且内容完整，生成数值选择题
        num_value, unit = numbers[0]
        q_text = f"【{section}】关于「{title}」，正确的数值是？"
        correct = f"{num_value}{unit}"

        try:
            num = float(num_value)
            if '.' in num_value:
                wrong1 = f"{num * 1.2:.1f}{unit}"
                wrong2 = f"{num * 0.8:.1f}{unit}"
                wrong3 = f"{num * 1.5:.1f}{unit}"
            else:
                wrong1 = f"{int(num * 1.2)}{unit}"
                wrong2 = f"{int(num * 0.8)}{unit}"
                wrong3 = f"{int(num * 1.5)}{unit}"
        except:
            wrong1, wrong2, wrong3 = "10" + unit, "20" + unit, "30" + unit

        options = [f"A. {correct}", f"B. {wrong1}", f"C. {wrong2}", f"D. {wrong3}"]
        answer = "A"

    elif content_complete and len(content) > 30:
        # 内容完整，生成判断型选择题
        # 截取合理长度
        display_content = content[:120] + "..." if len(content) > 120 else content
        q_text = f"【{section}】关于「{title}」，以下说法正确的是？"
        options = [
            f"A. {display_content}",
            "B. 该说法不正确",
            "C. 该说法部分正确",
            "D. 以上都不对"
        ]
        answer = "A"
    else:
        # 内容不完整，只生成判断题，不生成选择题
        # 生成判断题
        judgment_text = f"【{section}】{title}"
        if len(judgment_text) > 150:
            judgment_text = judgment_text[:150] + "..."

        questions.append({
            "id": f"q-{q_id:03d}",
            "type": "judgment",
            "section": section,
            "topic": topic,
            "knowledge_point_id": kp['id'],
            "question": judgment_text,
            "answer": True,
            "explanation": f"该知识点来自{section}" + (f"的{topic}" if topic else "") + f"。{content}",
            "difficulty": kp.get('difficulty', 2)
        })
        return questions, q_id + 1

    questions.append({
        "id": f"q-{q_id:03d}",
        "type": "choice",
        "section": section,
        "topic": topic,
        "knowledge_point_id": kp['id'],
        "question": q_text,
        "options": options,
        "answer": answer,
        "explanation": content,
        "difficulty": kp.get('difficulty', 2)
    })
    q_id += 1

    # 生成判断题
    judgment_text = f"【{section}】{title}：{content}"
    if len(judgment_text) > 180:
        judgment_text = judgment_text[:180] + "..."

    questions.append({
        "id": f"q-{q_id:03d}",
        "type": "judgment",
        "section": section,
        "topic": topic,
        "knowledge_point_id": kp['id'],
        "question": judgment_text,
        "answer": True,
        "explanation": f"该知识点来自{section}" + (f"的{topic}" if topic else ""),
        "difficulty": kp.get('difficulty', 2)
    })

    return questions, q_id + 1

def main():
    """主函数示例"""
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
    judgment_count = len([q for q in questions if q['type'] == 'judgment'])

    section_stats = {}
    for kp in valid_points:
        sec = kp.get('section', '')
        section_stats[sec] = section_stats.get(sec, 0) + 1

    print(f"\n章节分布:")
    for sec, count in section_stats.items():
        print(f"  {sec}: {count} 个知识点")

    print(f"\n题型分布:")
    print(f"  选择题: {choice_count}")
    print(f"  判断题: {judgment_count}")

    # 保存知识点
    kb_data = {
        "name": "医学基础必背考点",
        "source": "医学类-医学基础必背考点.pdf",
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

if __name__ == "__main__":
    main()
