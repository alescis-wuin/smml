# SMML GP0 — Politique de capture sélective du corpus Scrap Mechanic

**Statut :** proposition v1 basée sur le snapshot vanilla propre `1.0.6.889`  
**Fingerprint source :** `6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964`

## Objectif

Transformer l'installation complète de Scrap Mechanic en une archive GP0 compacte qui permet :

- l'analyse statique des scripts et registres ;
- la cartographie des hooks potentiels ;
- la conception du Content Composer ;
- les comparaisons entre builds ;
- l'étude des formats et dépendances ;
- la conservation d'une référence exacte pour les fichiers non copiés.

L'archive produite n'est pas un package de redistribution. Elle est un corpus privé d'analyse.

## Trois niveaux de capture

### `FULL`

Le contenu complet du fichier est copié dans `game/`.

Utilisé pour :

- Lua ;
- JSON/XML ;
- registres et bases déclaratives ;
- formats de configuration ;
- renderables ;
- shapesets ;
- effects ;
- layouts ;
- surfaces ;
- mondes et définitions légères ;
- OBJ/MTL ;
- exemples officiels de mods Axolot.

### `SAMPLE`

La famille complète reste décrite dans les manifests, mais seuls quelques fichiers représentatifs sont copiés.

Utilisé pour les familles utiles à comprendre mais trop volumineuses ou répétitives :

- `.blueprint` ;
- `.prefabson` ;
- `.tileson` ;
- `.dae` ;
- `.fbx` ;
- images principales ;
- mesh/skeleton compilés représentatifs.

L'échantillonnage est déterministe et cherche à couvrir :

- plusieurs racines du jeu ;
- variantes texte/binaire lorsqu'elles existent ;
- petits, moyens et gros fichiers ;
- un nombre limité de représentants par extension.

### `REFERENCE`

Le contenu n'est pas copié. Le fichier reste entièrement référencé par le scan :

- chemin ;
- taille ;
- SHA-256 ;
- extension ;
- métadonnées ;
- classification texte/binaire ;
- références/UUID relevés lorsque disponibles.

Utilisé notamment pour :

- `Cache/` ;
- `Release/` ;
- `.dll` / `.exe` ;
- banques audio ;
- fontes ;
- caches compilés ;
- `.tile`, `.prefab`, `.export` binaires ;
- gros assets dont le contenu n'est pas nécessaire au MVP.

## Règles de chemin prioritaires

| Chemin | Action | Raison |
|---|---|---|
| `Data/ExampleMods/**` | FULL | documentation officielle très utile et compacte |
| `installscript.vdf` | FULL | métadonnées d'installation |
| `Logs/**` | REFERENCE | runtime ; les logs d'expériences seront capturés explicitement |
| `Cache/**` | REFERENCE | données générées, non sources |
| `Release/**` | REFERENCE | binaires natifs hors périmètre initial |

Les règles de chemin sont prioritaires sur les règles d'extension.

## Taille projetée sur la baseline 1.0.6.889

| Classe | Fichiers candidats | Volume brut source |
|---|---:|---:|
| FULL | 10 236 | ~85,05 MiB |
| SAMPLE | 27 204 | ~13,25 GiB |
| REFERENCE | 23 930 | ~5,85 GiB |

Après échantillonnage :

- **10 303 fichiers copiés** ;
- **10 236 fichiers complets** ;
- **67 échantillons** ;
- **~115,06 MiB bruts copiés** ;
- **~19,07 GiB uniquement référencés**.

Le ZIP final devrait être sensiblement plus petit que 115 MiB grâce à la forte compressibilité des scripts et formats déclaratifs.

## Structure de l'archive finale

```text
smml-gp0-corpus-1.0.6.889.zip
├── game/
│   ├── Data/
│   ├── Survival/
│   ├── ChallengeData/
│   └── ...
│
└── _analysis/
    ├── README.txt
    ├── capture-policy.json
    ├── capture-summary.json
    ├── capture-decisions.jsonl
    ├── included-manifest.jsonl
    ├── reference-manifest.jsonl
    ├── capture-extension-summary.json
    └── source-scan/
        ├── summary.json
        ├── manifest.jsonl
        ├── manifest.csv
        ├── tree.txt
        ├── extensions.txt
        ├── extensions.csv
        ├── references.tsv
        ├── uuids.tsv
        └── autres rapports du scanner
```

## Garanties de l'outil de capture

Pour chaque fichier réellement copié :

1. le chemin est récupéré depuis le scan source ;
2. la taille actuelle est comparée à celle du scan ;
3. le SHA-256 actuel est recalculé ;
4. le fichier n'est copié que si le SHA-256 correspond ;
5. toute dérive provoque un arrêt au lieu de capturer silencieusement un autre état.

Les fichiers non copiés restent représentés dans `reference-manifest.jsonl` et dans le scan complet embarqué.

## Pourquoi ne pas tout capturer

Quatre familles seulement représentent l'essentiel du volume :

- textures TGA ;
- caches textures TCO ;
- FBX ;
- DAE.

Leur présence intégrale n'apporte pas une valeur proportionnelle pour les premières phases Hook Patcher / Content Composer. Le manifeste et des échantillons représentatifs suffisent initialement.

Cette politique pourra être étendue ultérieurement par domaine, par exemple :

- capture terrain ;
- capture animation ;
- capture audio ;
- capture cache ;
- capture GUI ;
- capture physique/collision.

## Critère de validation

La politique est considérée correcte pour GP0 si l'archive permet de réaliser sans nouvelle copie du jeu :

- l'inventaire des Lua ;
- l'analyse des `dofile` et globals ;
- la cartographie des callbacks ;
- l'analyse de `SurvivalGame`, `SurvivalPlayer`, `CarryTool`, `RecipeManager` ;
- la cartographie des principaux registres ;
- l'analyse des Shapes/Recipes/IconMap/localisation ;
- l'étude des exemples officiels de mods ;
- la construction de graphes de références ;
- les diffs textuels entre builds ;
- la préparation des probes GP0.2.

Si une analyse ultérieure nécessite une famille classée `REFERENCE`, une politique spécialisée pourra produire un corpus complémentaire sans changer la baseline.
