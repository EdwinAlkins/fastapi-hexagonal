# 6. Décisions transverses

Certaines préoccupations traversent toutes les couches : gérer les erreurs, les
transactions, et brancher les morceaux ensemble. Voici les trois patterns clés,
réutilisables tels quels.

## 1. Traduire les erreurs métier en HTTP (sans polluer le domaine)

Le domaine lève des **exceptions métier** (`TaskNotFound`, `EmailAlreadyUsed`),
il ignore HTTP. C'est à la **frontière** (présentation) qu'on décide du code de
statut. Astuce qui évite un handler par exception : mapper les **bases
sémantiques**.

```python
# domain/shared/exceptions.py
class DomainError(Exception): ...
class ValidationError(DomainError): ...   # → 422
class NotFoundError(DomainError): ...     # → 404
class ConflictError(DomainError): ...     # → 409
```

Chaque exception concrète hérite de la bonne base :

```python
class TaskNotFound(NotFoundError): ...
class EmailAlreadyUsed(ConflictError): ...
```

Et on enregistre **quatre** handlers, une fois pour toutes
(`presentation/api/error_handlers.py`) :

```python
@app.exception_handler(NotFoundError)
async def _not_found(_, exc): return _error(404, str(exc))
@app.exception_handler(ConflictError)
async def _conflict(_, exc): return _error(409, str(exc))
# + ValidationError → 422, DomainError → 400 (repli)
```

Bénéfice majeur : **un nouveau bounded context est couvert sans toucher ce
fichier**. Il suffit que ses exceptions héritent de la bonne base (FastAPI
remonte la hiérarchie de classes pour trouver le handler).

## 2. La frontière transactionnelle = la requête

Question : qui décide du `commit` / `rollback` ? **Pas le repository.** Sinon,
un use case qui fait deux écritures ne pourrait pas les rendre atomiques.

Ici, la transaction est pilotée par la **requête HTTP**, dans un seul endroit
(`dependencies/session.py`) :

```python
async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()      # tout a réussi → on valide
        except Exception:
            await session.rollback()    # une erreur → on annule tout
            raise
```

Conséquence : les repositories ne committent **jamais** ; ils mutent juste la
session. Un use case peut enchaîner plusieurs écritures dans **une seule
transaction atomique**. C'est une forme légère d'*Unit of Work*.

> Détail malin : les tests (`tests/conftest.py`) reproduisent *exactement* cette
> frontière, pour tester dans les mêmes conditions que la production.

## 3. La composition root : brancher les ports sur les adaptateurs

Quelque part, il faut bien relier le port abstrait (`TaskRepository`) à son
implémentation concrète (`SqlAlchemyTaskRepository`). Ce point de câblage
s'appelle la **composition root**. C'est le **seul** endroit qui connaît à la
fois les deux mondes ; tout le reste du code ignore ce branchement.

Ici, c'est le package `presentation/api/dependencies/`, avec l'injection de
dépendances de FastAPI :

```python
# dependencies/repositories.py
def get_task_repository(session: SessionDep) -> TaskRepository:
    return SqlAlchemyTaskRepository(session)     # port ← adaptateur

# dependencies/task.py
def get_create_task(tasks: TaskRepositoryDep, users: UserRepositoryDep) -> CreateTask:
    return CreateTask(tasks, users)              # use case ← ses ports
```

C'est aussi ce qui rend les **tests** faciles : il suffit de substituer un
adaptateur (ex. une session sur base in-memory) sans toucher au reste.

## À retenir

- Le domaine lève des **exceptions métier** ; la présentation les mappe en HTTP
  via des **bases sémantiques** → un nouveau contexte ne touche pas les handlers.
- La **transaction appartient à la requête**, pas au repository → écritures
  atomiques, repositories qui ne committent pas.
- La **composition root** est le seul endroit qui relie ports et adaptateurs ;
  c'est ce qui permet de tout remplacer (en test comme en prod).
