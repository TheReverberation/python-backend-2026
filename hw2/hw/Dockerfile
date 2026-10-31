FROM python:3.14-slim

WORKDIR ./

COPY . .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["uvicorn", "shop_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
