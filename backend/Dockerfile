# Stage 1: Builder — install dependencies
FROM python:3.12-slim AS builder

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app

COPY --chown=user:user requirements.lock.txt .
RUN pip install --no-cache-dir --user -r requirements.lock.txt

# Stage 2: Runtime — slim production image
FROM python:3.12-slim AS runtime

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860 \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

COPY --chown=user:user --from=builder /home/user/.local /home/user/.local
COPY --chown=user:user . /home/user/app

RUN mkdir -p /home/user/app/data && chown -R user:user /home/user/app

USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]

