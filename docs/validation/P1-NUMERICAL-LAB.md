# P1 本机数值实验与证据验收

日期：2026-11-02。对应主设计修订 0.7；当前实现是本机参考实验入口，不是 ASR 公共服务或 AAR 自主闭环。

## 已验证结果

机器记录见 [P1-REFERENCE-RESULTS.json](P1-REFERENCE-RESULTS.json)。使用 Python 3.12.12、OrbStack 的原生 linux/arm64 容器、MATPOWER 8.1、Octave 7.3.0。

| 检查 | 结果 |
|---|---|
| IEEE-118 原始规模 | 118 节点、54 发电机、186 支路 |
| 固定 PV/PQ、平启动 NR | 4 次迭代收敛 |
| 独立 Python 方程残差 | 最大 P/Q 分量不平衡 3.935784299266862e-13 p.u. |
| 原始固定输入 | 保持不变 |
| 运行约束 | 6 处发电机无功越限；186 条支路 RATE_A=0，热约束未评估 |
| 重复提交 | 返回同一 attempt，不重复计算 |
| 新 trial 重放 | 相同冻结请求、新容器，解矩阵完全相同；耗时不要求相同 |
| 电压/原负荷被改动 | 验证器拒绝 |
| NR 截断至 1 次迭代 | 求解未收敛，残差约 0.825375629 p.u.，结果和日志保留 |
| 0.001 秒执行时限 | timed_out，确认对应容器已移除 |
| 单元测试 | 28 项通过，含并发幂等、失败重试、产物篡改、发布中断恢复与未知执行拒绝自动重跑 |

上述基线仅证明参考数值链路和独立方程检查。无功限值不执行 PV/PQ 切换，而作为独立运行约束报告，因此不能宣称该解运行可行。它不证明 OOD 覆盖、算法创新或科学泛化。

## 运行与重放

在仓库根目录，使用 Python 3.12 及以上：

```sh
python3 -m unittest discover -s tests -v
python3 -m powerflow_lab.reference --key my-baseline
python3 -m powerflow_lab.reference --key my-baseline
python3 -m powerflow_lab.reference --key my-truncated --max-it 1
python3 -m powerflow_lab.reference --key my-timeout --timeout 0.001
```

CLI 输出终态 manifest；进程正常结束但方程无效时 execution 仍为 succeeded，必须读取 validation.json。超时/执行失败返回非零 CLI 状态。运行时镜像 ID 从 [numerical-environment.json](../../configs/numerical-environment.json) 读取，不跟随镜像 tag 漂移。

重放采用新 key，并通过 `--replay-of ORIGINAL_TRIAL_ID` 关联原试验；参数须与原请求一致。`--retry` 对原 key 创建新的 attempt，保留旧结果；它不是新的科学独立重跑。源码和 Python 版本进入请求身份：代码变化后重复旧 key 会冲突，不能借相同名字宣称相同重放。

每次试验存于被 Git 忽略的 `data/trials/<trial_id>/`：request.json、attempts/<attempt_id>/manifest.json、冻结输入、解、求解器元信息、验证报告、日志、源码副本、包清单及清理回执。manifest 对全部产物保存 hash/大小。验证历史记录可调用 `powerflow_lab.runner.verify_trial(root, key)`。

要在代码变化后复现，应取对应提交或保存的源码副本与同一镜像 ID，并使用原请求环境。当前 CLI 不自动执行任意历史 Python 快照；源码不匹配时拒绝，避免执行当前代码却称为冻结重放。原始数据位于当前工作机，跨机交接须额外导出完整试验目录和镜像，JSON 汇总不是完整复现包。

## 构建来源与可重复性边界

基础镜像 digest、MATPOWER 8.1 tag 归档 checksum、case118 文件 hash、参考脚本 hash、最终镜像 ID 及包清单 hash 已记录。完整包清单见 [numerical-packages.txt](../../configs/numerical-packages.txt)。MATPOWER 来自其[官方源码仓库](https://github.com/MATPOWER/matpower/tree/8.1)，保留镜像内上游许可证。

归档位置为 `.cache/matpower-8.1.container.tar.gz`，sha256 必须为 `5f08ced1a32e8d0d658ee54b73678c7364a899bae479882f2bc419e91442b69f`。同目录的 `matpower-8.1.tar.gz` 和 `matpower-8.1.complete.tar.gz` 是超时留下的部分下载，不可用。宿主网络下载较慢，容器内 HTTPS 下载成功。

首次准备归档可用：

```sh
mkdir -p .cache
docker run --rm --mount type=bind,src="$PWD/.cache",dst=/cache python:3.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c python -c 'import urllib.request; urllib.request.urlretrieve("https://codeload.github.com/MATPOWER/matpower/tar.gz/refs/tags/8.1", "/cache/matpower-8.1.container.tar.gz")'
shasum -a 256 .cache/matpower-8.1.container.tar.gz
docker build -t asr-numerical-base:dev -f docker/Dockerfile.numerical-base docker
docker build -t asr-matpower:8.1 -f docker/Dockerfile .
docker image inspect asr-matpower:8.1 --format '{{.Id}} {{.Architecture}}'
```

构建时再次强制校验归档 checksum。APT 仓库尚未固定到历史快照，因此重新构建可能得到新的包和镜像，**不承诺逐字节相同重建**。变更镜像后先重新导出包清单、检查版本和 case hash，建立新的环境记录并重跑本页验收，再更新配置；旧试验保持旧环境身份。固定现有镜像的执行重放已验证。

`compose.yaml` 提供等效限制下的原始调试运行，不生成试验 manifest；日常证据入口使用上述 Python CLI。Compose 的 ASR_NUMERICAL_IMAGE 可指定已记录 ID，输出目录须可写，ASR_UID/ASR_GID 与本机用户一致。

## 实现边界与待接入能力

- 验证器支持连通网络、单参考节点、固定 PV/PQ、恒功率负荷、固定拓扑；不支持 Q 限值切换、多 Slack/孤岛。电压初值可变，PV/Slack 电压设定及参考角仍须满足。
- 独立方程计算未调用 MATPOWER 的 Ybus 或残差，使用 Python 复数支路电流与节点平衡。变压器/并联电纳约定已对照 [MATPOWER makeYbus](https://matpower.org/docs/ref/matpower7.0/lib/makeYbus.html)，并用解析负例验证。
- 原始物理数据冻结，允许单 Slack 发电机有功及 PV/Slack 发电机无功求解变化；其限值独立评估。
- 本地 runner 用文件锁和原子发布保证当前单机入口的幂等与证据一致性，尚未接入设计中的数据库预算账本、身份权限和跨组件控制 API。
- 完整 manifest 已写但尚未原子发布时可自动恢复。未知执行或无 manifest 的 pending 目录阻止重跑，需先核对相关容器；当前不自动猜测进程死亡或回收预算。
- 实验容器无网络、无 Docker socket、只读 rootfs，并限制 CPU/内存/进程与时间。输出限制在发布阶段检查，未实现运行时磁盘配额；当前只执行受信任固定参考脚本，不是任意候选代码的正式安全验收。
- 复核使用独立数学实现，但尚未完成 P3 的独立权限身份及正式评价数据隔离验收。
- Octave 7.3.0 退出日志含 `ignoring const execution_exception` 提示；本次正常运行退出码为 0，完整产物及独立残差检查通过。该提示被保留，不以日志文本单独判定成功或失败。
