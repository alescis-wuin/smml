# SMML — reprise rapide pour une nouvelle conversation

Le dépôt Git est désormais la source canonique du projet.

Commencer par lire :

1. `README.md` ;
2. `docs/project/current-state.md` ;
3. `docs/project/decisions-and-invariants.md` ;
4. `docs/project/open-questions.md` ;
5. `docs/project/roadmap.md` ;
6. les spécifications sous `specs/`.

État : GP0 fermé pour Scrap Mechanic 1.0.6 / engine 889 / Steam build 25442087. Les sept contrats GP1 fondamentaux sont au stade candidate freeze dans le snapshot issu de `smml-gp1-foundation-v0.6.0`.

Priorité suivante : `PathPolicy` + hashing + `GameTargetInspector`, puis `TransactionEngine` avec fault injection et recovery fail-closed. Ne pas commencer par la GUI.

Toujours distinguer FACT, INFERENCE, DESIGN DECISION et OPEN QUESTION. Les preuves moteur ont priorité sur la documentation externe.
