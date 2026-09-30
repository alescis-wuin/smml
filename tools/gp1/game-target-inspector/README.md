# GameTargetInspector

Implémentation Python de référence de `GameTargetInspector v1`.

Exemple Linux + Steam + Proton :

```bash
python3 tools/gp1/game-target-inspector/smml_game_target_inspector.py \
  "$HOME/.local/share/Steam/steamapps/common/Scrap Mechanic" \
  --compatibility-layer proton \
  --output artifacts/game-target.json \
  --inventory-output artifacts/game-target-inventory.json.gz \
  --cache-diff-output artifacts/cache-diff.json \
  --require-known-canonical
```

Le `appmanifest_387990.acf` est recherché automatiquement deux niveaux au-dessus du game root (`steamapps/`). Utiliser `--appmanifest` uniquement si nécessaire.

L'outil est read-only sur l'installation. Le fichier de sortie est refusé s'il se trouve sous le game root.


`--inventory-output` produit l'inventaire complet sanitizé (`smml.file-inventory/1`). `--cache-diff-output` le compare à la baseline B0 embarquée et liste exactement les fichiers `Cache/` ajoutés, supprimés ou modifiés.

La policy canonique est choisie par le plan d'inspection ; le plan actif utilise `smml.canonical-game-policy/2`. `--require-known-canonical` rend le run fail-closed si le fingerprint canonique observé n'est pas un fingerprint connu pour la build.
