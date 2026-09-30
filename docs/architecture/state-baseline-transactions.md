# SMML — Référence d’architecture pour l’état, la baseline et la restauration

**Projet :** Scrap Mechanic Modding Layer (SMML)  
**Statut :** document de référence de conception  
**Date de référence :** 29 septembre 2026  
**Objet :** formaliser les conclusions issues des scans GP0 et fixer les exigences du futur gestionnaire de mods avant de poursuivre le développement.

---

# 1. Objectif

SMML ne doit pas être seulement un système capable d’installer des hooks, de composer du contenu et de charger des mods.

Il doit aussi être capable de :

- déterminer si une installation locale de Scrap Mechanic est saine avant toute modification ;
- distinguer une installation officielle, une installation modifiée et un état runtime normal ;
- conserver une baseline restaurable ;
- cartographier l’intégralité de l’installation ;
- attribuer chaque modification ou fichier ajouté à son propriétaire ;
- reconstruire un état désiré à partir d’une baseline et d’un profil de mods ;
- détecter les modifications externes ;
- restaurer proprement le jeu ;
- sauvegarder les données utilisateur importantes ;
- expliquer précisément pourquoi un fichier diffère de la baseline ;
- éviter les désinstallations LIFO fragiles ;
- ne jamais supprimer silencieusement un fichier dont la propriété n’est pas prouvée.

Ces fonctions sont désormais considérées comme des **fondations centrales de la plateforme**, et non comme de simples fonctions annexes du Mod Manager.

---

# 2. Constat expérimental

## 2.1. Ancienne installation

L’ancienne installation contenait encore des fichiers provenant de plusieurs anciens mods développés précédemment, notamment :

- `D7Tool` ;
- `Pumpkin*` ;
- `ParkingConnector` ;
- `DebugStick` ;
- PalletPress ;
- Pallet64 ;
- Composter ;
- leurs assets ;
- certains caches générés.

Ces fichiers n’étaient pas des fichiers Axolot obsolètes : ils provenaient de mods antérieurs.

Cette correction est importante pour l’interprétation des scans.

## 2.2. Comportement observé de Steam

Une désinstallation, une réinstallation et/ou une vérification d’intégrité Steam ne doivent pas être considérées comme la garantie d’un arbre de jeu canonique.

L’expérience montre qu’un dossier de jeu peut contenir :

- tous les fichiers officiels corrects ;
- des fichiers de mods supplémentaires encore présents ;
- des dossiers supplémentaires ;
- des caches ou artefacts générés ;
- sans que Steam ne les identifie nécessairement comme une erreur d’intégrité.

Conclusion :

> **« Steam validation réussie » n’est pas équivalent à « installation vanilla canonique ».**

SMML devra effectuer sa propre validation.

---

# 3. Snapshots de référence

Les états suivants doivent être distingués.

## 3.1. Snapshot A — corpus historique 1.0.5

Usage :

- fixture structurelle ;
- comparaison historique ;
- étude des changements entre builds ;
- tests du futur Hook Patcher ;
- analyse statique.

Il ne doit pas être utilisé comme baseline binaire de la build 1.0.6.889.

---

## 3.2. Snapshot C — ancienne installation modifiée

Cet état correspond à l’installation contenant les mods actifs et les résidus d’anciens mods.

Il est utile pour :

- identifier les modifications produites par les anciens installateurs ;
- étudier les résidus laissés après désinstallation ;
- construire des tests de détection de pollution ;
- vérifier la capacité future de SMML à expliquer et nettoyer ses propres artefacts.

Il ne doit pas être considéré comme une baseline propre.

---

## 3.3. Snapshot B0 — installation 1.0.6.889 fraîche, pré-lancement

Cet état constitue la baseline locale de référence actuelle.

Caractéristiques observées :

- 61 370 fichiers ;
- installation fraîche ;
- aucune erreur de scan ;
- aucun ancien mod présent ;
- état pris avant premier lancement ;
- inventaire intégral disponible ;
- SHA-256 disponible pour chaque fichier ;
- fingerprint global disponible.

Fingerprint de contenu observé :

```text
6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964
```

Cette valeur décrit cette installation précise et ne doit pas être supposée universelle sans comparaison avec d’autres installations officielles de la même build.

---

## 3.4. Snapshot B1 — installation 1.0.6.889 après premier lancement

Après un lancement normal puis une fermeture propre :

- les 61 370 fichiers de B0 sont restés byte-identical ;
- aucun fichier existant du jeu n’a été modifié ;
- aucun fichier n’a été supprimé ;
- un fichier de log supplémentaire a été créé ;
- plusieurs répertoires runtime vides ont été créés ;
- les fingerprints des principaux répertoires de contenu sont restés inchangés.

Conclusion :

> le premier lancement observé ne modifie pas la baseline de contenu du jeu ; il ajoute uniquement des artefacts runtime identifiables.

Cela permet d’introduire une distinction formelle entre **état canonique** et **état runtime**.

---

# 4. Modèle d’état de SMML

SMML doit distinguer au minimum quatre niveaux.

```text
Installation officielle attendue
        ↓
Baseline locale SMML
        ↓
État géré par SMML
        ↓
État runtime observé
```

## 4.1. Installation officielle attendue

Description d’une build connue de Scrap Mechanic.

Elle contient :

- version/build ;
- chemins attendus ;
- tailles attendues ;
- hashes attendus lorsque connus ;
- classification des fichiers ;
- règles sur les artefacts runtime autorisés.

Cette représentation peut provenir d’une installation de référence validée.

---

## 4.2. Baseline locale SMML

Photographie vérifiée de l’installation locale avant modification par SMML.

Elle doit être :

- créée avant toute première mutation ;
- immutable ;
- vérifiée après création ;
- stockée hors de l’arbre actif du jeu ;
- associée à un fingerprint ;
- associée à la build détectée ;
- restaurable.

Une baseline locale n’est pas nécessairement identique à une baseline globale officielle si l’utilisateur choisit explicitement de partir d’un état préexistant reconnu.

Pour le fonctionnement normal de SMML, la préférence doit aller à une installation locale validée comme canonique.

---

## 4.3. État géré par SMML

État déterministe produit par :

```text
Baseline
+ Hook Pack
+ Runtime SMML
+ Content Composer
+ Profil de mods résolu
```

Il constitue l’état que SMML est capable d’expliquer et de reconstruire.

---

## 4.4. État runtime

État géré auquel s’ajoutent les artefacts normaux créés par l’exécution du jeu :

- logs ;
- caches connus ;
- dossiers temporaires ;
- fichiers runtime documentés.

Ces différences ne doivent pas automatiquement invalider l’installation.

---

# 5. Fingerprints

SMML doit utiliser plusieurs niveaux de fingerprint.

## 5.1. Fingerprint exact

Prend en compte tous les fichiers suivis.

Usage :

- audit ;
- comparaison exacte ;
- reproduction de snapshots ;
- diagnostic.

Un simple log peut modifier ce fingerprint.

---

## 5.2. Fingerprint canonique

Ignore uniquement les artefacts runtime explicitement classifiés comme non structurants.

Exemples possibles :

```text
Logs/
certains fichiers de Cache/
artefacts temporaires reconnus
```

Usage :

- validation rapide d’une installation ;
- détection de mise à jour ;
- détection de drift ;
- compatibilité Hook Pack.

La liste d’exclusion doit être explicite et versionnée.

---

## 5.3. Fingerprints partiels

Calculer également un fingerprint pour les principales racines :

```text
Data/
Survival/
ChallengeData/
Release/
Cache/
```

Cela permet de localiser rapidement l’origine d’un changement.

---

# 6. Preflight Validator

Avant toute première installation de SMML, puis avant toute mutation importante, un validateur doit comparer l’état local à l’état attendu.

## 6.1. Catégories

Chaque objet doit être classé dans l’un des états suivants :

```text
EXPECTED
MISSING
MODIFIED
EXTRA
RUNTIME
UNREADABLE
```

### EXPECTED

Fichier attendu et conforme.

### MISSING

Fichier attendu absent.

### MODIFIED

Fichier attendu présent mais contenu différent.

### EXTRA

Fichier non attendu dans la baseline canonique.

### RUNTIME

Fichier supplémentaire reconnu comme artefact normal d’exécution.

### UNREADABLE

Objet dont SMML n’a pas pu établir l’état.

---

## 6.2. Politique de validation

### Installation propre

```text
EXPECTED + RUNTIME uniquement
```

Peut être acceptée.

### Fichier officiel modifié

```text
MODIFIED
```

Bloque par défaut l’installation de SMML.

### Fichier supplémentaire inconnu

```text
EXTRA
```

Ne doit jamais être supprimé automatiquement.

Il doit être :

- signalé ;
- attribué si possible ;
- éventuellement placé en quarantaine avec consentement explicite ;
- sinon laissé intact.

### Fichier supplémentaire connu comme appartenant à SMML

Peut être géré par les mécanismes d’ownership et de reconstruction.

---

# 7. Baseline Vault

SMML doit disposer d’un composant logique `BaselineVault`.

Responsabilités :

```text
capture
verify
store
restore
diff
```

## 7.1. Création

Avant toute première mutation :

1. détecter la build ;
2. effectuer le preflight ;
3. refuser l’installation si l’état est ambigu ;
4. cartographier entièrement le jeu ;
5. créer la baseline ;
6. vérifier la copie ;
7. enregistrer le fingerprint ;
8. seulement ensuite autoriser l’installation de SMML.

---

## 7.2. Emplacement

La baseline doit résider hors de l’arbre du jeu.

Exemple :

```text
SMML/
└── baselines/
    └── <game-build>/<fingerprint>/
```

---

## 7.3. Politique de stockage

Une baseline complète unique est acceptable pour une première version.

Éviter :

```text
backup-1 = 20 GiB
backup-2 = 20 GiB
backup-3 = 20 GiB
```

À terme, un stockage adressé par contenu peut être étudié :

```text
SHA-256
  ↓
blob unique
```

Les transactions ultérieures ne doivent stocker que les différences nécessaires.

---

# 8. Installation Manifest

SMML doit conserver un manifeste complet de l’installation.

Pour chaque objet :

```text
path
kind
size
sha256
extension
metadata
classification
```

Le manifeste sert à :

- valider ;
- comparer ;
- restaurer ;
- expliquer ;
- détecter un update Steam ;
- identifier les fichiers étrangers ;
- construire les futurs Hook Packs.

---

# 9. State Manifest

Après application d’un profil, SMML doit produire un état attendu.

Exemple conceptuel :

```text
baseline
+ smml-core
+ hook-pack
+ profile
= expected-managed-state
```

Le `State Manifest` doit décrire cet état.

SMML ne doit donc pas seulement savoir ce qu’il a fait : il doit savoir **à quoi l’installation doit ressembler maintenant**.

---

# 10. Ownership Ledger

Le gestionnaire doit enregistrer la propriété de tout artefact qu’il crée ou transforme.

## 10.1. Fichier exclusivement possédé

Exemple :

```text
Survival/SMML/Content/alexis.palletpress/...
```

Propriétaire :

```text
alexis.palletpress
```

---

## 10.2. Fichier partagé généré

Exemple :

```text
Survival/Objects/Database/shapesets.json
```

Propriétaire de la transformation :

```text
SMML Content Composer
```

Contributeurs :

```text
vanilla
mod A
mod B
mod C
```

---

## 10.3. Fichier vanilla hooké

Exemple :

```text
CarryTool.lua
```

Propriétés :

```text
baseline owner: Axolot
transform owner: SMML Hook Patcher
hook pack: <version>
contracts:
  - carry.beforePlacement@1
```

---

## 10.4. Dossiers

Les répertoires doivent également être suivis.

Un dossier peut être supprimé automatiquement uniquement si :

```text
il appartient à SMML
+
il ne contient plus aucun objet nécessaire
+
il est vide au moment de la suppression
```

---

# 11. Transaction Journal

Chaque opération de mutation doit générer un journal transactionnel.

Exemple conceptuel :

```json
{
  "transaction": "tx-0042",
  "beforeState": "...",
  "afterState": "...",
  "operations": [
    {
      "path": "Survival/...",
      "operation": "create",
      "owner": "alexis.palletpress",
      "afterSha256": "..."
    },
    {
      "path": "Survival/Scripts/game/tools/CarryTool.lua",
      "operation": "compose",
      "owner": "smml.hookpatcher",
      "beforeSha256": "...",
      "afterSha256": "..."
    }
  ]
}
```

Le journal doit permettre :

- audit ;
- recovery ;
- rollback ;
- diagnostic ;
- drift detection ;
- attribution.

---

# 12. Désinstallation d’un mod

SMML ne doit pas désinstaller un mod en rejouant simplement un installateur en sens inverse.

Le modèle doit être :

```text
état actuel désiré
-
mod X
=
nouvel état désiré
```

Puis :

```text
Baseline
+ mods restants
+ Hook Pack nécessaire
+ contenu résolu
→ reconstruction
```

Exemple :

```text
A + B + C
```

retrait de B :

```text
Baseline + A + C
```

Le Composer régénère ensuite les fichiers partagés.

Cette stratégie élimine la dépendance à un ordre LIFO de désinstallation.

---

# 13. Suppression sûre

Un fichier exclusivement possédé par un mod ne peut être supprimé automatiquement que si :

```text
currentSha256 == expectedManagedSha256
```

Sinon :

```text
DRIFT
```

SMML doit refuser la suppression silencieuse.

Cela protège :

- les modifications manuelles ;
- les interventions d’un autre outil ;
- les fichiers devenus partagés ;
- les états imprévus.

---

# 14. Drift Detection

Avant chaque mutation, SMML compare l’état courant à l’état géré attendu.

États proposés :

```text
CLEAN
RUNTIME_DRIFT
MANAGED_DRIFT
FOREIGN_MODIFICATION
GAME_UPDATE
BROKEN
```

## 14.1. CLEAN

L’état courant correspond à l’état attendu.

## 14.2. RUNTIME_DRIFT

Différences uniquement dues aux artefacts runtime autorisés.

Opération généralement permise.

## 14.3. MANAGED_DRIFT

Un objet possédé par SMML diffère de son état attendu.

Bloquer par défaut.

## 14.4. FOREIGN_MODIFICATION

Un fichier externe ou une modification inconnue est détectée.

Bloquer les opérations qui risqueraient de l’écraser.

## 14.5. GAME_UPDATE

Les fichiers officiels ont changé d’une manière compatible avec une nouvelle build ou un update Steam.

Le Hook Pack actuel ne doit plus être appliqué automatiquement.

## 14.6. BROKEN

État incohérent ou incomplet nécessitant recovery.

---

# 15. User Data Vault

Les données utilisateur doivent être gérées séparément de la baseline du jeu.

Composant logique :

```text
UserDataVault
```

Leurs emplacements exacts devront être cartographiés séparément pour Windows et Linux/Proton.

---

## 15.1. SaveSnapshot

Criticité maximale.

Politique :

- copie récursive ;
- hashes ;
- horodatage ;
- association à l’opération ;
- ne jamais restaurer implicitement ;
- ne jamais supprimer automatiquement une sauvegarde historique critique.

Snapshots recommandés avant :

- première installation SMML ;
- changement important de profil ;
- suppression d’un mod ajoutant du contenu persistant ;
- mise à jour majeure de Hook Pack ;
- migration de schéma ;
- recovery.

---

## 15.2. SettingsSnapshot

Sauvegarde des paramètres utilisateur pertinents :

- graphismes ;
- audio ;
- contrôles ;
- autres configurations locales identifiées.

Cette politique peut être moins stricte que celle des saves.

---

## 15.3. ModDataSnapshot

Données appartenant à SMML ou aux mods.

À définir après choix définitif de l’architecture de stockage.

---

# 16. Runtime Artifact Policy

SMML doit maintenir une liste versionnée des artefacts runtime normaux.

Exemples observés après premier lancement :

- création de `Logs/` ;
- création d’un nouveau `game-*.log` ;
- création de répertoires runtime ;
- aucun changement observé dans les 61 370 fichiers de la baseline pré-lancement.

La politique doit permettre d’ignorer ces différences lors du calcul du fingerprint canonique, sans les ignorer lors d’un audit exact.

---

# 17. Garbage Collection contrôlé

SMML peut nettoyer automatiquement uniquement les artefacts dont la propriété est prouvée.

Exemples :

```text
fichier créé par mod X
cache explicitement provoqué par mod X
dossier créé par SMML
sortie generated du Composer
```

Un fichier inconnu ne doit jamais être traité comme garbage uniquement parce qu’il n’existe pas dans la baseline vanilla.

---

# 18. Commande `explain`

La plateforme devrait pouvoir expliquer n’importe quel fichier géré.

Exemple :

```text
smml explain Survival/Scripts/game/tools/CarryTool.lua
```

Sortie conceptuelle :

```text
Baseline:
  SHA256: ...

Current:
  SHA256: ...

Modified by:
  SMML Hook Patcher

Hook Pack:
  scrap-mechanic-1.0.6.889

Transformations:
  runtime.bootstrap@1
  carry.beforePlacement@1
```

Pour un asset :

```text
smml explain Survival/SMML/Content/alexis.palletpress/foo.obj
```

```text
Created by:
  alexis.palletpress@0.4.0

Profile:
  survival-industrial

Transaction:
  tx-00028
```

Cette fonctionnalité doit être considérée comme un objectif d’architecture, même si elle n’est implémentée qu’après le MVP.

---

# 19. Architecture mise à jour

```text
                            MOD MANAGER
                                 │
                    ┌────────────┴────────────┐
                    │                         │
               STATE MANAGER              RESOLVER
                    │                         │
         ┌──────────┼───────────┐             │
         │          │           │             │
     Preflight   Baseline    User Data        │
     Validator    Vault        Vault          │
         │          │           │             │
         └──────────┴───────────┘             │
                    │                         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────┴─────────────┐
                    │                          │
               HOOK PATCHER             CONTENT COMPOSER
                    │                          │
                    └────────────┬─────────────┘
                                 │
                          RUNTIME ADAPTER
                                 │
                            MODDING API
                                 │
                                SDK
                                 │
                                MODS
```

Composants transverses :

```text
Installation Manifest
State Manifest
Ownership Ledger
Transaction Journal
Drift Detector
Runtime Artifact Policy
Diagnostics
```

---

# 20. Révision recommandée de GP2

La Grande Phase 2 doit être renforcée.

## GP2 — État, baseline et transactions

### Phase 2.1 — Installation Validator

- détection de build ;
- fingerprint canonique ;
- classification EXPECTED/MISSING/MODIFIED/EXTRA/RUNTIME ;
- refus d’un état ambigu.

### Phase 2.2 — Baseline Vault

- capture ;
- vérification ;
- stockage ;
- restauration ;
- comparaison.

### Phase 2.3 — User Data Vault

- découverte des emplacements ;
- SaveSnapshot ;
- SettingsSnapshot ;
- future ModDataSnapshot.

### Phase 2.4 — Installation Manifest

- inventaire complet ;
- métadonnées ;
- SHA-256 ;
- classification.

### Phase 2.5 — State Manifest

- état attendu après résolution ;
- fingerprint de l’état géré ;
- comparaison état réel/attendu.

### Phase 2.6 — Ownership Ledger

- fichiers ;
- dossiers ;
- fichiers partagés ;
- transformations ;
- caches ;
- contributeurs.

### Phase 2.7 — Transaction Engine

- plan ;
- staging ;
- validation ;
- commit atomique ;
- rollback ;
- journal.

### Phase 2.8 — Drift Detection

- CLEAN ;
- RUNTIME_DRIFT ;
- MANAGED_DRIFT ;
- FOREIGN_MODIFICATION ;
- GAME_UPDATE ;
- BROKEN.

### Phase 2.9 — Restore / Recovery

- retour baseline ;
- restauration d’un état géré ;
- reprise après transaction interrompue ;
- diagnostic.

### Phase 2.10 — Garbage Collection contrôlé

- suppression uniquement d’artefacts possédés ;
- validation des hashes ;
- nettoyage de dossiers vides possédés ;
- aucune suppression d’objet inconnu.

---

# 21. Exigences nouvelles à ajouter au cahier des charges

## Validation

**AR-054.** SMML doit valider l’installation locale avant sa première mutation.

**AR-055.** Une validation Steam réussie ne constitue pas une preuve suffisante d’une installation canonique.

**AR-056.** Un fichier supplémentaire inconnu ne doit jamais être supprimé automatiquement.

## Baseline

**AR-057.** Une baseline locale vérifiée doit être créée avant toute première modification SMML.

**AR-058.** La baseline doit être stockée hors de l’arbre du jeu.

**AR-059.** La baseline doit être immutable.

## Ownership

**AR-060.** Tout artefact créé par SMML ou par un mod doit avoir un propriétaire identifiable.

**AR-061.** Toute transformation d’un fichier vanilla doit avoir une provenance identifiable.

**AR-062.** Un artefact géré modifié extérieurement ne doit pas être écrasé ou supprimé silencieusement.

## Reconstruction

**AR-063.** La désinstallation d’un mod doit reconstruire l’état désiré depuis la baseline et les mods restants.

**AR-064.** La compatibilité entre mods ne doit pas dépendre d’un ordre LIFO d’installation/désinstallation.

## Données utilisateur

**AR-065.** Les sauvegardes utilisateur doivent être snapshotées avant toute opération présentant un risque de perte de contenu persistant.

**AR-066.** Les paramètres utilisateur doivent pouvoir être sauvegardés/restaurés indépendamment de la baseline du jeu.

## Runtime

**AR-067.** SMML doit distinguer les artefacts runtime normaux des modifications structurelles.

**AR-068.** Les fingerprints exact et canonique doivent être distincts.

---

# 22. Conséquences pour GP0

Les résultats actuels valident déjà plusieurs éléments nécessaires aux phases suivantes :

- une baseline propre peut être capturée ;
- le premier lancement observé ne modifie pas les fichiers structurants de cette baseline ;
- Steam ne doit pas être utilisé comme unique mécanisme de nettoyage ;
- des mods anciens peuvent laisser des fichiers orphelins sur plusieurs versions du jeu ;
- les fichiers/dossiers ajoutés doivent donc être suivis individuellement ;
- les caches doivent être gérés séparément ;
- les manifests de scan sont suffisamment riches pour construire le futur validateur.

Les prochaines tâches GP0 restent :

1. finaliser le scanner GP0 ;
2. produire un comparateur de snapshots ;
3. produire la capture sélective de fichiers textuels/déclaratifs ;
4. analyser les changements Lua entre 1.0.5 et 1.0.6.889 ;
5. cartographier les hooks potentiels ;
6. cartographier les registres de contenu ;
7. préparer les probes runtime Lua ;
8. étudier réseau et persistance.

---

# 23. Invariant principal

Le principe suivant doit guider toute la plateforme :

> **SMML ne doit jamais avoir besoin de deviner l’origine d’un changement qu’il a lui-même produit.**

Pour chaque différence qu’il crée, SMML doit connaître :

```text
qui
quoi
où
quand
pourquoi
depuis quel état
vers quel état
avec quel hash
pour quel profil
pour quelle version du jeu
```

Un état inconnu doit rester inconnu et provoquer une décision prudente, jamais une suppression ou un écrasement automatique.

---

# 24. Principe de reconstruction

La plateforme doit tendre vers le modèle suivant :

```text
Baseline immuable
        +
Profil résolu
        +
Hook Pack compatible
        +
Content Composer
        +
Runtime SMML
        ↓
État géré déterministe
```

La restauration et la désinstallation deviennent alors des problèmes de **reconstruction d’état**, et non des problèmes de « dépatch manuel ».

C’est cette propriété qui doit permettre à SMML de rester fiable lorsque le nombre de mods, de fichiers partagés, de versions et de profils augmentera.
