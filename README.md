# 可运行案例：本地工单诊断 CLI

全部工单为教学虚构快照，日期为 2026-10-31；不连接公司系统，不发送消息，不修改工单状态。`next_step` 为数据文件中写好的建议，不是线上故障分析结果。

## 为什么要做这个工具

教学人物小林协助研发同事跟进测试环境、CI 和权限问题。每张工单是一件需要跟进的事，包含编号、负责人、状态、阻塞原因和下一步建议。

小林每天要整理整个示例团队中阻塞至少三天的任务，交付一份包含编号、负责人、原因、下一步与快照日期的清单。例如 DEMO-101 的授权回调验收需要测试环境地址，地址尚未提供，因此先核实环境负责人与交付时间。小林是跟进负责人，不代表他可以独自解决所有依赖。

`blocked` 表示被未满足的条件卡住，`in-progress` 表示有人正在推进，`done` 表示完成。三天是教学关注阈值，不是公司 SLA。“查清楚并导出”是本轮目标；联系负责人、审批和推进状态另行处理。

## 环境与运行位置

本次验证：Windows PowerShell 5.1、Python 3.12.10。建议 Python 3.10 或以上；仅使用标准库，不需要第三方包。下载或克隆仓库后，在仓库根目录打开 PowerShell。下列命令均从仓库根目录运行。

```powershell
python --version
python .\triage.py --help
```

若 `python` 不可用，先确认 Python 安装与命令路径；使用 `py` 启动器的环境可改为相应 Python 3 命令。

## 十条命令，完成一次工单整理

```powershell
python .\triage.py --help
python .\triage.py list --help
python .\triage.py --version
python .\triage.py list
python .\triage.py list --status blocked
python .\triage.py list --status blocked --min-days 3
python .\triage.py show DEMO-101
python .\triage.py summary
python .\triage.py list --status blocked --min-days 3 --format json
python .\triage.py list --status blocked --min-days 3 --format json --output .\blocked-demo.json
```

预期：全部 8 条、阻塞 5 条、阻塞至少三天 3 条；三条编号按顺序为 DEMO-104、DEMO-101、DEMO-102。`--min-days 3` 包含第三天。重复导出到同名文件会拒绝覆盖，请换新文件名。

## PowerShell 管道实验

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$raw = & python .\triage.py list --status blocked --min-days 3 --format json
$cliExit = $LASTEXITCODE
if ($cliExit -ne 0) { throw "CLI 查询失败：$cliExit" }
$result = ($raw -join "`n") | ConvertFrom-Json
$result.tickets | Select-Object id, owner, waiting_days
```

CLI 返回文本，`ConvertFrom-Json` 解析为 PowerShell 对象。不要把 `2>&1` 合并的诊断文本当纯 JSON。Windows PowerShell 5.1 的默认文件重定向编码与 PowerShell 7 不同，因此教学导出使用程序自己的 `--output`。

## 从最小程序到机器调用

```powershell
python .\minimal_cli.py --name 小林
python .\daily_report.py
python .\verify_example.py
```

- `minimal_cli.py`：理解参数解析与最小入口。
- `triage.py`：命令入口、数据校验、筛选、汇总、输出与退出码。
- `daily_report.py`：以参数列表启动进程，设置超时，判断退出码，解析并检查 JSON 后生成摘要。
- `verify_example.py`：黑盒验证成功、空结果、错误、中文与空格路径、导出不覆盖及本地子进程超时。报告位于仓库内的 `verification/`，该目录不会提交到 Git。

超时实验：`python .\daily_report.py --timeout 0.001`。它故意给本地进程极短期限，预期调用方报告失败并返回 1；它不模拟真实网络故障。

## 输入与结果约定

`--data` 可指定 UTF-8 或 UTF-8 BOM JSON 文件。数据结构见 `tickets.json`；`schema_version=1`，日期 `as_of`、任务数组 `tickets`，每条含编号、标题、负责人、状态、连续阻塞天数、原因和下一步建议。编号唯一，天数非负，未阻塞项天数为零。输入日期目前仅按字符串校验，未实现日期解析或动态计算。

CLI 当前不读 stdin，不自动分页，不访问任何 API。`--owner` 是完整姓名精确匹配，状态必须是 `blocked`、`in-progress`、`done`。JSON 查询返回快照日期与结构版本，排序按等待天数降序、编号升序。

| 情况 | stdout | stderr | 退出码 |
| --- | --- | --- | --- |
| 普通查询成功 | 表格或 JSON | 空 | 0 |
| 空查询成功 | count=0 的结果 | 空 | 0 |
| JSON 导出成功 | 空 | 路径提示 | 0 |
| 参数或数据问题 | 空 | 用法文本或业务错误 JSON | 2 |
| 详情编号不存在 | 空 | NOT_FOUND JSON | 3 |
| 导出失败或目标已存在 | 空 | OUTPUT_FAILED JSON | 4 |

使用 `--output` 时需要同时指定 `--format json`，只创建新文件，不自动创建父目录。它是本地文件写入，不代表业务系统状态修改。

## 连接公司服务前要补的内容

字段与时间口径、数据适配器、认证与资源权限、分页完整性、部分结果、网络超时和限流，以及写操作的重复执行后果。本教程未实现或验证这些功能；可复用的是接口分层与可观察的输入输出约定。

## 许可证

本项目采用 [MIT License](LICENSE)。示例代码为教学编写，人物与工单数据均为虚构。
