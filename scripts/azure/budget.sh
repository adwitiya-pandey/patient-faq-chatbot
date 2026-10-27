#!/usr/bin/env bash
# Configure a strict $5 monthly budget with email alerts at 50% and 90% in Azure
set -euo pipefail

RG="${RG:-faq-bot-rg}"
BUDGET_NAME="${BUDGET_NAME:-faq-bot-budget}"
AMOUNT="${AMOUNT:-5}"
EMAIL="${EMAIL:-}"

echo "=== Patient FAQ Chatbot: Azure Budget Configuration ==="
echo "Resource Group: $RG"
echo "Budget Name:    $BUDGET_NAME"
echo "Monthly Limit:  \$$AMOUNT USD"
echo "======================================================="

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

# Prompt for notification email if not provided
if [ -z "$EMAIL" ]; then
  # Try to read default user email from active Azure account
  DEFAULT_EMAIL=$(az account show --query "user.name" -o tsv 2>/dev/null || true)
  if [[ "$DEFAULT_EMAIL" =~ @ ]]; then
    read -r -p "Enter notification email address [$DEFAULT_EMAIL]: " input_email
    EMAIL="${input_email:-$DEFAULT_EMAIL}"
  else
    read -r -p "Enter notification email address: " EMAIL
  fi
fi

if [ -z "$EMAIL" ]; then
  echo "ERROR: An email address is required to receive budget threshold alerts." >&2
  exit 1
fi
echo "Notification email: $EMAIL"

START_DATE=$(date -u +"%Y-%m-01")
END_DATE=$(date -u -d "+2 years" +"%Y-%m-01" 2>/dev/null || date -u -v+2y +"%Y-%m-01" 2>/dev/null || echo "2028-12-31")

echo "Creating budget: \$$AMOUNT monthly, start=$START_DATE, end=$END_DATE..."

# Attempt to create budget via CLI
if az consumption budget create \
  --budget-name "$BUDGET_NAME" \
  --amount "$AMOUNT" \
  --time-grain monthly \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  --resource-group "$RG" \
  --notifications "{
    \"Alert50\": {
      \"enabled\": true,
      \"operator\": \"GreaterThan\",
      \"threshold\": 50,
      \"contactEmails\": [\"$EMAIL\"]
    },
    \"Alert90\": {
      \"enabled\": true,
      \"operator\": \"GreaterThan\",
      \"threshold\": 90,
      \"contactEmails\": [\"$EMAIL\"]
    }
  }" --output none 2>/dev/null; then
  echo ""
  echo "=========================================================="
  echo "Budget configured successfully!"
  echo "Monthly limit: \$$AMOUNT USD"
  echo "Alert 1:       50% (\$$(awk "BEGIN {print $AMOUNT * 0.5}") USD) -> $EMAIL"
  echo "Alert 2:       90% (\$$(awk "BEGIN {print $AMOUNT * 0.9}") USD) -> $EMAIL"
  echo "=========================================================="
else
  echo ""
  echo "Note: Azure CLI consumption budget creation may not be permitted"
  echo "on certain subscription types (e.g. Free Trial or Sponsorship)."
  echo ""
  echo "To set this up manually in the Azure Portal in 60 seconds:"
  echo "1. Open https://portal.azure.com"
  echo "2. Navigate to 'Cost Management + Billing' -> 'Cost Management' -> 'Budgets'."
  echo "3. Click '+ Add'."
  echo "4. Set Scope to Resource Group: '$RG'."
  echo "5. Set Name: '$BUDGET_NAME', Reset Period: 'Monthly', Amount: '\$$AMOUNT'."
  echo "6. Set Alert Condition 1: 50% of budget -> recipient: $EMAIL."
  echo "7. Set Alert Condition 2: 90% of budget -> recipient: $EMAIL."
  echo "8. Click 'Create'."
  echo "=========================================================="
fi
