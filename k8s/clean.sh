#!/usr/bin/env bash
# Détruit le cluster Kind du projet (et donc tout ce qui tourne dedans).
# Usage :
#   ./k8s/clean.sh            # supprime le cluster Kind 'task-manager'
#   ./k8s/clean.sh --images   # supprime aussi les images Docker construites
set -euo pipefail

CLUSTER_NAME="task-manager"

echo "==> Suppression du cluster Kind '$CLUSTER_NAME'"
if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
  kind delete cluster --name "$CLUSTER_NAME"
else
  echo "    aucun cluster '$CLUSTER_NAME' — rien à supprimer."
fi

if [[ "${1:-}" == "--images" ]]; then
  echo "==> Suppression des images Docker du projet"
  docker image rm -f task-manager-api:latest task-manager-frontend:latest 2>/dev/null || true
fi

echo "✅ Nettoyage terminé."
