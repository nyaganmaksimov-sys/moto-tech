FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install --no-cache-dir -r /srv/backend/requirements.txt
COPY backend /srv/backend
RUN useradd --system --uid 10001 --create-home mototech && mkdir -p /private-photos && chown mototech:mototech /private-photos
USER mototech
EXPOSE 10000
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "10000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
