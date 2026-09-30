# PathPolicy v1 — note de jalon

Identifiant : `smml.path-policy/1`.

## But

Éliminer les règles de chemin dispersées avant l'implémentation de `GameTargetInspector`, `PackageValidator` et `TransactionEngine`.

## Décisions figées

- chemin logique relatif, UTF-8, Unicode NFC, séparateur `/` ;
- aucune correction silencieuse d'une entrée non canonique ;
- limites : 4096 octets UTF-8 par chemin, 255 par segment, 256 segments ;
- compatibilité portable Windows : caractères réservés, noms device et trailing dot/space rejetés ;
- collision key : `NFC(DefaultCaseFold Unicode 15.1.0(NFC(path)))` ;
- une collision portable est rejetée même sur un filesystem sensible à la casse ;
- parcours filesystem de production no-follow sous une racine de confiance ;
- symlink et reparse point interdits sur les objets gérés ;
- fichier existant à plusieurs hardlinks non mutable en v1 ;
- PathPolicy ne décide ni ownership ni hash attendu.

## Implémentation de référence actuelle

`reference/python/smml_reference/path_policy.py` est l'implémentation exécutable de référence. `tests/path_policy_validation.py` n'est plus qu'un shim de compatibilité pour les tests historiques. Elle ne constitue pas encore le backend filesystem de production.

Les validateurs sémantiques suivants l'utilisent :

- `tests/validation.py` ;
- `tests/transaction_journal_validation.py` ;
- `tests/package_manifest_validation.py` ;
- `tests/hook_pack_manifest_validation.py`.

## Validation du jalon

Au moment du gel candidat :

```text
94 / 94 fixtures historiques PASS
142 / 142 tests unitaires PASS
```

Le hashing déterministe et `GameTargetInspector v1` ont depuis été réalisés ; la prochaine étape est l'intégration transactionnelle.
