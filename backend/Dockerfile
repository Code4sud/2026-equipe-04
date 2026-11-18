FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=wsgi.py

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Les droits viennent de la machine qui construit : l'utilisateur non root doit pouvoir tout lire.
RUN useradd --system --uid 10001 --no-create-home app \
    && chmod -R a+rX /app \
    && chmod +x entrypoint.sh

USER app
EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "wsgi:app", \
     "--bind", "0.0.0.0:5000", \
     "--worker-class", "gthread", \
     "--workers", "2", \
     "--threads", "8", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--no-control-socket"]
