/** Conservative guard for pi native file tools. No shell or external coding exec. */
import fs from 'node:fs';
import path from 'node:path';
export function workspacePath(root, input, tool) {
  if (typeof input !== 'string' || !input || input.startsWith('~') || input.startsWith('@') || /[^\x20-\x7e]/.test(input)) throw new Error('workspace_path_required');
  root=fs.realpathSync(root);
  const resolved=path.resolve(root,input);
  const relative=path.relative(root,resolved);
  if (relative==='..' || relative.startsWith('../') || path.isAbsolute(relative) || relative.split(path.sep).some(x=>x==='.git'||x==='.pi')) throw new Error('workspace_path_escape');
  let current=root;
  for(const component of relative.split(path.sep).filter(Boolean)) {
    current=path.join(current,component);
    try { if(fs.lstatSync(current).isSymbolicLink()) throw new Error('workspace_symlink_forbidden'); }
    catch(error) { if(error.code!=='ENOENT') throw error; }
  }
  if(tool!=='write' && !fs.existsSync(resolved)) throw new Error('workspace_path_missing');
  return resolved;
}
