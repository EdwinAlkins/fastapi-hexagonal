# 10. Écrire en masse sans casser le domaine

> **TL;DR** — Le chapitre précédent jetait le domaine pour lire. On ne peut pas
> faire la même chose pour écrire : le domaine **est** la protection, et une
> écriture qui le contourne dépose dans la base des états que personne n'a
> validés. Mais « passer par le domaine » ne veut pas dire « passer par le use
> case de création » : `create()` sait fabriquer du neuf, pas **reconstituer** de
> l'existant. Le coût, lui, n'est jamais dans le domaine — il est dans les
> allers-retours. On garde donc les agrégats en mémoire et on groupe les I/O.

Le chapitre 09 s'achevait sur une règle qui ne bouge pas : *une écriture qui doit
faire respecter des invariants passe par le modèle qui les porte*. Reste à savoir ce que ça coûte quand il y en a cent
mille d'un coup — et ce que ça signifie exactement.

Le cas concret de ce dépôt : reprendre l'export NDJSON du chapitre précédent et
le **rejouer dans un autre déploiement**. Prétexte assumé — on verra plus bas que
ce scénario précis mériterait plutôt un `pg_dump` — mais il fallait une raison
d'écrire beaucoup pour montrer ce que coûte une écriture en masse.

## L'asymétrie avec la lecture

Elle mérite d'être posée clairement, parce que la tentation est grande de
transposer le raisonnement du chapitre 09.

| | Lecture | Écriture |
|---|---|---|
| Ce que protègent les agrégats | rien — on ne fait que regarder | les invariants du modèle |
| Peut-on les court-circuiter ? | **oui**, c'est même le bon usage | **non**, jamais |
| Ce qu'on optimise | la requête elle-même | le **transport** vers la base |

Un query service peut jeter le domaine parce qu'une projection n'engage aucun
invariant. Un import ne le peut pas : il introduit dans le système des états
dont il faudra répondre. Ce qu'on a le droit d'optimiser, c'est la façon dont ces
états atteignent la base — pas la vérification qu'ils sont valides.

## Le piège : `create()` ne sait pas représenter l'existant

C'est l'erreur qu'on ne voit qu'en essayant.

```python
@classmethod
def create(cls, *, owner_id, title, description=None) -> Task:
    return cls(
        id=TaskId.generate(),      # ← un NOUVEL identifiant
        status=TaskStatus.TODO,    # ← forcément TODO
        created_at=_now(),         # ← forcément maintenant
        completed_at=None,
    )
```

L'export transporte un `task_id`, un `status` qui vaut peut-être `done`, un
`created_at` d'il y a trois mois et un `completed_at`. Importer via
`CreateTask` puis `complete()` produirait **trois corruptions silencieuses** :
un identifiant neuf — donc la référence d'origine perdue et l'import plus
rejouable —, une date de création réécrite à aujourd'hui, une date de complétion
fausse.

On aurait l'impression d'être rigoureux, *puisqu'on passe par le métier*, tout
en détruisant les données. C'est le genre de bug qui ne se voit qu'à la
réconciliation, six mois plus tard.

## Reconstituer, ce n'est pas contourner

Le bon point d'entrée est le **constructeur**, exactement ce que fait déjà
`mappers.to_domain` quand il relit une ligne. Et la validation ne disparaît pas :
le constructeur construit `TaskId`, `UserId`, `TaskTitle`, `TaskStatus` — un
titre vide est refusé à l'import comme ailleurs.

La distinction à retenir :

> `create()` + les transitions répondent à « **cet état est-il atteignable ?** »
> Le constructeur + les value objects répondent à « **cet état est-il valide ?** »

Pour des entités qui existaient déjà ailleurs, la seconde question est la bonne.
La première est même activement nuisible : elle refuserait une tâche terminée
sous prétexte qu'on ne peut pas *naître* terminé.

Ce que la reconstitution ne rejoue pas, ce sont les règles de **transition** —
et c'est cohérent : elles portent sur des changements d'état, elles n'ont pas de
sens sur un état au repos.

C'est exactement la distinction du chapitre 09. Le bulk writer **ne passe pas par
le repository** — il écrit en une requête groupée — mais il passe bien par le
modèle qui porte les invariants. Ce n'est donc pas une exception à la règle, c'est
elle qui est formulée au bon niveau : ce qu'on ne contourne jamais, c'est le
modèle ; le chemin de persistance, lui, se négocie.

### Le trou que les value objects ne voient pas

Un value object valide **un** champ. Il ne peut rien dire d'une incohérence entre
plusieurs : un `status = "todo"` accompagné d'un `completed_at` renseigné passe
sans broncher. C'est un invariant de l'**entité**, et il faut donc le poser là :

```python
@classmethod
def reconstitute(cls, *, id, owner_id, title, description, status,
                 created_at, completed_at) -> Task:
    if status is TaskStatus.DONE and completed_at is None:
        raise InconsistentTaskState("une tâche terminée doit porter une date de complétion")
    if status is not TaskStatus.DONE and completed_at is not None:
        raise InconsistentTaskState("une tâche non terminée ne peut pas porter de date de complétion")
    if completed_at is not None and completed_at < created_at:
        raise InconsistentTaskState("la complétion précède la création")
    return cls(...)
```

`reconstitute` est délibérément **plus stricte que le mapper**. `to_domain` relit
*notre* base, dont nous sommes la source de vérité ; un import relit un fichier
dont nous ne garantissons rien. La même opération technique, deux niveaux de
confiance — et donc deux méthodes.

## Où part vraiment le temps

Pas dans le domaine. Construire 100 000 agrégats avec leurs value objects, c'est
du CPU pur : de l'ordre de la seconde. Le coût est ailleurs, et il se compte en
lisant le chemin unitaire :

| Étape | Coût par ligne |
|---|---|
| `CreateTask` → `users.exists(owner_id)` | 1 `SELECT` |
| `repository.save()` → `session.get(TaskModel, id)` | 1 `SELECT` |
| flush | 1 `INSERT` |

**Trois allers-retours par ligne**, soit 300 000 requêtes pour 100 000 tâches.
C'est le N+1 du chapitre 09, vu du côté écriture.

D'où le principe : **garder le domaine en mémoire, grouper les I/O.**

### La mesure

Aller-retour complet sur ce dépôt — export de 2 000 tâches réparties entre 50
propriétaires, base vidée, puis import — en comptant les requêtes réellement
émises :

| Chemin | Requêtes SQL |
|---|---|
| Unitaire (`CreateTask` ligne à ligne) | **6 000** (2 000 `INSERT` + 4 000 `SELECT`) |
| Import groupé (lots de 1 000) | **5** (4 `INSERT` + 1 `SELECT`) |

Rejouer le même fichier insère **0** ligne.

## L'échelle d'optimisation

| # | Geste | Effet |
|---|---|---|
| 1 | Supprimer le contrôle d'existence ligne à ligne | N `SELECT` → 0 ou 1 par lot |
| 2 | Supprimer la lecture-avant-écriture : à l'import on sait qu'on insère | N `SELECT` → 0 |
| 3 | `INSERT` multi-lignes (`insertmanyvalues`) par lots | N `INSERT` → N/1000 |
| 4 | Très gros volumes : `COPY` vers une table de transit, puis `INSERT … SELECT` | ~5–10× sur l'insertion |

Le geste 1 mérite un mot. `CreateTask` vérifie l'existence du propriétaire par
une requête ; ici l'export est **dénormalisé** — chaque ligne porte son
propriétaire — donc on l'insère avant la tâche et la question ne se pose plus.
Une requête groupée aurait déjà été un progrès ; zéro est mieux.

Et un choix des chapitres précédents devient ici un avantage décisif : les
**identités sont des UUIDv7 générées par le domaine**. Le lot entier se construit
donc en mémoire avant de toucher la base — ni `RETURNING`, ni aller-retour pour
apprendre un identifiant — et le préfixe temporel maintient les insertions au
bord droit de l'index, là où un `uuid4()` fragmenterait le B-tree.

## `ON CONFLICT` et sa limite

L'insertion groupée s'appuie sur `ON CONFLICT DO NOTHING` : une identité déjà
présente est ignorée plutôt qu'écrasée ou remontée en erreur. C'est ce qui rend
l'import **idempotent**, donc reprenable.

> ⚠️ **`ON CONFLICT` absorbe les conflits d'unicité. Il n'absorbe pas les
> violations de clé étrangère.**

La nuance a l'air technique ; elle est structurante. Si un utilisateur du fichier
porte un e-mail déjà détenu par une **autre** identité, il est ignoré — et ses
tâches violent alors la clé étrangère, ce qui fait échouer l'`INSERT` **entier**.
Une ligne douteuse emporte les 999 autres.

Il faut donc savoir qui est réellement entré, et c'est là que le contrôle groupé
revient : une requête par **lot**, et seulement quand un utilisateur a été
ignoré. Sur un import dans une base vierge — le cas courant — elle ne coûte rien.

Cette limite mérite d'être connue pour elle-même : c'est un cas où l'intuition
(« `DO NOTHING` va tout absorber ») est fausse, et où seule l'exécution contre un
vrai PostgreSQL le dit.

## La transaction : ni une par ligne, ni une pour tout

C'est ici que le chapitre 08 se nuance, et il faut le dire franchement.

La règle posée là-bas — *les repositories ne committent jamais, la frontière
transactionnelle appartient à l'adaptateur driving et entoure le use case* —
reste vraie pour tout ce qui répond à une requête. Un import en masse est le
contre-exemple assumé.

Une transaction unique de dix minutes serait un **défaut**, pas une garantie :

- avec **PgBouncer en mode transaction**, elle épingle une connexion serveur
  pendant toute sa durée — sur un pool de 20, c'est 5 % de la capacité retirée ;
- le WAL enfle, les lignes mortes s'accumulent ;
- un échec à 99 % perd les 99 %.

On découpe donc en lots, ce qui suppose de committer **pendant** le use case.

### Le port `UnitOfWork`

Comment committer sans qu'un use case connaisse SQLAlchemy ? En l'exprimant comme
un besoin, c'est-à-dire — chapitre 06 — par un port :

```python
class UnitOfWorkPort(ABC):
    """Rend durable ce qui a été écrit depuis le dernier point d'acquisition."""

    @abstractmethod
    async def commit(self) -> None: ...
```

Le use case dit « ce lot est acquis » ; l'adaptateur sait que cela signifie
`session.commit()`. La règle de dépendance est intacte.

Trois remarques sur ce port, parce qu'il est facile d'en mésuser :

- **Ce n'est pas le motif *Unit of Work* complet** de Fowler, qui suit les objets
  modifiés et décide quoi écrire. Ici, la session SQLAlchemy joue déjà ce rôle ;
  le port n'expose que le **point d'acquisition**.
- **Il ne rend pas le commit banal.** C'est la seule classe du dépôt, hors
  adaptateurs driving, à committer, et un use case doit le **demander
  explicitement** par son constructeur. On ne l'obtient jamais par effet de bord
  d'un repository — ce qui reste la règle du chapitre 08.
- **Il ne se justifie que par la durée.** Un use case qui répond à une requête
  HTTP n'a aucune raison de le prendre : sa transaction est déjà à la bonne
  taille. Le port existe parce que le traitement dure, pas parce qu'il écrit
  beaucoup.

### Ce qu'on échange

L'import **n'est pas atomique**, et c'est le comportement voulu. On échange
l'atomicité globale contre la **reprise** — ce qui n'est acceptable que parce que
les écritures sont idempotentes. Les deux décisions se tiennent : sans
idempotence, un import non atomique serait ingérable ; sans découpage,
l'idempotence serait inutile.

C'est le même raisonnement que l'*at-least-once* du chapitre suivant : on ne
cherche pas à garantir qu'une opération ne s'exécutera qu'une fois, on rend la
seconde exécution inoffensive.

## Rendre un rapport, pas un verdict

À 100 000 lignes, « tout ou rien » est un mauvais contrat : une seule ligne
douteuse condamnerait le lot. Le use case rend donc un bilan — lignes lues,
insérées, déjà présentes, **rejetées avec leur raison**.

Et c'est l'argument le moins évident en faveur du domaine dans un import. Un
`COPY` brut sur 100 000 lignes rend une erreur PostgreSQL opaque à la ligne
47 231 et s'arrête là. Le domaine, lui, sait dire :

```text
rang 47231 (01930000-…) : Adresse e-mail invalide : 'ada@@example.com'.
```

Les exceptions métier ne servent pas qu'à protéger la base : elles rendent
l'échec **diagnosticable**. C'est un bénéfice qu'on n'attend pas d'une couche
« architecture », et c'est souvent celui qui convainc.

## Restaurer n'est pas importer

Le piège le plus coûteux n'est pas de mal optimiser : c'est de se tromper de
catégorie. Avant d'écrire une ligne, il faut trancher.

| | Restauration | Import |
|---|---|---|
| D'où viennent les données | du même système, même version | d'ailleurs, ou d'un fichier édité |
| L'état était-il déjà valide ici ? | oui | on n'en sait rien |
| Le bon outil | `pg_dump` / `pg_restore` | le domaine |

Faire transiter une restauration par le métier serait plus lent, plus fragile et
sans bénéfice : on revaliderait des données que l'on a soi-même produites.
Inversement, importer des données étrangères par `pg_restore`, c'est renoncer à
toute garantie.

> **Et ce dépôt, alors ?**
>
> Appliqué honnêtement, ce critère range le scénario implémenté ici — même schéma,
> même version, d'un déploiement à l'autre — du côté de la **restauration**.
> `pg_dump` ferait le travail, plus vite, sans une ligne de code et sans rien
> perdre. L'import de ce dépôt est donc un **support pédagogique** : il fallait
> une écriture coûteuse pour montrer ce qu'elle coûte, et à quoi ressemble le
> chemin correct quand elle est justifiée.
>
> Ce n'est pas une coquetterie d'auteur. C'est la question à poser **avant** toute
> l'ingénierie de ce chapitre : *ai-je seulement besoin d'un import ?* La réponse
> est souvent non, et elle épargne alors un use case, deux ports, deux adaptateurs
> et leurs tests. Le meilleur code d'import reste celui qu'on n'écrit pas.

### Et le format ?

Ce dépôt réutilise le DTO d'export `TaskWithOwner` comme format d'import. C'est
un raccourci **assumé mais critiquable** : `TaskWithOwner` est un modèle de
**lecture**, dessiné pour un bouton dans une interface. Le lier au chemin d'import
signifie que le jour où l'on ajoute une colonne pour l'affichage, on change le
format d'échange sans le savoir.

Le défaut s'est manifesté aussitôt, et sa correction est plus instructive que le
défaut lui-même. L'export ne transportait pas `description` : un aller-retour
perdait donc les descriptions. Pour que l'import soit fidèle, on a ajouté le champ
au DTO d'**export** — c'est-à-dire au modèle de **lecture**.

Regarde bien le sens de ce qui vient de se passer. `TaskWithOwner` porte désormais
une colonne qu'**aucun écran n'affiche**, présente uniquement pour le chemin
d'écriture. Le couplage annoncé s'est réalisé, mais dans l'autre sens : ce n'est
pas l'affichage qui a pollué l'import, c'est l'import qui a pollué l'affichage. Un
format d'échange dédié aurait absorbé le besoin sans toucher au modèle de lecture.

Un vrai transfert entre déploiements mérite son propre format, **versionné**, et
découplé de ce que l'écran affiche.

Et le raccourci se paie tout de suite, pas plus tard : l'API diffuse du NDJSON,
tandis que le bouton du frontend enregistre un **tableau JSON** — deux formats pour
la même donnée, dont aucun n'est spécifié quelque part. Le premier fichier
téléchargé depuis l'interface s'est donc révélé **inimportable** par le CLI du même
dépôt. Le lecteur accepte désormais les deux, ce qui est un rattrapage, pas une
conception : un format d'échange qui n'existe que dans le code qui l'écrit finit
toujours par diverger de celui qui le lit.

## Où ça vit

| Élément | Emplacement |
|---|---|
| `Task.reconstitute` / `User.reconstitute` | `domain/<ctx>/entities.py` |
| `InconsistentTaskState` | `domain/task/exceptions.py` |
| `TaskBulkWriterPort`, `UserBulkWriterPort` | `application/<ctx>/bulk.py` |
| `UnitOfWorkPort` | `application/shared/unit_of_work.py` |
| `ImportTasks`, `ImportReport` | `application/task/` |
| `SqlAlchemy*BulkWriter`, `SqlAlchemyUnitOfWork` | `infrastructure/persistence/` |
| Commande `import-tasks` | `presentation/cli/app.py` |

Deux choix de structure méritent d'être justifiés.

**Un port séparé plutôt qu'un `save_all` sur le repository.** Le repository est le
port de cycle de vie de l'**agrégat** : il parle en `Task`, sert les écritures
unitaires et garantit un contrat de lecture-modification-écriture. Y greffer une
écriture groupée le transformerait peu à peu en couche d'accès générique. Le bulk
writer est un besoin distinct, il a son port — symétrique du query service du
chapitre 09.

**Une commande CLI, pas une route HTTP.** Un import tient des minutes ; une
requête HTTP doit rendre la main. C'est l'illustration la plus nette du principe
du chapitre 08 : la transaction entoure **le use case**, et l'adaptateur driving
qui la porte n'est pas forcément HTTP.

## À retenir

- **En lecture on jette le domaine ; en écriture on ne le peut pas.** C'est
  l'asymétrie qui gouverne tout le reste.
- « Passer par le domaine » ≠ « passer par le use case de création ».
  `create()` fabrique du neuf, **`reconstitute()` relit de l'existant**.
- Les invariants **inter-champs** ne peuvent pas vivre dans un value object : ils
  appartiennent à l'entité, et c'est la reconstitution qui les rejoue.
- **Le domaine n'est pas le coût.** Les allers-retours le sont : on garde les
  agrégats en mémoire et on groupe les I/O.
- `ON CONFLICT` absorbe les conflits d'unicité, **pas** les violations de clé
  étrangère.
- Un traitement long **découpe sa transaction**, et le demande explicitement par
  un `UnitOfWorkPort`. Il échange l'atomicité contre la reprise — ce que seule
  l'**idempotence** rend acceptable.
- Un import rend un **rapport**, pas un verdict. Les exceptions métier rendent
  l'échec diagnosticable.
- **Restaurer ≠ importer.** Se tromper de catégorie coûte plus cher que mal
  optimiser — et la bonne catégorie supprime parfois le besoin d'écrire du code.
  L'import de ce dépôt relève, par son propre critère, du `pg_dump` : il est là
  pour l'exemple.

## À toi de jouer

1. On te demande d'exposer l'import en `POST /api/v1/imports/tasks`, « pour que
   le front puisse déclencher la reprise ». **a.** deux raisons techniques de
   refuser ; **b.** quelle forme donnerais-tu à la fonctionnalité si le besoin
   est réel ?
2. Un collègue propose de supprimer `Task.reconstitute` et d'appeler directement
   le constructeur, « puisque c'est ce qu'il fait ». Qu'est-ce qu'on perd
   exactement ?
3. L'import tourne sur un fichier de 5 millions de lignes et sature la mémoire.
   Où chercherais-tu la fuite en premier, sachant que le use case consomme un
   générateur ?
4. On veut que l'import **mette à jour** les tâches déjà présentes au lieu de les
   ignorer (`DO UPDATE` plutôt que `DO NOTHING`). Quel invariant du chapitre 04
   cela met-il en danger, et que faudrait-il faire à la place ?

→ [Corrigés](14-annexes.md#c-corrigés-des-exercices)
