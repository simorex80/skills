# Reviewed Python 3.11 slim image; pinned to immutable Docker Hub index digest.
FROM python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

COPY constraints/ci-py3.11.txt /tmp/constraints.txt
RUN python -m pip install --no-cache-dir -c /tmp/constraints.txt \
    'markitdown[pdf,docx,pptx,xlsx]==0.1.9' && \
    python -m pip check

COPY scripts/convert.py /opt/markitdown/convert.py
USER 65534:65534
WORKDIR /work
ENTRYPOINT ["python", "-B", "/opt/markitdown/convert.py"]
