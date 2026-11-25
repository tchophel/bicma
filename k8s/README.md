# Deploy to namespace bcs
1. `docker login dev-harbor.systems.gov.bt -u bcs-user` (password from GovTech; never commit it)
2. Build and push (use `--platform linux/amd64` on Apple Silicon):
   `docker build --platform linux/amd64 -f backend/Dockerfile.prod -t dev-harbor.systems.gov.bt/bcs/cms-backend:v1 backend && docker push ...`
   `docker build --platform linux/amd64 -f frontend/Dockerfile.prod -t dev-harbor.systems.gov.bt/bcs/cms-frontend:v1 frontend && docker push ...`
3. Create secrets (`harbor-secret`, and `cms-secrets` with POSTGRES_PASSWORD, DJANGO_SECRET_KEY, FIELD_ENCRYPTION_KEY (see docs/ENCRYPTION.md), BICMA_ADMIN_EMAIL,
   BICMA_ADMIN_PASSWORD, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL) with `kubectl create secret ... -n bcs`.
4. `kubectl apply -f k8s/` (files: 00-config, 10-database, 20-backend, 30-frontend, 40-ingress; each can also be applied on its own)
5. Cron jobs still needed: `sla_alerts` hourly, `retry_failed_emails` every 5 minutes (CronJob using the backend image).
