# 1. Берем базовый образ Python
FROM python:3.10-slim

# 2. Устанавливаем зависимости для установки Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Скачиваем и устанавливаем Google Chrome (Stable)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# 4. Создаем рабочую папку
WORKDIR /app

# 5. Копируем файлы проекта
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

# 6. Запускаем бота
CMD ["python", "main.py"]