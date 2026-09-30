# Revue du code/outillage actuel

## `smml_gp0_scan_v1_2.py`

Bon : read-only, hashes, manifests, fingerprint contenu, séparation références static/runtime, racines CUSTOMIZATION/PARTICLE ajoutées.  
À améliorer avant production : schéma stable séparé des expérimentations, tests unitaires plus explicites, normalisation path/case policy partagée avec Composer.

## `smml_gp0_capture.py`

Bon : politique FULL/SAMPLE/REFERENCE déterministe, vérification source, corpus portable.  
À conserver comme outil research, pas forcément composant runtime.

## `smml_gp0_lab.py` v0.1.4

Points solides : hashes exacts de cibles, préparation avant commit, writes atomiques, backup cache, snapshot Save récursif + vérification, restore puis vérification, refuse uninstall sur drift, pas de réseau/sudo/subprocess.

Dettes identifiées :

1. **pas de lock exclusif** malgré la convention `flock` ; deux processus pourraient interférer ;
2. **symlink policy insuffisante** : les cibles jeu ne sont pas explicitement rejetées si symlink, et le snapshot Save reproduit les symlinks ;
3. **collecteur multi-session** : `len(storage_rows)==208` est évalué globalement ; deux worlds donnent 416 et faux négatif ;
4. **userdata stale** : `Lab.lua` appelle `totalQuantity` sur un Container invalide ; 829 erreurs observées ;
5. **package hygiene** : `__pycache__`/`.pyc` présents dans `smml.zip` ;
6. l'installation écrit plusieurs fichiers successivement sans journal write-ahead/recovery crash : acceptable pour probe jetable, insuffisant pour production ;
7. l'état encode des chemins locaux ; ne pas redistribuer state/log brut sans sanitation.

## Runtime.lua

Bonne adaptation au sandbox : affectation globale normale, capability probe, `sm.log` ; ne pas réintroduire `rawget/rawset` comme dépendance.  
Production : remplacer télémétrie `[ERROR]` utilisée volontairement par niveaux de log adaptés ; le probe utilisait `error` pour garantir la capture.

## Lab.lua

La matrice dry-run est une excellente technique de test : transaction + abort vérifie la politique sans consommer les ressources.  
À corriger : reacquisition/`sm.exists` du target, stage timeout, rate-limit erreur, session token explicite.
