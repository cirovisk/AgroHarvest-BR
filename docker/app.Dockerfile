FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for psycopg2 and other tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY docker/requirements.txt docker/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Cria um grupo e um usuário não-root (UID/GID 1000 para alinhar com o host em volumes montados)
RUN groupadd -g 1000 nonroot && \
    useradd -u 1000 -g nonroot -d /app -s /sbin/nologin nonroot

# Copy source code (will be overwritten by volume in dev, but good for build)
COPY . .

# Garante permissões adequadas no diretório de trabalho
RUN mkdir -p /app/data && chown -R nonroot:nonroot /app

# Environment variable defaults
ENV POSTGRES_HOST=postgres
ENV POSTGRES_PORT=5432
ENV POSTGRES_DB=cultivares_db
ENV PYTHONPATH=/app/src

USER nonroot

# Default command can be empty or keep the notebook one
CMD ["python", "src/main.py"]
