#!/usr/bin/env bash
# Sauvegarde / restauration LOGIQUE de la base (pg_dump) dans un dossier local.
# Simple et lisible : 1 backup = 1 fichier .sql.gz sur ton disque.
#
# Usage :
#   ./k8s/db-backup.sh backup                 # dump → db-backups/task_manager-<ts>.sql.gz
#   ./k8s/db-backup.sh list                   # liste les dumps
#   ./k8s/db-backup.sh restore <fichier> [-y] # applique un dump dans la base
#
# Se connecte au primaire Postgres via `kubectl exec` (pas d'exposition réseau).
set -euo pipefail

NS="task-manager"
CLUSTER="task-manager-db"
DB="task_manager"
BACKUP_DIR="$(cd "$(dirname "$0")/.." && pwd)/db-backups"

primary() {
  kubectl get cluster "$CLUSTER" -n "$NS" -o jsonpath='{.status.currentPrimary}' 2>/dev/null
}

cmd_backup() {
  mkdir -p "$BACKUP_DIR"
  local pod file
  pod=$(primary); [ -n "$pod" ] || { echo "❌ primaire introuvable"; exit 1; }
  file="$BACKUP_DIR/${DB}-$(date +%Y%m%d-%H%M%S).sql.gz"
  echo "==> Backup depuis $pod → $file"
  # --clean --if-exists : le dump recrée proprement (DROP puis CREATE) à la restauration.
  kubectl exec -n "$NS" "$pod" -c postgres -- \
    pg_dump -U postgres -d "$DB" --clean --if-exists \
    | gzip > "$file"
  echo "✅ $(du -h "$file" | cut -f1)  $file"
}

cmd_list() {
  ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "Aucun backup dans $BACKUP_DIR"
}

cmd_restore() {
  local file="${1:-}" assume_yes=""
  shift || true
  [ "${1:-}" = "-y" ] || [ "${1:-}" = "--yes" ] && assume_yes=1
  [ -n "$file" ] || { echo "Usage: $0 restore <fichier.sql.gz> [-y]"; exit 1; }
  [ -f "$file" ] || { echo "❌ fichier introuvable : $file"; exit 1; }
  local pod
  pod=$(primary); [ -n "$pod" ] || { echo "❌ primaire introuvable"; exit 1; }

  echo "⚠️  Restauration de '$file' dans la base '$DB' (écrase les tables existantes)."
  if [ -z "$assume_yes" ]; then
    printf "Confirmer ? [tape 'oui'] : "; read -r ans
    [ "$ans" = "oui" ] || { echo "Annulé."; exit 0; }
  fi
  # stdout → /dev/null (masque le bruit des SELECT internes du dump) ; les
  # erreurs restent visibles sur stderr et stoppent net (ON_ERROR_STOP=1).
  gunzip -c "$file" | kubectl exec -i -n "$NS" "$pod" -c postgres -- \
    psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 --quiet >/dev/null
  echo "✅ Restauré depuis $file"
}

case "${1:-}" in
  backup)  cmd_backup ;;
  list)    cmd_list ;;
  restore) shift; cmd_restore "$@" ;;
  *) echo "Usage: $0 {backup|list|restore <fichier> [-y]}"; exit 1 ;;
esac
