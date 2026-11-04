/** Read-only SDK projection helper. No Pi agent, auth client or model is started. */
import {pathToFileURL} from 'node:url';
let input='';
for await (const chunk of process.stdin) input+=chunk;
const {entries,leafId}=JSON.parse(input);
const {buildSessionProjection}=await import(pathToFileURL(process.argv[2]).href);
const result=buildSessionProjection(entries,leafId);
process.stdout.write(JSON.stringify({entries:result.entries.map(e=>({source_entry_id:e.sourceEntry.id,messages:e.messages}))}));
