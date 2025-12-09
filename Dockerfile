# 1. Берем легкий образ Python
FROM python:3.10-slim

# 2. Устанавливаем системные утилиты (wget, curl)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    ca-certificates \
    gnupg \
    libxss1 \
    libappindicator1 \
    liblibcrtf0 \
    && rm -rf /var/lib/apt/lists/*

# 3. Скачиваем и устанавливаем Chrome НАПРЯМУЮ (.deb файл)
# Это обходит проблему с ключами и репозиториями
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb

# 4. Настраиваем рабочую папку
WORKDIR /app

# 5. Копируем файлы и ставим библиотеки Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# 6. Запускаем
CMD ["python", "main.py"]
