# 09. Lire sans passer par le domaine

> **TL;DR** — Les agrégats sont conçus pour protéger les **écritures**. Pour
> lire, ils sont souvent le mauvais outil : sur-lecture, allers-retours, N+1, et
> une base qui sature pour afficher trois colonnes. Dans ces cas-là, on
> **court-circuite le domaine** : un *query service* fait le SQL exact et rend un
> DTO plat. Écriture stricte d'un côté, lecture rapide de l'autre — la forme
> légère de CQRS.

Tout ce qui précède protège les écritures : invariants, agrégats, frontières
transactionnelles. Ce chapitre est le contrepoint, et c'est là que beaucoup
d'architectures propres deviennent lentes.

## Le malentendu qui coûte cher

Quand on a passé du temps à construire un domaine soigné, un réflexe s'installe :
**tout doit passer par lui**. C'est vrai en écriture. C'est faux en lecture, et
s'y accrocher produit des systèmes corrects et inutilisables.

Un agrégat est optimisé pour une seule chose : garantir des invariants au moment
d'écrire. Il faut donc réunir **tout ce dont ces invariants dépendent**, et
reconstruire le modèle métier — value objects compris — avant de pouvoir décider
quoi que ce soit. Ce contrat a un prix, et ce prix n'achète rien quand on affiche
un tableau : il n'y a aucun invariant à faire respecter.

L'écriture et la lecture n'ont tout simplement pas les mêmes besoins :

| | Écriture | Lecture |
|---|---|---|
| Objectif | Protéger les invariants | Servir un écran, vite |
| Forme utile | Agrégat cohérent | Projection à plat |
| Granularité | L'agrégat entier | Exactement les champs affichés |
| Traverse les frontières d'agrégats ? | Non — les invariants sont en jeu | Oui — aucun invariant n'est engagé |
| Ce qui compte | La justesse | Le temps de réponse et la charge base |

## Ce que coûte vraiment une lecture par les agrégats

Prenons un écran banal : **50 tâches avec le nom de leur propriétaire**.

### Par les agrégats

```python
tasks = await task_repository.list(limit=50)          # 1 requête
for task in tasks:
    user = await user_repository.get(task.owner_id)   # 50 requêtes  ← N+1
    ...
```

Le compte : **51 requêtes** pour afficher 4 colonnes. Chaque `Task` reconstruit
un `TaskId`, un `UserId`, un `TaskTitle`, un `TaskStatus` ; chaque `User`
reconstruit un `UserName` et un `Email` — dont on n'affichera que le nom. Puis
tout est reconverti en `str` dans un DTO de sortie.

C'est le **N+1** ([ch. 05](05-relations-entre-agregats.md#le-piège-du-n1-côté-lecture)),
vu du côté applicatif. Et il est pernicieux : il ne se voit pas en développement
avec dix lignes de données, il se voit en production à 500 requêtes par seconde,
quand le pool de connexions est saturé et que la base passe son temps à répondre
à des micro-requêtes.

> **Le point important n'est pas la lenteur d'une page.** C'est qu'une lecture
> mal conçue consomme des connexions et du CPU base qui manquent alors aux
> **écritures** — celles-là mêmes qu'on a tant soigné à rendre correctes. Une
> lecture négligée finit par dégrader le chemin critique.

### Par un query service

```sql
SELECT t.id, t.title, t.status, u.name AS owner_name
FROM tasks t
JOIN users u ON u.id = t.owner_id
ORDER BY t.created_at DESC
LIMIT 50;
```

**Une requête.** Aucun agrégat construit, aucun value object alloué, exactement
les quatre colonnes affichées. La base fait ce qu'elle sait faire de mieux.

### La mesure, pas l'intuition

Ce dépôt implémente les **deux** chemins, et un test d'intégration compte les
requêtes SQL réellement émises en s'abonnant à l'événement SQLAlchemy
`before_cursor_execute`. Sur **200 tâches réparties entre 10 propriétaires**,
contre un vrai PostgreSQL :

| Chemin | Requêtes SQL | Durée |
|---|---|---|
| Par les agrégats (`list` puis un `get` par tâche) | **201** | 84,6 ms |
| Par le query service | **1** | 6,6 ms |

**201× moins de requêtes, 12,8× plus rapide** — et l'écart se creuse avec le
volume, puisque l'un est linéaire en nombre d'allers-retours et l'autre non.

Deux tests verrouillent ces chiffres dans `tests/integration/api/test_exports_api.py` :
l'un affirme que le query service émet **exactement 1** `SELECT`, l'autre que le
chemin par agrégats en émet **`1 + N`**. Le second est inhabituel — il teste un
défaut — mais c'est ce qui empêche la démonstration de se périmer en silence.

## Le geste : jeter le domaine, délibérément

C'est la partie contre-intuitive. Sur ce chemin de lecture, on **abandonne
volontairement** :

- **les entités et les value objects** — on ne construit ni `TaskTitle` ni
  `Email` ;
- **les invariants** — ils ne servent à rien : on ne modifie rien ;
- **la séparation des agrégats à la lecture** — on joint `tasks` et `users` sans
  scrupule, puisqu'aucun invariant de l'un ou de l'autre n'est engagé ;
- **les repositories** — on ne passe pas par `TaskRepository`.

Ce n'est pas une entorse honteuse à l'architecture : **c'est l'architecture qui
fonctionne comme prévu.** Les invariants existent pour empêcher d'écrire un état
incohérent ; une projection de lecture n'en engage aucun. Payer le prix d'une
protection qui ne protège rien ici est une erreur de conception, pas une preuve
de rigueur.

Le corollaire vaut d'être dit : ce n'est pas le mot « lecture » qui autorise le
raccourci. Une lecture qui sert à **décider d'une écriture** — charger une tâche
pour la compléter — repasse par l'agrégat, parce que la décision, elle, engage
bien les invariants.

La règle qui reste, elle, est ferme :

> **Une écriture qui doit faire respecter des invariants passe par le modèle qui
> les porte.** Un query service, lui, est en lecture seule, sans exception : le
> jour où il écrit, les invariants ne valent plus rien nulle part.

## Anatomie d'un query service

Ce dépôt en implémente un, qui sert l'export global des tâches avec leur
propriétaire. Le **port**, en `application/task/queries.py` :

```python
@dataclass(frozen=True, slots=True)
class TaskWithOwner:          # DTO de LECTURE : plat, des types simples
    task_id: str
    title: str
    description: str | None    # ← porté pour l'import, jamais affiché (ch. 10)
    status: str
    created_at: datetime
    completed_at: datetime | None
    owner_id: str
    owner_name: str
    owner_email: str


class TaskQueryPort(ABC):
    """Chemin de LECTURE. Aucune écriture, sans exception."""

    @abstractmethod
    def stream_with_owner(self) -> AsyncIterator[TaskWithOwner]: ...

    @abstractmethod
    async def count(self) -> int: ...
```

L'**implémentation**, en `infrastructure/persistence/task/queries.py` :

```python
async def stream_with_owner(self) -> AsyncIterator[TaskWithOwner]:
    statement = (
        select(
            TaskModel.id, TaskModel.title, TaskModel.description, TaskModel.status,
            TaskModel.created_at, TaskModel.completed_at,
            UserModel.id.label("owner_id"),
            UserModel.name.label("owner_name"),
            UserModel.email.label("owner_email"),
        )
        .join(UserModel, TaskModel.owner_id == UserModel.id)
        .order_by(TaskModel.created_at)
        .execution_options(yield_per=500)     # curseur serveur, mémoire constante
    )
    result = await self._session.stream(statement)
    async for row in result:
        yield TaskWithOwner(task_id=str(row.id), ...)
```

Cinq points de discipline :

- **L'implémentation vit dans l'infrastructure**, comme tout ce qui parle SQL.
- **Elle ne renvoie jamais d'entités**, seulement des DTO de lecture — sinon on
  réintroduit la navigation entre agrégats par la porte de derrière.
- **Elle est en lecture seule.** Aucun `INSERT`, aucun `UPDATE`, jamais.
- **Elle peut traverser plusieurs frontières d'agrégats**, parce qu'elle ne
  cherche ni à faire respecter ni à modifier leurs invariants : elle construit une
  **vue de lecture** adaptée au besoin. Le critère n'est pas « lecture = libre,
  écriture = interdit », c'est *est-ce que cette opération engage les invariants
  des agrégats qu'elle touche ?*. Ce qu'on veut éviter, c'est la reconstruction
  artificielle de plusieurs agrégats dans le modèle métier pour produire un écran.
- **Elle est bornée — ou elle diffuse.** Une lecture non bornée qui matérialise
  tout est une panne en attente. Ici on a choisi la seconde voie : un flux, avec
  `yield_per`, dont la mémoire ne dépend pas du volume.

### Pas de use case : le chemin de lecture est plus court

Le router appelle le port **directement**. Il n'y a rien à orchestrer : ni règle,
ni transaction à ouvrir, ni coordination entre agrégats. Ajouter un use case ne
ferait qu'insérer une indirection vide.

```text
écriture :  router → use case → domaine → repository     (4 niveaux)
lecture  :  router → query service                        (2 niveaux)
```

Cette asymétrie est visible dans l'arborescence, et c'est voulu : la lecture n'a
pas besoin des mêmes garanties, elle ne doit donc pas payer la même cérémonie.

### Streamer plutôt que paginer

L'export est diffusé en **NDJSON** — un objet JSON par ligne — dans une
`StreamingResponse`. C'est ce que le chemin par agrégats ne peut structurellement
pas offrir : il doit tout matérialiser avant de rendre la main.

> ⚠️ **Le prix du streaming** : le statut HTTP part avec le **premier octet**. Si
> la base tombe au milieu du flux, on ne peut plus renvoyer un 500 — le client
> reçoit un flux tronqué avec un `200 OK`. Un export NDJSON se valide donc en
> comparant le nombre de lignes reçues à un compte annoncé, jamais en se fiant au
> code de statut. C'est exactement ce que fait le bouton d'export du frontend.

Un détail non évident, vérifié plutôt que supposé : avec une `StreamingResponse`,
la dépendance `yield` qui fournit la session reste **ouverte pendant toute la
consommation du corps**. Sans cette propriété, le curseur serait fermé avant la
fin du flux. Le curseur vit ainsi *dans* la transaction de la requête, ce qui
reste compatible avec PgBouncer en mode transaction — seuls les curseurs
`WITH HOLD`, qui survivent au commit, y sont interdits.

### Faut-il un port ?

Deux écoles, et les deux se défendent.

| | Sans port | Avec port |
|---|---|---|
| Le router dépend de… | la classe concrète en infrastructure | une interface en `application/` |
| Cérémonie | minimale | une interface de plus |
| Test du router | exige une vraie base | doublure en mémoire possible |
| Cohérence avec ce dépôt | rompt le motif (tout passe par un port) | conforme |

Ce projet a tranché pour le **port** : la thèse du dépôt est que la règle de
dépendance est vérifiée et uniforme, et un router qui importerait directement une
classe SQLAlchemy serait le seul endroit à rompre le motif. Ailleurs, sauter le
port est parfaitement légitime — un query service *est* déjà le modèle de
lecture, et l'abstraire n'apporte parfois rien.

| Concept | Ce que dit le principe | Ce que fait ce projet |
|---------|------------------------|-----------------------|
| Chemin de lecture | Peut court-circuiter les agrégats | Agrégats pour les listes simples ; **query service** pour l'export joint ([voir plus bas](#et-ce-projet-)) |
| Abstraction des lectures | Non prescrite | Port en `application/`, implémentation en `infrastructure/` (par cohérence) |

## Quand basculer ? Le tableau de décision

| Situation | Chemin |
|---|---|
| Créer, modifier, supprimer | **Agrégats**, toujours |
| Charger un objet **pour le modifier** | **Agrégats** (il faut les invariants) |
| Afficher un objet seul, quelques champs | Agrégats — le coût est négligeable |
| Afficher une **liste** | Query service dès que la liste est longue ou fréquente |
| Afficher des données de **deux agrégats** | **Query service** |
| Compter, agréger, faire des statistiques | **Query service** (`COUNT`, `GROUP BY` — jamais en Python) |
| Exporter, alimenter un rapport | **Query service** |

Le signal le plus fiable : **tu écris une boucle Python qui refait ce qu'un
`JOIN` ou un `GROUP BY` ferait mieux.** À ce moment-là, la base est en train de
travailler pour rien.

## Et CQRS, alors ?

**CQRS** = *Command Query Responsibility Segregation* : séparer le modèle
d'**écriture** (commandes) du modèle de **lecture** (requêtes).

Attention à une confusion très répandue :

> **Query service ≠ CQRS.**

Ajouter un service de lecture est une bonne pratique locale. CQRS, au sens fort,
c'est **deux modèles distincts** — parfois deux bases, alimentées par des
projections, avec de la cohérence à terme entre les deux. C'est une architecture
lourde, justifiée par des besoins de scalabilité ou des écarts massifs entre
lecture et écriture.

Il y a un continuum, et il faut savoir où on se situe :

```text
1. Tout passe par les agrégats            ← le point de départ
2. + query services pour les lectures     ← ce projet aujourd'hui
3. + modèles de lecture dénormalisés      ← CQRS « léger »
4. + stockage de lecture séparé, projeté  ← CQRS complet
5. + événements comme source de vérité    ← Event Sourcing (autre sujet)
```

La grande majorité des applications s'arrêtent au **niveau 2** et ont raison.
C'est le meilleur rapport bénéfice/coût de toute cette liste : quelques classes
de lecture, aucune infrastructure supplémentaire, aucune cohérence à terme à
gérer. Monter d'un cran doit répondre à un problème **mesuré**, pas à une envie.

## Et ce projet ?

Il est au **niveau 2**, et de façon délibérément minimale : **un seul** chemin de
lecture, introduit parce qu'un besoin réel l'exigeait.

Ce besoin : le frontend a un bouton **« Exporter »** qui télécharge toutes les
tâches **avec les informations de leur propriétaire**. C'est le cas d'école —
deux agrégats joints, volume non borné, aucun invariant en jeu. C'est exactement
le point de bascule que ce chapitre annonçait ; il a été franchi quand il s'est
présenté, pas avant.

Le reste du projet est **resté au niveau 1**, et c'est un choix, pas un oubli :

- **Les trois endpoints de liste** (`GET /users`, `GET /tasks`,
  `GET /users/{id}/tasks`) passent toujours par les agrégats. Aucun ne joint deux
  agrégats, donc aucun n'a de N+1 : `list_by_owner` est un `SELECT` filtré sur une
  clé étrangère indexée.
- **Il y a du gaspillage résiduel**, assumé. Chaque ligne y est reconstruite en
  agrégat complet avec ses value objects, pour être aussitôt reconvertie en DTO de
  sortie. Invisible à cette échelle.
- **`ListTasksByOwner` fait deux allers-retours** : un `exists()` sur l'user, puis
  la liste. C'est le prix de la distinction entre « user inconnu » (404) et « user
  sans tâche » (liste vide). Un query service le ferait en une requête, avec un
  `LEFT JOIN` et un test sur le résultat.

C'est la leçon qui compte plus que le code : **on ne migre pas tout au niveau 2
parce qu'on a compris le niveau 2.** On y déplace ce qui le justifie, et on
mesure. Le dépôt contient les deux états côte à côte, ce qui rend la comparaison
lisible.

## À retenir

- Les agrégats protègent les **écritures**. En lecture, leur contrat coûte sans
  rien rapporter.
- Sur un chemin de lecture, on **abandonne délibérément** entités, value objects,
  invariants et séparation des agrégats. Ce n'est pas une entorse : c'est le bon
  usage.
- La règle qui ne bouge pas : **une écriture qui doit faire respecter des
  invariants passe par le modèle qui les porte** — y compris quand il y en a cent
  mille ([chapitre 10](10-ecritures-en-masse.md)).
- Un **query service** fait le SQL exact et rend un **DTO plat**, borné, en
  lecture seule.
- Le vrai danger du N+1 n'est pas la page lente, c'est la **charge base** qui
  manque ensuite aux écritures.
- **Query service ≠ CQRS.** Le niveau 2 du continuum suffit à presque tout le
  monde.

## À toi de jouer

1. Un écran affiche « mes 20 dernières tâches + le nom du propriétaire + le
   nombre total de mes tâches ». **a.** écris la signature du query service et de
   son DTO ; **b.** combien de requêtes SQL au minimum ? **c.** pourquoi ne pas
   ajouter cette méthode à `TaskRepository` ?
2. Un collègue propose que le query service renvoie des entités `Task` « pour
   réutiliser le mapper ». Donne les deux raisons de refuser.
3. Sur `GET /users/{id}/tasks`, on veut supprimer le `exists()` préalable pour
   n'avoir qu'une requête. Que perd-on du point de vue de l'appelant HTTP, et
   comment un query service pourrait-il rendre les deux à la fois ?

→ [Corrigés](14-annexes.md#c-corrigés-des-exercices)
