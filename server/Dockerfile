FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies for PyNaCl (libsodium)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim

# Runtime dependency for libsodium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsodium23 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -r -u 1001 -s /bin/false zkpm

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN chown -R zkpm:zkpm /app

USER zkpm

EXPOSE 8080

ENTRYPOINT ["python", "main.py"]
