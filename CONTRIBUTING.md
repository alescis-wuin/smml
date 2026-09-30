# Contribution au projet SMML

## Avant un commit

```bash
make check
```

La suite doit rester entièrement verte.

## Organisation

- ne pas créer de copies `-v2`, `-final`, `-old` des sources actives ;
- utiliser Git et des tags pour l'historique ;
- placer les spécifications dans `specs/`, les schémas dans `schemas/`, les fixtures dans `examples/` et les tests dans `tests/` ;
- ne pas commiter de logs bruts, chemins locaux privés, identifiants personnels ou états temporaires de probe ;
- placer les artefacts lourds/générés dans `artifacts/` ou `dist/`.

## Commits

Préférer un changement logique par commit. Préfixes recommandés :

```text
spec:
feat:
fix:
test:
docs:
chore:
```

## Évolution des formats publics

Un changement incompatible d'un contrat sérialisé doit créer une nouvelle version de format. Ne pas modifier silencieusement la sémantique d'un identifiant déjà publié comme `smml.<format>/1`.
