# Déploiement Kubernetes (Kind)

Manifestes pour faire tourner le stack **Task Manager** sur un cluster Kind local.
Voir `../infra-kind-plan.md` pour les explications détaillées et la correspondance
docker-compose → Kubernetes.

## Prérequis

- `docker`, `kind`, `kubectl` installés.
- Les ports **80/443** de l'hôte libres (mappés vers l'Ingress).

## Fichiers

| Fichier | Rôle |
|---|---|
| `kind-config.yaml` | Cluster Kind 4 nœuds (1 control-plane + 3 workers) + ports 80/443 |
| `namespace.yaml` | Namespace `task-manager` |
| `secrets.yaml` | Secrets divers (RedisInsight encryption key) - RabbitMQ utilise le secret généré par l'opérateur (`rabbitmq-default-user`) |
| `database.yaml` | Cluster CNPG (3 instances, anti-affinité) + Pooler (2) |
| `rabbitmq.yaml` | Cluster RabbitMQ (3 nœuds, géré par l'opérateur officiel) |
| `infra.yaml` | Valkey, Mailpit, Prometheus, RedisInsight |
| `api-config.yaml` | ConfigMap partagée API/worker |
| `migrate-job.yaml` | Job Alembic (`alembic upgrade head`) |
| `api-deployment.yaml` | API FastAPI + Service |
| `worker-deployment.yaml` | Worker d'e-mails |
| `frontend-deployment.yaml` | Frontend Nginx + Service |
| `ingress.yaml` | Entrée HTTP → frontend (`http://localhost`) |
| `ingress-dev.yaml` | Consoles de dev via hostnames `*.localhost` |
| `network-policies.yaml` | Segmentation réseau (qui peut parler à qui) |
| `db-backup.sh` | Backup/restore logique de la base (`pg_dump`) dans `db-backups/` |

## Lancement

Tout est automatisé par `deploy.sh` (à la racine du dépôt, exécuté depuis `../`) :

```bash
cd ..
./k8s/deploy.sh
```

Ou manuellement, dans l'ordre :

```bash
# 1. Cluster + Ingress Controller
kind create cluster --config k8s/kind-config.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl rollout status deployment/ingress-nginx-controller -n ingress-nginx --timeout=180s

# 2. Opérateur CloudNativePG (vérifier la dernière version sur le repo CNPG)
kubectl apply --server-side -f \
  https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.26/releases/cnpg-1.26.0.yaml
kubectl wait --for=condition=Available deployment/cnpg-controller-manager -n cnpg-system --timeout=180s

# 2b. Opérateur RabbitMQ Cluster (version v2.15.0)
RABBITMQ_OPERATOR_VERSION="v2.15.0"
kubectl apply -f \
  "https://github.com/rabbitmq/cluster-operator/releases/download/${RABBITMQ_OPERATOR_VERSION}/cluster-operator.yml"
kubectl wait --for=condition=Available deployment/rabbitmq-cluster-operator -n rabbitmq-system --timeout=180s

# 3. Build + load des images dans Kind
docker build -t task-manager-api:latest ./backend
docker build -t task-manager-frontend:latest --target production ./frontend
kind load docker-image task-manager-api:latest task-manager-frontend:latest --name task-manager

# 4. Namespace, secrets, BDD, dépendances
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/database.yaml
kubectl wait --for=condition=Ready cluster/task-manager-db -n task-manager --timeout=300s
kubectl apply -f k8s/infra.yaml
kubectl apply -f k8s/rabbitmq.yaml
kubectl wait --for=condition=Available rabbitmqcluster/rabbitmq -n task-manager --timeout=300s

# 5. Migrations, puis config + workloads
kubectl apply -f k8s/migrate-job.yaml
kubectl wait --for=condition=complete job/db-migrate -n task-manager --timeout=180s
kubectl apply -f k8s/api-config.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/ingress-dev.yaml
```

## URLs

L'application est accessible sur **http://localhost**.

Les consoles de dev sont exposées via l'Ingress sur des hostnames dédiés :

| Console | URL | Identifiants |
|---|---|---|
| 🖥️ Application | http://localhost | — |
| 📬 Mailpit (webmail de test) | http://mailpit.localhost | — |
| 🐰 RabbitMQ (management) | http://rabbitmq.localhost | Générés automatiquement par l'opérateur (secret `rabbitmq-default-user`) |
| 🔎 RedisInsight (cache Valkey) | http://redisinsight.localhost | — |
| 📊 Prometheus | http://prometheus.localhost | — |

> **Résolution DNS** — avec `systemd-resolved`, les noms `*.localhost` pointent
> déjà vers `127.0.0.1` : rien à configurer. Sinon, ajouter dans `/etc/hosts` :
> ```
> 127.0.0.1  mailpit.localhost rabbitmq.localhost redisinsight.localhost prometheus.localhost
> ```

> **Boutons de l'en-tête du frontend** — les raccourcis Mailpit / RedisInsight de
> l'app pointent vers `localhost:8025` / `localhost:5540` (valeurs figées au build).
> Pour qu'ils ciblent les URLs ci-dessus, rebuilder le frontend avec
> `--build-arg VITE_MAIL_UI_URL=http://mailpit.localhost` et
> `--build-arg VITE_REDIS_INSIGHT_URL=http://redisinsight.localhost`.

## Sauvegarde / restauration de la base (pg_dump)

Backup **logique** simple : 1 backup = 1 fichier `.sql.gz` dans `db-backups/`
(sur ton disque, ignoré par Git). Se connecte au primaire via `kubectl exec`.

```bash
./k8s/db-backup.sh backup                 # dump → db-backups/task_manager-<horodatage>.sql.gz
./k8s/db-backup.sh list                   # liste les dumps
./k8s/db-backup.sh restore <fichier>      # applique un dump (demande confirmation)
./k8s/db-backup.sh restore <fichier> -y   # sans confirmation
```

Le dump inclut le schéma (avec `alembic_version`) et les données ; la
restauration recrée proprement les objets (`--clean --if-exists`) puis les
recharge. Pas de PITR — on restaure à l'instant d'un dump.

## Sécurité

**SecurityContext** — les pods qu'on maîtrise sont durcis :
- **api / worker / migrate** : `runAsNonRoot` (uid 1000), `readOnlyRootFilesystem`,
  `allowPrivilegeEscalation: false`, `capabilities: drop [ALL]`, seccomp
  `RuntimeDefault`. `/tmp` monté en `emptyDir` (gunicorn/temp).
- **frontend** : image `nginx-unprivileged` (uid 101, écoute 8080), même durcissement.
- **postgres / pooler** : déjà non-root (uid 26) via l'opérateur CNPG — non modifiés.
- *Restent en défaut : valkey, rabbitmq, mailpit, prometheus, redisinsight
  (images tierces ; `readOnlyRootFilesystem` demande une validation par image).*

**NetworkPolicy** (`network-policies.yaml`) — segmentation testée (kindnet
l'applique). Une politique d'ingress par cible ; tout le reste est refusé :

```
ingress-nginx → frontend → api → ┬→ pooler → postgres
                                 ├→ rabbitmq
                                 ├→ valkey
                                 └→ mailpit
```

Le **frontend ne peut jamais joindre postgres/pooler directement** (vérifié :
un pod non listé sur la base time-out ; l'api passe). L'egress (dont le DNS)
reste libre.

## Mise à jour d'une image

Après un changement de code, reconstruire + recharger + redémarrer :

```bash
docker build -t task-manager-api:latest ./backend
kind load docker-image task-manager-api:latest --name task-manager
kubectl rollout restart deployment/api deployment/mail-worker -n task-manager
```

## Nettoyage

```bash
kind delete cluster --name task-manager
```
