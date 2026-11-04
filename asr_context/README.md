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

## Control接入边界

组织角色的`research_note`工具已接入`ControlService.research_note`与ResearchBridge：

- `save`提供`text`和`source_sequences`（共享组织记录seq），生成绑定当前控制/契约版本及来源的草稿。
- `adopt`提供`revision`和`expected_note`（初次为null），以并发版本检查明确采用自己的草稿。
- `read`恢复现行笔记；可提供`revision`预览自己的其它版本，不自动采用。检查结果为deferred时，不能当作已安装的记忆。

当前只接共享组织记录及控制版本；旧seq已经被修订时，保存会拒绝，不会悄悄改绑新版。采纳状态保存在原Control数据库，内容仍由不可变笔记文件保存。写入通过原幂等请求和事件账本记录；拒绝/版本冲突另记事件。多个角色的内容和采纳指针隔离；禁止直接读取服务端笔记目录。

这是本机服务/研究桥接工具接入，尚未扩展公共Control HTTP端点，也未运行新的真实模型会话。代码快照/原始实验文件引用、自动生成笔记、语义压缩、容量预警和Runtime安装仍待接入。采用笔记表示该角色选用一个工作记录版本，不表示科学结论已验证或权限发生改变。

### 原件引用

`save`现可附`artifact_references`：

```json
[
  {"kind":"snapshot","snapshot_sha256":"64位快照指纹","path":"method.py"},
  {"kind":"trial","trial_id":"实际实验ID","path":"study-result.json"}
]
```

Control的来源适配器按受控目录/已登记执行查找原件，核对当前项目、研究运行、实际执行、清单指纹和所引用文件的长度与指纹。失败实验的已发布结果也允许引用；未发布执行、路径越界、符号链接、原始输入载荷和独立评价资产不接受。实验文件目前只允许study-result.json、study-events.json、validation.json、result.json。

笔记保存的是原件绑定信息，不复制大型文件正文。恢复和采用时重新核对这些原件；损坏或丢失会明确报错并保留拒绝事件，不继续使用笔记。这里只检查指定文件及其清单身份，不声称已核验清单里所有其它文件。文件匹配不代表程序正确、实验有效或结论成立。

快照来自Control数据库同级`snapshots/`，实验原件路径来自同项目/运行的受管执行记录，调用者不能提供宿主绝对路径。适配器只承担来源解析，运行时独立核心仍不读取这些路径。原文读取服务、代码对象生存状态和科学语义保真尚待接入。

### 按需读取原文

`research_note`工具的`source_read`接收`revision`（可省略以使用现行笔记）、`artifact_reference`、`offset`和`limit`。只能读取自己的笔记已经引用且仍与绑定匹配的原件，每页重新核查项目/运行与指纹。笔记因控制版本变化而不再适合作为当前记忆时，历史原件仍可在当前成员权限下查询；这不会重新采用旧笔记。

位置按Unicode字符计算，默认每页8000字符，上限16000，目的是限制一次工具返回占用的上下文。多字节中文不会因分页被切坏。返回`offset/end_offset/next_offset/has_more/partial`以及原件字节数、完整原件指纹。根据`has_more`继续，分页片段不能直接冒充完整JSON或完整证据。范围超限会返回详细限制与恢复办法，原件不截断、不暂停研究。非UTF-8文件明确拒绝，不用替换字符掩盖内容变化。

请求不接受任意宿主路径，也不能以分页绕过其它成员的笔记权限或独立评价材料隔离。读取位置和来源指纹写入Control事件，完整工具结果沿用交流记录保留。分页读取是原文查询，仍不是语义压缩或Runtime安装。

## 摘要请求与保真检查

`summary.prepare(materials, obligations, role=..., max_bytes=...)`冻结受授权材料、版本指纹与调用方要求保留的事实，产生带指纹的运行时独立请求。`obligations`为`[{id, value, sources:[材料ID]}]`，值暂限字符串、布尔和整数；它不是核心自动推断的科学真相。准备请求会按完整UTF-8序列化大小核对调用方给定容量，放不下返回deferred，不静默删材料。

摘要候选为`{request_sha256, text, claims:[{id,value,citations}]}`。`summary.check`检查请求绑定、漏项、重复项、额外项、字段值及引用；问题返回rejected。字段匹配仅返回pending_semantic_review，eligible_for_application始终为false。自然语言可能与字段矛盾，程序检查不证明正文含义正确，也不能证明调用方没有漏列重要反证。

接口自身不调用模型，Runtime侧已完成首个真实生成/分开会话复核试验，但尚未接笔记自动采用路径；现有手写笔记工具仍是研究员自己负责的工作笔记。没有自动压缩的完成声明。测试含真实冻结报告的七项离线标注与受控错误，标注只用于验收，不会预设研究员未来的科学流程。

## 分开会话复核协议与真实试验

`summary_review.prepare_review/assess`绑定具体候选、原始材料和复核引文，要求生成与复核使用不同的受管会话标识。拒绝未知意见、伪造引文和候选错配。accept只记录模型意见为reviewed，不自动允许应用，不证明复核结论正确。

首个真实试验已完成两轮中文摘要与分开会话复核，并成功拒绝固定字段正确但正文夸大的反例，见`docs/validation/RESEARCH-CONTEXT-MODEL.md`。它使用同一订阅模型，不具备外部科学评价或环境独立性。Runtime侧试验器在integrations/runtimes中，核心不导入pi或SDK。
