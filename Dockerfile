# FROM tiangolo/uvicorn-gunicorn-fastapi:latest
FROM python:3.11

WORKDIR /app

COPY requirements.txt requirements.txt

# RUN pip install -r requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . ./app

EXPOSE 8722

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8722", "app.main:app"]