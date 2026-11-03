% Trusted transport wrapper; candidate claims are never evaluator decisions.
addpath('/opt/matpower');
install_matpower(1, 0, 0);
mpc = loadcase('case118');
ref_angle = mpc.bus(mpc.bus(:, 2) == 3, 9);
if numel(ref_angle) ~= 1, error('one reference bus required'); end
mpc.bus(:, 8) = 1;
mpc.bus(:, 9) = ref_angle;
addpath('/candidate');
result = candidate(mpc);
solution = struct('baseMVA', result.baseMVA, 'bus', result.bus, ...
                 'gen', result.gen, 'branch', result.branch);
claims = struct();
for name = {'solver_success', 'iterations', 'method'}
    if isfield(result, name{1}), claims.(name{1}) = result.(name{1}); end
end
payload = struct('solution', solution, 'claims', claims);
fprintf('\nASR_CANDIDATE_RESULT_V1:%s\n', jsonencode(payload));
fflush(stdout);
