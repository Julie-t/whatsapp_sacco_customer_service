#!/usr/bin/env bash
# ==============================================================================
# GCP Production Deployment Automation Script
# Service: WhatsApp SACCO Customer Service & AI Member Companion
# Target: Google Cloud Run (FastAPI), Cloud SQL, Compute Engine (Qdrant)
# ==============================================================================

set -euo pipefail

# Color formatting for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================================================${NC}"
echo -e "${BLUE}  Deploying WhatsApp SACCO AI Companion to Google Cloud Platform   ${NC}"
echo -e "${BLUE}===================================================================${NC}"

# 1. Configuration & Default Variables
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
    echo -e "${RED}Error: GCP PROJECT_ID is not set. Please run 'gcloud config set project <PROJECT_ID>' or export GCP_PROJECT_ID.${NC}"
    exit 1
fi

REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-whatsapp-sacco-api}"
REPO_NAME="${REPO_NAME:-sacco-docker-repo}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
VPC_CONNECTOR="${VPC_CONNECTOR:-sacco-vpc-connector}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-${PROJECT_ID}:${REGION}:sacco-postgres-prod}"

FULL_IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

echo -e "${YELLOW}Deployment Parameters:${NC}"
echo "  Project ID:        ${PROJECT_ID}"
echo "  Region:            ${REGION}"
echo "  Service Name:      ${SERVICE_NAME}"
echo "  Artifact Registry: ${REPO_NAME}"
echo "  Image Target:      ${FULL_IMAGE_NAME}"
echo "  Min Instances:     1 (Ensures zero cold-start for Twilio webhooks)"
echo "  Memory / CPU:      2GiB / 1 vCPU"
echo ""

# 2. Enable Required GCP APIs
echo -e "${BLUE}[1/5] Enabling required GCP service APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    compute.googleapis.com \
    sqladmin.googleapis.com \
    vpcaccess.googleapis.com \
    --project="${PROJECT_ID}"

# 3. Create Artifact Registry Repository if not exists
echo -e "${BLUE}[2/5] Ensuring Artifact Registry Docker repository exists...${NC}"
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Creating repository '${REPO_NAME}' in '${REGION}'..."
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Docker repository for WhatsApp SACCO microservices" \
        --project="${PROJECT_ID}"
else
    echo "Repository '${REPO_NAME}' already exists."
fi

# 4. Build and Push Container Image via Cloud Build
echo -e "${BLUE}[3/5] Building Docker container via Google Cloud Build...${NC}"
gcloud builds submit \
    --tag="${FULL_IMAGE_NAME}" \
    --project="${PROJECT_ID}"

# 5. Build Cloud Run Deployment Command
echo -e "${BLUE}[4/5] Deploying container image to Google Cloud Run...${NC}"

DEPLOY_FLAGS=(
    "--image=${FULL_IMAGE_NAME}"
    "--platform=managed"
    "--region=${REGION}"
    "--project=${PROJECT_ID}"
    "--allow-unauthenticated"
    "--min-instances=1"
    "--max-instances=10"
    "--memory=2Gi"
    "--cpu=1"
    "--timeout=60s"
    "--concurrency=80"
)

# Optional VPC Access connector for private Qdrant access
if gcloud compute networks vpc-access connectors describe "${VPC_CONNECTOR}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Attaching Serverless VPC Access connector: ${VPC_CONNECTOR}"
    DEPLOY_FLAGS+=("--vpc-connector=${VPC_CONNECTOR}")
else
    echo -e "${YELLOW}Notice: VPC connector '${VPC_CONNECTOR}' not found. Deploying without VPC connector.${NC}"
fi

# Optional Cloud SQL instance attachment
if gcloud sql instances describe "$(echo "${CLOUDSQL_INSTANCE}" | awk -F: '{print $NF}')" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Attaching Cloud SQL instance: ${CLOUDSQL_INSTANCE}"
    DEPLOY_FLAGS+=("--set-cloudsql-instances=${CLOUDSQL_INSTANCE}")
fi

# Bind Secret Manager secrets if they exist, otherwise keep environment configs
SECRETS_LIST=""
for secret in GROQ_API_KEY TWILIO_AUTH_TOKEN DATABASE_URL; do
    if gcloud secrets describe "${secret}" --project="${PROJECT_ID}" &>/dev/null; then
        if [[ -z "${SECRETS_LIST}" ]]; then
            SECRETS_LIST="${secret}=${secret}:latest"
        else
            SECRETS_LIST="${SECRETS_LIST},${secret}=${secret}:latest"
        fi
    fi
done

if [[ -n "${SECRETS_LIST}" ]]; then
    echo "Binding secrets from Secret Manager: ${SECRETS_LIST}"
    DEPLOY_FLAGS+=("--set-secrets=${SECRETS_LIST}")
else
    echo -e "${YELLOW}Notice: No matching secrets in Secret Manager found yet. Service will use default/injected env vars.${NC}"
fi

# Set base runtime environment variables
DEPLOY_FLAGS+=(
    "--set-env-vars=APP_ENV=production,GROQ_AUDIO_MODEL=whisper-large-v3-turbo,VOICE_ENABLED=true,MEMBER_DATA_DEMO_MODE=false"
)

# Execute Cloud Run deployment
gcloud run deploy "${SERVICE_NAME}" "${DEPLOY_FLAGS[@]}"

# 6. Output Webhook URL and Twilio Instructions
echo ""
echo -e "${GREEN}===================================================================${NC}"
echo -e "${GREEN}  DEPLOYMENT SUCCESSFUL!                                           ${NC}"
echo -e "${GREEN}===================================================================${NC}"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform=managed --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')
WEBHOOK_URL="${SERVICE_URL}/webhooks/whatsapp"
DASHBOARD_URL="${SERVICE_URL}/dashboard"

echo -e "Service Base URL:   ${BLUE}${SERVICE_URL}${NC}"
echo -e "Live Dashboard:     ${BLUE}${DASHBOARD_URL}${NC}"
echo -e "Health Check:       ${BLUE}${SERVICE_URL}/health${NC}"
echo ""
echo -e "${YELLOW}Twilio WhatsApp Sandbox Setup Instructions:${NC}"
echo "1. Go to Twilio Console: https://console.twilio.com/"
echo "2. Navigate to: Messaging -> Settings -> WhatsApp sandbox settings"
echo "3. Configure 'WHEN A MESSAGE COMES IN':"
echo -e "   - URL:     ${GREEN}${WEBHOOK_URL}${NC}"
echo "   - Method:  HTTP POST"
echo "4. Click 'Save' to apply zero-downtime routing to Cloud Run."
echo -e "${GREEN}===================================================================${NC}"
