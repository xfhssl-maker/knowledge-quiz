#!/usr/bin/env python3
"""
Knowledge Quiz Gradio 应用 v4.0
仅支持选择题，优化界面显示
"""

import os
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

import json
import gradio as gr
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============ 数据加载 ============

def load_knowledge_base():
    """加载知识库数据"""
    kb_path = Path(__file__).parent / "knowledge-base.json"
    q_path = Path(__file__).parent / "questions.json"

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

    # 仅保留选择题
    questions = [q for q in questions if q.get('type') == 'choice']

    return kb_data, questions

def load_answers():
    """加载答题记录"""
    answers_path = Path(__file__).parent / "answers.json"
    if answers_path.exists():
        with open(answers_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {}

def save_answers(answers):
    """保存答题记录"""
    answers_path = Path(__file__).parent / "answers.json"
    with open(answers_path, 'w', encoding='utf-8') as f:
        json.dump(answers, f, ensure_ascii=False, indent=2)

# 全局数据
KB_DATA, ALL_QUESTIONS = load_knowledge_base()
ANSWERS = load_answers()

# 构建知识点索引
KP_INDEX = {kp['id']: kp for kp in KB_DATA.get('knowledge_points', [])}

# 知识库名称（从数据动态读取，不再硬编码）
KB_NAME = KB_DATA.get('name', '知识库答题')

# 按章节分组
KP_BY_SECTION = defaultdict(list)
for kp in KB_DATA.get('knowledge_points', []):
    section = kp.get('section', '未知')
    KP_BY_SECTION[section].append(kp)

# 通用章节图标和颜色（按索引循环分配，不限定领域）
GENERIC_ICONS = ['📚', '📖', '🎯', '💡', '🔬', '📊', '🔑', '📝', '🏆', '🌟']
SECTION_COLORS = ['#ef4444', '#22c55e', '#3b82f6', '#8b5cf6', '#f59e0b', '#06b6d4', '#ec4899', '#14b8a6']

def get_section_icon(section_name):
    sections = KB_DATA.get('sections', [])
    idx = sections.index(section_name) if section_name in sections else 0
    return GENERIC_ICONS[idx % len(GENERIC_ICONS)]

def get_section_color(section_name):
    sections = KB_DATA.get('sections', [])
    idx = sections.index(section_name) if section_name in sections else 0
    return SECTION_COLORS[idx % len(SECTION_COLORS)]

# ============ 样式定义 ============

CARD_STYLE = """
<style>
    .kp-container { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 100%; }
    .section-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px 25px; border-radius: 16px; margin-bottom: 25px; }
    .section-header h2 { margin: 0 0 8px 0; font-size: 24px; font-weight: 600; }
    .kp-card { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
    .kp-card .kp-title { font-size: 16px; font-weight: 600; color: #1f2937; margin-bottom: 12px; }
    .kp-card .kp-content { color: #374151; line-height: 1.7; font-size: 14px; padding: 12px 15px; background: #f9fafb; border-radius: 8px; margin-bottom: 12px; }
    .kp-keyword { background: #ede9fe; color: #6d28d9; padding: 4px 10px; border-radius: 15px; font-size: 12px; }
    .kp-wrong { background: #fef2f2; color: #dc2626; padding: 4px 10px; border-radius: 15px; font-size: 12px; }
    .result-correct { background: #d1fae5; border: 2px solid #10b981; border-radius: 12px; padding: 16px; margin-top: 16px; }
    .result-wrong { background: #fee2e2; border: 2px solid #ef4444; border-radius: 12px; padding: 16px; margin-top: 16px; }
    .knowledge-tip { background: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 8px; padding: 16px; margin-top: 16px; }
    .option-btn { text-align: left; padding: 16px 20px; margin: 8px 0; font-size: 15px; border-radius: 12px; }
</style>
"""

# ============ 错题管理 ============

def get_wrong_questions():
    """获取错题列表"""
    wrong_ids = [qid for qid, ans in ANSWERS.items() if not ans.get('correct', True)]
    return [q for q in ALL_QUESTIONS if q['id'] in wrong_ids]

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
            result.append({'knowledge_point': kp, 'wrong_count': len(wrong_qs), 'wrong_questions': wrong_qs})
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
            correct = answer == q['answer']
            self.session_answers[q['id']] = {'answer': answer, 'correct': correct, 'time': datetime.now().isoformat()}
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

def get_filtered_questions(section, count):
    """获取筛选后的题目"""
    filtered = ALL_QUESTIONS.copy()
    if section != "全部":
        filtered = [q for q in filtered if q.get('section') == section]
    unanswered = [q for q in filtered if q['id'] not in ANSWERS]
    answered = [q for q in filtered if q['id'] in ANSWERS]
    filtered = unanswered + answered
    if count != "全部":
        num = int(count.replace("题", ""))
        filtered = filtered[:num]
    return filtered

def start_quiz(section, count):
    """开始答题"""
    questions = get_filtered_questions(section, count)
    if not questions:
        return ("### 暂无题目", "",
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                "", gr.update(selected=0))
    session.start(questions, mode="normal")
    return render_question()

def start_wrong_review(section):
    """开始错题复习"""
    wrong_questions = get_wrong_questions()
    if section != "全部":
        wrong_questions = [q for q in wrong_questions if q.get('section') == section]
    if not wrong_questions:
        return ("### 暂无错题", "",
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                "", gr.update(selected=2))
    session.start(wrong_questions, mode="wrong_review")
    return render_question()

def render_question():
    """渲染当前题目"""
    q = session.current()
    if not q:
        return ("### 答题结束", "",
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                "", gr.update(selected=0))

    total = len(session.questions)
    mode_tag = "错题复习" if session.mode == "wrong_review" else "答题"
    quiz_info = f"### {mode_tag} - 第 {session.index + 1} / {total} 题\n\n**章节**: {q.get('section', '')} | **考点**: {q.get('topic', '')}"

    question_text = q.get('question', '')
    options = q.get('options', [])

    # 解析选项文本
    opt_texts = []
    for opt in options:
        if '. ' in opt:
            text = opt.split('. ', 1)[1] if '. ' in opt else opt
        else:
            text = opt
        opt_texts.append(text)

    # 构建题目显示
    question_html = f"""
    <div style="background: white; border: 2px solid #e5e7eb; border-radius: 16px; padding: 24px; margin: 16px 0;">
        <div style="font-size: 18px; font-weight: 600; color: #1f2937; line-height: 1.6; margin-bottom: 20px;">
            {question_text}
        </div>
    </div>
    """

    saved = ANSWERS.get(q['id'])
    result_html = ""

    if saved:
        is_correct = saved.get('correct', False)
        if is_correct:
            result_html = f'<div class="result-correct"><b>回答正确!</b><br>{q.get("explanation", "")}</div>'
        else:
            result_html = f'<div class="result-wrong"><b>回答错误</b><br>正确答案: {q.get("answer", "")}<br>{q.get("explanation", "")}</div>'
        kp_id = q.get('knowledge_point_id')
        if kp_id:
            kp = KP_INDEX.get(kp_id)
            if kp:
                result_html += f'<div class="knowledge-tip"><b>知识点: {kp.get("title", "")}</b><br>{kp.get("content", "")}</div>'

    return (
        quiz_info,
        CARD_STYLE + question_html,
        gr.update(value=f"A. {opt_texts[0] if len(opt_texts) > 0 else ''}", visible=True),
        gr.update(value=f"B. {opt_texts[1] if len(opt_texts) > 1 else ''}", visible=True),
        gr.update(value=f"C. {opt_texts[2] if len(opt_texts) > 2 else ''}", visible=True),
        gr.update(value=f"D. {opt_texts[3] if len(opt_texts) > 3 else ''}", visible=True),
        result_html,
        gr.update()
    )

def select_choice(choice):
    session.answer(choice)
    return render_question()

def next_question():
    session.next()
    return render_question()

def prev_question():
    session.prev()
    return render_question()

# ============ 知识点显示 ============

def display_section_knowledge_points(section_name):
    """显示单个章节的知识点"""
    kps = KP_BY_SECTION.get(section_name, [])
    if not kps:
        return f"{CARD_STYLE}<div class='kp-container'><p>暂无知识点</p></div>"

    by_topic = defaultdict(list)
    for kp in kps:
        topic = kp.get('topic', '其他') or '其他'
        by_topic[topic].append(kp)

    result = CARD_STYLE + "<div class='kp-container'>"
    icon = get_section_icon(section_name)
    color = get_section_color(section_name)
    result += f'<div class="section-header" style="background:linear-gradient(135deg,{color},{color}dd)"><h2>{icon} {section_name}</h2><div style="font-size:14px;opacity:0.9">共 {len(kps)} 个知识点</div></div>'

    for topic, topic_kps in sorted(by_topic.items()):
        result += f'<div style="margin-bottom:20px"><div style="background:#f1f5f9;border-left:4px solid #3b82f6;padding:10px 15px;margin-bottom:10px;font-weight:600;color:#1e40af">{topic} ({len(topic_kps)})</div>'
        for i, kp in enumerate(topic_kps, 1):
            title = kp.get('title', '')
            content = kp.get('content', '')
            keywords = kp.get('keywords', [])
            keyword_tags = ''.join([f'<span class="kp-keyword">{kw}</span>' for kw in keywords[:3]])
            result += f'<div class="kp-card"><div class="kp-title">{i}. {title}</div><div class="kp-content">{content}</div><div style="font-size:12px">{keyword_tags}</div></div>'
        result += '</div>'

    result += "</div>"
    return result

def get_all_sections_display():
    """获取所有章节概览"""
    sections = KB_DATA.get('sections', [])
    total_kps = len(KB_DATA.get('knowledge_points', []))

    result = CARD_STYLE + "<div class='kp-container'>"
    result += f'<div style="background:linear-gradient(135deg,#0ea5e9,#06b6d4);color:white;border-radius:16px;padding:20px;margin-bottom:20px;display:flex;justify-content:space-around;flex-wrap:wrap;gap:15px;text-align:center">'
    result += f'<div><div style="font-size:28px;font-weight:700">{total_kps}</div><div style="font-size:13px;opacity:0.9">知识点</div></div>'
    result += f'<div><div style="font-size:28px;font-weight:700">{len(sections)}</div><div style="font-size:13px;opacity:0.9">章节</div></div>'
    result += f'<div><div style="font-size:28px;font-weight:700">{len(get_wrong_questions())}</div><div style="font-size:13px;opacity:0.9">错题</div></div>'
    result += '</div></div>'
    return result

# ============ 错题集 ============

def get_wrong_questions_display(section):
    """显示错题列表"""
    wrong_questions = get_wrong_questions()
    if section != "全部":
        wrong_questions = [q for q in wrong_questions if q.get('section') == section]
    if not wrong_questions:
        return f'{CARD_STYLE}<div class="kp-container"><div class="section-header" style="background:linear-gradient(135deg,#10b981,#059669)"><h2>太棒了!</h2><div style="font-size:14px">暂无错题</div></div></div>'

    result = CARD_STYLE + '<div class="kp-container">'
    result += f'<div class="section-header" style="background:linear-gradient(135deg,#ef4444,#dc2626)"><h2>错题集</h2><div style="font-size:14px">共 {len(wrong_questions)} 道</div></div>'

    for q in wrong_questions[:20]:
        q_text = q.get('question', '')[:100] + ('...' if len(q.get('question', '')) > 100 else '')
        q_type = "选择题" if q.get('type') == 'choice' else q.get('type', '')
        result += f'<div class="kp-card" style="border-left:4px solid #ef4444"><div class="kp-title">{q_text}</div><div><span class="kp-wrong">{q_type}</span> <span class="kp-keyword">答案: {q.get("answer","")}</span></div></div>'

    result += '</div>'
    return result

def get_weak_points_display():
    """显示薄弱知识点"""
    weak_kps = get_weak_knowledge_points()
    if not weak_kps:
        return f'{CARD_STYLE}<div class="kp-container"><div class="section-header" style="background:linear-gradient(135deg,#10b981,#059669)"><h2>很好!</h2><div style="font-size:14px">没有薄弱知识点</div></div></div>'

    result = CARD_STYLE + '<div class="kp-container">'
    result += '<div class="section-header" style="background:linear-gradient(135deg,#f59e0b,#d97706)"><h2>薄弱知识点</h2></div>'

    for item in weak_kps[:10]:
        kp = item['knowledge_point']
        result += f'<div class="kp-card" style="border-left:4px solid #f59e0b"><div class="kp-title"><span class="kp-wrong">错 {item["wrong_count"]} 次</span> {kp.get("title","")}</div><div class="kp-content">{kp.get("content","")}</div></div>'

    result += '</div>'
    return result

# ============ 学习报告 ============

def get_report():
    """生成学习报告"""
    total_q = len(ALL_QUESTIONS)
    answered = len(ANSWERS)
    correct = sum(1 for a in ANSWERS.values() if a.get('correct'))
    wrong = answered - correct
    accuracy = correct/answered*100 if answered > 0 else 0

    result = CARD_STYLE + '<div class="kp-container">'
    result += f'<div style="background:linear-gradient(135deg,#0ea5e9,#06b6d4);color:white;border-radius:16px;padding:20px;margin-bottom:20px;display:flex;justify-content:space-around;flex-wrap:wrap;gap:15px;text-align:center">'
    result += f'<div><div style="font-size:28px;font-weight:700">{total_q}</div><div style="font-size:13px;opacity:0.9">总题数</div></div>'
    result += f'<div><div style="font-size:28px;font-weight:700">{answered}</div><div style="font-size:13px;opacity:0.9">已答</div></div>'
    result += f'<div><div style="font-size:28px;font-weight:700;color:#86efac">{correct}</div><div style="font-size:13px;opacity:0.9">正确</div></div>'
    result += f'<div><div style="font-size:28px;font-weight:700;color:#fca5a5">{wrong}</div><div style="font-size:13px;opacity:0.9">错误</div></div>'
    result += f'<div><div style="font-size:28px;font-weight:700">{accuracy:.1f}%</div><div style="font-size:13px;opacity:0.9">正确率</div></div>'
    result += '</div></div>'

    return result

# ============ 创建 Gradio 应用 ============

def create_app():
    sections = KB_DATA.get('sections', [])

    with gr.Blocks(title="Knowledge Quiz") as app:
        gr.Markdown(f"# {KB_NAME}")

        with gr.Tabs() as tabs:
            # ====== 开始答题 Tab ======
            with gr.TabItem("开始答题", id=0):
                with gr.Row():
                    section = gr.Dropdown(["全部"] + sections, value="全部", label="章节")
                    count = gr.Dropdown(["全部", "10题", "20题", "50题"], value="20题", label="题数")

                start_btn = gr.Button("开始答题", variant="primary", size="lg")

                quiz_info = gr.Markdown("")
                quiz_question = gr.HTML("")

                # 选择题选项按钮
                btn_a = gr.Button("A. ", size="lg")
                btn_b = gr.Button("B. ", size="lg")
                btn_c = gr.Button("C. ", size="lg")
                btn_d = gr.Button("D. ", size="lg")

                quiz_result = gr.HTML("")

                with gr.Row():
                    prev_btn = gr.Button("上一题", size="lg")
                    next_btn = gr.Button("下一题", size="lg")

                # 事件绑定
                start_btn.click(start_quiz, [section, count],
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])

                btn_a.click(lambda: select_choice("A"), None,
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])
                btn_b.click(lambda: select_choice("B"), None,
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])
                btn_c.click(lambda: select_choice("C"), None,
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])
                btn_d.click(lambda: select_choice("D"), None,
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])

                prev_btn.click(prev_question, None,
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])
                next_btn.click(next_question, None,
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])

            # ====== 错题集 Tab ======
            with gr.TabItem("错题集", id=1):
                with gr.Row():
                    wrong_section = gr.Dropdown(["全部"] + sections, value="全部", label="章节")
                with gr.Row():
                    refresh_wrong_btn = gr.Button("刷新错题", size="lg")
                    review_wrong_btn = gr.Button("复习错题", variant="primary", size="lg")
                wrong_display = gr.HTML("")
                refresh_wrong_btn.click(get_wrong_questions_display, [wrong_section], wrong_display)
                review_wrong_btn.click(start_wrong_review, [wrong_section],
                    [quiz_info, quiz_question, btn_a, btn_b, btn_c, btn_d, quiz_result, tabs])
                weak_btn = gr.Button("查看薄弱知识点", variant="secondary", size="lg")
                weak_display = gr.HTML("")
                weak_btn.click(get_weak_points_display, None, weak_display)

            # ====== 知识点学习 Tab ======
            with gr.TabItem("知识点学习", id=2):
                overview_display = gr.HTML(get_all_sections_display())
                with gr.Row():
                    for section_name in sections:
                        count = len(KP_BY_SECTION.get(section_name, []))
                        icon = get_section_icon(section_name)
                        btn = gr.Button(f"{icon} {section_name} ({count})", size="lg")
                        btn.click(lambda s=section_name: display_section_knowledge_points(s), None, overview_display)

            # ====== 学习报告 Tab ======
            with gr.TabItem("学习报告", id=3):
                report_btn = gr.Button("刷新报告", variant="primary", size="lg")
                report_output = gr.HTML("")
                report_btn.click(get_report, None, report_output)

    return app

if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="127.0.0.1", server_port=7866, share=False, inbrowser=True,
               theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="purple"),
               css=".gradio-container { max-width: 1200px !important; }")
