#!/usr/bin/env python3
"""
Knowledge Quiz Gradio 应用
固定界面，内容从知识库 JSON 文件加载
支持错题集、知识点分类查看（卡片式显示）、智能题目生成
"""

import os
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

import json
import gradio as gr
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============ 数据目录 ============
# 优先使用用户数据目录 ~/.knowledge-quiz/，如果不存在则使用脚本所在目录
DATA_DIR = Path.home() / ".knowledge-quiz"
if not (DATA_DIR / "knowledge-base.json").exists():
    DATA_DIR = Path(__file__).parent

# ============ 数据加载 ============

def load_knowledge_base():
    """加载知识库数据"""
    kb_path = DATA_DIR / "knowledge-base.json"
    q_path = DATA_DIR / "questions.json"

    kb_data = {"knowledge_points": [], "sections": [], "topics": []}
    questions = []

    if kb_path.exists():
        with open(kb_path, 'r', encoding='utf-8') as f:
            kb_data = json.load(f)

    if q_path.exists():
        with open(q_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                questions = data
            elif isinstance(data, dict) and 'questions' in data:
                questions = data['questions']

    return kb_data, questions

def load_answers():
    """加载答题记录"""
    answers_path = DATA_DIR / "answers.json"
    if answers_path.exists():
        with open(answers_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {}

def save_answers(answers):
    """保存答题记录"""
    answers_path = DATA_DIR / "answers.json"
    with open(answers_path, 'w', encoding='utf-8') as f:
        json.dump(answers, f, ensure_ascii=False, indent=2)

# 全局数据
KB_DATA, ALL_QUESTIONS = load_knowledge_base()
ANSWERS = load_answers()

# 构建知识点索引
KP_INDEX = {kp['id']: kp for kp in KB_DATA.get('knowledge_points', [])}

# 按章节和考点分组的知识点
KP_BY_SECTION = defaultdict(list)
for kp in KB_DATA.get('knowledge_points', []):
    section = kp.get('section', '未知')
    KP_BY_SECTION[section].append(kp)

# ============ 样式定义 ============

CARD_STYLE = """
<style>
    .kp-container {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        max-width: 100%;
    }

    .section-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px 25px;
        border-radius: 16px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }

    .section-header h2 {
        margin: 0 0 8px 0;
        font-size: 24px;
        font-weight: 600;
    }

    .section-header .stats {
        font-size: 14px;
        opacity: 0.9;
    }

    .topic-group {
        margin-bottom: 30px;
    }

    .topic-header {
        background: linear-gradient(90deg, #f8fafc 0%, #e2e8f0 100%);
        border-left: 4px solid #3b82f6;
        padding: 12px 18px;
        margin-bottom: 15px;
        border-radius: 0 8px 8px 0;
        font-weight: 600;
        color: #1e40af;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .topic-header .count {
        background: #3b82f6;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
    }

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
        border-color: #c7d2fe;
    }

    .kp-card .kp-title {
        font-size: 16px;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid #f3f4f6;
        display: flex;
        align-items: flex-start;
        gap: 10px;
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
        font-size: 13px;
        font-weight: 600;
        flex-shrink: 0;
    }

    .kp-card .kp-content {
        color: #374151;
        line-height: 1.7;
        font-size: 14px;
        padding: 12px 15px;
        background: #f9fafb;
        border-radius: 8px;
        margin-bottom: 12px;
    }

    .kp-card .kp-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        font-size: 12px;
    }

    .kp-card .kp-keyword {
        background: #ede9fe;
        color: #6d28d9;
        padding: 4px 10px;
        border-radius: 15px;
        font-weight: 500;
    }

    .kp-card .kp-wrong {
        background: #fef2f2;
        color: #dc2626;
        padding: 4px 10px;
        border-radius: 15px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .kp-card .kp-difficulty {
        display: flex;
        gap: 3px;
    }

    .kp-card .kp-difficulty .star {
        color: #fbbf24;
        font-size: 14px;
    }

    .kp-card .kp-difficulty .star.empty {
        color: #d1d5db;
    }

    .overview-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
        margin: 20px 0;
    }

    .overview-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: all 0.3s ease;
        cursor: default;
    }

    .overview-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }

    .overview-card .icon {
        font-size: 32px;
        margin-bottom: 10px;
    }

    .overview-card .name {
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 5px;
    }

    .overview-card .count {
        color: #6b7280;
        font-size: 14px;
    }

    .total-stats {
        background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
        color: white;
        border-radius: 16px;
        padding: 25px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-around;
        align-items: center;
        flex-wrap: wrap;
        gap: 20px;
    }

    .total-stats .stat-item {
        text-align: center;
    }

    .total-stats .stat-value {
        font-size: 28px;
        font-weight: 700;
    }

    .total-stats .stat-label {
        font-size: 13px;
        opacity: 0.9;
        margin-top: 5px;
    }
</style>
"""

# ============ 错题管理 ============

def get_wrong_questions():
    """获取错题列表"""
    wrong_ids = [qid for qid, ans in ANSWERS.items() if not ans.get('correct', True)]
    wrong_questions = [q for q in ALL_QUESTIONS if q['id'] in wrong_ids]
    return wrong_questions

def get_weak_knowledge_points():
    """获取薄弱知识点"""
    wrong_questions = get_wrong_questions()
    weak_kps = defaultdict(list)

    for q in wrong_questions:
        kp_id = q.get('knowledge_point_id')
        if kp_id:
            weak_kps[kp_id].append(q)

    sorted_kps = sorted(weak_kps.items(), key=lambda x: -len(x[1]))

    result = []
    for kp_id, wrong_qs in sorted_kps:
        kp = KP_INDEX.get(kp_id)
        if kp:
            result.append({
                'knowledge_point': kp,
                'wrong_count': len(wrong_qs),
                'wrong_questions': wrong_qs
            })

    return result

# ============ 答题逻辑 ============

class QuizSession:
    def __init__(self):
        self.questions = []
        self.index = 0
        self.session_answers = {}
        self.mode = "normal"

    def start(self, questions, mode="normal"):
        self.questions = questions
        self.index = 0
        self.session_answers = {}
        self.mode = mode

    def current(self):
        if 0 <= self.index < len(self.questions):
            return self.questions[self.index]
        return None

    def answer(self, answer):
        q = self.current()
        if q:
            correct = (answer == q['answer']) or (q['type'] == 'choice' and answer == q['answer'])
            self.session_answers[q['id']] = {
                'answer': answer,
                'correct': correct,
                'time': datetime.now().isoformat()
            }
            ANSWERS[q['id']] = self.session_answers[q['id']]
            save_answers(ANSWERS)
            return correct
        return False

    def next(self):
        if self.index < len(self.questions) - 1:
            self.index += 1
            return True
        return False

    def prev(self):
        if self.index > 0:
            self.index -= 1
            return True
        return False

    def stats(self):
        answered = len(self.session_answers)
        correct = sum(1 for a in self.session_answers.values() if a['correct'])
        return answered, correct

session = QuizSession()

# ============ Gradio 界面函数 ============

def get_filtered_questions(q_type, section, count):
    """获取筛选后的题目"""
    filtered = ALL_QUESTIONS.copy()

    if q_type != "全部":
        type_map = {"选择题": "choice", "判断题": "judgment"}
        filtered = [q for q in filtered if q['type'] == type_map.get(q_type, q['type'])]

    if section != "全部":
        filtered = [q for q in filtered if q.get('section') == section]

    unanswered = [q for q in filtered if q['id'] not in ANSWERS]
    answered = [q for q in filtered if q['id'] in ANSWERS]
    filtered = unanswered + answered

    if count != "全部":
        num = int(count.replace("题", ""))
        filtered = filtered[:num]

    return filtered

def start_quiz(q_type, section, count):
    """开始答题"""
    questions = get_filtered_questions(q_type, section, count)
    if not questions:
        return "暂无题目", "", gr.update(visible=False), gr.update(visible=False), "", gr.update(selected=0)

    session.start(questions, mode="normal")
    return render_question()

def start_wrong_review(section):
    """开始错题复习"""
    wrong_questions = get_wrong_questions()

    if section != "全部":
        wrong_questions = [q for q in wrong_questions if q.get('section') == section]

    if not wrong_questions:
        return "暂无错题", "", gr.update(visible=False), gr.update(visible=False), "", gr.update(selected=2)

    session.start(wrong_questions, mode="wrong_review")
    return render_question()

def render_question():
    """渲染当前题目"""
    q = session.current()
    if not q:
        return "答题结束", "", gr.update(visible=False), gr.update(visible=False), "", gr.update(selected=0)

    answered, correct = session.stats()
    total = len(session.questions)

    mode_tag = "🔄 错题复习" if session.mode == "wrong_review" else "📝 答题"
    info = f"### {mode_tag} - 第 {session.index + 1} / {total} 题\n**章节**: {q.get('section', '')} | **考点**: {q.get('topic', '')}"
    question_text = f"**{q['question']}**"

    saved = ANSWERS.get(q['id'])
    result_html = ""

    if saved:
        is_correct = saved.get('correct', False)
        if is_correct:
            result_html = f"<div style='padding: 15px; background: #d1fae5; border-radius: 8px; margin-top: 15px;'><b>✓ 回答正确！</b><br>{q.get('explanation', '')}</div>"
        else:
            result_html = f"<div style='padding: 15px; background: #fee2e2; border-radius: 8px; margin-top: 15px;'><b>✗ 回答错误</b><br>正确答案: {q['answer']}<br>{q.get('explanation', '')}</div>"

        kp_id = q.get('knowledge_point_id')
        if kp_id:
            kp = KP_INDEX.get(kp_id)
            if kp:
                result_html += f"<div style='padding: 15px; background: #f0f9ff; border-left: 4px solid #3b82f6; margin-top: 15px; border-radius: 4px;'><b>📖 知识点: {kp.get('title', '')}</b><br>{kp.get('content', '')}</div>"

    return info, question_text, gr.update(visible=True), gr.update(visible=True), result_html, gr.update()

def select_choice(choice):
    session.answer(choice)
    return render_question()

def select_judgment(answer):
    session.answer(answer)
    return render_question()

def next_question():
    session.next()
    return render_question()

def prev_question():
    session.prev()
    return render_question()

# ============ 知识点分类查看（卡片式显示） ============

def display_section_knowledge_points(section_name):
    """显示单个章节的所有知识点（卡片式）"""
    kps = KP_BY_SECTION.get(section_name, [])

    if not kps:
        return f"{CARD_STYLE}<div class='kp-container'><p>章节 {section_name} 暂无知识点</p></div>"

    # 按考点分组
    by_topic = defaultdict(list)
    for kp in kps:
        topic = kp.get('topic', '其他') or '其他'
        by_topic[topic].append(kp)

    result = CARD_STYLE
    result += "<div class='kp-container'>"

    # 章节头部
    result += f"""
    <div class='section-header'>
        <h2>📚 {section_name}</h2>
        <div class='stats'>共 {len(kps)} 个知识点 · {len(by_topic)} 个考点</div>
    </div>
    """

    for topic, topic_kps in sorted(by_topic.items()):
        result += f"""
        <div class='topic-group'>
            <div class='topic-header'>
                📌 {topic}
                <span class='count'>{len(topic_kps)} 个</span>
            </div>
        """

        for i, kp in enumerate(topic_kps, 1):
            title = kp.get('title', '无标题')
            content = kp.get('content', '')
            keywords = kp.get('keywords', [])
            difficulty = kp.get('difficulty', 2)

            # 难度星星
            stars = ""
            for j in range(5):
                if j < difficulty:
                    stars += '<span class="star">★</span>'
                else:
                    stars += '<span class="star empty">☆</span>'

            # 关键词标签
            keyword_tags = ""
            if keywords:
                for kw in keywords[:4]:
                    keyword_tags += f'<span class="kp-keyword">{kw}</span>'

            # 错题数量
            kp_id = kp['id']
            wrong_count = sum(1 for qid, ans in ANSWERS.items()
                              if not ans.get('correct') and
                              next((q for q in ALL_QUESTIONS if q['id'] == qid and q.get('knowledge_point_id') == kp_id), None))

            wrong_tag = ""
            if wrong_count > 0:
                wrong_tag = f'<span class="kp-wrong">⚠️ 错题 {wrong_count} 道</span>'

            result += f"""
            <div class='kp-card'>
                <div class='kp-title'>
                    <span class='kp-number'>{i}</span>
                    <span>{title}</span>
                </div>
                <div class='kp-content'>{content}</div>
                <div class='kp-meta'>
                    <div class='kp-difficulty' title='难度'>{stars}</div>
                    {keyword_tags}
                    {wrong_tag}
                </div>
            </div>
            """

        result += "</div>"

    result += "</div>"
    return result

def get_all_sections_display():
    """获取所有章节列表（卡片式）"""
    sections = KB_DATA.get('sections', [])
    total_kps = len(KB_DATA.get('knowledge_points', []))

    result = CARD_STYLE
    result += "<div class='kp-container'>"

    # 总体统计
    result += f"""
    <div class='total-stats'>
        <div class='stat-item'>
            <div class='stat-value'>{total_kps}</div>
            <div class='stat-label'>知识点总数</div>
        </div>
        <div class='stat-item'>
            <div class='stat-value'>{len(sections)}</div>
            <div class='stat-label'>章节数量</div>
        </div>
        <div class='stat-item'>
            <div class='stat-value'>{len(get_wrong_questions())}</div>
            <div class='stat-label'>错题数量</div>
        </div>
    </div>
    """

    # 章节卡片
    result += "<div class='overview-container'>"

    section_icons = {
        '解剖学': '🫀',
        '生理学': '🧬',
        '药理学': '💊',
        '病理学': '🔬'
    }

    for section in sections:
        count = len(KP_BY_SECTION.get(section, []))
        icon = section_icons.get(section, '📖')

        result += f"""
        <div class='overview-card'>
            <div class='icon'>{icon}</div>
            <div class='name'>{section}</div>
            <div class='count'>{count} 个知识点</div>
        </div>
        """

    result += "</div></div>"
    return result

# ============ 错题集 ============

def get_wrong_questions_display(section):
    """显示错题列表"""
    wrong_questions = get_wrong_questions()

    if section != "全部":
        wrong_questions = [q for q in wrong_questions if q.get('section') == section]

    if not wrong_questions:
        return f"{CARD_STYLE}<div class='kp-container'><div class='section-header' style='background: linear-gradient(135deg, #10b981 0%, #059669 100%);'><h2>🎉 太棒了！</h2><div class='stats'>暂无错题，继续保持！</div></div></div>"

    by_section = defaultdict(list)
    for q in wrong_questions:
        by_section[q.get('section', '未知')].append(q)

    result = CARD_STYLE
    result += "<div class='kp-container'>"
    result += f"""
    <div class='section-header' style='background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);'>
        <h2>❌ 错题集</h2>
        <div class='stats'>共 {len(wrong_questions)} 道错题</div>
    </div>
    """

    for section_name in KB_DATA.get('sections', []):
        if section_name not in by_section:
            continue

        section_wrong = by_section[section_name]

        result += f"""
        <div class='topic-group'>
            <div class='topic-header' style='border-color: #ef4444; color: #dc2626;'>
                📚 {section_name}
                <span class='count' style='background: #ef4444;'>{len(section_wrong)} 道</span>
            </div>
        """

        for q in section_wrong:
            q_type = '选择题' if q['type'] == 'choice' else '判断题'
            q_text = q.get('question', '')[:100]
            if len(q.get('question', '')) > 100:
                q_text += '...'

            result += f"""
            <div class='kp-card' style='border-left: 4px solid #ef4444;'>
                <div class='kp-title' style='color: #dc2626;'>
                    <span class='kp-number' style='background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);'>!</span>
                    <span>{q_text}</span>
                </div>
                <div class='kp-meta'>
                    <span class='kp-keyword' style='background: #fee2e2; color: #dc2626;'>{q_type}</span>
                    <span class='kp-keyword' style='background: #d1fae5; color: #059669;'>正确答案: {q.get('answer', '')}</span>
                    <span class='kp-keyword'>{q.get('topic', '')}</span>
                </div>
            </div>
            """

        result += "</div>"

    result += "</div>"
    return result

def get_weak_points_display():
    """显示薄弱知识点"""
    weak_kps = get_weak_knowledge_points()

    if not weak_kps:
        return f"{CARD_STYLE}<div class='kp-container'><div class='section-header' style='background: linear-gradient(135deg, #10b981 0%, #059669 100%);'><h2>🎉 很好！</h2><div class='stats'>没有薄弱知识点</div></div></div>"

    result = CARD_STYLE
    result += "<div class='kp-container'>"
    result += f"""
    <div class='section-header' style='background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);'>
        <h2>🎯 薄弱知识点分析</h2>
        <div class='stats'>以下知识点需要重点复习</div>
    </div>
    """

    for item in weak_kps[:10]:
        kp = item['knowledge_point']
        wrong_count = item['wrong_count']

        result += f"""
        <div class='kp-card' style='border-left: 4px solid #f59e0b;'>
            <div class='kp-title' style='color: #d97706;'>
                <span class='kp-number' style='background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);'>{wrong_count}</span>
                <span>{kp.get('title', '')}</span>
            </div>
            <div class='kp-content'>{kp.get('content', '')}</div>
            <div class='kp-meta'>
                <span class='kp-keyword'>{kp.get('section', '')}</span>
                <span class='kp-keyword'>{kp.get('topic', '')}</span>
                <span class='kp-wrong'>⚠️ 错 {wrong_count} 次</span>
            </div>
        </div>
        """

    result += "</div>"
    return result

# ============ 学习报告 ============

def get_report():
    """生成学习报告"""
    total_q = len(ALL_QUESTIONS)
    answered = len(ANSWERS)
    correct = sum(1 for a in ANSWERS.values() if a.get('correct'))
    wrong = answered - correct

    result = CARD_STYLE
    result += "<div class='kp-container'>"

    # 总体统计
    accuracy = correct/answered*100 if answered > 0 else 0
    result += f"""
    <div class='total-stats'>
        <div class='stat-item'>
            <div class='stat-value'>{total_q}</div>
            <div class='stat-label'>题目总数</div>
        </div>
        <div class='stat-item'>
            <div class='stat-value'>{answered}</div>
            <div class='stat-label'>已答题数</div>
        </div>
        <div class='stat-item'>
            <div class='stat-value' style='color: #86efac;'>{correct}</div>
            <div class='stat-label'>正确题数</div>
        </div>
        <div class='stat-item'>
            <div class='stat-value' style='color: #fca5a5;'>{wrong}</div>
            <div class='stat-label'>错题数</div>
        </div>
        <div class='stat-item'>
            <div class='stat-value'>{accuracy:.1f}%</div>
            <div class='stat-label'>正确率</div>
        </div>
    </div>
    """

    # 章节进度
    sections = KB_DATA.get('sections', [])
    result += """
    <div class='topic-group'>
        <div class='topic-header'>📊 章节进度</div>
    """

    for sec in sections:
        sec_questions = [q for q in ALL_QUESTIONS if q.get('section') == sec]
        sec_answered = [q for q in sec_questions if q['id'] in ANSWERS]
        sec_correct = sum(1 for q in sec_answered if ANSWERS[q['id']]['correct'])
        sec_wrong = len(sec_answered) - sec_correct

        progress = len(sec_answered) / len(sec_questions) * 100 if sec_questions else 0
        accuracy = sec_correct / len(sec_answered) * 100 if sec_answered else 0

        result += f"""
        <div class='kp-card'>
            <div class='kp-title'>
                <span class='kp-number' style='background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);'>{sec[0]}</span>
                <span>{sec}</span>
            </div>
            <div class='kp-meta' style='gap: 15px;'>
                <span>进度: <strong>{progress:.0f}%</strong> ({len(sec_answered)}/{len(sec_questions)})</span>
                <span>正确率: <strong style='color: #059669;'>{accuracy:.0f}%</strong></span>
                <span class='kp-wrong' style='display: {"inline-flex" if sec_wrong > 0 else "none"};'>错题 {sec_wrong} 道</span>
            </div>
        </div>
        """

    result += "</div>"

    # 薄弱知识点
    weak_kps = get_weak_knowledge_points()
    if weak_kps:
        result += """
        <div class='topic-group'>
            <div class='topic-header' style='border-color: #f59e0b; color: #d97706;'>🎯 需要复习的知识点</div>
        """

        for item in weak_kps[:5]:
            kp = item['knowledge_point']
            result += f"""
            <div class='kp-card' style='border-left: 4px solid #f59e0b;'>
                <div class='kp-title' style='font-size: 14px;'>
                    <span class='kp-wrong'>错 {item['wrong_count']} 次</span>
                    {kp.get('title', '')}
                </div>
            </div>
            """

        result += "</div>"

    result += "</div>"
    return result

# ============ 创建 Gradio 应用 ============

def create_app():
    sections = KB_DATA.get('sections', [])

    with gr.Blocks(
        title="📚 Knowledge Quiz",
        theme=gr.themes.Soft(
            primary_hue="indigo",
            secondary_hue="purple",
            neutral_hue="slate",
        ),
        css="""
        .gradio-container { max-width: 1200px !important; }
        .tab-nav button { font-size: 16px !important; padding: 12px 24px !important; }
        """
    ) as app:
        gr.Markdown("# 📚 医学基础必背考点")

        with gr.Tabs() as tabs:
            # ====== 开始答题 Tab ======
            with gr.TabItem("🎯 开始答题", id=0):
                with gr.Row():
                    q_type = gr.Dropdown(["全部", "选择题", "判断题"], value="全部", label="题型")
                    section = gr.Dropdown(["全部"] + sections, value="全部", label="章节")
                    count = gr.Dropdown(["全部", "10题", "20题", "50题"], value="20题", label="题数")

                start_btn = gr.Button("开始答题", variant="primary", size="lg")

                quiz_info = gr.Markdown("")
                quiz_question = gr.Markdown("")

                with gr.Row(visible=False) as choice_row:
                    btn_a = gr.Button("A", size="lg")
                    btn_b = gr.Button("B", size="lg")
                    btn_c = gr.Button("C", size="lg")
                    btn_d = gr.Button("D", size="lg")

                with gr.Row(visible=False) as judgment_row:
                    btn_true = gr.Button("✓ 正确", variant="primary", size="lg")
                    btn_false = gr.Button("✗ 错误", variant="stop", size="lg")

                quiz_result = gr.HTML("")

                with gr.Row():
                    prev_btn = gr.Button("⬅️ 上一题", size="lg")
                    next_btn = gr.Button("下一题 ➡️", size="lg")

                start_btn.click(start_quiz, [q_type, section, count], [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])

                btn_a.click(lambda: select_choice("A"), None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])
                btn_b.click(lambda: select_choice("B"), None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])
                btn_c.click(lambda: select_choice("C"), None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])
                btn_d.click(lambda: select_choice("D"), None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])

                btn_true.click(lambda: select_judgment(True), None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])
                btn_false.click(lambda: select_judgment(False), None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])

                prev_btn.click(prev_question, None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])
                next_btn.click(next_question, None, [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])

            # ====== 错题集 Tab ======
            with gr.TabItem("❌ 错题集", id=1):
                with gr.Row():
                    wrong_section = gr.Dropdown(["全部"] + sections, value="全部", label="章节筛选")

                with gr.Row():
                    refresh_wrong_btn = gr.Button("🔄 刷新错题", size="lg")
                    review_wrong_btn = gr.Button("📝 复习错题", variant="primary", size="lg")

                wrong_display = gr.HTML("")

                refresh_wrong_btn.click(get_wrong_questions_display, [wrong_section], wrong_display)
                review_wrong_btn.click(start_wrong_review, [wrong_section], [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])

                gr.Markdown("---")
                weak_btn = gr.Button("🎯 查看薄弱知识点", variant="secondary", size="lg")
                weak_display = gr.HTML("")
                weak_btn.click(get_weak_points_display, None, weak_display)

            # ====== 知识点学习 Tab（卡片式显示） ======
            with gr.TabItem("📖 知识点学习", id=2):
                gr.Markdown("## 📚 知识点分类查看")
                gr.Markdown("点击下方按钮查看对应章节的所有知识点")

                # 章节概览
                overview_display = gr.HTML(get_all_sections_display())

                gr.Markdown("---")

                # 章节按钮
                section_buttons = []
                section_displays = []

                section_colors = {
                    '解剖学': '#ef4444',
                    '生理学': '#22c55e',
                    '药理学': '#3b82f6',
                    '病理学': '#8b5cf6'
                }

                with gr.Row():
                    for section_name in sections:
                        count = len(KP_BY_SECTION.get(section_name, []))
                        color = section_colors.get(section_name, '#6b7280')
                        btn = gr.Button(f"📖 {section_name} ({count}个)", size="lg", variant="secondary")
                        section_buttons.append((section_name, btn))

                gr.Markdown("")

                # 显示区域
                section_display = gr.HTML("")

                # 为每个按钮创建点击事件
                def make_show_func(section_name):
                    def show_section():
                        return display_section_knowledge_points(section_name)
                    return show_section

                for section_name, btn in section_buttons:
                    btn.click(make_show_func(section_name), None, section_display)

            # ====== 学习报告 Tab ======
            with gr.TabItem("📊 学习报告", id=3):
                report_btn = gr.Button("🔄 刷新报告", variant="primary", size="lg")
                report_output = gr.HTML("")

                report_btn.click(get_report, None, report_output)

    return app

if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="127.0.0.1", server_port=7866, share=False, inbrowser=True)
