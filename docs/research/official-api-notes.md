# API officielle — notes utiles au design

- Lua : 5.1.
- `GameClass` : instance unique, champs Network/Storage.
- `Player:getCarry()`, `getInventory()` : confirmés officiellement.
- `Container`: `canCollect`, `getRevision`, filters, collect/spend ; mutations critiques côté serveur selon fonctions.
- `Network`: RPC client/server, `setClientData`; minimiser fréquence et payload.
- `sm.storage`: serveur-only, save immédiat coûteux, persistance DB monde.
- `ScriptableObjectClass`: network, storage si save object, sync clients.
- `sm.shape.createPart`: serveur-only.
- `sm.exists`: utiliser pour guards de durée de vie quand applicable.
- Les callbacks `client_onUpdate` sont très fréquents ; ne pas y mettre du travail non graphique coûteux.

Les URLs exactes sont dans `WEB_SOURCES.json`.
