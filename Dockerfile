# 1. Utiliser une image Python officielle légère
FROM python:3.10-slim

# 2. Définir le dossier de travail à l'intérieur de la "boîte"
WORKDIR /app

# 3. Copier les dépendances en premier (pour optimiser le cache Docker)
COPY requirements.txt .

# 4. Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copier tout le reste de ton projet dans la boîte
COPY . .

# 6. Exposer le port 80 (attendu par Cloud Run, App Runner, Scaleway, etc.)
EXPOSE 80

# 7. La commande de démarrage (identique à ton Procfile Render)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:80", "--workers", "1", "--threads", "4", "--timeout", "60"]