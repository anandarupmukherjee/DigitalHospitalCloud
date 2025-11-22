FROM python:3.9-slim

# Install docker CLI and git
RUN apt-get update && apt-get install -y docker.io git curl && rm -rf /var/lib/apt/lists/*

# Install Docker Compose plugin manually
RUN mkdir -p /usr/libexec/docker/cli-plugins && \
    curl -SL https://github.com/docker/compose/releases/download/v2.29.1/docker-compose-linux-x86_64 -o /usr/libexec/docker/cli-plugins/docker-compose && \
    chmod +x /usr/libexec/docker/cli-plugins/docker-compose

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "300", "app:app"]
