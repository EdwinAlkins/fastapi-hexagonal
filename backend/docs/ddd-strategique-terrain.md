# DDD stratégique — carnet de terrain

> **Ce document n'est pas un chapitre du cours.** Le [cours](cours/README.md)
> enseigne le DDD *tactique* : ce qui se code. Ce carnet traite du DDD
> *stratégique* : ce qui se décide **avant** de coder, en salle, avec des gens
> qui ne sont pas développeurs. Il est écrit pour être *fait*, pas lu.
>
> Il contient aussi un diagnostic honnête de ce dépôt, à la fin. Il ne va pas te
> plaire complètement.

---

## 1. Pourquoi ce document existe séparément

Le cours ne peut pas enseigner le stratégique, pour une raison structurelle :
**il s'adosse à un dépôt de code, et le stratégique ne produit pas de code.**

Il produit des décisions de frontières. Or une frontière ne se lit pas dans un
fichier — elle se lit dans ce que *plusieurs personnes* entendent quand elles
disent le même mot. Un dépôt te montre le résultat d'un découpage ; il ne peut
pas te montrer le raisonnement qui l'a produit, ni les trois découpages écartés.

D'où le déséquilibre assumé : le cours consacre 12 chapitres au tactique et une
section au stratégique. Ce carnet corrige le tir dans le seul format qui a du
sens — une **procédure à exécuter**, pas une explication à comprendre.

### Le vrai enjeu, en une phrase

> Se tromper de pattern coûte une refonte de classe. Se tromper de frontière
> coûte une refonte de système.

Un modèle tactique impeccable posé sur de mauvaises frontières produit un système
propre localement et incohérent globalement — le pire cas, parce qu'il a l'air
bon. C'est pour ça que l'ordre compte : **stratégique d'abord, tactique ensuite.**

---

## 2. Le quoi : ce que le stratégique décide réellement

Trois décisions, et rien d'autre :

| Décision | Question à laquelle elle répond | Livrable |
|---|---|---|
| **Langage ubiquitaire** | Quel mot pour quelle chose, et qui l'emploie ? | Un glossaire par contexte |
| **Bounded contexts** | Où passent les frontières de sens ? | Une liste de contextes nommés |
| **Context map** | Comment les contextes se parlent, et qui subit qui ? | Un schéma de relations |

Ce ne sont pas des artefacts de documentation. Ce sont des **contrats** : le
glossaire dit ce que le code a le droit de nommer, les contextes disent ce qui a
le droit de dépendre de quoi, la context map dit qui casse qui en cas de
changement.

### La définition qui sert vraiment

Un **bounded context** est une frontière à l'intérieur de laquelle un **modèle
et son langage sont cohérents**, et dont les règles de signification sont
maîtrisées.

L'indice le plus facile à observer tient en une phrase : **si deux personnes
emploient le même mot pour deux choses différentes, examine une séparation.** Pas
« elles devraient s'accorder » — elles ont *raison* toutes les deux, dans leur
contexte. Attention toutefois : c'est un signal fort, pas une preuve. La
frontière se décide sur le modèle, pas sur un lexique.

Le réflexe à désapprendre : chercher le modèle unique qui satisfait tout le
monde. Il n'existe pas, et le poursuivre produit toujours la même chose — une
classe qui grossit, pleine de champs optionnels qui n'ont de sens que pour la
moitié des appelants, que plus personne n'ose modifier.

> **Le dédoublement d'un concept entre deux contextes n'est pas de la duplication
> à éliminer.** C'est le point où presque tout le monde se trompe, parce que dix
> ans d'entraînement à factoriser disent le contraire.

---

## 3. Le pourquoi : les symptômes de frontières fausses

Avant de lancer un atelier, vérifie que tu en as besoin. Voici les symptômes
observables — certains directement dans ton dépôt.

| Symptôme | Ce qu'il révèle | Comment le repérer |
|---|---|---|
| Une classe centrale que tout le monde importe (`User`, `Order`, `Product`) | Plusieurs contextes fusionnés de force | `grep -rc "import User"` — si c'est partout, c'est le signal |
| Des champs optionnels par groupes (« ces 6 champs ne servent qu'à la facturation ») | Deux concepts dans une classe | Lire les `| None` et voir s'ils se regroupent |
| Un même mot défini différemment selon l'interlocuteur | Frontière de sens non nommée | Écouter deux réunions métier |
| Des commits qui touchent systématiquement 5 modules | Frontière au mauvais endroit | `git log --name-only` sur 3 mois |
| Un « service » ou un « manager » qui grossit sans fin | Le contexte manquant est là, sans nom | Chercher les classes > 300 lignes |
| Des tables jointes en permanence dans les requêtes | Cohésion réelle non reflétée | Lire les `JOIN` récurrents |

Si tu n'as **aucun** de ces symptômes, tu n'as probablement pas de problème
stratégique — et tu peux ranger ce document. C'est le cas de ce dépôt
aujourd'hui, pour une raison qu'on verra en section 7.

---

## 4. Le comment : la procédure

Voici ce que tu fais concrètement. Compte une journée pour un système de taille
moyenne, ou deux demi-journées espacées d'une semaine (mieux : le cerveau
travaille entre les deux).

### Étape 0 — Réunir les bonnes personnes

C'est l'étape qu'on rate le plus souvent, et elle décide de tout le reste.

**Qui doit être là :**
- **1 à 3 experts métier** — les gens qui *font* le travail, pas ceux qui le
  managent. Le commercial qui saisit les commandes vaut mieux que le directeur
  commercial.
- **2 à 5 développeurs** — dont ceux qui maintiendront le code.
- **1 facilitateur** — qui ne prend pas parti sur le modèle, et dont le seul job
  est de faire parler les experts et d'empêcher les développeurs de parler
  technique.

**Qui ne doit pas être là :** personne qui a un intérêt à défendre une
architecture existante. Y compris toi, si tu as écrit le code actuel — d'où le
facilitateur externe.

**Le matériel :** un mur, des post-its de 4 couleurs, des marqueurs. Pas
d'écran, pas de Miro tant que le mur physique est possible. La contrainte
physique force la synthèse ; l'infini du canvas numérique la dissout.

**La règle d'or** : les développeurs écoutent et écrivent, ils ne proposent pas
de modèle. Dès qu'on entend « on pourrait faire une table… », le facilitateur
coupe.

### Étape 1 — EventStorming *big picture* (2 à 3 h)

L'outil le plus efficace pour cette phase. La version minimale :

1. **Les événements** (post-its orange). Chaque participant écrit tout ce qui
   *arrive* dans le système, **au passé** : « Commande passée », « Paiement
   accepté », « Colis expédié », « Tâche terminée ». Pas de discussion pendant
   20 minutes, on écrit en silence et on colle.
2. **La ligne de temps.** On ordonne les post-its de gauche à droite. Les
   doublons apparaissent, les trous aussi. C'est bruyant et c'est normal.
3. **Les points chauds** (post-its rouges). À chaque désaccord ou question sans
   réponse : un post-it rouge, et **on avance**. Ne jamais résoudre un désaccord
   sur le moment — le noter est plus précieux que le trancher.
4. **Les acteurs et les systèmes externes.** Qui déclenche quoi, qui reçoit quoi.

**Livrable de l'étape** : un mur d'événements ordonnés, photographié. Et la liste
des points rouges — qui vaut souvent plus que le reste.

### Étape 2 — Repérer les ruptures

C'est ici que les frontières apparaissent. Tu cherches trois choses sur ton mur :

- **Les ruptures de vocabulaire.** Le moment où « client » cesse de vouloir dire
  *prospect à convaincre* pour vouloir dire *adresse de livraison*. Marque-le.
- **Les pivots temporels.** Les endroits où le processus attend : validation
  humaine, paiement externe, livraison. Une attente est presque toujours une
  frontière — parce que la cohérence immédiate y est déjà impossible.
- **Les changements d'acteur.** Quand la personne qui agit change, le
  vocabulaire change presque toujours avec.

**L'exercice décisif** : prends chaque nom important et demande à voix haute
*« est-ce que ça veut dire la même chose ici et là ? »*. Note chaque « ah non,
pas tout à fait ». **Chaque « pas tout à fait » est une frontière.**

### Étape 3 — Nommer les contextes candidats

Entoure des zones du mur, donne-leur un nom **issu du métier** (`Facturation`,
`Expédition`, `Catalogue`) — jamais un nom technique (`Core`, `Common`,
`Referentiel`).

Puis, pour chacun, écris le **glossaire** : 5 à 15 termes, leur définition dans
*ce* contexte. Le glossaire est le livrable qui survit le mieux au temps ; c'est
souvent le seul artefact encore lu deux ans après.

Un contexte sans glossaire rédigé n'est pas un contexte, c'est un dossier.

### Étape 4 — Dessiner la context map

Pour chaque paire de contextes qui se parlent, choisis une relation :

| Relation | Ce que ça veut dire | Quand la choisir | Coût |
|---|---|---|---|
| **Shared kernel** | Un petit noyau commun, modifié d'un commun accord | Équipes très proches, noyau vraiment stable | Élevé à terme : tout changement se négocie |
| **Customer / supplier** | L'amont s'engage à servir l'aval ; l'aval peut négocier | Deux équipes, dépendance assumée | Moyen : demande une vraie relation |
| **Conformist** | L'aval adopte tel quel le modèle de l'amont | L'amont ne bougera jamais (SI historique, API tierce) | Faible à court terme, empoisonnant à long terme |
| **Anti-corruption layer** | L'aval traduit le modèle amont dans le sien | Le modèle amont est inadapté ou instable | Le plus coûteux à écrire, le moins coûteux à vivre |

Ajoute une flèche par relation, et **écris le sens de la dépendance** — c'est-à-
dire qui casse qui quand ça change. C'est l'information la plus utile de tout le
schéma.

L'**anti-corruption layer** est celle à connaître par cœur. C'est exactement le
principe que le cours applique partout à petite échelle : un mapper protège ton
domaine de l'ORM, un ACL protège ton contexte du modèle d'un autre système.
Chaque fois que tu intègres un truc que tu ne contrôles pas — un CRM, une API de
paiement, le SI d'un client — la question n'est pas *si* tu écris un ACL, mais
quand tu regretteras de ne pas l'avoir fait.

### Étape 5 — Décider quoi implémenter, et dans quel ordre

Tous les contextes identifiés ne méritent pas d'exister dans le code
**aujourd'hui**. Classe-les :

- **Le cœur** (*core domain*) — ce qui fait la valeur, ce que personne d'autre ne
  fait à ta place. C'est là que va l'effort tactique du cours : agrégats,
  invariants, tests. Il y en a **un**, rarement deux.
- **Le support** — nécessaire mais banal. Un CRUD honnête suffit
  ([ch. 11](cours/13-demarrer-un-projet.md#quand-ne-pas-utiliser-cette-architecture)).
- **Le générique** — auth, facturation, notifications. **Achète, n'écris pas.**

L'erreur classique est d'appliquer le traitement complet du cours aux trois
catégories. Le vrai geste stratégique, c'est de décider **où tu n'investis pas**.

---

## 5. Les tests de validation d'une frontière

Avant d'acter un découpage, passe-le à ces cinq tests. Chacun peut le
disqualifier à lui seul.

1. **Le test du mot** — un terme a-t-il exactement un sens dans ce contexte ? S'il
   en a deux, la frontière est probablement mal placée. Signal fort, pas preuve :
   c'est la cohérence du *modèle* qui tranche, pas le lexique seul.
2. **Le test de la transaction** — ce qui doit être cohérent *immédiatement*
   est-il à l'intérieur ? Si une règle exige une cohérence instantanée entre deux
   contextes, ils n'en font qu'un ([ch. 04](cours/04-les-agregats.md)).
3. **Le test de l'équipe** — une équipe peut-elle posséder ce contexte de bout en
   bout ? Un contexte qui exige trois équipes pour bouger n'est pas autonome.
   (Corollaire de la loi de Conway : ton découpage finira par ressembler à ton
   organigramme, que tu le veuilles ou non. Autant le choisir.)
4. **Le test du déploiement** — pourrait-il être déployé seul, en théorie ? Tu
   n'es pas obligé de le faire. Mais si la réponse est « impossible », la
   frontière est fictive.
5. **Le test du glossaire** — peux-tu écrire 10 termes définis sans jamais
   renvoyer à un autre contexte ? Si chaque définition dit « voir le contexte
   X », il n'y a qu'un contexte.

---

## 6. Ce que ça change dans le code

Une fois les frontières décidées, voici ce qui se traduit concrètement — et
surtout ce qui **ne** se traduit **pas**.

**Ce qui change :**
- Un package racine par contexte, avec sa propre tranche verticale complète.
- **Aucun import direct** d'un contexte vers un autre, sauf identités. Ce dépôt
  respecte déjà ça : `task` importe `UserId` et rien d'autre.
- Un contrat explicite à chaque frontière : identité partagée, événement
  d'intégration, ou ACL.
- Une règle import-linter par frontière, pour que ça reste vrai
  ([ch. 01](cours/01-regle-de-dependance.md)).

**Ce qui ne change pas nécessairement :**
- **Le nombre de bases de données.** Un contexte peut vivre dans un schéma
  logique de la même base. Séparer physiquement est une décision de déploiement,
  pas de modélisation.
- **Le nombre de services déployés.** Un monolithe modulaire à 4 contextes est
  souvent supérieur à 4 microservices — et infiniment plus facile à corriger
  quand une frontière s'avère fausse.
- **L'existence d'un shared kernel minimal.** Quelques classes sans logique
  (bases d'exceptions, types techniques) sont acceptables. Dès qu'une **règle** y
  entre, il faut le découper.

> **La séquence saine** : découpe d'abord en modules dans un monolithe. Vis avec
> six mois. Extrais ensuite ce qui a prouvé son autonomie. L'inverse — extraire
> avant d'avoir vécu avec — est la façon la plus fiable de figer une mauvaise
> frontière dans du réseau.

---

## 7. Diagnostic de ce dépôt

La partie que tu voulais. Elle est directe.

### Ce que le dépôt appelle « bounded contexts » n'en est probablement pas

`task` et `user` sont présentés partout — README, `CLAUDE.md`, cours — comme deux
bounded contexts. Passons-les aux cinq tests de la section 5 :

| Test | Résultat |
|---|---|
| Le mot | ❌ `User` a **un seul** sens dans tout le système : le propriétaire d'une tâche. Aucune rupture de vocabulaire. |
| La transaction | ⚠️ `CreateTask` vérifie l'existence du user **dans la même transaction**, et une FK `ON DELETE CASCADE` lie les tables. Cohérence immédiate exigée. |
| L'équipe | ❌ Une seule équipe, un seul dépôt, une seule personne. |
| Le déploiement | ❌ Un service, une base, une migration `001_initial_schema.py` qui crée les deux tables. |
| Le glossaire | ❌ Impossible d'écrire 10 termes de `task` sans parler de `user`, et réciproquement. |

**Verdict** : ce sont **deux agrégats dans un seul bounded context**, organisés en
modules. Pas deux contextes.

### Pourquoi ce n'est pas grave — et pourquoi il faut quand même le savoir

Ce n'est pas grave, pour trois raisons :

1. **Le découpage est bon quand même.** Deux agrégats bien séparés, référencés
   par identité, sans import croisé, c'est exactement ce qu'il faut faire. Le
   travail est juste ; c'est l'**étiquette** qui est trop ambitieuse.
2. **Le métier ne justifie pas deux contextes.** Le README le dit lui-même : « le
   métier est volontairement simple ». Un domaine à deux entités n'a
   structurellement pas assez de sens pour avoir deux vocabulaires.
3. **Ça prépare bien la suite.** Le fait que `task` ne connaisse qu'un `UserId`
   rend l'extraction future presque gratuite. C'est le bénéfice réel, et il est
   acquis.

Mais il faut le savoir, pour une raison précise : **le dépôt se présente comme
une référence à reproduire.** Quelqu'un qui le copie apprend « bounded context =
sous-dossier par entité ». C'est le contresens exact que la section stratégique
du cours essaie d'éviter — et le dépôt l'enseigne par l'exemple sans le dire.

### Les trois corrections que je ferais

Par ordre de rapport valeur/effort :

**1. Corriger le vocabulaire (30 minutes, gros gain).** Remplacer « deux bounded
contexts » par « deux **modules**, ou deux agrégats, tranchés verticalement » dans
le README racine, `backend/README.md` et `CLAUDE.md`. Ajouter une phrase :

> Ces deux tranches sont des **modules**, pas des bounded contexts : `User` a un
> seul sens dans tout le système. Le découpage vertical prépare une extraction
> future, il ne prétend pas à une frontière de sens.

Ça transforme une imprécision en leçon — et c'est plus honnête que ce que fait
99 % des dépôts « DDD » sur GitHub.

**2. Introduire un vrai second contexte, si tu veux démontrer le stratégique
(1 à 2 jours).** Le candidat évident est là et il manque : **l'authentification**.
Le dépôt n'en a aucune (`grep` sur `auth|jwt|token|password` dans `src/` : zéro
résultat), et c'est le cas d'école parfait, parce que le mot `User` y prend enfin
un **second sens** :

| | Contexte `identity` | Contexte `task` |
|---|---|---|
| `User` désigne | un compte : identifiants, mot de passe haché, sessions, rôles | un propriétaire : un nom, un e-mail de contact |
| Cycle de vie | création, activation, verrouillage, suppression RGPD | existe tant qu'il a des tâches |
| Ce qui traverse | `UserId`, et rien d'autre | — |

Voilà une **vraie** rupture de vocabulaire, et donc une vraie frontière. Elle
justifierait un ACL minuscule et démontrerait le stratégique par le code, ce que
le dépôt ne fait pas aujourd'hui. C'est aussi utile en soi : une API de démo sans
authentification est incomplète.

**3. Écrire le glossaire (2 heures).** Un `docs/glossaire.md` avec les termes du
métier et leur définition. C'est le livrable stratégique le moins cher et le plus
durable. Aujourd'hui, le langage ubiquitaire du dépôt existe *dans le code*
(`TaskAlreadyCompleted`, `EmailAlreadyUsed`) mais n'est écrit nulle part — donc
rien ne garantit qu'il reste cohérent quand tu ajouteras un contexte.

### Ce que je ne ferais pas

- **Découper `task` et `user` en deux services.** Aucun test de la section 5 ne
  le justifie, et ça coûterait la cohérence référentielle (la FK
  `ON DELETE CASCADE` deviendrait un processus de compensation).
- **Ajouter des contextes fictifs pour la démonstration.** Un `billing` sans
  besoin réel produirait exactement le mauvais exemple : des frontières
  décoratives.
- **Renommer les dossiers.** `domain/task/` et `domain/user/` sont bien nommés.
  C'est la **prose** autour qui sur-vend, pas la structure.

---

## 8. Pièges spécifiques à ta position

Tu es dans une configuration particulière — un dépôt de référence, écrit seul —
qui a ses pièges propres :

- **Pas d'expert métier.** Tu es à la fois le développeur et le client. Le
  stratégique est donc *impossible à pratiquer réellement* ici : il n'y a
  personne dont le vocabulaire diverge du tien. C'est la raison de fond du
  déséquilibre du cours, et aucune quantité d'écriture ne la contourne.
- **Le métier « volontairement simple » est un choix qui a un coût.** Il rend le
  dépôt lisible et rend le stratégique indémontrable. Assume-le explicitement
  plutôt que de laisser croire le contraire.
- **La tentation de la complétude.** Ajouter `billing`, `notification`, `audit`
  pour « montrer plus » abîmerait le dépôt. Sa valeur vient de ce qu'il est
  entièrement lisible en une soirée.
- **Le vocabulaire qui se sur-vend tout seul.** « Bounded context » sonne mieux
  que « module ». C'est précisément pour ça qu'il faut se surveiller : le mot le
  plus prestigieux est rarement le plus exact.

---

## 9. Ta prochaine action concrète

Si tu ne fais qu'une chose : **la correction n° 1** (le vocabulaire, 30 minutes).
Elle transforme le seul point du dépôt qui enseigne quelque chose de faux.

Si tu as deux jours : **la correction n° 2** (le contexte `identity`). C'est la
seule façon de faire passer le stratégique du texte à la démonstration — et le
seul moment où ce carnet deviendrait un chapitre légitime du cours.

Si tu veux pratiquer pour de vrai : **fais l'atelier de la section 4 sur un
système que tu connais au travail**, pas sur celui-ci. C'est là que le
stratégique s'apprend, et nulle part ailleurs.

---

## 10. Pour aller plus loin

- **Domain-Driven Design** (Eric Evans) — parties **IV et V**, les deux tiers du
  livre que presque personne ne lit. C'est là qu'est le stratégique.
- **Domain-Driven Design Distilled** (Vaughn Vernon) — 150 pages, va droit au
  stratégique. Le meilleur rapport temps/valeur du domaine.
- **Introducing EventStorming** (Alberto Brandolini) — la méthode de l'étape 1,
  par son auteur.
- **Team Topologies** (Skelton & Pais) — le lien entre frontières logicielles et
  frontières d'équipes ; le complément moderne indispensable au chapitre
  « contextes » d'Evans.
