% Frozen case118 reference. Only environment variables below configure execution.
addpath('/opt/matpower');
install_matpower(1, 0, 0);
max_it = str2double(getenv('ASR_MAX_IT'));
if ~isfinite(max_it) || max_it < 0 || max_it ~= fix(max_it)
    error('ASR_MAX_IT must be a nonnegative integer');
end
mpc = loadcase('case118');
% Flat start, preserving the single reference angle and all physical inputs.
ref_angle = mpc.bus(mpc.bus(:,2) == 3, 9);
if numel(ref_angle) ~= 1, error('one reference bus required'); end
mpc.bus(:,8) = 1;
mpc.bus(:,9) = ref_angle;
inp = struct('baseMVA', mpc.baseMVA, 'bus', mpc.bus, 'gen', mpc.gen, 'branch', mpc.branch);
fid = fopen('/output/input.json', 'w');
fputs(fid, jsonencode(inp)); fclose(fid);
opt = mpoption('pf.alg', 'NR', 'pf.tol', 1e-10, 'pf.nr.max_it', max_it, ...
    'pf.enforce_q_lims', 0, 'exp.use_legacy_core', 1, 'verbose', 1, 'out.all', 0);
[result, success] = runpf(mpc, opt);
out = struct('baseMVA', result.baseMVA, 'bus', result.bus, 'gen', result.gen, 'branch', result.branch);
fid = fopen('/output/solution.json', 'w');
fputs(fid, jsonencode(out)); fclose(fid);
meta = struct('solver_success', logical(success), 'iterations', result.iterations, ...
    'solver_elapsed_seconds', result.et, 'matpower_version', mpver('all'), ...
    'octave_version', version, 'policy', 'fixed-pv-pq-single-slack/1', ...
    'initialization', 'flat', 'max_iterations', max_it, 'pf_tolerance_pu', 1e-10);
fid = fopen('/output/solver.json', 'w');
fputs(fid, jsonencode(meta)); fclose(fid);
