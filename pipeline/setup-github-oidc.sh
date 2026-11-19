#!/usr/bin/env bash
# One-time setup: let GitHub Actions sign in to Azure with Microsoft Entra ID (OIDC, no secrets)
# and give it access to your Foundry project.
#
# Usage (Azure Cloud Shell or any shell with az and gh signed in):
#   ./setup-github-oidc.sh <owner/repo> <resource-group> <foundry-resource> [storage-account]
# Example:
#   ./setup-github-oidc.sh sbrahme/vancan-claims-agent rg-agentlab-dev-cac-ac01 aif-agentlab-dev-cac-ac01 stagentlabdevcacac01
set -euo pipefail
REPO="$1"; RG="$2"; FOUNDRY="$3"; STORAGE="${4:-}"
APP_NAME="gh-vancan-claims-agent"

APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
az ad sp create --id "$APP_ID" >/dev/null 2>&1 || true
echo "App registration: $APP_NAME ($APP_ID)"

# Which GitHub runs may sign in: pull requests, pushes to main, and the production environment.
i=0
for SUBJECT in "repo:${REPO}:pull_request" "repo:${REPO}:ref:refs/heads/main" "repo:${REPO}:environment:production"; do
  i=$((i+1))
  az ad app federated-credential create --id "$APP_ID" --parameters "{
    \"name\": \"github-${i}\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"${SUBJECT}\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" >/dev/null
  echo "Federated credential: $SUBJECT"
done

# Foundry User (formerly Azure AI User): create agent versions, run agents and evaluations.
FOUNDRY_ID=$(az cognitiveservices account show -g "$RG" -n "$FOUNDRY" --query id -o tsv)
az role assignment create --assignee "$APP_ID" --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope "$FOUNDRY_ID" >/dev/null
echo "Role: Foundry User on $FOUNDRY"

# Optional: write evaluation datasets to your storage connection.
if [ -n "$STORAGE" ]; then
  ST_ID=$(az storage account show -g "$RG" -n "$STORAGE" --query id -o tsv)
  az role assignment create --assignee "$APP_ID" --role "Storage Blob Data Contributor" --scope "$ST_ID" >/dev/null
  echo "Role: Storage Blob Data Contributor on $STORAGE"
fi

echo
echo "Set these GitHub repository variables (Settings > Secrets and variables > Actions > Variables):"
echo "  AZURE_CLIENT_ID=$APP_ID"
echo "  AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)"
echo "  AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)"
echo "  AZURE_AI_PROJECT_ENDPOINT=<copy from your Foundry project Home page>"
echo
echo "Or, with the GitHub CLI:"
echo "  gh variable set AZURE_CLIENT_ID -R $REPO -b $APP_ID"
echo "Then create the 'production' environment with required reviewers: Settings > Environments."
