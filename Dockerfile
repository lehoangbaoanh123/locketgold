FROM python:3.10-slim

# Cài Chrome
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    fonts-liberation \
    libnss3 libatk-bridge2.0-0 libxss1 libasound2 libgbm1 \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable

# Cài ChromeDriver (auto version gần đúng)
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver

# Setup app
WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "se.py"]
