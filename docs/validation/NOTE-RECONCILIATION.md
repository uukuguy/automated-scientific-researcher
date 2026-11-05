# 未登记草稿核对验收

已实现控制端显式核对，报告笔记文件与原保存/采纳回执是否对应，保留缺失、损坏、临时文件和不安全文件的可查状态。报告写入现有Control请求与事件，并随交流归档导出。不补造保存回执、不采纳、不删除文件、不创建笔记目录。

真实子进程使用临时Control库，在`NoteStore.save`完成后、`_commit_operation`登记保存前直接`os._exit(73)`。父进程确认退出码73，核对发现完整`unregistered`版本；本人history_read读取到原文，当前采纳仍为空。该测试没有模型或科学执行，不能外推为断电持久性保证。

10项专项检查通过，另扩展现有交流归档检查覆盖核对报告。完整检查：`uv run --extra aar python -m unittest discover -s tests -v`，651项，25环境跳过，其余通过。日志和源码指纹在`NOTE-RECONCILIATION.json`。

调用：`service.audit_research_notes(token, project, run, subject=..., idempotency_key=...)`。human/supervisor权限，指定成员当前必须有效。文件/账本在核对期间变化会产生deferred回执；权限失效拒绝提交。读取在写事务外，短事务只重新核对记录与文件/目录元数据。

结果中的`integrity`只表示文件自身完整性，`registration`表示原回执是否存在，`current_accepted`表示观察时采纳指针；三者不能混为科学正确性。`sources_current_verified=false`、`current_context_authorized=false`和`historical_receipt=true`明确说明恢复边界。幂等重放仍是历史观察，需要再次检查时用新键。

未登记可能来自崩溃或失败，不据文件存在判断原因。完整版本可由本人使用原history_read核查；修订和采纳继续受原来源、父版本及权限规则约束。临时文件原件留在受限目录，其正文不由既有笔记JSON导出器自动导出；报告只列出其存在。大量文件的清单/元数据仍占内存；尚无跨文件系统/数据库原子恢复、自动修复或断电保证。
