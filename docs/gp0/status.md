# GP0 — état de sortie au 29 septembre 2026

**Statut global : CLOSED pour Scrap Mechanic 1.0.6 build moteur 889 / Steam build 25442087.**

| Sous-phase | Statut | Preuve / remarque |
|---|---|---|
| 0.1 Baselines | **PASS build 889** | B0/B1, fingerprints, comparaison ancienne installation ; revalider à chaque nouvelle build |
| 0.2 Topologie/runtime | **PASS MVP** | multi-entry, sandbox, xpcall, Carry, lifecycle host/client ; client distinct validé en GP0.5 |
| 0.3 Hooks | **PASS FOR DESIGN** | inventaire statique + hooks Carry moteur ; formalisation Hook Pack passe en GP1 |
| 0.4 Content | **PASS FOR DESIGN** | registres/identités/dialectes cartographiés ; implémentation Composer passe en GP1 |
| 0.5 Network/Storage | **PASS** | probe v0.2.0, run GP05-20260929-153608, 16/16 checks combinés |

## GP0.5 — faits moteur établis

- deux processus Scrap Mechanic distincts, deux Steam/installations/préfixes Proton ;
- multijoueur A host / B client fonctionnel ;
- client→serveur, serveur→client, broadcast ;
- payloads de base et table imbriquée ;
- rejet contract/version/payload invalides ;
- enveloppe `nil` fail-open/rejet propre ;
- handler fautif isolé et RPC suivant opérationnel ;
- disconnect/reconnect ;
- restart monde/processus ;
- runtime client recréé au rejoin ;
- `setClientData` canaux 3 et 4 utilisables sur cette build ;
- état initial `setClientData` reçu par nouveau client ;
- storage absent→schema1→restart→migration schema2→restart→schema2 ;
- namespace logique vérifié.

## Gate de sortie

Les conditions suivantes sont satisfaites :

- transport global viable derrière abstraction ;
- persistance namespacée + migration démontrées ;
- vrai second processus client testé ;
- comportement restart/rejoin documenté ;
- backend et invariants runtime suffisamment établis pour spécifier GP1.

## Limites connues non bloquantes

- host et client étaient sur la même machine physique : ce test prouve la séparation processus/Steam/Proton et le chemin réseau moteur, pas les performances WAN ;
- aucun serveur dédié officiel n'est dans la distribution cible actuelle : `N/A` pour GP0, à requalifier si Axolot en publie un ;
- stress, latence, perte et budgets réseau appartiennent à une validation ultérieure ;
- canaux `setClientData` observés ne doivent pas être figés universellement.

## Fermeture propre

Après la campagne :

- `finish` host/client exécuté ;
- snapshot Save host restauré ;
- probe retiré ;
- merge final PASS ;
- hash vanilla de `SurvivalGame.lua` vérifié identique sur A et B ;
- aucun fichier `SMMLProbeNS` restant listé.

Voir :

- `03_GP0/GP0_5_NETWORK_STORAGE_RESULTS.md`
- `05_ANALYSIS/GP0_CLOSURE_2026-09-29.md`
- `06_EVIDENCE/gp0-network-storage/GP05-20260929-153608/`
