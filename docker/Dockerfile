ARG NUMERICAL_BASE=asr-numerical-base:dev
FROM ${NUMERICAL_BASE}
COPY .cache/matpower-8.1.container.tar.gz /tmp/matpower.tar.gz
RUN echo '5f08ced1a32e8d0d658ee54b73678c7364a899bae479882f2bc419e91442b69f  /tmp/matpower.tar.gz' | sha256sum -c - \
 && mkdir /opt/matpower && tar -xzf /tmp/matpower.tar.gz -C /opt/matpower --strip-components=1 \
 && rm /tmp/matpower.tar.gz
COPY scripts/reference_pf.m /opt/asr/reference_pf.m
WORKDIR /tmp
ENTRYPOINT ["octave", "--no-gui", "--quiet", "/opt/asr/reference_pf.m"]
