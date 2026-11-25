FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir --require-hashes -r requirements.lock
COPY manage.py ./
COPY accounts accounts
COPY complaints complaints
COPY config config
COPY core core
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
