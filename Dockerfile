# Usa uma imagem Python otimizada e leve
FROM python:3.11-slim-bullseye

# Previne a criação de arquivos .pyc e força o log em tempo real (sem buffer)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código fonte do bot
COPY . .

# Executa o motor em tempo real
CMD ["python", "realtime_main.py"]
