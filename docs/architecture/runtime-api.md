# Runtime API — principes établis après GP0

## Environnement Lua observé

- Lua 5.1 d'après l'API officielle.
- `pcall`, `xpcall` présents dans le sandbox observé.
- `rawget`, `rawset`, `debug.traceback` absents dans le sandbox observé.
- `sm.log` utilisable en lancement normal ; `print` n'est pas un canal de log fiable hors `-dev`.

## Dispatcher

Pour chaque handler :

```text
adapter context
→ validate contract/version
→ validate payload
→ xpcall(handler, errorAdapter)
→ collect result according to contract category
→ continue or cancel according to explicit semantics
```

Le diagnostic doit ajouter `modId`, `contractId`, phase, callback, build et world/session token ; ne pas dépendre d'une traceback Lua complète.

## Contrats

- Notification : aucun retour déterminant.
- Cancellable : serveur tranche ; politiques de composition explicites (`deny-wins`, `first-deny`, etc.).
- Transform : pipeline ordonné, type validé à chaque étape.
- Query : requête synchrone bornée ; éviter hot paths.
- Service : interface stable offerte par Core.

## Carry

La preuve host montre :

```text
client intent (`cl_tryInsert`)
→ vanilla target/validation
→ sendToServer `sv_n_sendItem`
→ server callback
→ event cible `sv_e_receiveItem`
→ transaction container
```

La future API ne doit pas confondre intention client et autorité serveur.

## TransportService — décision MVP

GP0.5 a validé `SurvivalGame.network` entre deux processus Scrap Mechanic distincts.

Backend MVP :

```text
SurvivalGame.network
        ↓
TransportService
        ↓
contract router / validation / xpcall
        ↓
mods
```

Règles :

- ne jamais exposer les callbacks/noms vanilla aux mods ;
- client→serveur et serveur→client(s) pour commandes/événements ponctuels ;
- enveloppe minimale versionnée : contractId, contractVersion, requestId optionnel, payload ;
- validation stricte avant tout accès au payload ;
- erreurs de handler isolées et journalisées ;
- payloads non fiables même lorsqu'ils proviennent d'un client SMML.

## Replicated state

`setClientData` a été observé fonctionnel sur canaux 3 et 4 et livre l'état initial à un client qui rejoint après publication.

Utilisation prévue :

```text
petit état serveur courant
→ setClientData
→ clients présents + clients tardifs
```

Ne pas l'utiliser comme bus d'événements. Le canal exact est une capability de build/Hook Pack, pas un contrat API public.

## Client lifecycle

Le leave/rejoin a créé un nouveau runtime Lua client dans le probe.

Conséquences :

- aucun singleton client ne doit être supposé durable ;
- bootstrap idempotent ;
- handlers/abonnements réenregistrables ;
- état durable récupéré depuis serveur/storage/profil, pas depuis globals client.

## StorageService

`sm.storage` est un backend serveur démontré pour :

```text
absent
→ schema 1
→ restart
→ load schema 1
→ migration 1→2
→ save schema 2
→ restart
→ load schema 2
```

API publique recommandée :

```text
StorageService.load(modId, key)
StorageService.save(modId, key, value)
StorageService.registerMigration(modId, fromSchema, toSchema, fn)
```

Règles :

- namespace logique par `modId`;
- `schemaVersion` explicite ;
- migrations déterministes/idempotentes ;
- écritures rares, coalescées, jamais par tick ;
- disable ≠ purge automatique ;
- données `worldContent` traitées avec avertissements/policies spécifiques.

## Userdata lifetime

Toute référence `Shape`, `Container`, `ScriptableObject`, etc. conservée entre ticks doit être considérée invalide potentiellement. Utiliser `sm.exists` sur les userdata qui le permettent et reacquérir la référence depuis son propriétaire lorsque nécessaire.
