# BBModel → navigateur (GLB + viewer web)

Outils pour **visualiser des modèles Blockbench** (`.bbmodel`) sur le web : conversion en **GLB** (glTF 2.0 binaire) via Python, ou **affichage direct** dans le navigateur sans export intermédiaire.

## Contenu du dépôt

| Fichier / dossier | Rôle |
|-------------------|------|
| `bbmodel_to_gltf.py` | Script Python : `.bbmodel` → `.glb` ou `.gltf` + binaire |
| `index.html` | Page web autonome : glisser-déposer un `.bbmodel` pour le voir en 3D (Three.js) |
| `bbmodels/` | Exemples de modèles (optionnel) |
| `old/` | Anciennes versions du convertisseur et scripts utilitaires |

## Prérequis (Python)

- Python 3.10+ recommandé  
- Dépendance : [pygltflib](https://pypi.org/project/pygltflib/)

```bash
pip install pygltflib
```

## Utiliser le script Python

### Conversion minimale

Le fichier de sortie prend par défaut le même nom que l’entrée, avec l’extension `.glb` :

```bash
python bbmodel_to_gltf.py chemin/vers/modele.bbmodel
```

### Spécifier la sortie

```bash
python bbmodel_to_gltf.py modele.bbmodel --output export/modele.glb
```

Pour un `.gltf` séparé + `.bin` + texture PNG à côté :

```bash
python bbmodel_to_gltf.py modele.bbmodel --output export/modele.gltf
```

### Options utiles

| Option | Description |
|--------|-------------|
| `--scale FACTEUR` | Échelle appliquée aux positions (défaut : `0.0625`, soit 1/16, adapté au style Minecraft) |
| `--texture-name nom.png` | Nom du fichier image référencé en mode `.gltf` (externe) |
| `--linear` | Filtre de texture linéaire au lieu du plus proche voisin |

### Texture

Le script charge la texture dans cet ordre de priorité :

1. Fichier image à côté du `.bbmodel` (même nom que dans `textures[0]`, ou `.png` / `.jpg` dérivé du nom)
2. Champ `source` en `data:image/...;base64,...` dans le JSON
3. Chemins `relative_path` ou `path` s’ils pointent vers un fichier existant

La **première entrée** du tableau `textures` du `.bbmodel` est utilisée pour tout le mesh (modèles multi-textures : une seule image est embarquée pour l’instant).

### Comportement du GLB produit

- Géométrie et UV alignées sur la logique Blockbench (`setShape` / `updateUV`)
- Transparence des textures : matériau en mode **MASK** avec `alphaCutoff` pour éviter les zones transparentes affichées en gris
- Hitboxes / cubes masqués : heuristique sur le nom (`hitbox`, `collision`, `_hb`) et champs `export` / `visibility`

## Utiliser l’interface web (`index.html`)

Aucun serveur n’est obligatoire : ouvrez le fichier dans un navigateur récent (Chrome, Edge, Firefox).

1. Double-cliquez sur `index.html` ou faites **Fichier → Ouvrir** dans le navigateur.
2. Glissez un fichier `.bbmodel` sur la zone, ou utilisez **Ouvrir .bbmodel**.
3. Le modèle s’affiche en 3D (orbite : clic pour tourner, molette pour zoomer).

La page charge **Three.js** et les contrôles depuis un CDN (connexion Internet requise au premier chargement). Elle lit le JSON du `.bbmodel` et la texture embarquée en base64 comme le script Python.

### Limitations du viewer web

- Même logique de texture que le script : **première texture** du projet pour tout le mesh.
- Pas d’export GLB depuis la page (visualisation uniquement).

## Visualiser un GLB ailleurs

Une fois le fichier généré par Python, vous pouvez l’ouvrir avec :

- [https://gltf-viewer.donmccurdy.com](https://gltf-viewer.donmccurdy.com)  
- Blender (Import glTF 2.0)  
- Tout moteur ou viewer compatible glTF 2.0  

## Référence Blockbench

Pour éditer les `.bbmodel` : [https://web.blockbench.net](https://web.blockbench.net)

## Licence

Précisez ici la licence de votre choix si vous publiez le dépôt.
