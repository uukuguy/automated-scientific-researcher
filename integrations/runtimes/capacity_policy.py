"""Host-owned capacity configuration. Loading never grants scientific budget."""
import hashlib
import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2]/'configs/capacity-policy.json'
NAMES = frozenset(('context_boundary_ms', 'projection_seconds', 'journal_bytes',
                   'summary_bytes', 'review_bytes', 'pi_message_bytes',
                   'pi_buffer_bytes', 'pi_pending_records', 'pi_records', 'async_log_warning_bytes', 'observation_drain_seconds', 'async_log_drain_seconds', 'observation_recovery_record_bytes', 'observation_recovery_records', 'observation_recovery_snapshot_bytes'))


def load_policy(path=None):
    value = json.loads(Path(path or DEFAULT_PATH).read_text())
    if (type(value) is not dict or set(value) != {'schema', 'revision', 'limits'} or
            value['schema'] != 'asr-capacity-policy/1' or
            type(value['revision']) is not int or value['revision'] < 1 or
            type(value['limits']) is not dict or set(value['limits']) != NAMES):
        raise ValueError('invalid_capacity_policy')
    for name, limit in value['limits'].items():
        if (type(limit) is not dict or
                set(limit) != {'value','unit','scope','purpose','adequacy','recovery'} or
                type(limit['value']) is not int or limit['value'] < 1 or
                any(type(limit[k]) is not str or not limit[k].strip()
                    for k in ('unit','scope','purpose','adequacy','recovery'))):
            raise ValueError('invalid_capacity_limit')
        expected_unit = 'ms' if name == 'context_boundary_ms' else 'seconds' if name in ('projection_seconds', 'observation_drain_seconds', 'async_log_drain_seconds') else 'records' if name in ('pi_pending_records', 'pi_records', 'observation_recovery_records') else 'bytes'
        if limit['unit'] != expected_unit:
            raise ValueError('invalid_capacity_unit')
    if value['limits']['pi_buffer_bytes']['value'] < value['limits']['pi_message_bytes']['value']:
        raise ValueError('capacity_buffer_smaller_than_message')
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return {**value, 'sha256': hashlib.sha256(encoded).hexdigest()}
