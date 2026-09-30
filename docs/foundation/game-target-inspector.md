# GameTargetInspector v1 — note de jalon

## But

Produire un `smml.game-target/1` déterministe à partir d'une installation locale observée, sans autoriser de mutation.

## Décisions figées

- `steamAppId`, `steamBuildId`, branche et `installdir` sont vérifiés depuis le Steam appmanifest local ;
- `gameVersion` et `engineBuild` proviennent d'un plan versionné indexé par Steam build + branche ;
- un Steam build inconnu est refusé, jamais reconnu heuristiquement ;
- host OS/architecture sont observés ; game OS/architecture viennent du plan ;
- une couche de compatibilité cross-OS doit être déclarée explicitement ;
- inventaire complet des fichiers réguliers sous game root ;
- symlink/reparse/objets spéciaux et collisions `PortableCollisionKey` refusés ;
- acquisition de fichier avec contrôles `lstat/fstat` avant/après et `O_NOFOLLOW` lorsqu'il existe ;
- seconde passe metadata obligatoire pour détecter un changement pendant l'inspection ;
- exact/canonical/root/target fingerprints utilisent uniquement `Hashing v1` ;
- la sortie ne contient ni timestamp ni chemin local ;
- un `GameTargetIdentity` produit n'est jamais une autorisation de mutation.

## Implémentation

Code de référence :

```text
reference/python/smml_reference/game_target_inspector.py
```

CLI :

```text
tools/gp1/game-target-inspector/smml_game_target_inspector.py
```

Plan courant :

```text
policies/smml.game-target-inspection-plan-1.json
```

## Limites v1

- pas de découverte automatique de toutes les bibliothèques Steam ;
- pas d'interrogation réseau ;
- pas de reconnaissance d'une build inconnue ;
- pas de cache de hash ;
- pas de parallélisation ;
- backend Python de référence, pas encore backend handle-relative final Windows/POSIX ;
- le `TransactionEngine` doit réinspecter ses préconditions juste avant mutation.
