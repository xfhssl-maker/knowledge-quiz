#!/usr/bin/env python3
"""
AI 题目生成器 v2.0
根据知识库生成多样化选择题，利用交叉干扰项提升题目质量
支持6种题型：数值型、定义型、挖空型、归属型、排序型、对比型
"""

import json
import random
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class Question:
    """题目数据结构"""
    id: str
    type: str           # choice
    subtype: str        # numeric / definition / fillblank / belong / sequence / compare
    section: str
    topic: str
    knowledge_point_id: str
    question: str
    options: List[str]
    answer: str
    explanation: str
    difficulty: int

    def to_dict(self):
        return asdict(self)


class QuestionGenerator:
    """题目生成器 v2.0 - 多题型 + 交叉干扰"""

    def __init__(self):
        self.questions: List[Question] = []
        self.q_counter = 0
        self.all_kps: List[Dict] = []
        self.kps_by_section: Dict[str, List[Dict]] = defaultdict(list)
        self.kps_by_topic: Dict[str, List[Dict]] = defaultdict(list)

    def generate_id(self) -> str:
        self.q_counter += 1
        return f"q-{self.q_counter:03d}"

    # ============ 索引与干扰项 ============

    def _build_index(self, kps: List[Dict]):
        """建立知识点索引，用于交叉干扰"""
        self.all_kps = kps
        for kp in kps:
            sec = kp.get('section', '')
            topic = kp.get('topic', '')
            if sec:
                self.kps_by_section[sec].append(kp)
            if topic:
                self.kps_by_topic[topic].append(kp)

    def _get_same_section_kps(self, kp: Dict) -> List[Dict]:
        """获取同章节其他知识点"""
        section = kp.get('section', '')
        return [k for k in self.kps_by_section.get(section, []) if k.get('id') != kp.get('id')]

    def _get_content_distractors(self, kp: Dict, count: int = 3, max_len: int = 120) -> List[str]:
        """从同章节其他知识点中提取内容片段作为干扰项"""
        candidates = self._get_same_section_kps(kp)
        if len(candidates) < count:
            # 不足时从全局补充
            candidates += [k for k in self.all_kps
                          if k.get('id') != kp.get('id') and k not in candidates]
        random.shuffle(candidates)
        distractors = []
        for c in candidates:
            content = c.get('content', '').strip()
            if content and len(content) >= 10:
                # 截取合理长度的片段
                text = content[:max_len]
                if len(content) > max_len:
                    text += "..."
                # 避免和已有干扰项重复
                if text not in distractors:
                    distractors.append(text)
            if len(distractors) >= count:
                break
        return distractors

    def _get_title_distractors(self, kp: Dict, count: int = 3) -> List[str]:
        """从同章节其他知识点中提取标题作为干扰项"""
        candidates = self._get_same_section_kps(kp)
        if len(candidates) < count:
            candidates += [k for k in self.all_kps
                          if k.get('id') != kp.get('id') and k not in candidates]
        random.shuffle(candidates)
        distractors = []
        for c in candidates:
            title = c.get('title', '').strip()
            if title and title not in distractors and len(title) >= 2:
                distractors.append(title)
            if len(distractors) >= count:
                break
        return distractors

    def _shuffle_options(self, correct: str, wrongs: List[str]) -> Tuple[List[str], str]:
        """随机排列选项，返回 (options, correct_letter)"""
        all_opts = [correct] + wrongs[:3]
        random.shuffle(all_opts)
        idx = all_opts.index(correct)
        letter = chr(65 + idx)
        options = [f"{chr(65 + i)}. {opt}" for i, opt in enumerate(all_opts)]
        return options, letter

    # ============ 6种题型 ============

    def _gen_numeric(self, kp: Dict) -> Optional[Question]:
        """题型1: 数值型 - 提取数值，问具体数量/距离"""
        content = kp.get('content', '')
        title = kp.get('title', '')
        section = kp.get('section', '')
        topic = kp.get('topic', '')
        kp_id = kp.get('id', '')

        # 匹配数字+单位
        units = r'(cm|ml|min|m|mg|mmHg|%|天|小时|次|个|岁|层|种|块|对|条|支|根|部|期|篇|章|节|页|名|位|项|类|种|种)'
        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*' + units, content)
        if not numbers:
            return None

        num_value, unit = numbers[0]
        try:
            num = float(num_value)
        except ValueError:
            return None

        # 根据标题推断问法
        question_templates = [
            f"【{section}】{title}约为多少？",
            f"【{section}】{title}的数量是？",
            f"【{section}】关于{title}，正确的数值是？",
        ]
        question_text = random.choice(question_templates)

        # 生成数值干扰项
        wrong_values = set()
        if num == int(num):
            offsets = [-2, -1, 1, 2, 3, -3, 5, -5, 10, -10]
            random.shuffle(offsets)
            for offset in offsets:
                wrong = int(num + offset)
                if wrong > 0 and wrong != int(num):
                    wrong_values.add(wrong)
                if len(wrong_values) >= 3:
                    break
            while len(wrong_values) < 3:
                wrong_values.add(int(num + random.randint(4, 15)))
        else:
            for factor in [0.8, 1.2, 1.5, 0.5, 2.0, 0.6, 1.8]:
                wrong = round(num * factor, 1)
                if wrong > 0 and wrong != num:
                    wrong_values.add(wrong)
                if len(wrong_values) >= 3:
                    break

        wrong_list = list(wrong_values)[:3]
        correct_opt = f"{num_value}{unit}"
        wrong_opts = [f"{w}{unit}" for w in wrong_list]

        options, answer = self._shuffle_options(correct_opt, wrong_opts)

        return Question(
            id=self.generate_id(), type='choice', subtype='numeric',
            section=section, topic=topic, knowledge_point_id=kp_id,
            question=question_text, options=options, answer=answer,
            explanation=content, difficulty=kp.get('difficulty', 2)
        )

    def _gen_definition(self, kp: Dict) -> Optional[Question]:
        """题型2: 定义型 - 术语：定义格式"""
        content = kp.get('content', '')
        title = kp.get('title', '')
        section = kp.get('section', '')
        topic = kp.get('topic', '')
        kp_id = kp.get('id', '')

        # 检测术语：定义 的分隔
        sep_match = re.search(r'[：:——]', content)
        if not sep_match:
            return None

        pos = sep_match.start()
        term = content[:pos].strip()
        definition = content[pos + 1:].lstrip('：:——').strip()

        if len(term) < 2 or len(definition) < 8:
            return None

        # 问法
        question_templates = [
            f"【{section}】{term}是指什么？",
            f"【{section}】{term}的定义是？",
            f"【{section}】关于{term}，以下哪项描述正确？",
        ]
        question_text = random.choice(question_templates)

        # 正确选项
        correct_opt = definition[:150] if len(definition) > 150 else definition

        # 从同章节其他知识点抽取干扰项
        distractors = self._get_content_distractors(kp, count=3, max_len=150)

        if len(distractors) < 3:
            return None

        options, answer = self._shuffle_options(correct_opt, distractors[:3])

        return Question(
            id=self.generate_id(), type='choice', subtype='definition',
            section=section, topic=topic, knowledge_point_id=kp_id,
            question=question_text, options=options, answer=answer,
            explanation=content, difficulty=kp.get('difficulty', 2)
        )

    def _gen_fillblank(self, kp: Dict) -> Optional[Question]:
        """题型3: 挖空型 - 将列举中某项挖空"""
        content = kp.get('content', '')
        title = kp.get('title', '')
        section = kp.get('section', '')
        topic = kp.get('topic', '')
        kp_id = kp.get('id', '')

        # 检测明确的列举格式（不含通用冒号分隔，避免过度触发）
        list_content = None
        # 优先匹配"包括"、"分为"等明确列举词
        for pattern in [r'包括(.+)', r'分为(.+)', r'由(.+)组成']:
            match = re.search(pattern, content)
            if match:
                list_content = match.group(1).strip()
                break

        if not list_content or len(list_content) < 6:
            return None

        # 用顿号/逗号分割
        items = re.split(r'[、，,；;]', list_content)
        items = [item.strip() for item in items if len(item.strip()) >= 2]

        if len(items) < 3:
            return None

        # 随机挖掉一个项
        blank_idx = random.randint(0, len(items) - 1)
        blank_item = items[blank_idx]
        blanked = list_content.replace(blank_item, '____', 1)

        # 清理问法：不要把整个content塞进去
        question_text = f"【{section}】{title}中，横线处应填？({blanked[:80]})"

        # 干扰项：从同章节其他知识点的标题中取 + 列表中其他项
        other_items = [item for item in items if item != blank_item]
        random.shuffle(other_items)

        title_dist = self._get_title_distractors(kp, count=5)

        wrong_opts = []
        # 优先用列表中其他项（最真实的干扰）
        for item in other_items:
            if item not in wrong_opts:
                wrong_opts.append(item)
            if len(wrong_opts) >= 2:
                break
        # 补充同章节标题
        for td in title_dist:
            if td not in wrong_opts and td != blank_item and len(td) <= 15:
                wrong_opts.append(td)
            if len(wrong_opts) >= 3:
                break

        # 最后兜底
        while len(wrong_opts) < 3:
            fake = f"其他{random.choice(['结构', '类型', '部位', '成分'])}"
            if fake not in wrong_opts:
                wrong_opts.append(fake)

        options, answer = self._shuffle_options(blank_item, wrong_opts[:3])

        return Question(
            id=self.generate_id(), type='choice', subtype='fillblank',
            section=section, topic=topic, knowledge_point_id=kp_id,
            question=question_text, options=options, answer=answer,
            explanation=content, difficulty=kp.get('difficulty', 2)
        )

    def _gen_belong(self, kp: Dict) -> Optional[Question]:
        """题型4: 归属判断型 - 属于/不属于"""
        content = kp.get('content', '')
        title = kp.get('title', '')
        section = kp.get('section', '')
        topic = kp.get('topic', '')
        kp_id = kp.get('id', '')

        # 需要至少3个同章节知识点才有意义
        same_sec = self._get_same_section_kps(kp)
        if len(same_sec) < 3:
            return None

        # 随机选择"属于"或"不属于"
        is_positive = random.choice([True, False])

        # 提取本知识点的核心描述
        correct_desc = content[:120] if len(content) <= 120 else content[:120] + "..."

        # 用 topic（如果有）作为归类标签，比 title 更合适
        label = topic if topic and len(topic) <= 10 else section
        if is_positive:
            question_text = f"【{section}】以下哪项属于「{label}」？"
        else:
            question_text = f"【{section}】以下哪项不属于「{label}」？"

        # 干扰项：同章节其他知识点
        distractors = self._get_content_distractors(kp, count=3, max_len=120)
        if len(distractors) < 3:
            return None

        if is_positive:
            options, answer = self._shuffle_options(correct_desc, distractors[:3])
        else:
            # "不属于"题：答案应该是某个干扰项（不属于该主题的内容）
            all_opts = distractors[:3] + [correct_desc]
            random.shuffle(all_opts)
            answer = None
            for i, opt in enumerate(all_opts):
                if opt in distractors[:3]:
                    answer = chr(65 + i)
                    break
            if not answer:
                answer = 'A'
            options = [f"{chr(65 + i)}. {opt}" for i, opt in enumerate(all_opts)]

        return Question(
            id=self.generate_id(), type='choice', subtype='belong',
            section=section, topic=topic, knowledge_point_id=kp_id,
            question=question_text, options=options, answer=answer,
            explanation=content, difficulty=kp.get('difficulty', 2)
        )

    def _gen_sequence(self, kp: Dict) -> Optional[Question]:
        """题型5: 排序型 - 含顺序信息"""
        content = kp.get('content', '')
        title = kp.get('title', '')
        section = kp.get('section', '')
        topic = kp.get('topic', '')
        kp_id = kp.get('id', '')

        # 检测是否含顺序信息
        has_sequence = bool(
            re.search(r'依次|顺序|第一.*第二|首先.*然后|先后|由.*到|从.*到', content)
        )
        if not has_sequence:
            return None

        # 提取序号项
        items = re.findall(r'第[一二三四五六七八九十\d]+[个步骤期层阶段]?[：:是]?\s*([^\s，,。；;第]+)', content)
        if len(items) < 3:
            return None

        # 检测"由外向内"/"由内向外"等方向性
        direction_match = re.search(r'由[内外上下]向[内外上下]', content)
        direction = direction_match.group(0) if direction_match else ''

        if direction:
            question_text = f"【{section}】{direction}依次经过的结构是？"
        else:
            question_text = f"【{section}】{title}的正确顺序是？"

        correct_opt = ' → '.join(items[:4])
        # 生成打乱顺序的干扰项
        wrong_opts = []
        for _ in range(3):
            shuffled = items[:4]
            random.shuffle(shuffled)
            opt = ' → '.join(shuffled)
            if opt != correct_opt and opt not in wrong_opts:
                wrong_opts.append(opt)

        while len(wrong_opts) < 3:
            shuffled = items[:4]
            random.shuffle(shuffled)
            opt = ' → '.join(shuffled)
            if opt != correct_opt and opt not in wrong_opts:
                wrong_opts.append(opt)

        options, answer = self._shuffle_options(correct_opt, wrong_opts[:3])

        return Question(
            id=self.generate_id(), type='choice', subtype='sequence',
            section=section, topic=topic, knowledge_point_id=kp_id,
            question=question_text, options=options, answer=answer,
            explanation=content, difficulty=kp.get('difficulty', 2)
        )

    def _gen_compare(self, kp: Dict) -> Optional[Question]:
        """题型6: 对比选择型 - 兜底题型，利用交叉干扰"""
        content = kp.get('content', '')
        title = kp.get('title', '')
        section = kp.get('section', '')
        topic = kp.get('topic', '')
        kp_id = kp.get('id', '')

        if len(content) < 10:
            return None

        # 多样化问法
        question_templates = [
            f"【{section}】关于「{title}」，以下哪项描述正确？",
            f"【{section}】下列关于{title}的描述，正确的是？",
            f"【{section}】关于{title}，哪项说法是正确的？",
        ]
        question_text = random.choice(question_templates)

        # 正确选项
        correct_opt = content[:150] if len(content) <= 150 else content[:150] + "..."

        # 交叉干扰：同章节其他知识点内容
        distractors = self._get_content_distractors(kp, count=3, max_len=150)

        # 如果交叉干扰不足，用简单改写
        while len(distractors) < 3:
            idx = len(distractors)
            distractors.append(f"与{title}无关的描述{idx + 1}")

        options, answer = self._shuffle_options(correct_opt, distractors[:3])

        return Question(
            id=self.generate_id(), type='choice', subtype='compare',
            section=section, topic=topic, knowledge_point_id=kp_id,
            question=question_text, options=options, answer=answer,
            explanation=content, difficulty=kp.get('difficulty', 2)
        )

    # ============ 主生成方法 ============

    def generate_from_knowledge_base(self, kb_path: str) -> List[Question]:
        """从知识库生成多样化选择题"""
        with open(kb_path, 'r', encoding='utf-8') as f:
            kb_data = json.load(f)

        kps = kb_data.get('knowledge_points', [])
        self._build_index(kps)

        subtype_counts = defaultdict(int)

        for kp in kps:
            # 按优先级尝试各题型，但 definition/belong/compare 随机轮换避免单一
            q = (self._gen_numeric(kp)
                 or self._gen_fillblank(kp)
                 or self._gen_sequence(kp)
                 or self._gen_varied(kp))  # definition/belong/compare 随机选一

            if q:
                self.questions.append(q)
                subtype_counts[q.subtype] += 1

        return self.questions

    def _gen_varied(self, kp: Dict) -> Optional[Question]:
        """在 definition/belong/compare 中随机选一种，避免题型过于集中"""
        same_sec = self._get_same_section_kps(kp)
        has_enough_peers = len(same_sec) >= 3

        # 构建可选题型列表
        candidates = []
        candidates.append('definition')  # 总是可选
        if has_enough_peers:
            candidates.append('belong')
        candidates.append('compare')

        # 随机选择
        choice = random.choice(candidates)

        if choice == 'definition':
            return self._gen_definition(kp)
        elif choice == 'belong':
            return self._gen_belong(kp)
        else:
            return self._gen_compare(kp)

    def save(self, output_path: str):
        """保存题库"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([q.to_dict() for q in self.questions], f, ensure_ascii=False, indent=2)

        # 统计题型分布
        subtype_counts = defaultdict(int)
        for q in self.questions:
            subtype_counts[q.subtype] += 1

        print(f"[OK] 题库已保存: {output_path}")
        print(f"   - 总题数: {len(self.questions)}")
        for subtype, count in sorted(subtype_counts.items()):
            print(f"   - {subtype}: {count} 道")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='AI 题目生成器 v2.0')
    parser.add_argument('input', nargs='?', default='~/.knowledge-quiz/knowledge-base.json',
                        help='知识库文件路径')
    parser.add_argument('-o', '--output', default='~/.knowledge-quiz/questions.json',
                        help='输出文件路径')

    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"知识库文件不存在: {input_path}")
        return

    generator = QuestionGenerator()
    generator.generate_from_knowledge_base(str(input_path))

    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generator.save(str(output_path))


if __name__ == '__main__':
    main()
