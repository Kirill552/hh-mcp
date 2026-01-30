FROM python:3.12-slim

WORKDIR /app

# Системные зависимости для Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем hh-applicant-tool
COPY hh-applicant-tool ./hh-applicant-tool
RUN pip install --no-cache-dir -e './hh-applicant-tool[playwright]'
RUN playwright install chromium

# Копируем MCP сервер
COPY hh_mcp_server.py .

# MCP работает через stdio
CMD ["python", "hh_mcp_server.py"]
