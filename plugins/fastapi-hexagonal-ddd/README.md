# Plugin `fastapi-hexagonal-ddd`

Un **Agent Skill** installable qui transmet la méthode de ce dépôt — architecture
hexagonale et DDD tactique appliqués à un backend Python/FastAPI — plutôt que son
code.

Le skill ne dit pas « recopie ce Task Manager ». Il aide un agent à décider :
où placer une règle, où tracer une frontière d'agrégat, quel port créer, quand
court-circuiter le domaine en lecture — et, tout aussi important, **quand cette
architecture est surdimensionnée**.

Le contenu est en anglais (déclenchement plus fiable côté Claude, Codex et Cursor) ;
le cours source reste en français dans [`backend/docs/cours/`](../../backend/docs/cours/README.md).

## Installation

### Claude Code

```
/plugin marketplace add EdwinAlkins/fastapi-hexagonal
/plugin install fastapi-hexagonal-ddd@fastapi-hexagonal
```

### OpenAI Codex

```bash
codex plugin marketplace add EdwinAlkins/fastapi-hexagonal
codex plugin add fastapi-hexagonal-ddd@fastapi-hexagonal
```

Ou, depuis une session Codex : `/plugins`.

### Cursor

```
/add-plugin https://github.com/EdwinAlkins/fastapi-hexagonal
```

Puis installer `fastapi-hexagonal-ddd` depuis **Customize**. En local, copier
`plugins/fastapi-hexagonal-ddd` dans `~/.cursor/plugins/local/` et recharger
la fenêtre.

> Les manifestes Codex (`.codex-plugin/plugin.json` et
> `.agents/plugins/marketplace.json`) sont validés par l'outillage officiel :
>
> ```bash
> python3 scripts/validate_plugin.py plugins/fastapi-hexagonal-ddd
> ```
>
> (script `validate_plugin.py` du skill `plugin-creator`, dépôt `openai/codex`).
> Le format reste récent : en cas d'erreur après une mise à jour de Codex,
> régénérer avec `$plugin-creator`.

## Contenu

```
skills/fastapi-hexagonal-ddd/
├── SKILL.md                              # règle de dépendance, arbre de décision, workflows
└── references/
    ├── architecture.md                   # couches, placement des règles, ports, import-linter
    ├── strategic-ddd.md                  # bounded contexts, context map, ACL, atelier
    ├── domain.md                         # VO, entités, agrégats, relations, exceptions
    ├── application.md                    # use cases, ports, DTO, piège de la cérémonie
    ├── persistence.md                    # modèles ORM, mappers, repositories, adaptateurs
    ├── transactions-and-errors.md        # frontière transactionnelle, dual write, outbox, erreurs, composition root
    ├── reads-and-writes.md               # query services, N+1, CQRS, imports en masse, idempotence
    ├── events-and-messaging.md           # cache, événements domaine/intégration, quand un broker se justifie
    ├── testing.md                        # 3 niveaux de tests, doublures, testcontainers, checklist
    └── project-structure.md              # découpage vertical, recette de démarrage
```

Le `SKILL.md` reste court : l'agent ne charge un fichier de `references/` que
lorsque la tâche l'exige (*progressive disclosure*).

## Périmètre volontairement restreint

Ce skill couvre **l'architecture applicative**. Il ne couvre pas Kubernetes,
l'observabilité, le frontend ni la CI — un skill qui essaie de tout faire se
déclenche mal.

Il distingue systématiquement le **principe** (transférable) du **choix de ce
dépôt** (UUIDv7, RabbitMQ, Valkey, PostgreSQL, import-linter, testcontainers).
Ces derniers sont présentés comme des options défendables, jamais comme des lois.

## Développement

Le skill est un dossier de markdown : pas de build, pas de dépendances. Après
modification, recharger côté Claude avec `/plugin marketplace update fastapi-hexagonal`.

Toute correction de fond doit d'abord être faite dans le cours
([`backend/docs/cours/`](../../backend/docs/cours/README.md)), qui reste la
source de vérité, puis répercutée ici.

Pour diffuser une version — marketplace GitHub, catalogue public Claude, annuaire
public OpenAI — suis [`PUBLIER.md`](PUBLIER.md).

## Licence

AGPL-3.0 — voir [`LICENSE`](../../LICENSE).
