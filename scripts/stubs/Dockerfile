# Stub image for orchestrators whose source code is not in this branch
# (rf004_create_offer_app and rf005_query_post_app are developed in
# separate branches). It serves the liveness/readiness ping endpoints so
# the full k8s/ deployment and the Ingress routing can be verified locally
# without the real application code.
#
# Build (once per tag):
#   docker build -t rf004-create-offer-app:v0.0.0 scripts/stubs
#   docker build -t rf005-query-post-app:v0.0.0 scripts/stubs

FROM python:3.11.11-slim

WORKDIR /app
COPY stub_server.py .

USER 1000
EXPOSE 8000

CMD ["python", "stub_server.py"]
