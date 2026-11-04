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
