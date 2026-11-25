# Deploy to namespace bcs
1. `docker login dev-harbor.systems.gov.bt -u bcs-user` (password from GovTech; never commit it)
2. Build and push (use `--platform linux/amd64` on Apple Silicon):
   `docker build --platform linux/amd64 -f backend/Dockerfile.prod -t dev-harbor.systems.gov.bt/bcs/cms-backend:v1 backend && docker push ...`
   `docker build --platform linux/amd64 -f frontend/Dockerfile.prod -t dev-harbor.systems.gov.bt/bcs/cms-frontend:v1 frontend && docker push ...`
3. Create the secrets with `kubectl create secret ... -n bcs`: `harbor-secret` (registry login) and `cms-secrets` with
   - always: POSTGRES_PASSWORD, DJANGO_SECRET_KEY, **FIELD_ENCRYPTION_KEY** (see docs/ENCRYPTION.md: back it up, the encrypted data cannot be read without it),
     BICMA_ADMIN_EMAIL, BICMA_ADMIN_PASSWORD, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL
   - Bhutan NDI sign-in: **NDI_API_CLIENT_ID, NDI_API_CLIENT_SECRET, NDI_NATS_SEED_KEY** (the NDI addresses are in 00-config.yaml, staging values: change them for production)
   - citizen registry (BCRS): BCRS_CLIENT_ID, BCRS_CLIENT_SECRET (or BCRS_API_TOKEN)
   - optional: ZEST_API_TOKEN, GITHUB_TOKEN, SONARQUBE_TOKEN, ZAP_API_KEY (the Security scan and Solve button can also take these in Settings)

   Example: `kubectl create secret generic cms-secrets -n bcs --from-literal=POSTGRES_PASSWORD=... --from-literal=FIELD_ENCRYPTION_KEY=... --from-literal=NDI_API_CLIENT_ID=... --from-literal=NDI_API_CLIENT_SECRET=... --from-literal=NDI_NATS_SEED_KEY=...` (add the other names the same way; never commit the values).
   Network: the backend pod must reach NDI (HTTPS 443 to the NDI_API_HOST and NDI_API_AUTH_ENDPOINT hosts, and NATS TCP 4222 to NDI_NATS_HOST) and the citizen registry. Ask GovTech to allow this egress if a NetworkPolicy or firewall blocks it.
4. `kubectl apply -f k8s/` (files: 00-config, 10-database, 20-backend, 30-frontend, 40-ingress, 50-scheduler, 60-clamav; each can also be applied on its own).
   The ClamAV pod needs about 2 GB and a few minutes on first start. When it is Ready, change CLAMAV_REQUIRED to "1" in 00-config.yaml and re-apply so uploads are refused if the scanner is down.
   Keep cms-backend at one replica: it holds the NDI NATS connection.
5. Background jobs (API checks, email retries, SLA alerts, security scans, log cleanup, shrinking pictures of resolved complaints) run in the `cms-scheduler` pod (50-scheduler.yaml); no CronJobs are needed.
