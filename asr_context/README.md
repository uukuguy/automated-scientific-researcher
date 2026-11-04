# 研究上下文核心

这个包独立于智能体运行时，当前提供原文投影和带来源的研究笔记。它不调用模型、不管理研究任务或预算，也不代表某个运行时已经采用了压缩结果。

## 代码依赖与证据引用

`Material.references`表示必须一起进入上下文的依赖，例如继续编程需要的代码。`Material.citations`表示必须有可访问来源和目录记录、但原文可以按需取回的证据。二者都不能引用缺失或不可访问的材料。

`compact(materials, role=..., max_bytes=...)`先保护指定材料、未完成交互及其依赖，再优先加入较新的可选内容。输出`asr-research-context/2`：完整材料目录指纹、保留项、移出项和实际正文。容量按完整JSON的UTF-8字节计算，不是模型token估算。最低必要输出也放不下时返回`deferred`；调用方必须保留原上下文并处理，不能把它当作已应用。

## 笔记版本与恢复

`NoteStore(root, scope=...)`以内容指纹保存不可变笔记，包含父版本、正文和来源的版本/指纹。`save`返回版本号，重复保存相同内容返回相同号；不维护“当前笔记”指针。调用方持久化实际采用的版本，草稿和分叉不自动成为现行记忆。磁盘损坏或跨scope读取会报错。

```python
from asr_context import Material, compact
from asr_context.notes import NoteStore, restore

source = Material('trial:001', 'r1', '本次实验的原始结果')
store = NoteStore('/tmp/example-research-notes', scope='project/run/lead')
draft = store.save('当前证据仍不足以支持普遍性结论。', sources=[source])
# 实际应用由宿主明确保存它采用的版本；这里仅演示调用。
result = restore(store, accepted_revision=draft, materials=[source], role='lead')
if result['status'] == 'ready':
    projection = compact([source, result['material']], role='lead', max_bytes=4000)
```

`restore`核查当前提供的来源。缺失或不可访问返回`source_unavailable`；版本、内容或元数据改变返回`source_changed`，均不返回笔记材料供安装。通过后产生受保护笔记，引用为可按需回查的`citations`。旧来源仍可供历史审查，但不能以旧来源替代当前状态核查后声称笔记仍有效。

scope和role是调用方提供的绑定与筛选条件，并非认证。宿主仍负责访问授权、来源读取与当前Control状态。笔记正文的事实正确性、反证覆盖、科学结论强度不能靠指纹检查证明。

## 已验证与后续边界

离线测试覆盖不可变修订、草稿选择、来源变更/缺失/不可访问、引用目录、容量不足和真实故障笔记。6次实际错误可缩成有来源的简要记录，明确区分上下文拒绝与连接终止；这不是模型生成的语义摘要验收。

尚未接入研究工具、Control的笔记采纳记录、模型摘要、主动容量预警、原文查询服务或Runtime安装。完整研究状态与权限仍由现有ASR服务负责，不能以笔记替换它们。
