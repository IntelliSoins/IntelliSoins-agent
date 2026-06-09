# Exploration de Mamba-3 sur Apple Silicon (MLX)

Ce répertoire contient des ressources pour étudier et expérimenter avec l'architecture **Mamba-3** et son intégration sur macOS via le framework **MLX** d'Apple.

---

## 🚀 Qu'est-ce que Mamba-3 ?

Introduit en **mars 2026** par des chercheurs de CMU, Princeton, Cartesia AI et Together AI (_« Mamba-3: Improved Sequence Modeling using State Space Principles »_), **Mamba-3** est une évolution majeure des architectures State Space Models (SSM).

### Améliorations clés par rapport à Mamba-1 et Mamba-2 :

1.  **Discrétisation Exponentielle-Trapézoïdale :** Plus expressive que la discrétisation Euler-exponentielle classique. Elle capture mieux la dynamique continue lors du passage à des tokens discrets.
2.  **Mises à jour complexes (Complex-Valued State Update) :** Utilise des états complexes pour doubler la capacité de mémorisation. Mamba-3 atteint une perplexité similaire à Mamba-2 avec **la moitié de la taille de l'état caché** ($d_{state} = 32$ au lieu de $64$).
3.  **Formulation MIMO (Multi-Input, Multi-Output) :** Optimise la bande passante mémoire et l'utilisation du GPU au décodage sans pénalité de latence.

---

## 🍏 Statut de l'intégration dans MLX (Apple Silicon)

L'intégration de Mamba-3 dans l'écosystème Apple Silicon est en développement actif :

- **Kernel natif Metal :** La **Pull Request #3519** (liée à l'issue #1935) sur le dépôt officiel [ml-explore/mlx](https://github.com/ml-explore/mlx) introduit un **kernel Mamba-3 SSD Metal fusionné** (fused kernel). Cela permet d'exécuter la récurrence complexe sans souffrir des boucles séquentielles lentes en Python.
- **Conversion de poids :** Des travaux communautaires sur Hugging Face (ex: `aifeifei798/Mamba3-MIMO-Tiny-HF` et `RtaForge/Mamba3-2.7B`) servent de bancs de test pour valider l'inférence.

---

## 📁 Contenu du dossier

- [explore.py](file:///Users/michaelahern/ai-servers/mamba3-mlx/explore.py) : Prototype en pur MLX simulant la récurrence complexe, la discrétisation trapézoïdale et la structure MIMO de Mamba-3.

---

## 🛠️ Comment exécuter le prototype

### 1. Prérequis

Installez les dépendances nécessaires dans votre environnement virtuel :

```bash
pip install mlx
```

### 2. Lancement du script

Pour tester l'instanciation et la propagation avant (forward pass) du bloc Mamba-3 avec MLX :

```bash
python explore.py
```

---

## 📚 Ressources Utiles

- **Papier de recherche :** [arXiv:2603.15569](https://arxiv.org/abs/2603.15569)
- **Code Mamba Officiel :** [state-spaces/mamba](https://github.com/state-spaces/mamba)
- **Kernel Metal MLX :** Suivre les PRs de [ml-explore/mlx](https://github.com/ml-explore/mlx)
