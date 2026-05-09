# Sử dụng Python bản chính thức
FROM python:3.10-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements vào và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Mở cổng 8080 cho Flask
EXPOSE 8080

# Lệnh khởi chạy bot
CMD ["python", "bot.py"]
