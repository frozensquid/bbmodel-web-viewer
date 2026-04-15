# BBModel Viewer

**[Français](#fr)** · **[English](#en)**

---

<a id="fr"></a>

## Français

Éditeur web pour **voir et composer** des scènes 3D à partir de modèles Blockbench, sans installation lourde : ouvrir le fichier, importer des assets, placer les éléments, animer et exporter le résultat en image ou en projet sauvegardable.

### L’éditeur (`index.html`)

#### Démarrage

Ouvrez `index.html` dans un navigateur récent (Chrome, Edge, Firefox, etc.). Vous pouvez travailler en ouvrant le fichier directement depuis votre disque ; un serveur local n’est pas indispensable pour l’usage courant.

#### Ce que vous pouvez importer

- **`.bbmodel`** — projet Blockbench ; le viewer affiche le modèle et, s’il y en a, les **animations** des os.
- **`.glb`** — modèle 3D déjà au format glTF binaire, pour le mélanger avec d’autres éléments dans la même scène.
- **`.bbmv`** — **projet** enregistré depuis cette page : toute la scène (plusieurs modèles, lumières, images, texte, réglages) revient telle que vous l’aviez laissée, y compris l’animation en cours de lecture sur chaque modèle.

La zone d’accueil au premier lancement accepte le glisser-déposer ; les panneaux latéraux proposent aussi d’**ajouter** des modèles ou des médias.

#### Composer la scène

- **Modèles** — plusieurs modèles dans une même vue ; sélection, déplacement et rotation avec le gizmo (modes déplacement / rotation).
- **Animations** — barre en bas lorsque le modèle porte des animations Blockbench : choix de l’animation, lecture / pause, curseur de temps, option pour forcer la lecture en boucle.
- **Images** — plaquer des images dans l’espace 3D, les positionner et les mettre à l’échelle.
- **Texte** — ajouter du texte en 3D (contenu, couleur, police, taille dans la scène).
- **Lumières** — placer des sources lumineuses, régler couleur et intensité, ombres selon les options.
- **Environnement** — fond (ciel), sol, grille au sol ; tout reste lisible pour travailler la mise en scène.
- **Turntable** — rotation automatique autour de la scène, avec réglage de vitesse ; elle se coupe dès que vous manipulez la vue à la souris pour éviter les conflits.
- **Caméra d’export** — caméra optionnelle dans la scène pour cadrer précisément les **exports PNG et GIF** ; vous pouvez aussi vous contenter de la vue « éditeur » courante.

La navigation 3D classique s’applique : orbiter, zoomer, explorer la scène.

#### Exporter

- **Export (PNG / GIF)** — une fenêtre permet de choisir le format, une largeur maximale et un nom de fichier.  
  - **PNG** : une image fixe, soit depuis la vue actuelle, soit depuis la caméra d’export si vous l’avez activée.  
  - **GIF** : une séquence d’images ; vous choisissez le nombre d’images, un mode **turntable** (tour complet) ou **vue fixe**, et le délai entre les images. Si une animation est sélectionnée, elle est prise en compte dans la séquence.
- **Exporter / importer projet (`.bbmv`)** — sauvegarde complète de la scène pour la reprendre plus tard sur cette même page (modèles inclus, placement, lumières, médias, préférences, état des animations).

#### Langue

Un sélecteur de langue est disponible dans l’interface ; les textes peuvent être complétés ou ajustés via les fichiers du dossier `lang/`.

#### À savoir

Pour le premier chargement, la page peut **télécharger depuis Internet** des bibliothèques utilisées pour l’affichage 3D et, pour le GIF, un petit module d’encodage. L’export GIF suppose en pratique que ce chargement ait réussi au moins une fois.

Le projet vise les modèles **type Blockbench / cubes** ; les animations portent sur le squelette (os), pas sur tous les effets possibles dans l’éditeur Blockbench.

### Script Python `bbmodel_to_gltf.py` (FR)

Outil **en ligne de commande** pour convertir un fichier **`.bbmodel`** en **`.glb`** (un seul fichier) ou en **`.gltf`** (fichier texte + binaire + texture à côté), **sans** passer par le navigateur.

**Prérequis** — Python **3.10+** recommandé ; bibliothèque **pygltflib**.

```bash
pip install pygltflib
```

**Lancement**

```bash
python bbmodel_to_gltf.py chemin/vers/modele.bbmodel
```

Sans `--output`, un fichier `.glb` est créé à côté du `.bbmodel`, avec un nom dérivé de l’entrée.

| Argument | Description |
|----------|-------------|
| `input_file` | Chemin vers le `.bbmodel` (obligatoire). |
| `--output` | Chemin du fichier de sortie (extension `.glb` ou `.gltf`). |
| `--scale` | Facteur d’échelle (défaut : `1/16`, cohérent avec un rendu « blocs » / Minecraft). |
| `--texture-name` | Nom du fichier image exporté en mode `.gltf` (ressource externe). |
| `--linear` | Filtre de texture lissé au lieu du mode « pixel art » (plus proche voisin). |

**Texture** — le script utilise en priorité une image à côté du `.bbmodel`, puis les données dans le JSON Blockbench, puis des chemins valides dans le projet. La **première texture** du projet couvre tout le maillage dans ce flux.

Tout viewer ou moteur compatible **glTF 2.0** peut ouvrir le `.glb` produit.

---

<a id="en"></a>

## English

A single-page **web editor** to **view and stage** 3D scenes from Blockbench models—no heavy install: open the file, import assets, arrange everything, play animations, and export stills, GIFs, or a full project you can reopen later.

### The editor (`index.html`)

#### Getting started

Open `index.html` in a recent browser (Chrome, Edge, Firefox, etc.). You can open the file straight from disk; a local server is not required for typical use.

#### What you can import

- **`.bbmodel`** — Blockbench project; the viewer shows the model and any **bone** animations.
- **`.glb`** — binary glTF model to combine with other content in the same scene.
- **`.bbmv`** — **project** saved from this page: the whole scene (multiple models, lights, images, text, settings) comes back as you left it, including playback state per model.

The welcome area supports drag-and-drop; side panels also let you **add** models or media.

#### Building the scene

- **Models** — several models in one view; select, move, and rotate with the gizmo (translate / rotate modes).
- **Animations** — bottom bar when the model has Blockbench animations: pick an animation, play/pause, scrub time, optional forced looping.
- **Images** — place images in 3D space, position and scale them.
- **Text** — add 3D text (content, color, font, size in the scene).
- **Lights** — place lights, set color and intensity, shadows where supported.
- **Environment** — sky/background, ground, ground grid for a clear stage.
- **Turntable** — auto-rotation around the scene with speed control; it turns off when you orbit with the mouse to avoid fighting the controls.
- **Export camera** — optional in-scene camera to frame **PNG and GIF** exports precisely; you can also use the current editor view.

Standard 3D navigation: orbit, zoom, explore.

#### Export

- **Export (PNG / GIF)** — choose format, max width, and filename.  
  - **PNG** — one still, either the current editor view or the export camera if enabled.  
  - **GIF** — image sequence; set frame count, **turntable** (full spin) or **fixed** camera, and delay between frames. If an animation is selected, it is included in the sequence.
- **Export / import project (`.bbmv`)** — full scene snapshot to reopen later on this same page (embedded models, transforms, lights, media, preferences, animation state).

#### Language

A language selector is in the UI; strings live under `lang/` for edits or additions.

#### Notes

On first load, the page may **download** 3D libraries from the internet and, for GIFs, a small encoder. GIF export expects that load to succeed at least once.

The tool targets **Blockbench-style / cube** models; animations cover the bone rig, not every Blockbench effect.


### Python script `bbmodel_to_gltf.py` (EN)

**Command-line** tool to turn a **`.bbmodel`** into **`.glb`** (single file) or **`.gltf`** (JSON + bin + sidecar texture) **without** the browser.

**Requirements** — Python **3.10+** recommended; **pygltflib**.

```bash
pip install pygltflib
```

**Run**

```bash
python bbmodel_to_gltf.py path/to/model.bbmodel
```

Without `--output`, a `.glb` is written next to the `.bbmodel` with a derived name.

| Argument | Description |
|----------|-------------|
| `input_file` | Path to the `.bbmodel` (required). |
| `--output` | Output path (`.glb` or `.gltf`). |
| `--scale` | Global scale factor (default `1/16`, block-style / Minecraft-friendly). |
| `--texture-name` | Image filename when exporting external `.gltf` assets. |
| `--linear` | Linear texture filtering instead of nearest-neighbor (“pixel art”). |

**Texture** — the script looks for an image beside the `.bbmodel`, then embedded data in the Blockbench JSON, then valid paths in the project. The **first** project texture drives the whole mesh in this pipeline.

Any **glTF 2.0** viewer or engine can open the resulting `.glb`.
