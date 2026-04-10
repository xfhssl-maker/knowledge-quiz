#!/usr/bin/env python3
"""
Knowledge Quiz Gradio 应用
固定界面，内容从知识库 JSON 文件加载
支持错题集、知识点分类查看
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

# ============ 错题管理 ============

def get_wrong_questions():
    """获取错题列表"""
    wrong_ids = [qid for qid, ans in ANSWERS.items() if not ans.get('correct', True)]
    wrong_questions = [q for q in ALL_QUESTIONS if q['id'] in wrong_ids]
    return wrong_questions

def get_wrong_questions_by_section():
    """按章节分组获取错题"""
    wrong_questions = get_wrong_questions()
    by_section = defaultdict(list)
    for q in wrong_questions:
        by_section[q.get('section', '未知')].append(q)
    return dict(by_section)

def get_weak_knowledge_points():
    """获取薄弱知识点（关联错题）"""
    wrong_questions = get_wrong_questions()
    weak_kps = defaultdict(list)  # kp_id -> [wrong_questions]

    for q in wrong_questions:
        kp_id = q.get('knowledge_point_id')
        if kp_id:
            weak_kps[kp_id].append(q)

    # 按错误次数排序
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
        self.mode = "normal"  # normal, wrong_review

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

# ============ Gradio 界面 ============

def get_filtered_questions(q_type, section, count):
    """获取筛选后的题目"""
    filtered = ALL_QUESTIONS.copy()

    if q_type != "全部":
        type_map = {"选择题": "choice", "判断题": "judgment"}
        filtered = [q for q in filtered if q['type'] == type_map.get(q_type, q['type'])]

    if section != "全部":
        filtered = [q for q in filtered if q.get('section') == section]

    # 智能选题：优先未答过的
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

    # 模式标识
    mode_tag = "🔄 错题复习" if session.mode == "wrong_review" else "📝 答题"

    # 题目信息
    info = f"### {mode_tag} - 第 {session.index + 1} / {total} 题\n**章节**: {q.get('section', '')} | **考点**: {q.get('topic', '')}"

    # 题目文本
    question_text = f"**{q['question']}**"

    # 获取已答题的答案
    saved = ANSWERS.get(q['id'])

    # 结果显示
    result_html = ""
    if saved:
        is_correct = saved.get('correct', False)
        if is_correct:
            result_html = f"<div style='padding: 15px; background: #d1fae5; border-radius: 8px; margin-top: 15px;'><b>✓ 回答正确！</b><br>{q.get('explanation', '')}</div>"
        else:
            result_html = f"<div style='padding: 15px; background: #fee2e2; border-radius: 8px; margin-top: 15px;'><b>✗ 回答错误</b><br>正确答案: {q['answer']}<br>{q.get('explanation', '')}</div>"

        # 显示知识点
        kp_id = q.get('knowledge_point_id')
        if kp_id:
            kp = KP_INDEX.get(kp_id)
            if kp:
                result_html += f"<div style='padding: 15px; background: #f0f9ff; border-left: 4px solid #3b82f6; margin-top: 15px; border-radius: 4px;'><b>📖 知识点: {kp.get('title', '')}</b><br>{kp.get('content', '')}</div>"

    return info, question_text, gr.update(visible=True), gr.update(visible=True), result_html, gr.update()

def select_choice(choice):
    """选择答案"""
    session.answer(choice)
    return render_question()

def select_judgment(answer):
    """判断题选择"""
    session.answer(answer)
    return render_question()

def next_question():
    """下一题"""
    session.next()
    return render_question()

def prev_question():
    """上一题"""
    session.prev()
    return render_question()

# ============ 知识点分类查看 ============

def get_knowledge_points_grouped(section_filter, topic_filter, keyword):
    """获取分类后的知识点列表"""
    points = KB_DATA.get('knowledge_points', [])

    # 过滤
    if section_filter != "全部":
        points = [p for p in points if p.get('section') == section_filter]

    if topic_filter != "全部":
        points = [p for p in points if p.get('topic') == topic_filter]

    if keyword:
        keyword = keyword.lower()
        points = [p for p in points if
                  keyword in p.get('title', '').lower() or
                  keyword in p.get('content', '').lower() or
                  any(keyword in k.lower() for k in p.get('keywords', []))]

    # 按章节+考点分组
    grouped = defaultdict(lambda: defaultdict(list))
    for p in points:
        section = p.get('section', '未知')
        topic = p.get('topic', '其他') or '其他'
        grouped[section][topic].append(p)

    # 格式化输出
    result = f"**共 {len(points)} 个知识点**\n\n"

    for section in KB_DATA.get('sections', []):
        if section not in grouped:
            continue

        section_points = sum(len(p) for p in grouped[section].values())
        result += f"\n## 📚 {section} ({section_points} 个)\n\n"

        for topic, topic_points in grouped[section].items():
            result += f"### 📌 {topic} ({len(topic_points)} 个)\n\n"

            for i, p in enumerate(topic_points):
                # 知识点卡片
                result += f"**{i+1}. {p.get('title', '无标题')}**\n\n"
                result += f"> {p.get('content', '')}\n\n"

                if p.get('keywords'):
                    result += f"*关键词: {', '.join(p['keywords'])}*\n\n"

                # 显示关联的错题数量
                kp_id = p['id']
                wrong_count = sum(1 for qid, ans in ANSWERS.items()
                                  if not ans.get('correct') and
                                  next((q for q in ALL_QUESTIONS if q['id'] == qid and q.get('knowledge_point_id') == kp_id), None))
                if wrong_count > 0:
                    result += f"⚠️ **错题: {wrong_count} 道**\n\n"

                result += "---\n\n"

    return result or "未找到匹配的知识点"

def get_topics_for_section(section):
    """获取指定章节的考点列表"""
    points = KB_DATA.get('knowledge_points', [])
    if section != "全部":
        points = [p for p in points if p.get('section') == section]

    topics = sorted(set(p.get('topic', '') for p in points if p.get('topic')))
    return ["全部"] + topics

def update_topic_dropdown(section):
    """更新考点下拉框"""
    topics = get_topics_for_section(section)
    return gr.update(choices=topics, value="全部")

# ============ 错题集 ============

def get_wrong_questions_display(section):
    """显示错题列表"""
    wrong_questions = get_wrong_questions()

    if section != "全部":
        wrong_questions = [q for q in wrong_questions if q.get('section') == section]

    if not wrong_questions:
        return "🎉 暂无错题，继续加油！"

    # 按章节分组
    by_section = defaultdict(list)
    for q in wrong_questions:
        by_section[q.get('section', '未知')].append(q)

    result = f"## ❌ 错题集 (共 {len(wrong_questions)} 道)\n\n"

    for section_name in KB_DATA.get('sections', []):
        if section_name not in by_section:
            continue

        section_wrong = by_section[section_name]
        result += f"### 📚 {section_name} ({len(section_wrong)} 道)\n\n"

        for q in section_wrong:
            result += f"**题目**: {q.get('question', '')[:80]}...\n\n"
            result += f"- 类型: {'选择题' if q['type'] == 'choice' else '判断题'}\n"
            result += f"- 正确答案: {q.get('answer', '')}\n"
            result += f"- 考点: {q.get('topic', '')}\n\n"

            # 关联知识点
            kp_id = q.get('knowledge_point_id')
            if kp_id and kp_id in KP_INDEX:
                kp = KP_INDEX[kp_id]
                result += f"📖 **知识点**: {kp.get('title', '')}\n"
                result += f"> {kp.get('content', '')[:100]}...\n\n"

            result += "---\n\n"

    return result

def get_weak_points_display():
    """显示薄弱知识点"""
    weak_kps = get_weak_knowledge_points()

    if not weak_kps:
        return "🎉 没有薄弱知识点，继续保持！"

    result = f"## 🎯 薄弱知识点分析\n\n"
    result += f"以下知识点需要重点复习：\n\n"

    for item in weak_kps[:10]:  # 显示前10个最薄弱的
        kp = item['knowledge_point']
        wrong_count = item['wrong_count']

        result += f"### ⚠️ {kp.get('title', '')} (错 {wrong_count} 次)\n\n"
        result += f"> {kp.get('content', '')}\n\n"
        result += f"- 章节: {kp.get('section', '')}\n"
        result += f"- 考点: {kp.get('topic', '')}\n"

        if kp.get('keywords'):
            result += f"- 关键词: {', '.join(kp['keywords'])}\n"

        result += "\n---\n\n"

    return result

# ============ 学习报告 ============

def get_report():
    """生成学习报告"""
    total_q = len(ALL_QUESTIONS)
    answered = len(ANSWERS)
    correct = sum(1 for a in ANSWERS.values() if a.get('correct'))
    wrong = answered - correct

    report = f"""## 📊 学习报告

### 总体统计
- **题目总数**: {total_q}
- **已答题数**: {answered}
- **正确题数**: {correct}
- **错题数**: {wrong}
- **正确率**: {correct/answered*100:.1f}% ({correct}/{answered})

### 章节进度
"""

    # 按章节统计
    sections = KB_DATA.get('sections', [])
    for sec in sections:
        sec_questions = [q for q in ALL_QUESTIONS if q.get('section') == sec]
        sec_answered = [q for q in sec_questions if q['id'] in ANSWERS]
        sec_correct = sum(1 for q in sec_answered if ANSWERS[q['id']]['correct'])
        sec_wrong = len(sec_answered) - sec_correct

        progress = len(sec_answered) / len(sec_questions) * 100 if sec_questions else 0
        accuracy = sec_correct / len(sec_answered) * 100 if sec_answered else 0

        report += f"\n**{sec}**\n"
        report += f"- 进度: {progress:.0f}% ({len(sec_answered)}/{len(sec_questions)})\n"
        report += f"- 正确率: {accuracy:.0f}%\n"
        report += f"- 错题: {sec_wrong} 道\n"

    # 薄弱知识点
    weak_kps = get_weak_knowledge_points()
    if weak_kps:
        report += f"\n### 🎯 需要复习的知识点\n"
        for item in weak_kps[:5]:
            kp = item['knowledge_point']
            report += f"- **{kp.get('title', '')}** (错 {item['wrong_count']} 次)\n"

    return report

# ============ 创建 Gradio 应用 ============

def create_app():
    sections = ["全部"] + KB_DATA.get('sections', [])

    with gr.Blocks(title="📚 Knowledge Quiz") as app:
        gr.Markdown("# 📚 医学基础必背考点")

        with gr.Tabs() as tabs:
            # ====== 开始答题 Tab ======
            with gr.TabItem("🎯 开始答题", id=0):
                with gr.Row():
                    q_type = gr.Dropdown(["全部", "选择题", "判断题"], value="全部", label="题型")
                    section = gr.Dropdown(sections, value="全部", label="章节")
                    count = gr.Dropdown(["全部", "10题", "20题", "50题"], value="20题", label="题数")

                start_btn = gr.Button("开始答题", variant="primary")

                quiz_info = gr.Markdown("")
                quiz_question = gr.Markdown("")

                with gr.Row(visible=False) as choice_row:
                    btn_a = gr.Button("A")
                    btn_b = gr.Button("B")
                    btn_c = gr.Button("C")
                    btn_d = gr.Button("D")

                with gr.Row(visible=False) as judgment_row:
                    btn_true = gr.Button("✓ 正确")
                    btn_false = gr.Button("✗ 错误")

                quiz_result = gr.HTML("")

                with gr.Row():
                    prev_btn = gr.Button("⬅️ 上一题")
                    next_btn = gr.Button("下一题 ➡️")

                # 事件绑定
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
                    wrong_section = gr.Dropdown(sections, value="全部", label="章节筛选")

                with gr.Row():
                    refresh_wrong_btn = gr.Button("🔄 刷新错题")
                    review_wrong_btn = gr.Button("📝 复习错题", variant="primary")

                wrong_display = gr.Markdown("")

                refresh_wrong_btn.click(get_wrong_questions_display, [wrong_section], wrong_display)
                review_wrong_btn.click(start_wrong_review, [wrong_section], [quiz_info, quiz_question, choice_row, judgment_row, quiz_result, tabs])

                # 薄弱知识点
                gr.Markdown("---")
                weak_btn = gr.Button("🎯 查看薄弱知识点")
                weak_display = gr.Markdown("")
                weak_btn.click(get_weak_points_display, None, weak_display)

            # ====== 知识点学习 Tab ======
            with gr.TabItem("📖 知识点学习", id=2):
                with gr.Row():
                    kp_section = gr.Dropdown(sections, value="全部", label="章节")
                    kp_topic = gr.Dropdown(["全部"], value="全部", label="考点")

                kp_keyword = gr.Textbox(label="关键词搜索", placeholder="输入关键词...")

                kp_search_btn = gr.Button("🔍 搜索", variant="primary")

                # 知识点统计
                kp_stats = gr.Markdown(f"**知识点总数**: {len(KB_DATA.get('knowledge_points', []))} 个")

                kp_results = gr.Markdown("", elem_classes=["kp-scroll"])

                # 章节变化时更新考点列表
                kp_section.change(update_topic_dropdown, [kp_section], [kp_topic])

                kp_search_btn.click(get_knowledge_points_grouped, [kp_section, kp_topic, kp_keyword], kp_results)

            # ====== 学习报告 Tab ======
            with gr.TabItem("📊 学习报告", id=3):
                report_btn = gr.Button("🔄 刷新报告", variant="primary")
                report_output = gr.Markdown("")

                report_btn.click(get_report, None, report_output)

    # 添加自定义 CSS
    app.load(lambda: None)

    return app

if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="127.0.0.1", server_port=7864, share=False, inbrowser=True)
