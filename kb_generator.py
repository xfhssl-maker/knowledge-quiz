#!/usr/bin/env python3
"""
AI 知识库生成器
从 OCR 识别结果生成结构化的知识库 JSON
"""

import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class KnowledgePoint:
    """知识点数据结构"""
    id: str
    section: str
    topic: str
    title: str
    content: str
    keywords: List[str]
    difficulty: int
    source: str = ""

    def to_dict(self):
        return asdict(self)

class KnowledgeBaseGenerator:
    """知识库生成器"""

    def __init__(self):
        self.knowledge_points: List[KnowledgePoint] = []
        self.sections = set()
        self.topics = set()
        self.kp_counter = 0

    def generate_id(self) -> str:
        """生成知识点 ID"""
        self.kp_counter += 1
        return f"kp-{self.kp_counter:03d}"

    def extract_keywords(self, text: str) -> List[str]:
        """提取关键词（通用方法，不限定领域）"""
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
        from collections import Counter
        word_freq = Counter(chinese_words)
        # 过滤停用词
        stopwords = {'的是', '了一', '在一', '和一', '以一', '上一', '下一', '中一',
                     '这是', '那个', '这个', '什么', '怎么', '如果', '因为', '所以',
                     '但是', '而且', '或者', '以及', '不是', '没有', '可以', '需要'}
        for word, _ in word_freq.most_common(10):
            if word not in stopwords and word not in keywords and len(word) >= 2:
                keywords.append(word)

        # 去重并限制数量
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen and len(kw) >= 2:
                seen.add(kw)
                unique.append(kw)

        return unique[:5]

    def estimate_difficulty(self, content: str) -> int:
        """评估难度 (1-5)"""
        length = len(content)

        if length < 20:
            return 1
        elif length < 50:
            return 2
        elif length < 100:
            return 3
        elif length < 200:
            return 4
        else:
            return 5

    def parse_text_content(self, text: str, source_name: str = "知识库") -> Dict[str, Any]:
        """
        解析文本内容，生成结构化知识库
        支持多种格式：
        1. 章节标题格式：# 章节名 / ## 考点名
        2. 条目格式：1. 知识点 / - 知识点
        3. 键值格式：标题：内容
        """

        lines = text.strip().split('\n')

        current_section = "通用"
        current_topic = "基础知识"
        pending_content = []
        pending_title = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测章节标题 (# 或 数字. 或 【】)
            section_match = re.match(r'^#+\s*(.+)$', line)
            if section_match:
                # 保存之前累积的内容
                if pending_title and pending_content:
                    self._add_knowledge_point(
                        pending_title,
                        '\n'.join(pending_content),
                        current_section,
                        current_topic,
                        source_name
                    )
                    pending_content = []

                title = section_match.group(1).strip()
                if '章' in title or '篇' in title:
                    current_section = title
                else:
                    current_topic = title
                continue

            # 检测【章节】格式
            bracket_match = re.match(r'^【(.+?)】(.*)$', line)
            if bracket_match:
                section_name = bracket_match.group(1)
                rest = bracket_match.group(2).strip()

                if pending_title and pending_content:
                    self._add_knowledge_point(
                        pending_title,
                        '\n'.join(pending_content),
                        current_section,
                        current_topic,
                        source_name
                    )
                    pending_content = []

                current_section = section_name
                if rest:
                    pending_title = rest
                continue

            # 检测数字编号知识点 (1. / 1、 / （1）)
            numbered_match = re.match(r'^[（(]?(\d+)[)）.、]\s*(.+)$', line)
            if numbered_match:
                # 保存之前的
                if pending_title and pending_content:
                    self._add_knowledge_point(
                        pending_title,
                        '\n'.join(pending_content),
                        current_section,
                        current_topic,
                        source_name
                    )
                    pending_content = []

                pending_title = numbered_match.group(2).strip()
                continue

            # 检测键值格式 (标题：内容)
            kv_match = re.match(r'^([^:：]+)[：:]\s*(.+)$', line)
            if kv_match:
                if pending_title and pending_content:
                    self._add_knowledge_point(
                        pending_title,
                        '\n'.join(pending_content),
                        current_section,
                        current_topic,
                        source_name
                    )
                    pending_content = []

                title = kv_match.group(1).strip()
                content = kv_match.group(2).strip()

                # 如果内容很长，直接创建知识点
                if len(content) > 10:
                    self._add_knowledge_point(
                        title,
                        content,
                        current_section,
                        current_topic,
                        source_name
                    )
                else:
                    pending_title = title
                    pending_content = [content] if content else []
                continue

            # 普通文本行
            if pending_title:
                pending_content.append(line)
            elif len(line) > 5:
                # 没有标题时的独立内容
                pending_title = line[:50] + ('...' if len(line) > 50 else '')
                pending_content = [line]

        # 保存最后的知识点
        if pending_title and pending_content:
            self._add_knowledge_point(
                pending_title,
                '\n'.join(pending_content),
                current_section,
                current_topic,
                source_name
            )

        return self.to_dict()

    def _add_knowledge_point(self, title: str, content: str, section: str, topic: str, source: str):
        """添加知识点"""
        # 清理内容
        content = content.strip()
        if not content or len(content) < 5:
            return

        # 检查是否已存在相似内容
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        existing = [kp for kp in self.knowledge_points if kp.id.endswith(content_hash)]
        if existing:
            return

        kp = KnowledgePoint(
            id=f"{self.generate_id()}-{content_hash}",
            section=section,
            topic=topic,
            title=title[:100],  # 限制标题长度
            content=content,
            keywords=self.extract_keywords(title + ' ' + content),
            difficulty=self.estimate_difficulty(content),
            source=source
        )

        self.knowledge_points.append(kp)
        self.sections.add(section)
        self.topics.add(topic)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": "知识库",
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "sections": sorted(list(self.sections)),
            "topics": sorted(list(self.topics)),
            "knowledge_points": [kp.to_dict() for kp in self.knowledge_points],
            "stats": {
                "total_points": len(self.knowledge_points),
                "total_sections": len(self.sections),
                "total_topics": len(self.topics)
            }
        }

    def save(self, output_path: str):
        """保存知识库"""
        data = self.to_dict()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] 知识库已保存: {output_path}")
        print(f"   - 知识点: {len(self.knowledge_points)} 个")
        print(f"   - 章节: {len(self.sections)} 个")
        print(f"   - 考点: {len(self.topics)} 个")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='AI 知识库生成器')
    parser.add_argument('input', help='输入文件 (OCR 结果)')
    parser.add_argument('-o', '--output', default='~/.knowledge-quiz/knowledge-base.json',
                        help='输出文件路径')
    parser.add_argument('-n', '--name', default='知识库', help='知识库名称')

    args = parser.parse_args()

    # 读取输入
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 生成知识库
    generator = KnowledgeBaseGenerator()
    generator.parse_text_content(text, args.name)

    # 保存
    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generator.save(str(output_path))


if __name__ == '__main__':
    main()
