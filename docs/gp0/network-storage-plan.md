# GP0.5 — Plan de probe réseau et persistance

## Statut d'exécution

**EXÉCUTÉ ET FERMÉ le 29 septembre 2026.** Le probe v0.2.0, run `GP05-20260929-153608`, a produit un merge `overall_pass=true` sur les 16 critères. Voir `GP0_5_NETWORK_STORAGE_RESULTS.md` et `05_ANALYSIS/GP0_CLOSURE_2026-09-29.md`.

Le texte ci-dessous est conservé comme plan historique ayant conduit à la campagne.

## Ce que l'API officielle établit

- `Network.sendToServer` : client→serveur ; le serveur reçoit aussi le joueur émetteur.
- `Network.sendToClient(s)` : serveur→client(s).
- `Network.setClientData` : dernier état automatiquement synchronisé, y compris vers nouveaux clients ; utiliser parcimonieusement.
- `sm.storage` : serveur-only ; `save` est décrit comme lent et doit être rare.
- `sm.storage` annonce un namespace « current mod », mais SMML opère dans le Survival direct : **ne pas dépendre de cette isolation pour séparer les mods SMML**.
- `GameClass` est unique et possède `network` et `storage`.
- ScriptableObjectClass possède aussi `network` et, si save object, `storage`.

## Hypothèse MVP recommandée

Commencer par **`SurvivalGame.network` derrière une abstraction `TransportService`** :

- zéro registre contenu supplémentaire ;
- une instance Game unique ;
- création/lifecycle déjà central ;
- surface de patch minimale.

Ne pas exposer cette décision aux mods. Si les tests montrent des limites, remplacer l'implémentation par ScriptableObject sans changer l'API publique.

## Probe N1 — RPC multiplexé

Message enveloppe minimal :

```text
contractId
contractVersion
requestId optionnel
payload borné
```

Tester client host→server, server→host, invalid contract, invalid payload, handler throw isolé, et si possible second client distant.

## Probe N2 — client data

Canal SMML réservé. Tester : initial set, mise à jour, world unload/reload, nouveau client si disponible. Mesurer nombre d'appels et taille sérialisée.

## Probe S1 — persistance

Utiliser une clé interne explicitement namespacée, par exemple structure/string contenant :

```text
smml.core
modId
schemaVersion
dataKey
```

Scénario : absence → write schema1 → reload → read → migrate schema2 → restart jeu → read schema2 → disable/re-enable mod → read. Écriture uniquement transitions, jamais tick.

## Probe S2 — isolation logique

Deux faux mods A/B avec même `dataKey` mais `modId` différent. Vérifier absence de collision dans le service SMML. Le test ne cherche pas à prouver le namespace moteur ; il prouve le namespace plateforme.

## Choix Game.network vs ScriptableObject

Critères :

- disponibilité au bon moment ;
- comportement world reload ;
- remote client ;
- persistance ;
- coût en hooks/contenu ;
- possibilité d'isoler erreurs ;
- facilité de diagnostic et de migration.

Décision après logs : `SurvivalGame.network` est retenu comme backend MVP derrière `TransportService`. `setClientData` est réservé au petit état répliqué ; `sm.storage` passe derrière `StorageService` namespacé/schema-versionné.
