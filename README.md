# Automated Scientific Researcher

ASR 构建可持续运行、可恢复、可复核的自动化科研系统。人类设定课题、研究变量、评价规则和预算，智能体在授权范围内提出假设、实现候选方法、执行实验并分析证据。

首个应用是电网运行样本探索与潮流求解方法研究。样本生成、求解算法、初值与数值实现都可以作为研究变量；固定参考基线不限制候选方法创新。

## 系统分工

| 部分 | 职责 |
|---|---|
| Capstone 科学研究模式 | 人类工作台：课题对话、研究配置、运行观察、方向指导及发现复核入口 |
| ASR 控制与实验服务 | 契约、预算、控制回执、真实实验、原始证据及恢复 |
| AAR 研究执行器 | 在契约内自主选择方法、编写候选代码、安排实验、分析结果 |
| 独立评价器 | 基于冻结材料验证原问题、重跑实验并检查结论 |

目标闭环：建立课题 → 发布研究契约 → 自主研究与真实实验 → 人类介入 → 候选发现 → 独立复核 → 继续研究或交付结果。

## 当前状态

总体架构、研究变量和人机交互原则已确认；最小闭环详细设计与 Capstone 准备交接已形成。接口是待实现的设计，尚未完成跨项目联调。

P1 本机数值切片已完成：MATPOWER 8.1 / Octave 7.3.0 的 IEEE-118 参考实验、独立 Python 方程验证、不可覆盖的证据、并发幂等、失败保留和重放均已有运行证据。当前进入 **P2：契约、控制服务与单研究员接入**；尚无可调用 ASR API 或已验证的 AAR 自主闭环。

参考基线在 4 次迭代后达到约 `3.94e-13 p.u.` 残差，但有 6 处无功越限，186 条支路热限额未评估，因此不宣称运行可行。详见 [P1 验收记录](docs/validation/P1-NUMERICAL-LAB.md)。

研发采用 OrbStack + Docker Compose，不额外设置虚拟机。Python 要求 3.12 及以上。参考执行使用固定镜像 ID；APT 构建源尚未固定到历史快照，重建镜像需要重新验收。

## 文档入口

- [项目主设计](docs/PROJECT-DESIGN.md)：持续维护的目标、架构、变量、边界与设计状态。
- [最小闭环详细设计](docs/architecture/ASR-MINIMUM-LOOP.md)：契约、状态转换、实验协议、预算、证据、恢复、AAR 接入及接口候选。
- [Capstone 交接说明](docs/handoffs/CAPSTONE-SCIENTIFIC-RESEARCH-MODE.md)：可并行开展的工作台准备任务、职责和验收条件。
- [工作清单](docs/plans/WORKLIST.md)：交付顺序、依赖与当前实现证据。
- [数值环境实施计划](docs/superpowers/plans/2026-11-02-container-lab.md)：P1 的参考实验切片。
- [决策记录](docs/status/DECISIONS.md)与[状态入口](docs/status/INDEX.md)：设计理由、工作日志和恢复位置。
- [原始任务书](docs/IEEE118_OOD_Sample_Expansion_Task_v2_2.md)：业务研究背景，不能覆盖后续确认的项目边界。

## 开发与验证

开始工作先读 [AGENTS.md](AGENTS.md)、主设计和当前工作清单。`CLAUDE.md` 链接到同一份仓库规则。

本地 AAR 上游位于被忽略的 `3th-party/automated-w2s-research/`，Python 包根为其中的 `w2s_research/`。后续适配应固定来源并将补丁保存到受版本控制的目录，不能只修改被忽略副本。

已有已记录镜像时，在仓库根目录执行：

```sh
python3 -m unittest discover -s tests -v
python3 -m powerflow_lab.reference --key my-baseline
```

首次构建、重复提交、截断实验及重放方法见 [数值实验操作说明](docs/validation/P1-NUMERICAL-LAB.md)。模拟服务只能证明接口与交互；真实潮流计算、独立验证和实际模型驱动研究分别需要独立的运行证据。执行完成、求解收敛、方程有效、运行可行和科学结论成立分别报告。
