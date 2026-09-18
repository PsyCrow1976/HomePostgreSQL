# Same Postgres major as the db image so dump/restore SQL matches.
FROM postgres:16-alpine

RUN apk add --no-cache python3 py3-pip

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY app.py .

EXPOSE 8000
CMD ["python3", "app.py"]
