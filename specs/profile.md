# SMML Profile v1

Statut : **candidate freeze** pour GP1 Foundation.

Identifiant de schéma :

```text
smml.profile/1
```

JSON Schema :

```text
urn:smml:schema:profile:1
```

## 1. Objet

`Profile v1` décrit l'**intention portable** de l'utilisateur : cible de jeu souhaitée, packages racines demandés et politiques de résolution explicitement choisies.

Le Profile n'est ni :

- un résultat de résolution ;
- un lockfile ;
- un inventaire de packages installés ;
- un état d'installation ;
- un journal transactionnel ;
- une autorisation de mutation du jeu.

Un Profile ne contient donc ni chemin local, ni package digest, ni version effectivement résolue, ni ordre final, ni timestamp.

## 2. Décisions normatives

### PR-001 — Identité du profil

`id` est une identité locale stable de profil, par exemple :

```text
survival-industrial
```

La v1 impose un slug ASCII lower-case :

```text
[a-z0-9][a-z0-9._-]*
```

`name` est un libellé humain mutable. `description` est optionnel.

L'ordre des packages dans le fichier Profile n'a aucune valeur sémantique.

### PR-002 — Cible portable

`target` décrit la cible souhaitée sans recopier un `GameTargetIdentity` complet.

`steamAppId` est obligatoire. Les contraintes suivantes sont optionnelles et exactes :

- `gameVersions` ;
- `engineBuilds` ;
- `steamBuildIds` ;
- `steamBranches` ;
- `canonicalGameFingerprints` ;
- `hostOs` ;
- `gameOs` ;
- `compatibilityLayers`.

Tous les champs présents sont combinés en **AND**.

Le Profile ne contient volontairement pas `installationExactFingerprint` : les artefacts runtime locaux ne doivent pas rendre un profil non portable.

La résolution doit s'effectuer contre une cible réellement observée. Si `target` ne correspond pas à cette cible, la résolution échoue avant toute mutation.

### PR-003 — Packages racines demandés

`packages` contient uniquement les packages explicitement demandés par le profil.

Chaque demande contient :

```text
id
range
```

`range` utilise exactement la grammaire SemVer SMML v1 définie par `PackageManifest v1`.

Un même `id` ne peut apparaître qu'une fois.

Un Profile vide (`packages = []`) est valide : il représente un profil sans mod racine utilisateur. Les composants de plateforme sélectionnés automatiquement n'apparaissent pas dans cette liste.

### PR-004 — Dépendances soft

`policies.softDependencies` possède deux valeurs :

```text
selected-only
include-if-available
```

`selected-only` : une dépendance soft n'introduit jamais à elle seule un nouveau package ; si le package compatible est déjà sélectionné pour une autre raison, la relation peut participer au graphe et à l'ordre.

`include-if-available` : le Resolver peut ajouter un package compatible uniquement en raison d'une dépendance soft. L'absence d'un candidat compatible n'est jamais bloquante.

Avec un ensemble de candidats identique, ce choix doit produire un résultat déterministe.

### PR-005 — Sélection explicite des providers de capability

`policies.capabilityProviders` permet de lever explicitement une ambiguïté de provider.

Une entrée contient :

```text
id
version
providers[]
```

`providers` est une liste non vide d'IDs de packages autorisés/sélectionnés pour cette capability.

La sélection doit être compatible avec les cardinalités déclarées par les consommateurs dans leurs `PackageManifest`. Par exemple, une exigence `exactlyOne` est incompatible avec deux providers sélectionnés.

Un package cité ici n'a pas besoin d'être un package racine du Profile : il peut être sélectionné transitivement par le Resolver.

Une même capability `<id>@<version>` ne peut apparaître qu'une fois dans cette politique.

### PR-006 — Ambiguïté de provider

`policies.providerAmbiguity` vaut en v1 :

```text
error
```

Lorsqu'une capability nécessitant une sélection exclusive possède plusieurs solutions valides et qu'aucune règle plus forte ni sélection explicite du Profile ne tranche, le Resolver doit échouer avec un diagnostic au lieu de choisir silencieusement un provider.

Cette règle ne transforme pas une capability `many` ou `oneOrMore` en capability exclusive.

### PR-007 — Intégrité et digest du Profile

Le Profile doit être encodé en UTF-8 sans BOM.

Le digest de provenance est dérivé, jamais auto-déclaré :

```text
profileDigest = SHA-256 des octets exacts du fichier profile.json
```

Le digest exact peut changer lors d'un simple reformatage sans changer la sémantique de résolution. Le Lockfile conserve ce digest comme provenance de l'entrée exacte ayant servi à la résolution.

### PR-008 — Ce qui reste hors Profile v1

Sont volontairement hors v1 :

- chemins de repository ou URL de téléchargement ;
- signatures / trust ;
- package digests ;
- ordre résolu ;
- overrides de contenu ;
- chemins locaux ;
- état enabled/disabled redondant ;
- décisions de désinstallation/snapshot ;
- état runtime.

Les contraintes de contenu et overrides devront être spécifiés avec le futur CIR/Resolver au lieu d'être inventés dans le Profile.

## 3. Exemple

```json
{
  "schema": "smml.profile/1",
  "id": "survival-industrial",
  "name": "Survival Industrial",
  "target": {
    "steamAppId": 387990,
    "gameVersions": ["1.0.6"],
    "engineBuilds": [889]
  },
  "packages": [
    {
      "id": "com.example.pallet64",
      "range": ">=1.0.0 <2.0.0"
    }
  ],
  "policies": {
    "softDependencies": "selected-only",
    "providerAmbiguity": "error",
    "capabilityProviders": []
  }
}
```

## 4. Invariants testables

Un validateur conforme doit notamment refuser :

- un `id` de profil hors grammaire ;
- deux demandes du même package ;
- un range SemVer non supporté ;
- deux sélections pour la même capability ;
- deux fois le même provider dans une sélection ;
- un sélecteur de cible dont une liste contient des doublons ;
- une valeur de politique inconnue.

La fonction de matching Profile -> cible doit vérifier toutes les contraintes présentes et ne jamais déduire une compatibilité à partir de la seule version du jeu lorsque le Profile demande explicitement des preuves supplémentaires.
