# 7. Organisation & tests

## Organiser par bounded context (tranches verticales)

Il y a deux façons de ranger un projet :

- **Par couche technique** (horizontal) : tous les modèles ensemble, tous les
  repositories ensemble, tous les schémas ensemble.
- **Par bounded context** (vertical) : tout ce qui concerne `task` ensemble,
  tout ce qui concerne `user` ensemble.

Ce projet utilise le découpage **vertical**, à chaque couche :

```
domain/task/          domain/user/
application/task/     application/user/
persistence/task/     persistence/user/
v1/schemas/task.py    v1/schemas/user.py
v1/routers/tasks.py   v1/routers/users.py
dependencies/task.py  dependencies/user.py
```

Pourquoi ? Parce qu'on travaille **par fonctionnalité**, pas par couche. Ajouter
un contexte = ajouter des dossiers, sans toucher aux fichiers existants. On lit
un contexte de bout en bout sans sauter dans dix fichiers fourre-tout.

### Ce qui reste transverse (au niveau racine)

Tout n'est pas propre à un contexte. Ces éléments restent partagés :

- `domain/shared/` — les bases d'exceptions.
- `persistence/database.py` (moteur, session) et `converters.py` (helper commun).
- `dependencies/session.py` et `dependencies/repositories.py` — le câblage transverse.

### La bonne dose de centralisation

Nuance importante apprise dans ce projet : **on ne découpe pas tout
mécaniquement**. La composition root (`dependencies/`) garde un `__init__.py`
« façade » qui réexpose tout, car son intérêt *est* d'être un point d'entrée
unique. À l'inverse, les schémas sont simplement découpés, sans façade, car ils
n'ont aucun rôle centralisateur. **Le découpage sert la lisibilité, ce n'est pas
un dogme à appliquer partout.**

## La pyramide de tests

L'architecture rend deux niveaux de tests naturels et complémentaires.

### Tests unitaires : le domaine, purs et rapides

Ils testent les règles métier **sans base ni HTTP**. Instantanés.

```python
# tests/unit/domain/test_task_entity.py
def test_complete_twice_is_rejected() -> None:
    task = Task.create(owner_id=UserId.generate(), title=TaskTitle("x"))
    task.complete()
    with pytest.raises(TaskAlreadyCompleted):
        task.complete()
```

C'est *possible et facile* précisément parce que le domaine ne dépend d'aucun
framework (chapitre 1). Si tes règles métier sont dures à tester, c'est souvent
le signe qu'elles sont mélangées à de la technique.

### Tests d'intégration : l'API de bout en bout

Ils exercent toute la chaîne (HTTP → use case → domaine → BDD réelle), via un
client HTTP asynchrone, sur un **PostgreSQL et un Valkey jetables** démarrés par
[testcontainers] (`tests/conftest.py`) — les mêmes moteurs qu'en production.

Viser le moteur réel plutôt qu'un substitut in-memory coûte quelques secondes
au démarrage de la suite, mais c'est ce qui fait tester ce qui tourne vraiment :
type `uuid` natif, `timestamptz`, violation d'unicité, `ON DELETE CASCADE`. Un
test qui passe sur un dialecte que la prod n'utilise pas ne prouve pas
grand-chose. La contrepartie : `pytest` exige un démon Docker.

Les conteneurs rendent aussi la suite **hermétique**, ce qui vaut d'être
souligné pour le cache : sans eux, un Redis écoutant sur le port par défaut de
la machine — la stack `docker compose` du projet, typiquement — serait utilisé
par les tests, qui liraient alors des entrées laissées par un run précédent. Le
cache est vidé entre deux tests, et la fixture `cache` permet d'observer
directement ce que l'API y écrit (`tests/integration/api/test_users_cache.py`).

[testcontainers]: https://testcontainers-python.readthedocs.io/

```python
# tests/integration/api/test_users_api.py
async def test_list_user_tasks_returns_only_owned_tasks(client):
    alice = await _create_user(client, email="alice@example.com")
    await client.post(f"/api/v1/users/{alice}/tasks", json={"title": "T1"})
    tasks = await client.get(f"/api/v1/users/{alice}/tasks")
    assert all(t["owner_id"] == alice for t in tasks.json())
```

La `client` fixture (dans `conftest.py`) monte l'app réelle et **remplace juste
la session** par une base in-memory — le reste du câblage (DI) est authentique.
C'est la composition root (chapitre 6) qui rend ça trivial.

### La règle de répartition

- Une **règle métier / un invariant** → test **unitaire** (domaine).
- Un **parcours applicatif / un cas d'erreur HTTP** → test **d'intégration**.

Beaucoup de tests unitaires rapides à la base, quelques tests d'intégration au
sommet. On ne teste pas les mêmes choses deux fois.

## Les garde-fous automatisés (ce projet)

```bash
uv run ruff check .   # style & erreurs courantes
uv run mypy           # typage strict
uv run pytest         # les deux niveaux de tests
```

Ajoute le test d'architecture du chapitre 1 (`grep` sur le domaine) et tu as un
filet de sécurité complet.

## À retenir

- Découpe **par contexte** (vertical), garde le vraiment transverse à la racine.
- Le découpage sert la **lisibilité** — pas un dogme (cf. façade vs pas de façade).
- Domaine → tests **unitaires** purs ; parcours → tests **d'intégration**.
- Un domaine pur est un domaine **facile à tester** : c'est le juge de paix.
