#!/usr/bin/env bash
# Sauvegarde / restauration LOGIQUE de la base (pg_dump) dans un dossier local.
# Simple et lisible : 1 backup = 1 fichier .sql.gz sur ton disque.
#
# Usage :
#   ./k8s/db-backup.sh backup                 # dump → db-backups/task_manager-<ts>.sql.gz
#   ./k8s/db-backup.sh list                   # liste les dumps
#   ./k8s/db-backup.sh restore <fichier> [-y] # applique un dump dans la base
#   ./k8s/db-backup.sh verify <fichier>       # restaure dans une base JETABLE et contrôle
#
# `verify` est le geste qui manque à la plupart des dispositifs de sauvegarde :
# une sauvegarde qu'on n'a jamais restaurée n'est pas une sauvegarde validée,
# c'est un fichier dont on espère quelque chose. Il ne touche JAMAIS la base
# réelle — il travaille dans une base temporaire qu'il supprime ensuite.
#
# Se connecte au primaire Postgres via `kubectl exec` (pas d'exposition réseau).
set -euo pipefail

NS="task-manager"
CLUSTER="task-manager-db"
DB="task_manager"
VERIFY_DB="task_manager_verify"
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

# Supprime la base de vérification. Appelée par un trap EXIT, donc elle ne peut
# s'appuyer que sur des variables globales.
cleanup_verify() {
  [ -n "${VERIFY_POD:-}" ] || return 0
  kubectl exec -n "$NS" "$VERIFY_POD" -c postgres -- \
    psql -U postgres -d postgres --quiet \
    -c "DROP DATABASE IF EXISTS $VERIFY_DB;" >/dev/null 2>&1 || true
}

# Restaure un dump dans une base jetable, contrôle qu'il est exploitable, puis
# supprime la base. La base de production n'est jamais touchée : c'est ce qui
# rend l'exercice répétable sans appréhension — donc ce qui le rend fait.
cmd_verify() {
  local file="${1:-}"
  [ -n "$file" ] || { echo "Usage: $0 verify <fichier.sql.gz>"; exit 1; }
  [ -f "$file" ] || { echo "❌ fichier introuvable : $file"; exit 1; }
  # Volontairement GLOBAL : le trap EXIT ci-dessous s'exécute après la sortie de
  # cette fonction, où une variable `local` n'existe plus — et `set -u` fait
  # alors échouer le nettoyage au pire moment.
  VERIFY_POD=$(primary); [ -n "$VERIFY_POD" ] || { echo "❌ primaire introuvable"; exit 1; }
  local pod="$VERIFY_POD"

  echo "==> Vérification de '$file' dans la base jetable '$VERIFY_DB'"

  # Filet : quoi qu'il arrive ensuite, la base temporaire disparaît.
  trap cleanup_verify EXIT

  cleanup_verify
  kubectl exec -n "$NS" "$pod" -c postgres -- \
    psql -U postgres -d postgres -v ON_ERROR_STOP=1 --quiet \
    -c "CREATE DATABASE $VERIFY_DB;" >/dev/null

  echo "    restauration…"
  gunzip -c "$file" | kubectl exec -i -n "$NS" "$pod" -c postgres -- \
    psql -U postgres -d "$VERIFY_DB" -v ON_ERROR_STOP=1 --quiet >/dev/null

  # Smoke tests : un dump qui se charge sans erreur peut très bien être vide.
  # On vérifie donc qu'il y a bien un schéma, et qu'Alembic a un cran posé.
  echo "    contrôles…"
  local tables alembic
  tables=$(kubectl exec -n "$NS" "$pod" -c postgres -- psql -U postgres -d "$VERIFY_DB" \
    -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
  alembic=$(kubectl exec -n "$NS" "$pod" -c postgres -- psql -U postgres -d "$VERIFY_DB" \
    -tAc "SELECT version_num FROM alembic_version;" 2>/dev/null || true)

  echo
  echo "    tables (schéma public) : $tables"
  echo "    cran alembic_version   : ${alembic:-<absent>}"
  for t in tasks users; do
    local n
    n=$(kubectl exec -n "$NS" "$pod" -c postgres -- psql -U postgres -d "$VERIFY_DB" \
      -tAc "SELECT count(*) FROM $t;" 2>/dev/null || echo "?")
    echo "    lignes dans $t        : $n"
  done
  echo

  if [ "${tables:-0}" -gt 0 ] && [ -n "$alembic" ]; then
    echo "✅ Sauvegarde VALIDÉE : elle se restaure et le schéma est exploitable."
  else
    echo "❌ Sauvegarde NON VALIDÉE : restaurée, mais schéma vide ou sans cran Alembic."
    exit 1
  fi
}

case "${1:-}" in
  backup)  cmd_backup ;;
  list)    cmd_list ;;
  restore) shift; cmd_restore "$@" ;;
  verify)  shift; cmd_verify "$@" ;;
  *) echo "Usage: $0 {backup|list|restore <fichier> [-y]|verify <fichier>}"; exit 1 ;;
esac
