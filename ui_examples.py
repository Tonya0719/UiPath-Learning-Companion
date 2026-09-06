"""Local development examples. Filling an example never calls a model."""
from schemas.outputs import PracticeQuestion

LEARNING = {'learn_question': '为什么我修改了 DataTable 中的数据，Google Sheets 里的内容却没有变化？请解释原因，以及应该增加什么操作。',
            'learn_week': 2, 'learn_depth': 'Brief'}
NEXT = {'build_week': 1, 'exercise_1': 'User Interface Automation', 'help_mode': '下一步',
        'next_last': '已创建 Use Application/Browser，并连接到 Streamlit 注册页面。',
        'next_state': '浏览器作用域已经配置好，但还没有添加 Type Into 活动。'}
DEBUG = {'build_week': 3, 'exercise_3': 'Document Data Extraction', 'help_mode': 'Debug',
         'debug_activity': 'Write Range',
         'debug_error': '处理多个 PDF 发票时，workflow 没有报错，但 Overall 表里只保留了最后一张发票的数据。我希望保留所有发票，应该检查哪些地方？',
         'debug_change': '从处理一张 PDF 改成循环处理多张 PDF。'}
GENERATE = {'gen_topic': 'DataTable 与 Google Sheets 的区别，以及修改数据后为什么需要显式写回',
            'gen_difficulty': 'Medium', 'gen_type': 'Workflow Logic'}

def explanation_example():
    return PracticeQuestion(status='GENERATED', question_id='EXAMPLE-DATATABLE',
        question='某个 workflow 将 Google Sheets 读取到 DataTable，并只修改了 DataTable 中的一个值。怎样才能让这个修改出现在原表格中？',
        options={'A': '将修改后的数据显式写回 Google Sheets。', 'B': '等待 DataTable 自动同步到 Google Sheets。',
                 'C': '只需要重命名 DataTable 变量。', 'D': '关闭浏览器后，修改会自动保存到原表格。'},
        correct_answer='A', knowledge_point='DataTable 显式写回', question_type='Workflow Logic', difficulty='Medium',
        course_evidence_ids=['W2-C-01'], answer_rationale='DataTable 是内存副本，修改原表格需要显式写回。')
