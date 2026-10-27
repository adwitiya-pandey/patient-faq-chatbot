#!/usr/bin/env bash
# Deploy patient-faq-chatbot to Azure Container Apps
# Ensures zero-cost idle operation: min-replicas=0, logs-destination=none.
set -euo pipefail

# Configuration with sensible defaults
RG="${RG:-faq-bot-rg}"
LOCATION="${LOCATION:-centralindia}"
ENV_NAME="${ENV_NAME:-faq-bot-env}"
APP_NAME="${APP_NAME:-faq-bot-app}"
IMAGE="${IMAGE:-ghcr.io/adwitiya-pandey/patient-faq-chatbot:latest}"
PORT="8501"

echo "=== Patient FAQ Chatbot: Azure Container Apps Deployment ==="
echo "Resource Group:       $RG"
echo "Location:             $LOCATION"
echo "Environment Name:     $ENV_NAME"
echo "App Name:             $APP_NAME"
echo "Container Image:      $IMAGE"
echo "Target Port:          $PORT"
echo "Min / Max Replicas:   0 / 1 (scale-to-zero enabled)"
echo "CPU / Memory:         0.5 / 1.0Gi"
echo "Log Analytics:        none (--logs-destination none)"
echo "==========================================================="

# Check Azure CLI
command -v az >/dev/null 2>&1 || {
  echo "ERROR: Azure CLI (az) is not installed." >&2
  echo "Please install it: https://learn.microsoft.com/cli/azure/install-azure-cli" >&2
  exit 1
}

# Check Azure authentication
if ! az account show >/dev/null 2>&1; then
  echo "ERROR: Not logged into Azure CLI." >&2
  echo "Please log in: az login --use-device-code" >&2
  exit 1
fi

SUBSCRIPTION_NAME=$(az account show --query "name" -o tsv)
echo "Active Subscription:  $SUBSCRIPTION_NAME"

# Check GEMINI_API_KEY without echoing it
if [ -z "${GEMINI_API_KEY:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ENV_FILE="$SCRIPT_DIR/../../.env"
  if [ -f "$ENV_FILE" ]; then
    echo "Reading GEMINI_API_KEY from .env..."
    GEMINI_API_KEY=$(grep -E '^GEMINI_API_KEY=' "$ENV_FILE" | head -n 1 | cut -d= -f2- | tr -d '"\r')
  fi
fi

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "ERROR: GEMINI_API_KEY environment variable is not set and was not found in .env." >&2
  echo "Please export GEMINI_API_KEY='...' before running this script." >&2
  exit 1
fi
echo "GEMINI_API_KEY is present (length: ${#GEMINI_API_KEY} chars, secret value hidden)."

# 1. Register required Azure resource providers
echo "Checking resource provider registrations..."
az provider register --namespace Microsoft.App --output none 2>/dev/null || true
az provider register --namespace Microsoft.OperationalInsights --output none 2>/dev/null || true

# 2. Create Resource Group (idempotent)
echo "Creating resource group '$RG' in '$LOCATION'..."
az group create --name "$RG" --location "$LOCATION" --output none

# 3. Create Container Apps Environment with no log analytics ingestion
if ! az containerapp env show --name "$ENV_NAME" --resource-group "$RG" >/dev/null 2>&1; then
  echo "Creating Container Apps environment '$ENV_NAME' (logs-destination: none)..."
  az containerapp env create \
    --name "$ENV_NAME" \
    --resource-group "$RG" \
    --location "$LOCATION" \
    --logs-destination none \
    --output none
else
  echo "Container Apps environment '$ENV_NAME' already exists."
fi

# 4. Create or update Container App
if ! az containerapp show --name "$APP_NAME" --resource-group "$RG" >/dev/null 2>&1; then
  echo "Creating Container App '$APP_NAME'..."
  az containerapp create \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --environment "$ENV_NAME" \
    --image "$IMAGE" \
    --target-port "$PORT" \
    --ingress external \
    --min-replicas 0 \
    --max-replicas 1 \
    --cpu 0.5 \
    --memory 1.0Gi \
    --secrets "gemini-key=$GEMINI_API_KEY" \
    --env-vars "GEMINI_API_KEY=secretref:gemini-key" "LLM_MODE=live" \
    --output none
else
  echo "Updating existing Container App '$APP_NAME'..."
  az containerapp update \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --image "$IMAGE" \
    --secrets "gemini-key=$GEMINI_API_KEY" \
    --set-env-vars "GEMINI_API_KEY=secretref:gemini-key" "LLM_MODE=live" \
    --min-replicas 0 \
    --max-replicas 1 \
    --output none
fi

# 5. Retrieve ingress URL
FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$RG" --query "properties.configuration.ingress.fqdn" -o tsv)

echo ""
echo "=========================================================="
echo "Deployment successful!"
echo "Application URL: https://${FQDN}"
echo "Health Check:    https://${FQDN}/_stcore/health"
echo ""
echo "Note: Replicas will scale to zero when idle (0 cost)."
echo "First request after idle will have a brief cold start."
echo "=========================================================="
