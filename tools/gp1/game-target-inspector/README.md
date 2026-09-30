# GameTargetInspector

Implémentation Python de référence de `GameTargetInspector v1`.

Exemple Linux + Steam + Proton :

```bash
python3 tools/gp1/game-target-inspector/smml_game_target_inspector.py \
  "$HOME/.local/share/Steam/steamapps/common/Scrap Mechanic" \
  --compatibility-layer proton \
  --output artifacts/game-target.json
```

Le `appmanifest_387990.acf` est recherché automatiquement deux niveaux au-dessus du game root (`steamapps/`). Utiliser `--appmanifest` uniquement si nécessaire.

L'outil est read-only sur l'installation. Le fichier de sortie est refusé s'il se trouve sous le game root.
