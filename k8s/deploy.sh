#!/usr/bin/env bash
# Déploie le stack Task Manager sur un cluster Kind local.
# À exécuter depuis la racine du dépôt : ./k8s/deploy.sh
set -euo pipefail

CLUSTER_NAME="task-manager"
NS="task-manager"
CNPG_MANIFEST="https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.30/releases/cnpg-1.30.0.yaml"
# Envoy Gateway : embarque les CRD Gateway API standard (gatewayclasses,
# gateways, httproutes, referencegrants…), pas besoin de les installer à part.
ENVOY_GATEWAY_VERSION="v1.9.1"
ENVOY_GATEWAY_MANIFEST="https://github.com/envoyproxy/gateway/releases/download/${ENVOY_GATEWAY_VERSION}/install.yaml"
METRICS_SERVER_MANIFEST="https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"

# URLs des consoles de dev, figées dans le bundle frontend au build (les
# boutons de l'en-tête pointent dessus). Doivent correspondre à httproutes.yaml.
MAIL_UI_URL="http://mailpit.localhost"
REDIS_INSIGHT_URL="http://redisinsight.localhost"

# Se placer à la racine du dépôt (parent de ce script), quel que soit le CWD.
cd "$(dirname "$0")/.."

# Prérequis, avant toute action : Kind ouvre beaucoup de watches inotify (un
# kubelet et un conteneur par nœud). Sous les limites par défaut de certaines
# distributions, le cluster devient instable de façon peu lisible — des pods qui
# ne démarrent jamais, des logs qui se figent.
#
# On se contente d'AVERTIR : élever ces limites demande les droits root, et un
# script de déploiement n'a pas à réclamer sudo — encore moins à échouer sur un
# refus alors que le déploiement, lui, a réussi.
WATCHES=$(cat /proc/sys/fs/inotify/max_user_watches 2>/dev/null || echo 0)
INSTANCES=$(cat /proc/sys/fs/inotify/max_user_instances 2>/dev/null || echo 0)
if [ "$WATCHES" -lt 524288 ] || [ "$INSTANCES" -lt 1024 ]; then
  echo "⚠️  Limites inotify basses (watches=$WATCHES, instances=$INSTANCES)."
  echo "    Si Kind devient instable, exécute :"
  echo "      sudo sysctl -w fs.inotify.max_user_watches=524288"
  echo "      sudo sysctl -w fs.inotify.max_user_instances=1024"
  echo "    Le déploiement continue malgré tout."
  echo
fi

echo "==> 1/6  Cluster Kind + Envoy Gateway (${ENVOY_GATEWAY_VERSION})"
if ! kind get clusters | grep -qx "$CLUSTER_NAME"; then
  kind create cluster --config k8s/kind-config.yaml
else
  echo "    cluster '$CLUSTER_NAME' déjà présent, on réutilise."
  # Le mapping d'entrée (hostPort 80 → NodePort 30080) est figé à la CRÉATION du
  # cluster. Un cluster né avant le passage à Gateway API porte encore l'ancien
  # mapping 80→80 : rien ne répondra sur http://localhost.
  if ! docker port "${CLUSTER_NAME}-control-plane" 2>/dev/null | grep -q '^30080/tcp'; then
    echo "    ⚠️  ce cluster n'expose pas le NodePort 30080 (mapping d'avant Gateway API)."
    echo "        Recrée-le :  ./k8s/clean.sh && ./k8s/deploy.sh"
    exit 1
  fi
fi
# --server-side : les CRD Gateway API dépassent la limite de taille de
# l'annotation last-applied-configuration d'un apply client-side.
kubectl apply --server-side -f "$ENVOY_GATEWAY_MANIFEST"
# rollout status tolère le cas « pod pas encore créé » (contrairement à
# `kubectl wait` sur un sélecteur, qui échoue si rien ne matche à l'instant T).
kubectl rollout status deployment/envoy-gateway \
  -n envoy-gateway-system --timeout=300s

echo "==> 2/6  Metrics Server (kubectl top)"
# Kind utilise des certificats kubelet auto-signés : sans
# --kubelet-insecure-tls, Metrics Server échoue en x509.
kubectl apply -f "$METRICS_SERVER_MANIFEST"
if ! kubectl get deployment metrics-server -n kube-system \
  -o jsonpath='{.spec.template.spec.containers[0].args[*]}' \
  | grep -qw -- '--kubelet-insecure-tls'; then
  kubectl patch -n kube-system deployment metrics-server \
    --type=json \
    -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
fi
kubectl -n kube-system rollout status deployment metrics-server --timeout=120s

echo "==> 3/6  Opérateur CloudNativePG"
kubectl apply --server-side -f "$CNPG_MANIFEST"
kubectl wait --for=condition=Available deployment/cnpg-controller-manager \
  -n cnpg-system --timeout=180s

# Version de l'opérateur RabbitMQ Cluster
RABBITMQ_OPERATOR_VERSION="v2.15.0"
RABBITMQ_OPERATOR_MANIFEST="https://github.com/rabbitmq/cluster-operator/releases/download/${RABBITMQ_OPERATOR_VERSION}/cluster-operator.yml"

echo "==> 3b/6  Opérateur RabbitMQ Cluster (version ${RABBITMQ_OPERATOR_VERSION})"
kubectl apply -f "$RABBITMQ_OPERATOR_MANIFEST"
kubectl wait --for=condition=Available deployment/rabbitmq-cluster-operator \
  -n rabbitmq-system --timeout=180s

echo "==> 4/6  Build + load des images dans Kind"
docker build -t task-manager-api:latest ./backend
docker build -t task-manager-frontend:latest --target production \
  --build-arg VITE_MAIL_UI_URL="$MAIL_UI_URL" \
  --build-arg VITE_REDIS_INSIGHT_URL="$REDIS_INSIGHT_URL" \
  ./frontend
kind load docker-image task-manager-api:latest task-manager-frontend:latest --name "$CLUSTER_NAME"

echo "==> 5/6  Namespace, secrets, base de données, dépendances"
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/database.yaml
kubectl wait --for=condition=Ready cluster/task-manager-db -n "$NS" --timeout=300s
kubectl apply -f k8s/infra.yaml
kubectl apply -f k8s/rabbitmq.yaml
# Attendre que le cluster RabbitMQ soit prêt
# kubectl wait --for=condition=Available rabbitmqcluster/rabbitmq \
#   -n "$NS" --timeout=300s

echo "==> 6/6  Migrations, puis config + workloads"
kubectl apply -f k8s/migrate-job.yaml
kubectl wait --for=condition=complete job/db-migrate -n "$NS" --timeout=180s
kubectl apply -f k8s/api-config.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/pdb.yaml
# GatewayClass + EnvoyProxy + Gateway, puis les routes. Envoy Gateway provisionne
# le data plane (Deployment + Service NodePort) en réaction à la Gateway.
kubectl apply -f k8s/gateway.yaml
kubectl wait --for=condition=Programmed gateway/task-manager -n "$NS" --timeout=300s
kubectl apply -f k8s/httproutes.yaml
# Segmentation réseau (kindnet applique les NetworkPolicy).
kubectl apply -f k8s/network-policies.yaml

echo
echo "✅ Déploiement terminé."
echo "   Application  : http://localhost"
echo "   Mailpit      : http://mailpit.localhost"
echo "   RabbitMQ     : http://rabbitmq.localhost"
echo "   RedisInsight : http://redisinsight.localhost"
echo "   Prometheus   : http://prometheus.localhost"
echo "   Suivi        : kubectl get pods -n $NS -w"
echo "   Métriques    : kubectl top nodes  (attendre ~30–60s après le deploy)"
