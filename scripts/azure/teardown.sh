#!/usr/bin/env bash
# Teardown patient-faq-chatbot Azure resources
# Deletes the entire resource group to eliminate all cloud resources and costs.
set -euo pipefail

RG="${RG:-faq-bot-rg}"
FORCE="${FORCE:-0}"

echo "=== Patient FAQ Chatbot: Azure Teardown ==="
echo "Target Resource Group: $RG"
echo "==========================================="

# Check Azure CLI
command -v az >/dev/null 2>&1 || {
  echo "ERROR: Azure CLI (az) is not installed." >&2
  exit 1
}

# Check Azure authentication
if ! az account show >/dev/null 2>&1; then
  echo "ERROR: Not logged into Azure CLI." >&2
  echo "Please log in: az login --use-device-code" >&2
  exit 1
fi

# Check if resource group exists
if ! az group show --name "$RG" >/dev/null 2>&1; then
  echo "Resource group '$RG' does not exist. Nothing to tear down."
  exit 0
fi

# Confirm deletion unless forced
if [ "$FORCE" != "1" ] && [ "${1:-}" != "-y" ] && [ "${1:-}" != "--yes" ]; then
  read -r -p "Are you sure you want to completely delete resource group '$RG' and all its resources? (y/N): " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Teardown aborted by user."
    exit 0
  fi
fi

echo "Initiating deletion of resource group '$RG' (background operation)..."
az group delete --name "$RG" --yes --no-wait

echo ""
echo "=========================================================="
echo "Resource group '$RG' deletion initiated in background."
echo "Azure will remove the Container App, Environment, and"
echo "all associated resources. No further costs will incur."
echo "=========================================================="
