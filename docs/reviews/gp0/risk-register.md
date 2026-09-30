# Registre des risques

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Update jeu change anchors/hashes | haute | haute | Hook Packs/build + preflight fail-closed |
| Autre manager a patché mêmes fichiers | moyenne/haute | haute | FOREIGN_MODIFICATION + diagnostics, pas de merge aveugle |
| Extras Steam non suivis | démontré | haute | scan exact + baseline locale |
| Corruption/perte save | faible mais critique | critique | snapshot récursif vérifié, jamais DB edit |
| Cache mal invalidé | moyenne | haute | causal mapping par famille, targeted invalidation |
| Userdata stale | démontré | moyenne | sm.exists/reacquire, lifecycle-aware handles |
| Hot hook trop coûteux | moyenne | moyenne/haute | budgets, instrumentation, ne pas exporter tout callback |
| Storage trop fréquent | moyenne | haute | buffer mémoire + transitions seulement |
| RPC trop bavard/non validé | moyenne | haute | multiplexage, limites payload, serveur autoritaire |
| UUID/path collision | moyenne | haute | resolver + CIR provenance + stable IDs |
| Baseline contient résidu | historique démontré | critique | clean validation + fingerprint + capture avant SMML |
| Crash au commit | moyenne | haute | journal write-ahead + recovery idempotent |
| Symlink/path traversal | faible | haute | reject symlinks, canonical roots |
| Framework tiers co-installé | croissante en 2026 | haute | signatures/interoperability preflight |
| Native DLL future fragilise sécurité | moyenne | haute | backend différé, signature/compatibilité strictes |
