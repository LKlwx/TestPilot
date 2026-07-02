FROM python:3.14-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

RUN addgroup --system app && adduser --system --group app

COPY --chown=app:app . .

EXPOSE 5000

ENV FLASK_APP=run.py
ENV FLASK_DEBUG=0

VOLUME ["/app/instance"]

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

USER app

CMD ["python", "run.py"]
