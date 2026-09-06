# dev_v2.4 A/B/C 最终测试接入交接

## 已完成

1. 基于 `dev_v2.3` 创建独立的 `dev_v2.4`，没有修改旧版本。
2. 原样接入 Evaluation/Prompt 组提供的 A-1.0 与 B-1.0 Prompt。
3. C 版继续使用已验证的 C-1.3，且与本次交接文件内容一致。
4. Prompt 路由已调整为：A → A-1.0、B → B-1.0、C → C-1.3。
5. 三版结果会分别记录正确的 Prompt 版本号，并继续使用相同输出 Schema。
6. 最终20条案例保存为 `evaluation/final_cases.json`，没有覆盖原有开发案例 `evaluation/cases.json`。
7. 最终案例共20条，模块分布为7/7/6；全部为 `approved`，全部标记 `used_for_development=false`，所有期望证据ID有效。

## 验证

- 76项自动测试通过，其中13项因当前环境未安装 Streamlit 而按条件跳过。
- 原20条开发案例 dry run 通过，仍为 draft。
- 最终20条案例 dry run 通过，系统识别为 reviewed/approved。
- A/B请求不包含 EVIDENCE 或 STYLE_REFERENCES；C请求包含检索证据及适用的例题风格参考。
- 正式60条尚未运行，因此最终测试集尚未被模型测试结果用于进一步调参。

## 正式运行前需要小组确认

1. 冻结最终20条案例，不再根据输出修改案例。
2. 确认成功标准、评分表和评分人。
3. 确认三版使用相同模型、temperature和任务级思考设置。
4. 预先确定接口或格式失败的统一重试规则，避免只替换表现较差的单条结果。

## 运行命令

结构预检，不调用模型：

```powershell
python evaluation/run_eval.py --cases evaluation/final_cases.json --variant all
```

正式运行60条：

```powershell
python evaluation/run_eval.py --cases evaluation/final_cases.json --run --variant all
```

运行后将同一时间戳的 JSON 和 JSONL 文件交给 Evaluation 组进行人工评分。不要分享 `.env` 或 API Key。
