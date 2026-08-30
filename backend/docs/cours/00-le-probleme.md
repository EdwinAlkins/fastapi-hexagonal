# 00. Le problème

> **TL;DR** — Dans une application mal structurée, le code métier finit
> facilement par se dissoudre dans les détails techniques. On ne s'en aperçoit
> pas en écrivant, mais en essayant de tester, de changer un outil, ou simplement
> de retrouver une règle six mois plus tard.

Avant de présenter une solution, il faut ressentir le problème. Sinon
l'architecture ressemble à de la cérémonie gratuite — et pour un projet simple,
elle l'est effectivement ([chapitre 13](13-demarrer-un-projet.md#quand-ne-pas-utiliser-cette-architecture)).

## Le code qui paraît normal

Voici une version « directe » de la création d'une tâche. Elle fonctionne, elle
est courte, et elle est écrite comme ça dans énormément de projets :

```python
@router.post("/tasks")
async def create_task(payload: CreateTaskRequest, db: AsyncSession = Depends(get_db)):
    user = await db.get(UserModel, payload.owner_id)
    if user is None:
        raise HTTPException(404, "user introuvable")
    if not payload.title.strip():
        raise HTTPException(422, "titre vide")

    task = TaskModel(
        id=uuid4(),
        owner_id=payload.owner_id,
        title=payload.title.strip(),
        status="todo",
        created_at=datetime.now(UTC),
    )
    db.add(task)
    await db.commit()
    return task
```

Rien n'est absurde ici. Le problème n'est pas ce qu'on voit, c'est ce qui
devient impossible.

## Ce qui casse ensuite

**1. Les règles métier n'existent nulle part.** « Un titre ne peut pas être
vide » est une règle de l'entreprise. Ici elle vit dans un router HTTP. Le jour
où une commande CLI, un import CSV ou un worker crée aussi des tâches, la règle
est soit dupliquée, soit oubliée. Elle n'a **pas de domicile**.

**2. Tester une règle exige toute la pile.** Pour vérifier qu'un titre vide est
refusé, il faut un client HTTP, une session, une base. Trois secondes de setup
pour tester une comparaison de chaîne. Résultat prévisible : on ne teste pas.

**3. « Terminer une tâche » n'est écrit nulle part.** Chaque endroit qui veut
terminer une tâche fait `task.status = "done"` et espère penser à
`completed_at`. La règle « on ne termine pas deux fois » n'a aucun endroit où
être garantie ; elle est réimplémentée, partiellement, à chaque appel.

**4. Changer d'outil devient un chantier.** Passer de SQLite à PostgreSQL,
remplacer FastAPI, changer de bibliothèque de validation : tout le code métier
est concerné, parce qu'il n'a jamais été séparé.

**5. On ne sait plus où lire le métier.** La question « quelles sont les règles
d'une tâche ? » n'a pas de réponse par un fichier. Il faut lire les routers, les
modèles ORM, quelques services, et deviner.

## La même chose, réorganisée

L'architecture de ce projet répond à ces cinq points en donnant un **domicile**
à chaque type de décision :

```python
# domain/task/value_objects.py — la règle du titre, une fois, pour tous les appelants
class TaskTitle:
    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyTitle()

# domain/task/entities.py — la règle de transition d'état, protégée par l'entité
class Task:
    def complete(self) -> None:
        if self.status is TaskStatus.DONE:
            raise TaskAlreadyCompleted()
        self.status = TaskStatus.DONE
        self.completed_at = _now()

# application/task/use_cases/create_task.py — l'enchaînement, sans règle métier
class CreateTask:
    async def execute(self, command: CreateTaskCommand) -> TaskDTO:
        owner_id = UserId.from_string(command.owner_id)
        if not await self._users.exists(owner_id):
            raise UserNotFound(str(owner_id))
        task = Task.create(owner_id=owner_id, title=TaskTitle(command.title))
        await self._tasks.save(task)
        return TaskDTO.from_entity(task)
```

Le router, lui, ne fait plus que traduire du HTTP. Il ne contient plus une seule
décision métier.

C'est plus de fichiers. C'est le **coût**, assumé. Le bénéfice : les règles ont
une adresse, elles se testent en millisecondes, et elles s'appliquent quel que
soit l'appelant — l'API, le CLI (`task-manager-cli create-user`) ou le worker
RabbitMQ de ce projet.

## Ce que ce cours essaie vraiment de t'apprendre

Pas une liste de dossiers à créer. Une question à te poser en permanence :

> **Cette décision, à qui appartient-elle ?**

Tout le reste — ports, agrégats, DTO, mappers, composition root — n'est que la
machinerie qui rend la réponse à cette question exécutable. Le
[chapitre 02](02-ou-vit-une-regle.md) y est entièrement consacré.

## À retenir

- Le vrai problème n'est pas esthétique : c'est **l'absence de domicile** pour
  les règles métier.
- Les symptômes : règles dupliquées, tests lents ou absents, invariants non
  garantis, outils non remplaçables, métier illisible.
- La solution coûte des fichiers et de l'indirection. Elle se rentabilise quand
  le métier est riche et le projet durable — pas toujours.

## À toi de jouer

1. Dans le premier extrait, la vérification `payload.title.strip()` est faite
   dans le router. Cite **deux** chemins d'exécution de ce projet qui ne
   passeraient jamais par ce router — et pour lesquels la règle serait donc
   absente.
2. Le premier extrait fait `await db.commit()` dans le handler. Qu'est-ce que ça
   rend impossible si demain la création d'une tâche doit aussi débiter un quota
   utilisateur dans la même opération ?

→ [Corrigés](14-annexes.md#c-corrigés-des-exercices)
