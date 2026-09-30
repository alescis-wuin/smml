# Questions ouvertes

Les questions GP0 transport/persistance fondamentales sont fermées. Les points ci-dessous appartiennent à GP1+ ou à des validations complémentaires.

## Runtime / multiplayer

- Quel format exact de handshake de profil/fingerprints doit bloquer un client divergent ?
- Comment classifier les contrats `client-only`, `server-only` et `both` ?
- Quelle compatibilité inter-version des contrats accepter entre client et serveur ?
- Quel canal `setClientData` réserver par build, et faut-il un allocator/capability au lieu d'un numéro fixe ?
- Quelle limite de taille/fréquence imposer aux RPC et états répliqués ?
- Validation complémentaire sur deux machines physiques/WAN : quels budgets de latence/perte/burst ?
- Si un serveur dédié officiel apparaît, quelles différences lifecycle/network/storage faudra-t-il requalifier ?
- Quelle qualité d'erreur produire sans `debug.traceback` ? Le dispatcher doit enrichir systématiquement avec contrat/mod/callback/phase.

## Storage

- Encodage physique final des namespaces/records SMML dans `sm.storage`.
- Stratégie de dirty flags/coalescing/flush.
- Politique de rétention des données lors de disable/uninstall.
- Classification d'impact `none/runtimeState/playerState/worldContent`.
- Migration multi-étapes, rollback et compatibilité downgrade.

## Content Composer

- Politique exacte des UUID vanilla dupliqués : precedence baseline + provenance plutôt qu'unicité globale stricte.
- Politique des noms d'effets dupliqués.
- Casefold Windows/Proton dans le CIR sans détruire l'orthographe exacte à réémettre.
- Recipes commentées : lexer minimal contrôlé vs dialecte JSON5.
- Icon atlas : allocation stable, réservation, migration, fragmentation.
- Quels caches précis invalider par famille de contenu au-delà des cas déjà démontrés ?

## State / transactions

- Format CAS/dédup du Baseline Vault.
- Granularité du write-ahead journal et protocole de fsync/rename par OS.
- Interaction avec Steam update pendant transaction.
- Garbage collection sans supprimer un état encore référencé.
- Politique de détection/récupération après crash ou coupure électrique.
- Politique multi-processus/verrouillage sur game root, state root et save root.

## Distribution / interop

- Format public final des mods SMML.
- Signature/authenticité/dépôt éventuel.
- Migration/coexistence avec bootstrapper, autres managers et Rivet.
- Stratégie Windows native après validation Linux/Proton.
