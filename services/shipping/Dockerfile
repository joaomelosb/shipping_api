FROM python:3.10-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn[standard]

COPY app.py .
EXPOSE 4040
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "4040", "--workers", "1", "--timeout-keep-alive", "120"]