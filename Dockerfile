FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

