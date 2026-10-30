FROM python:3.11-slim
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

# OpenSSL 3 legacy provider engedélyezése az MD4 / NTLM támogatáshoz
RUN printf "[openssl_init]\nproviders = provider_sect\n\n[provider_sect]\ndefault = default_sect\nlegacy = legacy_sect\n\n[default_sect]\nactivate = 1\n\n[legacy_sect]\nactivate = 1\n" >> /etc/ssl/openssl.cnf && \
    sed -i 's/^openssl_conf = .*/openssl_conf = openssl_init/' /etc/ssl/openssl.cnf || \
    sed -i '1s/^/openssl_conf = openssl_init\n/' /etc/ssl/openssl.cnf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
