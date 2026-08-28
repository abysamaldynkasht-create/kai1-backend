FROM ollama/ollama:latest

# ضبط البيئة وتفادي التوقف
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# تثبيت Python ومكتبات التشغيل
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تثبيت متطلبات بايثون - باستخدام --break-system-packages للتوافق
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# نسخ ملفات المشروع
COPY main.py Modelfile entrypoint.sh ./

# منح صلاحية التنفيذ لملف التشغيل
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

