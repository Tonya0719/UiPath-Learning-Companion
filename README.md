# PE6202 UiPath Learning Companion — 独立开发副本

基于 Xinyi 2026-09-04 代码继续开发。所有改动位于本目录；不修改原始代码和 Senmiao 原始数据。

## 当前完成的内容

- 已实际接入 31 张 Concept、20 张 Task、9 张教师例题卡；新增 3 张官方文档摘要卡。
- 保留三个平衡模块和五个原有函数入口：知识问答、下一步、Debug、出题、讲题。
- 扩大检索字段，增加常用中英文术语映射；无匹配时不跨 Week/Exercise 回退，也不返回零相关卡片。
- 增加任务顺序映射，检索当前及相邻任务作为上下文；不是自动确认学生已完成的步骤。
- 五类 Prompt 包含任务、证据、边界、输出 schema 和信息不足处理；检索内容不作为指令。
- 引用 ID 校验后，由程序补充真实资料名称、页码和官方链接；这不能替代“结论是否被证据支持”的人工审核。
- 模型接口支持超时提示、部分临时 HTTP 错误的一次重试，以及无效输出的一次格式修复。
- 出题参考例题风格时不提供未核实答案；检查 A–D 格式、选项重复、来源 ID 与文本近似复制。
- 讲题沿用出题证据；发现答案或逐项解释不一致时不判分；界面保存提交时答案。
- 三个模块均显示相关状态、澄清问题和资料来源。默认演示模式明确标注，不伪造诊断或新试题。
- 增加 20 个待复核的开发测试案例及 A/B/C 运行入口，默认只检查，不调用模型。

## 启动

建议在 PowerShell 中创建独立 Python 3.10+ 环境后运行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\start.ps1
```

`start.ps1` 会优先使用本目录的 `.venv`；`launch.py` 只监听本机，不发布到互联网。启动后访问终端显示的本地地址，默认 `http://127.0.0.1:8501`。

## 配置真实模型

DeepSeek V4 官方接口的思考策略：知识问答（learning）显式关闭思考；出题（generate）和 Debug 开启 low 强度思考。下一步、讲题沿用服务默认设置。格式修复沿用原任务的思考策略，A/B/C 对同一任务使用相同策略。该策略由 `llm_client.py` 设置，不需要更改 `.env`，且不会传给其他模型服务。实际速度和回答质量仍需对比测试。

1. 在本目录复制 `.env.example` 为 `.env`，填写模型服务的 API key、地址和模型名。
2. 将 `MOCK_LLM` 改为 `false`，重启程序。
3. 先用每个行为一个问题小规模联调，再进行批量评价。

接口使用 `/chat/completions` 和 JSON object 输出，服务需要兼容该请求格式。当前模型名沿用原配置，并不代表已经选型或验证。API key 不要放进源码、报告或群聊；`.gitignore` 已忽略 `.env`。

默认模式只进行资料预览：知识模块展示相关内容，操作模块不模拟真实诊断，测验模块不生成或批改试题。不要将演示运行当成模型效果。

## 数据与来源

`data/concept_cards.json`、`task_cards.json`、`question_cards.json` 是 Senmiao 数据的副本，原始答案标注保留不变。9 道答案均为 `answer_verified=false`，需由组员按课程材料核对。

`data/task_sequence.json` 按现有任务卡及来源页码顺序整理，供邻接上下文检索使用；仍需数据组核对步骤粒度，尤其是开放式练习。

`data/official_cards.json` 是 2026-09-04 核对页面后生成的简短摘要，保留产品、文档版本和 URL，不是整个 UiPath 文档库：

- [Google Workspace Write Range](https://docs.uipath.com/activities/other/latest/productivity/google-workspace-sheets-write-range-connections)
- [Google Workspace Read Range](https://docs.uipath.com/activities/other/latest/productivity/google-workspace-sheets-read-range-connections)
- [Google Workspace Delete Range](https://docs.uipath.com/activities/other/latest/productivity/google-workspace-sheets-delete-range-connections)

以上是动态 latest 文档的摘要快照，不代表学生已安装的活动包版本。课程步骤与官方行为有差异时需核查环境。后续可按失败案例补充其他相关文档。

## 检查与测试

### 网页里的示例和 C 版记录导出

五个行为均提供一键示例：知识问答、下一步、Debug、出题，以及可直接载入固定题目的讲题示例。按钮只填写内容，不调用模型；确认后点击提问/获取指导/生成题目/提交答案才运行。讲题示例是开发测试题，非教师题目，载入时预选 B，可修改后提交。

运行中会显示检索、等待模型、格式检查或重试阶段，完成后显示总耗时。阶段来自实际程序事件；并非模型内部思考进度或预计剩余时间。

页面底部“测试与导出”默认折叠。每次提交自动保留输入、输出、引用资料、C 版 Prompt 版本、模型/思考参数、耗时、处理阶段和重试次数；错误请求也有记录。可下载单条/全部 JSON，或适合组员查看的 Markdown。不会因点击下载重新调用模型。

记录仅存于当前浏览器会话，最多保留最近 50 条，未保存的记录可能在刷新断线或重启后丢失。请及时下载。示例填充不产生记录，只有提交请求才会记录。导出是未评分的开发功能测试，不是正式 A/B/C 结果。

导出使用字段白名单，不包含完整系统提示、原始模型响应、请求头或 .env 内容；会遮盖当前 API key、常见 sk- 密钥和 Bearer 值。仍可能包含姓名、邮箱或业务信息，分享前需要人工复核。导出包含试题答案，不适合作为无答案的学生练习卷。

在本目录执行：

```powershell
python scripts/validate_data.py
python -m unittest discover -s tests -v
python evaluation/run_eval.py
```

若使用本地 `.packages/` 而不是已安装依赖的虚拟环境，测试前在当前 PowerShell 会话设置 `$env:PYTHONPATH = (Join-Path $PWD '.packages')`。这只影响当前会话。

结构检查不验证课程事实；自动化测试主要验证程序逻辑。实际模型效果需要下面的正式评价流程。

## A/B/C 评价

`evaluation/cases.json` 中 20 个案例由本次开发新增，全部标记为 `draft`，并标记已用于开发冒烟测试；不是同学已经完成的 gold dataset。分配为知识 7、下一步 3、Debug 4、出题 3、讲题 3。讲题输入是独立编写的候选测试题，不是教师例题。

- A-1.0：最简任务提示；无检索和教师示例。
- B-1.0：结构化提示；无检索和教师示例。
- C-1.3：完整检索、例题风格参考与引用检查。

三版分别记录独立的 Prompt 版本号。生成的练习题默认标记为
`NEEDS_HUMAN_REVIEW`，逐题人工核对后再正式使用。

三版保留相同最小输出 schema 和输入检查。出题等内容检查的差异属于完整系统的一部分，不可仅凭 B/C 差异归因于某个检索算法。

默认 `python evaluation/run_eval.py` 只检查案例和数据，不产生模型费用。真实调用需要 API 配置，并显式执行：

```powershell
python evaluation/run_eval.py --run --variant all --allow-draft
```

先单独试跑一条 C 版案例，可执行：

```powershell
python evaluation/run_eval.py --run --variant C --allow-draft --case-id M1_04
```

确认模型、密钥和输出正常后，再去掉 `--case-id M1_04` 跑完 C 版 20 条。`--case-id` 可以重复填写，以只运行若干指定案例。

这个命令运行开发案例，不是最终评价；可能产生 60 次基础模型请求，遇格式修复或临时错误可能增加。最终评价应由评价组核对案例、rubric 和来源后，将 `review_status` 设为 `approved`，最好另建未参与调试的保留案例文件，再去掉 `--allow-draft`。

`evaluation/final_cases.json` 是 Evaluation 组提供的20条已审核保留案例，全部标记为 `approved` 和 `used_for_development=false`。不要用它调整 Prompt、检索或代码。冻结模型、temperature、数据和成功标准后，使用以下命令一次性运行正式 A/B/C：

```powershell
python evaluation/run_eval.py --cases evaluation/final_cases.json --run --variant all
```

正式运行前先执行不带 `--run` 的同一命令进行结构预检。若正式运行出现接口或格式错误，保留原始结果，不要静默替换；由小组先确定统一的失败重试规则。

每次运行生成独立的 `evaluation/results/*.jsonl`，包括案例、A/B/C、模型参数、Prompt 版本、数据哈希、证据、输出、耗时和空白人工评分栏。文件可能包含用户输入，不要公开未脱敏日志。单个案例失败不会中断其他案例。

## 尚未完成 / 不应宣称

- 尚未运行正式 A/B/C 60条评价。
- 九道例题答案仍需对应组员审核。
- 现有检索是轻量关键词检索，不是 BM25、embedding 或多模态 RAG；阈值和术语表需通过实际问题调优。
- 文本近似与格式检查不能保证语义新颖、单一正确答案或教学质量，仍需人工评价。
- 尚未实现截图输入、跨模块自动上下文、公开部署或完整官方资料覆盖。

下一步最重要的是配置小组确定的真实模型，完成五类行为的小规模联调，再与 Prompt、数据和评价组一起修正失败案例。
