# Manifest et Resolver — recommandations issues de l'audit

## Identité

Inspirer la discipline, pas le format exact, de frameworks comme BepInEx :

- `id` permanent, recommandé reverse-DNS ou namespace stable ;
- `name` humain mutable ;
- `version` SemVer ;
- `game`/build compatibility séparée de la version du mod ;
- ne jamais réutiliser un ID pour un autre projet.

## Dépendances

Chaque dépendance :

```json
{
  "id": "example.foundation",
  "range": ">=1.2.0 <2.0.0",
  "kind": "hard"
}
```

`hard` : absence/incompatibilité bloque le mod.  
`soft` : influence l'ordre/capacités mais n'empêche pas le chargement.

## Capacités

Un mod peut `provide`, `require`, `conflict` des capacités abstraites, par exemple :

- `smml.api.carry.beforePlacement@1`
- `content.shape.registration@1`
- `service.storage@1`

Le Resolver travaille sur IDs **et** capacités.

## Ordre déterministe

1. filtrer incompatibilités jeu/API ;
2. résoudre hard deps ;
3. sélectionner providers de capabilities ;
4. détecter cycles ;
5. appliquer contraintes d'ordre explicites ;
6. topological sort ;
7. tie-break stable par ID ;
8. produire lockfile complet avec hashes package/contributions.

Ne jamais utiliser l'ordre de découverte filesystem comme ordre sémantique.

## Conflits

Catégories :

- identité exclusive (UUID/path contractuellement unique) ;
- mergeable (list/map avec clé définie) ;
- ordered extension ;
- transform conflict ;
- baseline anomaly connue ;
- foreign modification non attribuée.

Le Resolver ne doit pas « choisir le dernier » silencieusement.
