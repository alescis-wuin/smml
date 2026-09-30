# GP0.2 — Chronologie complète des preuves runtime

## v0.1.0 — échec utile : emplacement de script invalide

Le runtime avait été placé sous `Survival/SMMLProbe/Runtime.lua`. Le moteur a refusé ce chemin, puis l'instrumentation a référencé une globale jamais créée et le chargement Survival a échoué. Décision : tout runtime Lua injecté doit vivre sous une zone de scripts acceptée, ici `Survival/Scripts/...`.

## v0.1.1 — échec utile : sandbox Lua incomplet

Le chemin `Survival/Scripts/SMMLProbe/Runtime.lua` est accepté et exécuté. Le runtime échoue ensuite sur `rawget`: `attempt to call global 'rawget' (a nil value)`. Décision : ne jamais assimiler « Lua 5.1 » à « bibliothèque standard complète exposée par le sandbox ».

## v0.1.2 — chargement Survival réparé, télémétrie inadéquate

`rawget/rawset` supprimés comme dépendances et instrumentation rendue fail-open. Le monde Survival charge. Aucun événement dans `game-*.log` car le probe utilisait `print`. La documentation officielle recommande `-dev` pour console/hot reload ; pour nos runs normaux, `sm.log` est le canal fiable.

## v0.1.3 — topologie et isolation

Résumé du premier run : 30 événements, dont 10 callbacks (`server_onCreate`/`client_onCreate`) sur SurvivalGame, SurvivalPlayer, QuestManager, Crafter et CarryTool.

Constats :

- SurvivalPlayer/QuestManager/CarryTool/Crafter sont évalués avant notre bootstrap SurvivalGame et voient la globale absente au top-level ;
- après bootstrap, les callbacks observés voient la même table runtime sur host ;
- runtime évalué une fois ; deux appels bootstrap → `initCount=1` ;
- `pcall=true`, `xpcall=true`, `rawget=false`, `rawset=false`, `debug.traceback=false` ;
- erreur volontaire isolée par `xpcall`, séquence A → erreur B → C continue ;
- conclusion : `ensureRuntime()` multi-entry + dispatcher xpcall, sans dépendre d'une traceback Lua standard.

## v0.1.3 carry — drop et insertion client partielle

Deuxième session agrégée : 64 événements. `cl_tryDrop` client suivi de `sv_n_dropCarry` serveur : chemin drop confirmé. `cl_tryInsert` est atteint mais pas encore `sv_n_sendItem`, ce qui motive le laboratoire ciblé.

## v0.1.4 — Carry / Storage Laboratory

Le laboratoire crée 16 fixtures stockage et teste 13 items par fixture avec transactions sèches : 208 cas par world load. Deux world loads ont produit deux matrices identiques. Le collecteur brut a compté 416 et marqué `storage_matrix_complete=false` : défaut d'agrégation, pas défaut moteur.

Run de référence :

- 208/208 cas ; 113 acceptés, 95 refusés ;
- beginTransaction/dry-run/abort réussis ; contenu inchangé après abort ;
- inventaire nouveau joueur : 40 slots, 38 libres avant loadout ;
- Carry : Scrap Wood → Resource Collector → `cl_tryInsert` → branch container / canCollect=true → `sv_n_sendItem` client → serveur → `ResourceContainer.sv_e_receiveItem` → Carry=0 / target=1 → success=true.

## Erreur du harnais v0.1.4

Premier world : 829 erreurs identiques `Lab.lua:433: Container does not exist`. Le target Resource Collector a été déplacé/invalidé pendant le test et le lab a conservé un Container stale. Cela ne remet pas en cause la seconde session réussie ; cela impose une règle générale : vérifier/reacquérir les userdata/containers conservés entre ticks.

## Ce qui est démontré / non démontré

### Démontré moteur sur host

- chemin runtime valide sous `Survival/Scripts` ;
- globals/table runtime partagés entre callbacks client/serveur observés après bootstrap ;
- bootstrap multi-entry idempotent ;
- capacités Lua listées ci-dessus ;
- isolation `xpcall` ;
- Carry drop client→serveur ;
- Carry insert client→RPC→serveur→ResourceContainer ;
- containers/filtres sur matrice testée ;
- world reload crée une nouvelle session/runtime propre.

### Encore non démontré

- client distant ;
- serveur dédié ;
- comportement complet `server_onRefresh` ;
- transport réseau global SMML ;
- persistance SMML / migration de schema ;
- performance sous charge de nombreux mods.
