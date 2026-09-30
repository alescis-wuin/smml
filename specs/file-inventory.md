# FileInventory — spécification v1

**Schema ID :** `smml.file-inventory/1`  
**Statut :** GP1 / diagnostic read-only

## 1. Objectif

`FileInventory` est une sortie déterministe du `GameTargetInspector` destinée au diagnostic, à la comparaison de baseline et à la production de preuves. Elle ne contient aucun chemin local, timestamp, nom d'utilisateur ou inode.

Elle réutilise exclusivement `PathPolicy v1` et `Hashing v1`.

## 2. Structure

```text
schema

target
  steamAppId
  steamBuildId
  steamBranch

scope
  game-root
  ou prefix(path)

contentTreeAlgorithm
summary
files[]
  path
  size
  sha256
```

`files[]` est ordonné par `PortableCollisionKey(path)` puis par les octets UTF-8 exacts du chemin.

## 3. Invariants

### FI-001 — octets exacts

`sha256` est le SHA-256 des octets exacts du fichier observé pendant l'inspection stable.

### FI-002 — chemins

Chaque `path` DOIT être valide selon `PathPolicy v1`. Les doublons exacts et collisions `PortableCollisionKey` sont interdits.

### FI-003 — scope

`scope.kind = game-root` contient l'inventaire complet.

`scope.kind = prefix` exige un `path` terminé par `/` et chaque fichier DOIT appartenir à ce préfixe.

### FI-004 — summary

`summary` DOIT être exactement `smml.content-tree-sha256/1` appliqué à `files[]`.

### FI-005 — déterminisme

À fichiers identiques, metadata Steam identique et même scope, le document logique DOIT être identique. Aucun timestamp n'est ajouté.

## 4. FileInventoryDiff

`smml.file-inventory-diff/1` compare deux inventaires de même cible et même scope et distingue :

```text
added
removed
modified
unchanged
```

Une modification signifie une différence de `size` ou de `sha256` pour le même chemin logique.

Le diff PEUT annoter une entrée avec une classification (`rebuildable-cache`, `runtime-ephemeral`, `immutable-game-content`, `unknown`) et avec `strictTargetFingerprint=true` lorsqu'un chemin reste une preuve forte de compatibilité malgré son exclusion du fingerprint canonique.

## 5. Sécurité

Un inventaire est une preuve read-only. Il ne constitue jamais une autorisation d'écriture et ne remplace pas les préconditions immédiates du `TransactionEngine`.
