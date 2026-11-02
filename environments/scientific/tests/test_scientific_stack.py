"""Exercise local scientific storage, sparse numerics, plotting and notebook kernel."""
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve
import pytest


def test_sparse_analysis_graph_and_parquet_plot_roundtrip(tmp_path):
    graph = nx.path_graph(3)
    assert nx.is_connected(graph)
    matrix = csc_matrix([[3., 1.], [1., 2.]])
    solved = spsolve(matrix, [9., 8.])
    assert np.allclose(solved, [2., 3.])
    frame = pd.DataFrame({'bus': [1, 2], 'vm_pu': solved})
    parquet = tmp_path / 'result.parquet'
    frame.to_parquet(parquet, engine='pyarrow', index=False)
    pd.testing.assert_frame_equal(frame, pd.read_parquet(parquet))
    fig, ax = plt.subplots()
    ax.plot(frame.bus, frame.vm_pu)
    output = tmp_path / 'voltage.png'
    fig.savefig(output)
    plt.close(fig)
    assert plt.imread(output).shape[0] > 100


def test_notebook_kernel_uses_this_isolated_python(tmp_path):
    pytest.importorskip('ipykernel')
    client_module = pytest.importorskip('jupyter_client')
    manager = client_module.KernelManager(kernel_name='python3')
    # Override only this in-memory kernelspec; do not install a global kernel.
    manager.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
    manager.start_kernel(cwd=str(tmp_path))
    client = manager.client()
    client.start_channels()
    try:
        client.wait_for_ready(timeout=20)
        message_id = client.execute('import sys; import pandapower; print(sys.executable)')
        output = ''
        while True:
            message = client.get_iopub_msg(timeout=20)
            if message['parent_header'].get('msg_id') != message_id:
                continue
            if message['msg_type'] == 'error':
                pytest.fail(str(message['content']))
            if message['msg_type'] == 'stream':
                output += message['content']['text']
            if message['msg_type'] == 'status' and message['content']['execution_state'] == 'idle':
                break
        assert str(Path(sys.executable)) in output
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)
