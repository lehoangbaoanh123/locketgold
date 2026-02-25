FROM python:3.10-slim

# Cài Chromium + driver + thư viện cần thiết cho Selenium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libxss1 \
    libasound2 \
    libgbm1 \
    libgtk-3-0 \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Khai báo path cho Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Tắt sandbox để chạy trên Render
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# Cài thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Quan trọng để Render detect
EXPOSE 10000

# Chạy bot
CMD ["python", "bot.py"]
