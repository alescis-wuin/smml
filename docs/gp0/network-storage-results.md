# GP0.5 — Résultats Network / Storage

## Identification

- Probe : `smml-gp0-network-storage-probe-v0.2.0`
- Run : `GP05-20260929-153608`
- Cible : Scrap Mechanic 1.0.6, engine build 889, Steam build 25442087
- Host A : Steam/installation/Proton distinct
- Client B : second Steam/installation/Proton distinct
- Machine physique : même hôte Linux
- Résultat combiné : **PASS**

## Checks combinés

Les 16 checks du mergeur sont à `true` :

1. `remote_client_to_server`
2. `server_to_remote_client`
3. `server_broadcast_to_remote_client`
4. `unknown_contract_rejected`
5. `bad_version_rejected`
6. `invalid_payload_rejected`
7. `handler_error_isolated`
8. `nil_envelope_fail_open`
9. `setClientData_usable_channel`
10. `setClientData_new_client_initial_state`
11. `remote_disconnect_reconnect`
12. `world_or_process_reload`
13. `storage_absent_to_schema1`
14. `storage_schema1_reload_and_migration`
15. `storage_schema2_survives_restart`
16. `logical_namespace_isolation`

`overall_pass=true`.

## Network

Le client B a exécuté la matrice RPC sur plusieurs créations de runtime.

Validé :

- client→server ;
- réponse server→client ;
- broadcast ;
- booléen ;
- nombre ;
- chaîne ;
- table imbriquée ;
- contrat inconnu rejeté ;
- version inconnue rejetée ;
- payload invalide rejeté ;
- handler volontairement fautif isolé ;
- RPC valide immédiatement après ;
- enveloppe `nil` reçue comme valeur inattendue puis rejetée sans casser le dispatcher.

## `setClientData`

Canaux communs observés utilisables : **3, 4**.

Le serveur publie un état avant l'arrivée du client ; le client rejoint et reçoit cet état. Après trafic distant, une nouvelle révision est reçue. Le comportement reste valide après restart.

Interprétation :

- viable pour petit état répliqué ;
- ne pas exposer le numéro de canal dans l'API publique ;
- sélectionner/réserver le canal par build/Hook Pack/capability.

## Lifecycle

Compteurs cumulés observés :

- server create : 3 ;
- server unload : 3 ;
- client create côté B : 4.

Le client a un runtime distinct après leave/rejoin. Les trois sessions host utilisent des runtimes distincts après fermeture/redémarrage complet.

## Storage

Séquence démontrée :

```text
session 1
  load absent
  namespace check
  save schema 1

session 2
  load schema 1
  namespace check
  migrate 1 → 2
  save schema 2

session 3
  load schema 2
  namespace check
  aucune nouvelle migration
```

Compteurs host cumulés :

- `storage.load.absent = 1`
- `storage.save.schema1 = 1`
- `storage.load.schema1 = 1`
- `storage.migration.1to2 = 1`
- `storage.save.schema2 = 1`
- `storage.load.schema2 = 1`
- `storage.namespace.check = 3`

Deux faux mods utilisant le même logical key sous des `modId` différents restent isolés.

## Conséquence architecturale

Transport MVP :

```text
SurvivalGame.network
→ TransportService
→ validation contract/version/payload
→ xpcall handler
→ réponse/broadcast
```

Storage MVP :

```text
sm.storage
→ StorageService
→ namespace modId
→ schemaVersion
→ migrations
→ dirty/coalesced writes
```

## Preuve

- `06_EVIDENCE/gp0-network-storage/GP05-20260929-153608/combined-summary.json`
- `06_EVIDENCE/gp0-network-storage/GP05-20260929-153608/SUMMARY.txt`
- `06_EVIDENCE/gp0-network-storage/GP05-20260929-153608/GP05-final-combined.zip`

Les logs bruts host/client ne sont pas inclus afin d'éviter la redistribution de chemins locaux et identifiants.
