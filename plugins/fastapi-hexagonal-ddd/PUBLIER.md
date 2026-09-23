# Publier le plugin `fastapi-hexagonal-ddd`

> **TL;DR** — « Publier » recouvre **deux choses différentes** : distribuer depuis
> ton dépôt GitHub (immédiat, sous ton contrôle) et entrer dans un **catalogue
> public** Anthropic ou OpenAI (soumission, revue, validation par un tiers). Le
> premier marche déjà aujourd'hui ; le second demande une release figée et une
> identité vérifiée. Garde **un seul dépôt** pour les deux.

## Les quatre canaux, et ce qu'ils coûtent

| Canal | Qui décide | Ce que l'utilisateur tape | État ici |
|---|---|---|---|
| Marketplace GitHub, Claude Code | toi | `/plugin marketplace add EdwinAlkins/fastapi-hexagonal` | **prêt** |
| Marketplace GitHub, Codex | toi | `codex plugin marketplace add EdwinAlkins/fastapi-hexagonal` | **prêt** |
| Catalogue public Claude (`claude-community`) | Anthropic, après revue | `/plugin install fastapi-hexagonal-ddd@claude-community` | à soumettre |
| Annuaire public OpenAI (ChatGPT **et** Codex) | OpenAI, après revue | installation depuis l'annuaire | à soumettre |

Les deux premiers ne demandent l'autorisation de personne : un dépôt Git public
avec les bons manifestes **est** un marketplace. Les deux derniers sont des
vitrines dont tu ne contrôles ni le calendrier ni l'acceptation.

Il existe aussi un `claude-plugins-official`, sélectionné directement par
Anthropic : **il n'y a pas de procédure pour y candidater.** Ne construis pas ton
plan dessus.

## Ce que le dépôt contient déjà

Ce n'est pas un dépôt dédié au plugin : c'est le dépôt de référence, et le plugin
vit dedans. Les manifestes sont donc à deux étages.

```text
fastapi-hexagonal/
├── .claude-plugin/marketplace.json        # marketplace Claude Code (racine)
├── .agents/plugins/marketplace.json       # marketplace Codex (racine)
├── .cursor-plugin/marketplace.json        # marketplace Cursor (racine)
└── plugins/fastapi-hexagonal-ddd/
    ├── .claude-plugin/plugin.json         # manifeste du plugin, côté Claude
    ├── .codex-plugin/plugin.json          # manifeste du plugin, côté Codex
    ├── README.md
    └── skills/fastapi-hexagonal-ddd/
        ├── SKILL.md
        └── references/                    # 10 fiches chargées à la demande
```

Le marketplace s'appelle `fastapi-hexagonal`, le plugin `fastapi-hexagonal-ddd` —
d'où l'identifiant d'installation `fastapi-hexagonal-ddd@fastapi-hexagonal`. Ces
deux noms se retrouvent dans le README du plugin et sur la
[page d'accueil du site](../../docs/index.html) : les changer est un balayage, pas
une retouche.

### Un dépôt, pas deux

La tentation est de sortir le plugin dans son propre dépôt, plugin à la racine.
**Ne le fais pas sans raison précise.** Le skill n'est pas une source
indépendante : c'est une traduction du cours, et le cours vit ici. Deux dépôts,
c'est deux vérités qui divergent au premier correctif.

La seule raison valable d'extraire serait qu'un catalogue public exige le plugin
**à la racine** du dépôt soumis. Vérifie-le au moment de la soumission ; si c'est
le cas, publie un dépôt miroir généré depuis celui-ci, jamais édité à la main.

## Étape 0 — valider, toujours

```bash
claude plugin validate ./plugins/fastapi-hexagonal-ddd          # le plugin
claude plugin validate ./plugins/fastapi-hexagonal-ddd --strict # + les avertissements
claude plugin validate .                                        # le marketplace
```

Au 21 septembre 2026, les trois passent, `--strict` compris. `--strict` transforme
les avertissements en erreurs (champs non reconnus, métadonnées manquantes) : c'est
la version à mettre en CI, et celle que tu veux verte **avant** toute soumission.

Côté Codex, le format est plus récent et bouge encore. Les manifestes se valident
avec l'outillage officiel — le script `validate_plugin.py` du skill `plugin-creator`
du dépôt `openai/codex` :

```bash
python3 scripts/validate_plugin.py plugins/fastapi-hexagonal-ddd
```

En cas d'erreur après une mise à jour de Codex, régénère le manifeste avec
`$plugin-creator` plutôt que de le rafistoler.

## Étape 1 — distribuer depuis GitHub

Rien à publier : il suffit que `main` soit à jour sur `EdwinAlkins/fastapi-hexagonal`.

**Claude Code**

```text
/plugin marketplace add EdwinAlkins/fastapi-hexagonal
/plugin install fastapi-hexagonal-ddd@fastapi-hexagonal
```

**Codex** — `codex plugin marketplace add` accepte un chemin local,
`owner/repo[@ref]`, une URL HTTPS ou SSH :

```bash
codex plugin marketplace add EdwinAlkins/fastapi-hexagonal --ref main
codex plugin add fastapi-hexagonal-ddd@fastapi-hexagonal
codex plugin marketplace list          # vérifier ce que Codex considère
```

Ce dépôt est lourd (backend, frontend, k8s, site). Si le clonage gêne, Codex sait
faire un checkout partiel :

```bash
codex plugin marketplace add EdwinAlkins/fastapi-hexagonal --sparse plugins/fastapi-hexagonal-ddd
```

À tester avant de le documenter pour tes utilisateurs : le manifeste de
marketplace vit en dehors de ce chemin, dans `.agents/plugins/`.

**Avant d'annoncer**, teste le chemin local, qui n'exige aucun push :

```bash
claude plugin marketplace add .
codex plugin marketplace add .
```

Et vérifie ce que le plugin coûte réellement à une session :

```bash
claude plugin details fastapi-hexagonal-ddd
```

## Étape 2 — figer une version

Une release est un point fixe : le catalogue public de Claude pointe vers un
**commit précis** de ton dépôt, pas vers `main`. Tant que tu ne tagues pas, tu ne
peux pas dire ce que les gens ont installé.

Quatre fichiers portent un numéro de version, et ils doivent concorder :

| Fichier | Champ |
|---|---|
| `plugins/fastapi-hexagonal-ddd/.claude-plugin/plugin.json` | `version` |
| `plugins/fastapi-hexagonal-ddd/.codex-plugin/plugin.json` | `version` (avec son suffixe `+codex.<horodatage>`) |
| `.claude-plugin/marketplace.json` | `metadata.version` |
| `.cursor-plugin/marketplace.json` | `metadata.version` |

Puis :

```bash
claude plugin tag ./plugins/fastapi-hexagonal-ddd --dry-run
claude plugin tag ./plugins/fastapi-hexagonal-ddd -m "fastapi-hexagonal-ddd %s" --push
```

La commande crée un tag `fastapi-hexagonal-ddd--v1.0.0` et vérifie que
`plugin.json` et l'entrée de marketplace qui l'englobe sont d'accord.

**Elle refuse un arbre de travail sale.** Sur ce dépôt aujourd'hui :

```text
✘ Uncommitted changes affecting this release — commit them first so the tag
  points at the version you intend to release (or use --force)
```

C'est le bon comportement : `--force` te donnerait un tag qui ne décrit pas ce que
les gens installeront. Commite d'abord.

## Étape 3 — le catalogue public Claude (`claude-community`)

Anthropic tient deux catalogues : `claude-plugins-official`, qu'il choisit seul,
et `claude-plugins-community`, alimenté par soumission. Ta cible est le second.

1. `claude plugin validate ./plugins/fastapi-hexagonal-ddd --strict` au vert ;
2. une version taguée et poussée (étape 2) ;
3. soumission :
   - développeur individuel → <https://platform.claude.com/plugins/submit>
   - organisation Team/Enterprise → <https://claude.ai/admin-settings/directory/submissions/plugins/new>
4. Anthropic passe une revue et un contrôle de sécurité ;
5. accepté, le plugin est ajouté à `anthropics/claude-plugins-community`, dont le
   catalogue est synchronisé périodiquement sur un commit de ton dépôt.

Après acceptation, l'installation devient :

```text
/plugin marketplace add anthropics/claude-plugins-community
/plugin install fastapi-hexagonal-ddd@claude-community
```

Ton propre marketplace continue de fonctionner en parallèle. Garde-le : il te sert
à diffuser un correctif sans attendre la synchronisation du catalogue.

## Étape 4 — l'annuaire public OpenAI (ChatGPT **et** Codex)

Le point important : **ChatGPT et Codex partagent le même annuaire.** Tu ne publies
pas deux fois ; une publication approuvée peut apparaître des deux côtés.

Le parcours :

```text
Create plugin → Skills only → upload du paquet → revue OpenAI → approuvé
                                                                   │
                                                    publication déclenchée par toi
                                                                   │
                                              ┌────────────────────┴───────────────┐
                                        ChatGPT Plugin Directory          Codex Plugin Directory
```

Deux conséquences pratiques :

- **Une identité développeur ou entreprise vérifiée est exigée** avant une
  publication publique. C'est la démarche la plus longue : commence par là.
- **Tu gardes la main sur le dernier pas.** Approuvé ≠ publié : c'est toi qui
  déclenches la mise en ligne.

Documentation : <https://developers.openai.com/plugins/deploy/submission>

### Tu peux soumettre le paquet Claude tel quel

OpenAI documente une procédure d'import d'un plugin Claude Code existant : un
plugin *skills-only* contenant

```text
.claude-plugin/plugin.json
skills/.../SKILL.md
```

est accepté, et le manifeste Claude est converti en manifeste Codex pendant le
processus. Voir <https://developers.openai.com/plugins/guides/submit-claude-plugin>.

Ce dépôt possède déjà les deux manifestes : garde-les. L'import est un filet, pas
une raison de laisser mourir `.codex-plugin/plugin.json` — la distribution directe
par `codex plugin marketplace add`, elle, en dépend.

## Checklist avant de soumettre

- [ ] `claude plugin validate . && claude plugin validate ./plugins/fastapi-hexagonal-ddd --strict`
- [ ] `SKILL.md` et les 10 fiches de `references/` relus — le cours d'abord, le skill ensuite
- [ ] les quatre numéros de version concordent
- [ ] `LICENSE` présent à la racine (AGPL-3.0) et référencé par les manifestes
- [ ] `README.md` du plugin à jour : installation, périmètre, ce que le skill ne couvre pas
- [ ] un `CHANGELOG.md` dans `plugins/fastapi-hexagonal-ddd/` si tu comptes sortir une v1.1
- [ ] arbre de travail propre, tag poussé
- [ ] installation testée depuis GitHub, sur une machine qui n'est pas la tienne
- [ ] identité développeur vérifiée côté OpenAI (à lancer en avance)

## Ce qui va bouger

Les formats de plugin des deux côtés sont récents. OpenAI recommande maintenant un
`plugin.json` **portable à la racine du plugin**, tout en continuant de supporter
`.codex-plugin/plugin.json` : il n'y a rien à refaire aujourd'hui, mais c'est la
migration à surveiller. Quand une commande de ce document cesse de fonctionner,
crois la sortie du CLI plutôt que ce fichier, et corrige-le.

## Sources

- [Créer et distribuer un marketplace de plugins — Claude Code](https://code.claude.com/docs/en/plugin-marketplaces)
- [Créer des plugins — Claude Code](https://code.claude.com/docs/en/plugins)
- [Soumission de plugins — OpenAI](https://developers.openai.com/plugins/deploy/submission)
- [Préparer son plugin pour la distribution — OpenAI](https://developers.openai.com/plugins/build/plugins)
- [Soumettre un plugin Claude Code à OpenAI](https://developers.openai.com/plugins/guides/submit-claude-plugin)
