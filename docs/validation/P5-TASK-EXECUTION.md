# P5 任务到真实实验的工程验收

2026-11-03。完成任务准入、Lead/worker工具绑定和真实容器链路验证；P5科研验收仍未完成。

## 已完成

- 协调任务缺省没有实验权限。任务可明确允许study:label、study:analysis、study:fit，但仍受原契约、固定科学profile及共享预算约束。
- 只有当前in_progress任务的真实assignee能提交，必须携带task_id及当前revision。组织者、人类控制凭据、其他worker或旧版本不能冒充该任务执行者。
- 准入与预算预留位于同一事务，冻结成员、方向、任务记录及操作；失败准入不占用预算，重复请求不重复执行或收费。
- 领取后不能扩大权限。有排队、运行或未对账实验时不能完成／取消任务。已取消且未启动的实验以及已发布失败证据都可以如实交付；失败不自动重试。
- Supervisor将完整绑定写入manifest，发布／恢复时核对。研究员状态显示任务版本和绑定摘要，避免只靠会话记忆判断归属。
- research-organization-study/1仅允许Lead/worker在OOD开发契约下绑定，角色对话和预算仍走原流程；组织者继续使用协调profile。旧参考／复现实验入口不能绕过组织任务授权。

## 验证

完整工程检查：`uv run --extra aar python -m unittest discover -s tests -v`，共354项，332项通过、22项环境跳过。组织相关检查共33项，其中31项通过、2项真实容器检查默认跳过。

显式选择科学镜像`sha256:cd5dc68c73d6c397c838dff732111ee72d90bb5161243690ca3d12ea06a90012`后，两项真实容器检查通过：

1. worker经ResearchBridge提交任务绑定的数值label，真实生成一个样本并返回labelled状态，manifest保留原任务版本。
2. worker经同一路径运行故意抛错的analysis，返回failed，保留原始错误、任务绑定和实际消耗，释放预留后如实完成任务。

代码：`tests/test_organization_experiments.py`、`tests/test_organization_execution.py`。前者另覆盖错人／错版本／无授权拒绝、排队及运行中不能关闭、取消队列后的幂等回放、旧入口封堵、失败进程的证据归属及篡改拒绝、角色profile绑定和紧凑状态恢复。

可复查材料：`artifacts/p5-task-execution-checks-001/receipt.json`及`inventory.json`，包含两份独立工程fixture账本、容器证据与日志，共30个文件另加inventory。初次导出遇到macOS的/var与/private/var路径别名，在已复制的成功fixture上恢复归档，没有重跑该成功样例；经过摘要核对。账本中的原始绝对路径按receipt里的source_root→archive_root映射读取。

这些是开发者设定的有界工程样例，没有模型调用，不是团队提出的3584个求解槽位研究。原P4与P5设计运行均未重开。没有声称新采样方案有效、多个模型并行执行或模型已自主使用新profile完成研究。

## 接下来必须解决

团队配对方案复用跨arm坐标，而旧study接口禁止跨trial坐标重复。需要冻结配对身份、重复求解计费和样本用途，再决定允许哪些明确复用，不能直接取消防泄漏去重。

团队的acquisition_ledger.py仍需要原生标签适配、可信的求解前输入来源、不可变存储绑定及可执行测试。原报告的“未运行”状态保持有效；本次只检查了源码并完成周边准入链路，未导入或执行该原型。实际团队科研仍需新的契约、评价冻结和模型驱动证据。
