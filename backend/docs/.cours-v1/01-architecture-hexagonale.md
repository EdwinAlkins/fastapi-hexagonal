# 1. L'architecture hexagonale

## Le problème qu'elle résout

Dans une application « classique », le code métier finit mélangé au framework
web, aux requêtes SQL, aux schémas JSON. Résultat : impossible de tester une
règle métier sans lancer une base de données, impossible de changer de
framework sans tout réécrire, et la logique importante est noyée dans la
plomberie.

L'architecture hexagonale (aussi appelée **ports & adapters**) répond à ça avec
**une seule règle**.

## La règle de dépendance

> Les dépendances du code pointent **toujours vers l'intérieur**, vers le cœur
> métier. Le cœur ne connaît rien du monde extérieur.

```
┌─────────────────────────────────────────────────────────┐
│  Presentation (FastAPI)      ─ adaptateur « driving »    │
│  Infrastructure (SQLAlchemy) ─ adaptateurs « driven »    │
│        │                                                 │
│        ▼                                                 │
│     Application (use cases)                              │
│        │                                                 │
│        ▼                                                 │
│      Domain (entités, value objects, ports)  ← Python pur│
└─────────────────────────────────────────────────────────┘
```

Concrètement, dans ce projet, les 4 couches sont :

- **Domain** (`src/task_manager/domain/`) — le cœur. Zéro import de framework.
- **Application** (`application/`) — les use cases. Dépend *uniquement* du domaine.
- **Infrastructure** (`infrastructure/`) — la BDD, la config. Dépend du domaine.
- **Presentation** (`presentation/`) — l'API HTTP. Dépend du domaine et de l'application.

Les couches externes (infra, présentation) dépendent des couches internes
(application, domaine). **Jamais l'inverse.**

## Driving vs driven : les deux côtés de l'hexagone

- Un adaptateur **driving** (pilotant) déclenche l'application : l'API HTTP
  reçoit une requête et appelle un use case. C'est le côté « gauche ».
- Un adaptateur **driven** (piloté) est appelé par l'application : la base de
  données stocke une tâche quand un use case le demande. C'est le côté « droit ».

Le point clé : le use case ne connaît pas l'API qui l'appelle, ni la base qui le
sert. Il ne connaît que des **ports** (voir chapitre 3).

## Comment on la vérifie ici

La règle de dépendance n'est pas qu'un principe : elle est **mécaniquement
vérifiable**. Le domaine ne doit importer aucun framework :

```bash
grep -rE "fastapi|sqlalchemy|pydantic" src/task_manager/domain/   # → aucun résultat
```

Si cette commande renvoie quelque chose, c'est que le cœur a été contaminé par
un détail technique. C'est un test d'architecture que tu peux mettre en CI.

## Ce que ça t'apporte concrètement

- **Testabilité** — le domaine se teste sans base ni HTTP, en millisecondes.
- **Remplaçabilité** — passer de SQLite à PostgreSQL, ou de FastAPI à autre
  chose, ne touche que les adaptateurs. Le cœur ne bouge pas. Ce template a
  justement fait cette migration : seuls la config, le moteur SQLAlchemy et les
  tests ont changé — pas une ligne de `domain/` ni d'`application/`.
- **Lisibilité** — la logique métier est isolée, on la lit sans la plomberie.

## À retenir

- Une seule règle : les dépendances pointent vers l'intérieur.
- Le cœur (domaine) est en langage pur, sans framework.
- « Port » = interface, « adaptateur » = implémentation.
- La règle est vérifiable par un simple `grep`.
