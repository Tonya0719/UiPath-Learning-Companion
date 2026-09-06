# UiPath Learning Companion

一个基于 Streamlit 的 UiPath 学习辅助应用，用来围绕课程内容提供三类能力：

1. 知识问答
2. 操作与 Debug 指导
3. 模拟题生成与题目讲解

项目当前支持本地运行，也支持部署到 Streamlit Cloud。默认可以以预览模式运行，不调用模型；当配置好 API key 后，可以切换到真实模型调用。

## 功能概览

- 知识问答
  - 解释概念、活动、课程知识点
  - 支持按 Week 过滤
  - 返回知识点、练习关联和常见误区
- 操作与 Debug
  - 根据当前步骤、界面状态或报错，给出下一步建议
  - 支持两种模式：
    - 下一步指导
    - 问题诊断
- 模拟题与讲解
  - 根据主题、难度和题型生成练习题
  - 支持提交答案后解释正确项与错误项
  - 题目生成后标记为需人工复核，避免直接当成正式题库
- 运行记录与导出
  - 在页面底部保留会话内测试记录
  - 支持导出 JSON 和 Markdown
  - 导出内容会做敏感信息脱敏

## 技术栈

- Python 3.10+
- Streamlit 1.63
- Pydantic 2.x
- 标准库 `urllib` 负责 HTTP 请求
- 本地配置读取：
  - `.env`
  - Streamlit Cloud 的 `Secrets`（TOML）

## 项目结构

```text
app.py              # Streamlit 主应用
launch.py           # 本地启动器，调用 streamlit run app.py
start.ps1           # Windows 本地启动脚本
config.py           # 配置加载，支持 .env 与 st.secrets
llm_client.py       # 模型请求、重试、格式修复、证据约束
runtime.py          # 运行时实验模式与事件记录
ui_runs.py          # 测试记录、脱敏和导出
ui_examples.py      # 页面示例数据
ui_theme.py         # 页面样式
modules/            # 业务逻辑
retrieval/          # 检索与数据读取
schemas/            # Pydantic 输出 schema
data/               # 课程数据与卡片
evaluation/         # 评估脚本与案例
tests/              # 单元测试
```

## 本地运行

建议使用独立虚拟环境：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\start.ps1
```

默认访问地址：

```text
http://127.0.0.1:8501
```

也可以直接运行：

```powershell
streamlit run app.py
```

不要用 `python app.py` 直接启动，这个文件是 Streamlit 页面入口，不是普通命令行程序。

## 配置

### 1. 本地配置

项目支持从仓库根目录的 `.env` 读取配置。示例文件是 `.env.example`。

`.env` 示例：

```dotenv
MOCK_LLM=false
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_TEMPERATURE=0.0
LLM_TIMEOUT=45
```

### 2. Streamlit Cloud 配置

Streamlit Cloud 的 Secrets 页面使用 TOML 格式。可直接填：

```toml
MOCK_LLM = false
LLM_API_KEY = "your_api_key"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4.1-mini"
LLM_TEMPERATURE = 0.0
LLM_TIMEOUT = 45
```

### 3. 配置优先级

当前配置读取顺序是：

1. 本地环境变量
2. `.env`
3. Streamlit `st.secrets`

这意味着：

- 本地开发优先使用 `.env`
- 部署到 Streamlit Cloud 时，优先使用 Cloud Secrets
- `MOCK_LLM=true` 时进入资料预览模式，不调用模型
- `MOCK_LLM=false` 时调用真实模型

## 页面说明

页面分为三个主 Tab：

1. 知识问答
2. 操作与 Debug
3. 模拟题与讲解

页面侧边栏显示当前知识库统计信息。底部“测试与导出”区域会记录当前会话里的调用结果，最多保留最近 50 条。

## 模型与检索

项目不是纯聊天机器人，而是“检索 + 结构化输出 + 约束校验”的学习辅助应用。

- `retrieval/` 负责从课程卡片中检索相关内容
- `llm_client.py` 负责调用模型、处理重试、做格式校验
- `schemas/` 用 Pydantic 定义输出结构
- `runtime.py` 记录每次请求的阶段事件

模型调用使用 OpenAI 兼容的 `/chat/completions` 风格接口。默认实现会要求模型输出 JSON object，再由 schema 校验结果。

## 测试与评估

### 单元测试

```powershell
python -m unittest discover -s tests -v
```

### 数据检查

```powershell
python scripts/validate_data.py
```

### 评估脚本

默认只做结构检查和数据验证，不直接调用模型：

```powershell
python evaluation/run_eval.py
```

如果要实际跑评估，需要在配置好模型后显式开启：

```powershell
python evaluation/run_eval.py --run --variant all --allow-draft
```

## 部署到 Streamlit Cloud

1. 推送仓库到 GitHub
2. 在 Streamlit Cloud 里选择这个仓库
3. Main file path 填 `app.py`
4. 在 Secrets 中填入模型配置
5. `MOCK_LLM` 设为 `false` 后重启应用

如果仍停留在预览模式，优先检查：

- Cloud 上是不是最新 commit
- Secrets 是否填在当前 app 对应的 workspace
- `MOCK_LLM` 是否仍然为 `true`

## 安全说明

- 不要把真实 API key 写进仓库
- `.env` 已经在 `.gitignore` 中忽略
- 导出日志会对常见敏感字段做脱敏，但分享前仍建议人工复核

## 已知限制

- 这不是完整的正式题库系统，生成题仍需要人工复核
- 检索逻辑目前是轻量关键字检索，不是 BM25 / 向量 RAG
- 课程数据、题目数据与官方资料卡片仍需要持续人工校对
- 测试记录只保存在当前浏览器会话中，刷新或重启后可能丢失

## 许可证

未单独声明许可证时，默认按项目当前仓库约定处理。

