# MELODI Automation Engine

Le module `melodi_automation` est le moteur d'automatisation de MELODI. Il permet de concevoir, exécuter et superviser des workflows métier de manière visuelle et programmable, sans coupler directement les modules d'application.

## 1. Objectif du module

MELODI est un ERP modulaire. Chaque module peut produire des événements, exposer des actions et manipuler des données, mais la logique de coordination entre ces modules doit rester souple et évolutive. C'est précisément le rôle du module d'automatisation : orchestrer des séquences d'actions entre modules, déclencher des traitements à partir d'événements métier, et fournir un moteur d'exécution fiable pour la gestion des processus internes.

En pratique, il permet de transformer des procédures manuelles en workflows automatisés :

- déclencher une action après un événement métier,
- parcourir un graphe de nœuds métier,
- exporter/importer un workflow,
- tester ou simuler un scénario avant mise en production,
- consigner chaque exécution dans un journal d’audit.

---

## 2. Ce que le module apporte

### 2.1 Des workflows métier configurables

Le module gère des workflows enregistrés en base avec :

- un nom et une description,
- un déclencheur événementiel ou webhook,
- une version de workflow,
- une liste de nœuds et de connexions,
- un état actif/inactif,
- un historique d'exécutions.

Chaque workflow est versionné, ce qui permet de restaurer une version antérieure si nécessaire et de conserver un historique exploitable.

### 2.2 Un moteur d'exécution orienté graphe

Les workflows ne sont pas de simples tâches linéaires. Ils sont représentés sous forme de graphe de nœuds (nodes) reliés entre eux. Chaque nœud représente une étape ou une logique particulière :

- déclencheur d'événement,
- déclencheur webhook,
- condition logique (if/switch),
- transformation de données,
- appel d'une action de module,
- requête HTTP,
- journalisation,
- contrôle de flux.

Le moteur exécute ces nœuds selon les connexions du graphe, transmet les données entre étapes et enregistre les traces d'exécution.

### 2.3 Des déclencheurs événementiels et webhook

Le moteur s’abonne automatiquement aux événements actifs enregistrés en base. Lorsqu'un module émet un événement, le service d'automatisation vérifie s'il existe un workflow associé et le déclenche en arrière-plan.

Le module prend aussi en charge les webhooks externes via des tokens spécifiques, ce qui permet de lancer des workflows à partir de systèmes tiers sans dépendre du backend MELODI directement.

### 2.4 Une architecture modulaire et extensible

La plateforme MELODI favorise un couplage faible entre modules. Ici, le module Automation Engine est conçu pour fonctionner sans dépendre directement des tables d’autres modules.

Il s’intègre via :

- actions inter-modules,
- événements persistants,
- registre dynamique de nœuds,
- appels de service génériques.

Un module tiers peut exposer ses propres nœuds personnalisés et les rendre disponibles dans le moteur sans modifier le cœur MELODI.

---

## 3. Fonctions clés

### 3.1 Builder de workflow

L’interface d’administration permet de :

- créer un workflow,
- modifier ses propriétés,
- choisir son type de déclenchement,
- dessiner ses nœuds et connexions,
- enregistrer des types personnalisés,
- activer ou désactiver le workflow,
- simuler l’exécution.

Cette interface est centralisée dans l’admin MELODI et offre un point d’entrée visuel pour les opérations de workflow.

### 3.2 API de gestion

Le module expose des endpoints REST pour :

- lister les workflows,
- créer, modifier ou supprimer un workflow,
- importer/exporter un workflow,
- télécharger les fichiers de configuration exportés,
- tester un workflow,
- simuler une exécution,
- voir les exécutions et les logs,
- restaurer une version précédente,
- régénérer le token webhook.

Ces endpoints rendent le module compatible avec des usages multi-clients : interface web, intégrations externes, scripts de maintenance ou outils d’administration.

### 3.3 Journalisation et traçabilité

Chaque exécution est enregistrée avec un statut, un contexte de travail et des journaux détaillés. Cela permet de :

- suivre la progression du workflow,
- localiser une erreur,
- diagnostiquer un blocage,
- confirmer la fiabilité d’un traitement automatique.

La trace est essentielle pour les processus métiers sensibles comme la facturation, la trésorerie, le CRM ou les workflows de gestion interne.

### 3.4 Détection dynamique des nœuds disponibles

Le système dispose d’un registre de nœuds qui charge :

- les nœuds standard du moteur,
- les nœuds provenant de modules tiers,
- les nœuds exposés via un mécanisme de hooks.

Cela rend l’automatisation extensible sans modifier le cœur du module à chaque ajout fonctionnel.

---

## 4. Structure technique

Le module est organisé selon les conventions MELODI :

- `module.py` : chargement du module, enregistrement des routes, permissions, navigation et abonnement aux événements,
- `config.py` : paramètres et constantes de configuration,
- `models/` : modèles de workflow, versions, exécutions et journaux,
- `repositories/` : logique d'accès aux données et requêtes de persistance,
- `services/` : moteur de service, exécution et orchestration,
- `controllers/` : API REST et contrôleurs d’interface web,
- `nodes/` : catalogue des nœuds disponibles et gestion des nœuds personnalisés,
- `templates/` et `static/` : interface d’administration et ressources associées,
- `langs/` : pack de traduction FR/EN.

---

## 5. Modèles principaux

Le module est centré sur quatre objets techniques :

- `WorkflowModel` : workflow principal,
- `WorkflowVersionModel` : historique de versions du workflow,
- `ExecutionModel` : exécution d’un workflow,
- `ExecutionLogModel` : journal détaillé d’une exécution.

Cette séparation permet une meilleure gestion de la traçabilité, du debug et de la restauration rapide d’une version antérieure.

---

## 6. Cas d’usage typiques

Le module peut servir dans de nombreux scénarios :

- lorsqu’un client passe une commande, déclencher la création d’une facture,
- à la validation d’une commande, transmettre une notification interne,
- à la réception d’un événement externe, lancer un processus d’intégration,
- lorsqu’un statut change, exécuter des tâches de synchronisation,
- dès qu’un webhook arrive, traiter automatiquement une demande tierce,
- lorsqu’une erreur survient, déclencher un alerting ou une journalisation spécifique.

Le moteur est particulièrement utile lorsqu’une organisation a besoin d’automatiser des séquences métier qui traversent plusieurs modules MELODI sans créer de dépendances fortes entre eux.

---

## 7. Pourquoi ce module est important dans MELODI

Le module `melodi_automation` est un élément central de l’architecture ERP car il transforme un système modulaire en un environnement dynamique capable d’automatiser des opérations métier complexes.

Il apporte :

- plus de réactivité opérationnelle,
- moins de tâches manuelles,
- une meilleure cohérence des traitements,
- une traçabilité complète,
- une extensibilité via les modules MELODI.

En somme, il permet de passer d’un ERP orienté uniquement sur la gestion des données à un ERP capable de réagir automatiquement aux événements du business.

---

## 8. Conclusion

Le module `melodi_automation` est le moteur d’orchestration de MELODI. Il permet de modéliser les processus métier sous forme de workflows, de connecter les événements entre modules, d’exécuter des actions automatiquement et de garder un historique fiable de chaque opération.

C’est un module stratégique pour toute organisation qui souhaite automatiser ses opérations sans rigidifier l’architecture ni introduire de couplages techniques fragiles entre modules.
