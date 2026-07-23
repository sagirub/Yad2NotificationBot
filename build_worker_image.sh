#!/usr/bin/env bash
#
# Build and push the Yad2 scanner WORKER container image (CloakBrowser + Chromium)
# to ECR, then print the image URI to use with `serverless deploy`.
#
# Why manual? Serverless-managed image builds stall behind the corporate proxy's
# TLS interception. Building/pushing manually (with VPN off) is reliable — proven
# with the cloak_lambda_test image.
#
# Usage:
#   ./build_worker_image.sh [tag]
#   # then:
#   WORKER_IMAGE_URI=<printed-uri> TELEGRAM_BOT_TOKEN=... ADMIN_CHAT_ID=... \
#     ADMIN_BOT_TOKEN=... npx serverless deploy --stage <stage> --region eu-west-2
set -euo pipefail

REGION="${AWS_REGION:-eu-west-2}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REPO="yad2-worker"
TAG="${1:-latest}"
URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO}"

echo "== Ensuring ECR repo ${REPO} exists in ${REGION} =="
aws ecr create-repository --repository-name "${REPO}" --region "${REGION}" \
    >/dev/null 2>&1 || echo "  (repo already exists)"

echo "== Docker login to ECR =="
aws ecr get-login-password --region "${REGION}" \
    | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "== Building image (linux/amd64, docker manifest for Lambda) =="
# --provenance=false + --output type=docker => plain Docker v2 manifest that
# Lambda accepts (avoids the OCI/attestation manifest error).
docker build \
    --platform linux/amd64 \
    --provenance=false \
    --output type=docker \
    -f Dockerfile.worker \
    -t "${REPO}:${TAG}" \
    .

echo "== Tagging & pushing to ECR =="
docker tag "${REPO}:${TAG}" "${URI}:${TAG}"
docker push "${URI}:${TAG}"

echo ""
echo "==================================================================="
echo "WORKER_IMAGE_URI=${URI}:${TAG}"
echo "==================================================================="
