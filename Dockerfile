FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DATA_DIR=/data

WORKDIR /app

RUN apk add --no-cache ca-certificates su-exec \
    && addgroup -S app \
    && adduser -S -G app app \
    && mkdir -p /data \
    && chown -R app:app /data

COPY --chown=app:app server.py ./
COPY --chown=app:app public ./public
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "server.py"]
