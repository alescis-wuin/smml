# Rapport de référence — Projet Scrap Mechanic Survival

## 1. Référentiel retenu

Le **handoff v1.0 du 28 septembre 2026** devient la source de vérité principale du projet. Les éléments plus anciens présents dans les connaissances du projet, anciens paquets, anciens journaux et notes restent utiles pour la généalogie des décisions et les régressions, mais ne doivent pas supplanter l’état documenté dans ce handoff. Son script de vérification d’intégrité a été exécuté avec succès.

L’archive du jeu est une seconde source de référence, principalement pour l’étude du vanilla. Elle contient un manifeste de **61 522 fichiers représentant environ 20,93 Go**, mais seulement **16 345 fichiers, environ 2,09 Go**, sont matériellement embarqués ; 45 177 sont référencés mais exclus, essentiellement des binaires. Il s’agit donc d’un excellent corpus de scripts, configurations, assets accessibles et métadonnées, mais pas d’une image binaire exhaustive du jeu.

Une différence de version importante doit être conservée en permanence dans le raisonnement :

| Référence | Version observée | Usage |
|---|---:|---|
| Archive du jeu fournie | **1.0.5.876** | Référence structurelle vanilla |
| Handoff / log moteur du 27 septembre | **1.0.6.889** | Référence du projet actuellement testé |
| Version publique officielle | **Patch 1.0.6**, mis à jour le **21 septembre 2026** | Référence externe actuelle |

Axolot indique que 1.0.6 est actuellement en ligne et que d’autres correctifs sont encore en préparation. Le jeu reste donc dans une période de changements assez rapprochés.

Conséquence : **aucun hash ni aucune ancre byte-level provenant uniquement de l’archive 1.0.5 ne doit être considéré comme autoritaire pour 1.0.6**. L’archive peut en revanche servir à comprendre la structure, construire des fixtures, rechercher des patterns vanilla et effectuer des comparaisons.

---

## 2. État consolidé du projet

| Branche | Version | État consolidé |
|---|---:|---|
| Presse à palettes | **0.3.2** | Branche principale ; 5 ressources × 14 profils = **70 palettes** ; `PropFull` validé en moteur ; nouveaux colliders Triangle à valider physiquement |
| Composteur | **0.2.3** | Architecture transactionnelle solide ; tests mocks/installateur aboutis ; validation réelle dans le moteur encore à faire |
| Pallet64 | **0.2.6** | Prototype d’asset et de packaging stable ; pas encore de validation moteur complète |

La ligne directrice reste cohérente : **modifier directement Survival**, préserver le monde Survival existant, augmenter la densité de stockage et réduire le nombre de Shapes physiques, tout en conservant une logique industrielle tangible. Les abstractions de type téléportation logistique, UI omniprésente ou modification directe des bases de sauvegarde restent hors cible.

La presse conserve notamment son UUID historique `d653c411-8db9-4e2f-8bd2-7a3728aa4b13`. Les palettes utilisent désormais les 24 orientations orthogonales grâce à `PropFull`. La convention géométrique établie — bloc logique, axe longitudinal Y de 8 blocs, séparation entre enveloppe `hull`, collider physique et rendu — est suffisamment mature pour servir de base définitive.

### Validation reproduite pendant cette analyse

Les tests des paquets de reprise ont été réexécutés indépendamment :

| Paquet | Résultat reproduit |
|---|---|
| Presse 0.3.2 | **27/27** tests installateur |
| Presse — géométrie | **70 variantes**, 14 profils |
| Presse — rotations | **769 vérifications** réussies |
| Presse — colliders | 7 Triangle + 7 Grid cohérents statiquement |
| Pallet64 | **16 tests réussis**, 1 test legacy optionnel ignoré faute de fixture historique |
| Composteur | **16/16 tests installateur** reproduits |
| Presse sur vanilla 1.0.5 fourni | `install --dry-run` accepté, aucune écriture |

Ces résultats augmentent fortement la confiance dans les transformations de fichiers et les invariants statiques, mais **ne remplacent pas les validations physiques dans Bullet/le moteur**.

---

## 3. Technologies et architecture réelles de Scrap Mechanic

Le jeu utilise son propre moteur. Axolot a historiquement indiqué utiliser **Bullet Physics** pour la physique ; les contraintes et collisions complexes sont précisément identifiées comme une source majeure de coût. Cette architecture justifie directement notre stratégie consistant à remplacer des dizaines de ressources physiques par une seule Shape physique et des représentations purement visuelles.

Le contrat de scripting officiel est toujours **Lua 5.1**. Les scripts sont organisés en classes moteur (`ShapeClass`, `ToolClass`, `WorldClass`, etc.) et communiquent avec les objets C++ du moteur par userdata.

Le corpus fourni montre également directement :

| Domaine | Technologie / formats observés |
|---|---|
| Rendu | moteur Axolot interne, **DirectX 11**, shader cache |
| Physique | Bullet historiquement ; API `sm.physics` |
| Audio | **FMOD Studio** |
| GUI | **MyGUI 3.4.2** observé dans le log 1.0.5 |
| Crash reporting | BugSplat |
| Scripting | Lua 5.1 |
| Modèles | DAE, FBX, OBJ |
| Description du rendu | `.rend` |
| Objets | `.shapeset` |
| Textures | TGA, notamment DIF / ASG / NOR |
| Monde | `.world`, `.tileson`, `.prefabson`, assetsets |
| Effets | `.effectset`, particules |
| Kinematics | `.kinematicset`, `.tracknodes` |
| Cache | `.cbo`, `.dco`, `.mco`, `.tco`, shader cache |

Dans la seule partie physiquement présente de l’archive figurent notamment **641 Lua, 2 678 JSON, 4 462 `.rend`, 101 `.shapeset`, 2 095 DAE, 841 OBJ, 356 FBX, 1 635 `.prefabson` et 776 `.tileson`**.

La version 1.0 du jeu, sortie le **24 juillet 2026**, a également introduit une importante refonte graphique, avec un nouveau système de matériaux, un éclairage fortement amélioré, des effets volumétriques et une refonte du monde.

---

## 4. Modding : distinction essentielle

Le chemin officiellement prévu par Axolot repose principalement sur le **Mod Tool**, le Workshop, les mods Blocks & Parts et les **Custom Games**. Le Mod Tool expose entre autres scripts de jeu et de monde, outils/armes, NPC, projectiles, kinematics, effets et terrains.

Notre projet suit volontairement un autre chemin : **patcher Survival directement**, parce que conserver le monde et le comportement Survival natifs fait partie des exigences.

Ce choix reste techniquement viable, mais il impose d’assumer quatre responsabilités que le système Workshop prend normalement en charge : compatibilité entre versions, fusion des fichiers partagés, reconstruction des caches et réversibilité exacte.

Axolot recommande lui-même de conserver les mods sur la version du jeu pour laquelle ils ont été conçus durant les transitions importantes. Cette recommandation est particulièrement pertinente depuis la 1.0.

Les signalements communautaires récents sur la 1.0 confirment aussi des comportements de cache où une version mise à jour d’un script peut ne pas être immédiatement utilisée. Ils constituent une corroboration, pas une spécification officielle.

Notre stratégie actuelle reste donc correcte : **invalidation ciblée**, conservation des autres caches, premier lancement normal sur l’installation actuelle, puis seulement utilisation de `-dev` si le workflow de développement l’exige. L’API officielle recommande `-dev` pour la console et le hot-reload, mais cela ne signifie pas qu’il doit être le premier lancement après une invalidation de cache sur cette installation.

---

## 5. Analyse de la presse 0.3.2

L’architecture générale est saine.

Les opérations modifiant les inventaires utilisent des transactions serveur `sm.container.beginTransaction/endTransaction`, conformément au modèle officiel. Ces transactions sont serveur-only et peuvent couvrir plusieurs conteneurs.

Les ressources visibles d’une palette sont réalisées par des effets `ShapeRenderable` attachés à l’Interactable. L’API recommande précisément les effets hébergés lorsqu’un effet doit suivre correctement position, orientation et vélocité d’une Shape.

Cela donne un compromis particulièrement approprié à Scrap Mechanic : **une seule Shape / un seul collider physique**, mais jusqu’à 64 représentations visuelles de ressources.

### Le verrou P0 reste la collision Triangle

Les colliders `profile-convex-prism-v1` sont cohérents statiquement et le log 1.0.6 montre leur rechargement par le moteur. Il reste cependant impossible de conclure qu’ils se comportent correctement sans le test moteur.

La phase **1.9A** reste donc prioritaire avant toute autre modification fonctionnelle : Triangle ×6, ×24, ×32 et ×64, contacts sur surface, bord, coin, empilage, orientations latérales, sur l’extrémité, retournées, puis sauvegarde/rechargement. Une Grid doit servir de contrôle.

Le critère critique n’est pas seulement « la palette ne traverse pas » : il faut vérifier qu’aucun coin vide de l’ancien parallélépipède englobant ne crée de support invisible.

La règle artificielle de support « deux bandes longitudinales complètes » doit rester en **1.9B conditionnelle**. Si Bullet et les nouveaux colliders donnent déjà un comportement satisfaisant, cette règle apporterait de la complexité et des cas limites sans bénéfice.

Si elle devient réellement nécessaire, l’API actuelle permet de faire une validation serveur par raycasts groupés avec `sm.physics.multicast`; `distanceRaycast` est explicitement présenté comme moins coûteux lorsqu’on cherche seulement une collision.

---

## 6. Optimisations identifiées dans le code actuel

L’analyse détaillée de `PalletPress.lua`, `PalletBundle.lua` et du vanilla fait apparaître plusieurs améliorations avant multiplication des machines.

| Point | Observation | Adaptation recommandée |
|---|---|---|
| Persistance | `self.storage:save` est actuellement appelé périodiquement toutes les 5 s, même au repos | Introduire un **dirty flag** ; sauvegarder sur changement discret et périodiquement seulement pendant un travail actif |
| Inventaire | Le conteneur de 96 slots peut être rescanné très fréquemment | Mettre en cache les quantités via `getRevision`, `hasChanged` ou `bindOnTransaction` |
| Réseau | `sv_publish` est appelé toutes les 0,25 s et reconstruit un snapshot complet | N’envoyer que lorsqu’un état change ; synchroniser la progression moins souvent ou l’interpoler côté client |
| Palette ×64 | 64 effets `ShapeRenderable` restent actifs | Utiliser `Effect:setStartStopDistance` pour le culling distant |
| Insertion CarryTool | `sv_e_receiveItem` valide item/quantité mais n’appelle pas le contrôle distance/monde de `sv_accept` | Réutiliser une validation serveur équivalente et contrôler explicitement la source |
| Packaging Composteur | `SHA256SUMS` référence deux `.pyc` dans `__pycache__` | Ne jamais distribuer ni hasher `__pycache__` dans la prochaine version |

La documentation officielle signale que les écritures dans `sm.storage` sont relativement coûteuses et doivent rester rares. Elle recommande également de réduire les données réseau et de ne les envoyer que lorsqu’elles sont nécessaires ou modifiées.

Pour les conteneurs, `bindOnTransaction`, `getRevision` et `hasChanged` sont directement disponibles. Le vanilla les utilise déjà pour éviter certains travaux permanents.

Ces optimisations ne sont pas nécessaires pour réussir 1.9A. Elles deviennent en revanche importantes avant une généralisation à de nombreuses presses, composteurs et docks simultanés.

---

## 7. Nouvelle piste forte pour les commandes physiques de la presse

Le vanilla `ResourceContainer.lua` fournit un pattern particulièrement adapté à notre objectif de commandes physiques sans multiplier les Shapes.

Le conteneur détermine quel emplacement le joueur vise en effectuant un raycast puis en transformant le point d’intersection en coordonnées locales de la Shape. Une seule Shape peut donc présenter plusieurs zones interactives logiques.

Ce principe permettrait de conserver **une seule presse physique**, tout en ayant sur sa façade des zones correspondant à :

- profil précédent / suivant ;
- Triangle / Grid ;
- récupération ;
- futur bouton marche/arrêt ;
- éventuel bouton d’upgrade ou de diagnostic.

Les boutons eux-mêmes peuvent rester intégrés au mesh ou être rendus par effets, tandis que le script calcule la région visée avec `shape:transformPoint()`.

Cette approche est mieux alignée avec les objectifs du projet que plusieurs petites Shapes interactives : moins de physique, pas de joints supplémentaires, pas de problème de sauvegarde d’assemblage, et aspect réellement « panneau de commande ».

---

## 8. Visualisation dynamique du contenu de la presse

Le même `ResourceContainer.lua` vanilla constitue un bon modèle pour l’étape visuelle suivante.

Plutôt que recréer continuellement des effets, la presse pourrait maintenir un **pool de ShapeRenderable** et :

1. observer la révision du conteneur ;
2. ne recalculer le rendu que lorsque son contenu change ;
3. affecter le bon UUID aux effets nécessaires ;
4. démarrer/arrêter les effets en fonction du nombre de ressources ;
5. appliquer `setStartStopDistance` pour les longues distances.

L’API supporte nativement les offsets relatifs au host, l’échelle et le démarrage/arrêt basé sur la distance.

On obtiendrait ainsi une presse qui se remplit réellement à chaque insertion sans créer de physique supplémentaire et sans synchronisation continue de géométrie.

---

## 9. Upgrades

Le vanilla `Seat.lua` donne une référence claire : coût en **Component Kits**, transaction serveur, puis `shape:replaceShape()` pour passer à l’UUID du niveau suivant. L’API documente officiellement `Shape.replaceShape` comme opération serveur.

Pour notre presse, je préfère cependant maintenir le concept déjà retenu de **presse unique à UUID stable** et enregistrer le niveau dans `self.storage`, sauf si une évolution géométrique impose réellement plusieurs Shapes.

Cela évite :

- la multiplication des UUID persistants ;
- les risques liés aux conteneurs pendant un remplacement ;
- la migration des anciennes presses déjà posées ;
- une complexification inutile des sauvegardes.

Les Component Kits peuvent être consommés exactement avec la transaction vanilla. Le niveau peut modifier temps de cycle, capacité, profils disponibles ou efficacité sans remplacer la Shape.

---

## 10. Dock Resource Collector

Deux mécanismes vanilla sont particulièrement intéressants.

`Refinery.lua` crée une `AreaTrigger`, recherche les Resource Collectors proches et transfère leurs ressources par transaction. Il utilise en parallèle `sm.pipeGraph` pour les circuits logistiques. L’API actuelle de `sm.pipeGraph` expose recherche de conteneurs, chemins, entrées/sorties et tâches automatisées.

Le nouveau `ParkingConnector.lua` présent dans le corpus 1.0.5 montre également une architecture de **dock explicite**, avec détection spatiale, état stable et contrôle serveur.

La direction la plus cohérente reste donc un **dock local**, sans réseau de téléportation :

Resource Collector → zone de dock → transfert transactionnel vers la presse.

Le mode manuel actuel doit rester disponible. Un futur raccordement `pipeGraph` peut être proposé comme couche supplémentaire, mais ne doit pas devenir une dépendance nécessaire au fonctionnement de la presse.

---

## 11. Performance et raison d’être des palettes compactes

Le choix « 1 palette = 1 Shape » est particulièrement pertinent compte tenu de l’architecture physique du jeu.

Axolot a expliqué que le coût physique devient élevé lorsque les collisions et contraintes de créations complexes interagissent. Réduire le nombre d’objets soumis à la physique, plutôt que simplement réduire le nombre de triangles graphiques, est donc le levier structurel le plus intéressant.

La palette ×64 actuelle donne ainsi 64 ressources visuellement identifiables pour **un seul objet Bullet**.

La prochaine optimisation logique n’est pas de revenir à plusieurs Shapes : elle consiste à réduire le coût purement graphique des 64 `ShapeRenderable`. `setStartStopDistance` constitue une première optimisation presque gratuite ; un proxy lointain unique pourrait venir plus tard seulement si un benchmark montre que cela vaut la complexité.

---

## 12. Gestion commune des patches Survival

Les trois branches touchent plusieurs fichiers centraux communs : enregistrement des shapesets, recettes, `RecipeManager`, IconMap et descriptions de langue ; la presse touche également `CarryTool`.

Les patchers individuels sont déjà défensifs et leurs tests sont bons, mais plusieurs installateurs indépendants conserveront toujours une dette de coordination.

La cible à moyen terme devrait être un **Direct Survival Patch Manager** unique utilisant des opérations sémantiques déclaratives.

Chaque module décrirait ses intentions (« ajouter ce shapeset », « ajouter cette recette », « enregistrer cette icône », « enregistrer ces textes », « ajouter cette cible CarryTool ») au lieu de posséder seul un fichier partagé.

Le gestionnaire pourrait alors recomposer les fichiers à partir d’une base observée et de l’ensemble des modules actifs, détecter les modifications externes, effectuer une transaction atomique commune, puis invalider une seule fois les caches concernés.

Cela supprimera la plupart des contraintes LIFO restantes et rendra la coexistence avec d’autres modifications sensiblement plus sûre.

---

## 13. Compatibilité de versions à formaliser

L’installateur de la presse accepte actuellement en dry-run le baseline 1.0.5 fourni, alors que le projet fonctionne en 1.0.6.889. C’est un bon signe de robustesse des patchs sémantiques, mais il ne faut pas l’interpréter comme une certification multi-version.

Chaque futur paquet devrait distinguer explicitement :

| Champ | Signification |
|---|---|
| `target_game_version` | version principale développée |
| `engine_tested_versions` | versions réellement lancées et testées |
| `structurally_tested_versions` | versions dont les fichiers ont passé installateur/tests |
| `unknown_compatible` | ancrages acceptés mais sans certification moteur |

Ainsi, 1.0.5 pourrait actuellement être « structurally tested », tandis que **1.0.6.889** est la cible moteur.

Avant un nouveau package public, les sept fichiers partagés de la presse devront être repris ou comparés à une **installation propre 1.0.6** plutôt qu’à l’archive fournie.

---

## 14. Priorités opérationnelles retenues

| Priorité | Travail | Critère de sortie |
|---|---|---|
| **P0** | Phase 1.9A, colliders Triangle | comportement réel satisfaisant dans toutes les orientations significatives + reload |
| **P0** | Examiner les tracebacks `SurvivalPlayer.lua:862` | cause reproduite ou pression innocentée |
| **P1** | Durcir `sv_e_receiveItem` | distance/monde/source validés serveur |
| **P1** | Rendu progressif du contenu | pool ShapeRenderable piloté par révision du conteneur |
| **P1** | Optimiser stockage/réseau/scans | dirty state + transactions/revisions |
| **P1** | Panneau de commande par raycast local | commandes physiques sans Shapes supplémentaires |
| **P2** | Upgrades Component Kits | niveau persistant, UUID principal stable |
| **P2** | Benchmark ×64 et culling | mesures avant/après |
| **P3** | Vraies recettes de fabrication des palettes | bois/corde/colle/énergie selon équilibrage |
| **P4** | Dock Resource Collector local | transfert transactionnel, fallback manuel |
| **P5** | Validation moteur complète Composteur | cycle, escrow, lift, reload, multiplayer |
| **P6** | Gestionnaire commun de patches | composition déterministe de tous les mods Survival |

---

## 15. Règles de conception à conserver comme invariants

- Le **handoff courant prime** sur les anciennes notes.
- Aucun changement direct des bases `.db` de monde.
- Sauvegarde récursive complète de `Save/` avant une modification du jeu.
- UUID déjà présent dans une sauvegarde = identité persistante à ne pas changer.
- Serveur autoritaire sur inventaires, production, déblocages et upgrades.
- Client utilisé essentiellement pour rendu, GUI et prédiction visuelle.
- Transactions natives pour tout échange de ressources.
- `self.storage` réservé à l’état compact qui ne peut pas être porté par les conteneurs, avec écritures parcimonieuses.
- Synchronisation réseau uniquement lorsque l’état utile change.
- `hull`, collider et visuel restent trois contrats distincts.
- Block-space comme référentiel géométrique ; conversion en mètres à la frontière des effets.
- Un seul objet physique chaque fois qu’un ensemble visuel peut raisonnablement être représenté par des effets.
- Cache invalidé de façon ciblée ; aucune suppression globale.
- Toute hypothèse issue d’un vieux tutoriel ou d’un mod pré-1.0 doit être vérifiée contre les fichiers vanilla et l’API actuelle.
- L’injection DLL et les API non officielles restent hors architecture normale ; elles ne seraient envisagées que si une limitation du Lua officiel bloque réellement un objectif indispensable.

## 16. Référentiel de travail pour les prochaines étapes

Pour la suite du projet, je considérerai **Presse 0.3.2 + handoff du 28 septembre + installation moteur 1.0.6.889** comme baseline. L’archive 1.0.5 servira de corpus vanilla de recherche et de fixtures, jamais de baseline binaire 1.0.6.

Pour les nouveaux développements, l’ordre de preuve sera : **test dans le moteur actuel → fichiers/package local → API officielle → code vanilla actuel → tests statiques/mocks → sources communautaires récentes → hypothèse**.

Les nouvelles décisions techniques devront être évaluées au minimum selon quatre axes : persistance dans les sauvegardes, comportement multijoueur serveur/client, coût physique/rendu, et réversibilité de l’installation.