"""Local development examples. Filling an example never calls a model."""

from schemas.outputs import PracticeQuestion

LEARNING = {
    "learn_question": "Why doesn't Google Sheets change after I modify the DataTable? Explain the cause and what action should be added.",
    "learn_week": 2,
    "learn_depth": "Brief",
}

LEARNING_ZH = {
    "learn_question": "为什麽我修改了 DataTable 里的数据，Google Sheets 里的内容却没有变化？请解释原因，以及应该增加什麽操作。",
    "learn_week": 2,
    "learn_depth": "Brief",
}

NEXT = {
    "build_week": 1,
    "exercise_1": "User Interface Automation",
    "help_mode": "next_step",
    "next_last": "Created Use Application/Browser and connected to the Streamlit registration page.",
    "next_state": "The browser scope is configured, but Type Into has not been added yet.",
}

NEXT_ZH = {
    "build_week": 1,
    "exercise_1": "User Interface Automation",
    "help_mode": "next_step",
    "next_last": "已创建 Use Application/Browser，并连接到 Streamlit 注册页面。",
    "next_state": "浏览器作用域已经配置好，但还没有添加 Type Into 活动。",
}

DEBUG = {
    "build_week": 3,
    "exercise_3": "Document Data Extraction",
    "help_mode": "debug",
    "debug_activity": "Write Range",
    "debug_error": "When processing multiple PDF invoices, the workflow does not throw an error, but the Overall sheet keeps only the last invoice. I want to keep all invoices. What should I check?",
    "debug_change": "Changed from handling one PDF to looping over multiple PDFs.",
}

DEBUG_ZH = {
    "build_week": 3,
    "exercise_3": "Document Data Extraction",
    "help_mode": "debug",
    "debug_activity": "Write Range",
    "debug_error": "处理多个 PDF 发票时，workflow 没有报错，但 Overall 表里只保留了最后一张发票的数据。我希望保留所有发票，应该检查哪些地方？",
    "debug_change": "从处理一张 PDF 改成了循环处理多张 PDF。",
}

GENERATE = {
    "gen_topic": "Google Sheets",
    "gen_difficulty": "Medium",
    "gen_type": "Workflow Logic",
}

GENERATE_ZH = {
    "gen_topic": "Google Sheets",
    "gen_difficulty": "Medium",
    "gen_type": "Workflow Logic",
}


def examples(language="zh"):
    if language == "en":
        return {
            "learning": LEARNING,
            "next_step": NEXT,
            "debug": DEBUG,
            "generate": GENERATE,
        }
    return {
        "learning": LEARNING_ZH,
        "next_step": NEXT_ZH,
        "debug": DEBUG_ZH,
        "generate": GENERATE_ZH,
    }


def explanation_example(language="zh"):
    if language == "en":
        return PracticeQuestion(
            status="GENERATED",
            question_id="EXAMPLE-DATATABLE",
            question="A workflow reads Google Sheets into a DataTable and changes one value in the DataTable only. How can that change appear back in the original spreadsheet?",
            options={
                "A": "Write the modified data back to Google Sheets explicitly.",
                "B": "Wait for the DataTable to sync automatically with Google Sheets.",
                "C": "Only rename the DataTable variable.",
                "D": "Close the browser and let the spreadsheet save itself.",
            },
            correct_answer="A",
            knowledge_point="Explicit write-back for DataTable",
            question_type="Workflow Logic",
            difficulty="Medium",
            course_evidence_ids=["W2-C-01"],
            answer_rationale="A DataTable is an in-memory copy, so updating the original spreadsheet requires an explicit write-back.",
        )
    return PracticeQuestion(
        status="GENERATED",
        question_id="EXAMPLE-DATATABLE",
        question="某个 workflow 把 Google Sheets 读到 DataTable，且只修改了 DataTable 里的一个值。怎样才能让这个修改出现在原表格中？",
        options={
            "A": "将修改后的数据显式写回 Google Sheets。",
            "B": "等待 DataTable 自动同步到 Google Sheets。",
            "C": "只需要重命名 DataTable 变量。",
            "D": "关闭浏览器后，修改会自动保存到原表格。",
        },
        correct_answer="A",
        knowledge_point="DataTable 显式写回",
        question_type="Workflow Logic",
        difficulty="Medium",
        course_evidence_ids=["W2-C-01"],
        answer_rationale="DataTable 是内存副本，修改原表格需要显式写回。",
    )
