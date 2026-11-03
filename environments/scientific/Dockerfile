# Build with an isolated context containing only this file and requirements.txt.
# requirements.txt must be uv export --locked --no-dev --no-emit-project output.
# Local-only base: build script verifies its image ID before and after building.
FROM asr-matpower:8.1
COPY requirements.txt /opt/asr/requirements.txt
RUN python3 -m pip install --no-cache-dir --require-hashes -r /opt/asr/requirements.txt
COPY source /opt/asr/source
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/matplotlib
ENV PYTHONPATH=/opt/asr/source PYTHONDONTWRITEBYTECODE=1
WORKDIR /tmp
ENTRYPOINT ["python3"]
