# KOT_TAS

Outil TAS (*tool-assisted speedrun*) pour **King of Thieves**, joué sur
l'émulateur Android **MEmu**, sous Windows.

Tu poses les sauts d'un run sur une frise. L'outil les rejoue à l'image près,
et tu décales d'une image, rejoues, recommences, jusqu'à ce que le run passe.
Il s'attache au jeu avec [Frida](https://frida.re) pour lire la position du
héros et tenir le temps du jeu, et il tape dans le jeu par adb.

> **Règle d'usage : uniquement sur ta propre base, jamais contre celle d'un
> autre joueur.**
>
> Projet personnel, non affilié à ZeptoLab. Tu l'utilises à tes risques.

## Ce qu'il te faut

- Windows 10 ou 11, 64 bits.
- Une connexion internet, pour l'installation et le premier lancement.
- Environ 3 Go d'espace disque (MEmu et le jeu).

## Installation

Compte une demi-heure. Chaque étape finit par une vérification : ne passe à
la suivante que si elle réussit.

### 1. MEmu

1. Télécharge MEmu sur <https://www.memuplay.com> et installe-le avec les
   options proposées par défaut.
2. Lance MEmu et attends l'écran d'accueil Android.
3. Ouvre les **Paramètres** de MEmu (icône d'engrenage dans la barre de
   droite) :
   - onglet **Moteur** (*Engine*) : active le **mode Root** (*Root mode*) ;
   - onglet **Affichage** (*Display*) : choisis la résolution
     **1600 × 900** (préréglage ou résolution personnalisée), DPI **300**.
4. Enregistre, puis redémarre MEmu quand il te le propose.

Pourquoi : l'outil a besoin des droits root sur l'émulateur pour y lancer
frida-server, et il tape au centre d'un écran de 1600 × 900, la seule
résolution sur laquelle il a été testé.

**Vérification :** après le redémarrage, les paramètres de MEmu montrent
toujours le mode Root activé et 1600 × 900.

### 2. King of Thieves 2.84

1. Dans MEmu, ouvre le **Play Store**, connecte-toi avec un compte Google et
   installe **King of Thieves**.
2. Lance le jeu une fois, jusqu'à ta base, pour qu'il finisse de télécharger
   ses données.

**Vérification :** dans MEmu, *Paramètres* Android → *Applications* →
*King of Thieves* : la version affichée doit être **2.84**.

L'outil est lié à cette version exacte (versionCode 4755781) : il lit la
mémoire du jeu à des adresses relevées sur la 2.84. Avec une autre version, il
refuse de démarrer plutôt que de lire n'importe quoi. Si le Play Store
installe une version plus récente, l'outil ne marchera pas tant que ces
adresses n'auront pas été mises à jour (voir [Limites](#limites)).

### 3. Python

1. Télécharge l'installeur Windows de Python sur
   <https://www.python.org/downloads/windows/> : la version 3.10 ou plus
   récente (l'outil est testé en 3.14).
2. Lance l'installeur. **Sur le premier écran, coche « Add python.exe to
   PATH »**, puis clique sur *Install Now*.
3. Si tu passes par *Customize installation*, laisse **« tcl/tk and IDLE »**
   coché : la fenêtre de l'atelier en a besoin.

**Vérification :** ouvre un **nouveau** terminal (menu Démarrer, tape
`PowerShell`, Entrée) et tape :

```
python --version
```

Il doit répondre `Python 3.x.y` avec x égal à 10 ou plus. S'il ouvre le
Microsoft Store ou dit que la commande est introuvable, la case « Add
python.exe to PATH » n'a pas été cochée : relance l'installeur, choisis
*Modify*, puis *Next*, coche **« Add Python to environment variables »** et
valide. Ouvre ensuite un nouveau terminal.

### 4. Récupérer le projet

Au choix :

- **Sans Git** : sur <https://github.com/Ant6508/KOT_TAS>, bouton vert
  **Code** → **Download ZIP**. Fais un clic droit sur le fichier téléchargé →
  *Extraire tout…*. Le ZIP contient un dossier `KOT_TAS-main` : c'est lui, le
  dossier du projet. Range-le où tu veux, par exemple `C:\KOT_TAS`.
- **Avec Git** (<https://git-scm.com/download/win>), plus pratique pour
  récupérer les mises à jour :

  ```
  git clone https://github.com/Ant6508/KOT_TAS C:\KOT_TAS
  ```

Toutes les commandes qui suivent se tapent dans un terminal ouvert **dans le
dossier du projet** :

```
cd C:\KOT_TAS
```

**Vérification :** `dir` liste notamment `controller`, `scripts` et
`pyproject.toml`.

### 5. Environnement Python

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

La première commande crée un Python propre au projet, dans `.venv`. La
seconde y installe Frida 17.18.0 et pytest. Toutes les commandes du projet
appellent ensuite **ce** Python, `.venv\Scripts\python.exe`, sans activation :
pas besoin de `Activate.ps1`, que PowerShell bloque souvent.

**Vérification :** la dernière ligne affichée commence par
`Successfully installed` et cite `frida-17.18.0`.

### 6. Vérifier l'installation

```
.venv\Scripts\python.exe -m pytest -q
```

**Vérification :** la dernière ligne dit `N passed`, sans `failed` ni
`error`. Ces tests ne touchent ni au jeu ni à MEmu : ils vérifient que le
projet est complet et que Python est bien installé.

### 7. Premier lancement

1. Lance MEmu, puis King of Thieves, jusqu'à ta base.
2. Dans le terminal :

   ```
   .venv\Scripts\python.exe scripts\atelier.py
   ```

   La fenêtre **Atelier TAS** s'ouvre.
3. Clique sur **▶ Essayer (relance)**. L'outil relance le jeu et s'y attache.

   **La toute première fois**, il installe d'abord frida-server sur MEmu, le
   petit programme par lequel Frida lit le jeu : le terminal affiche
   `frida-server absent : telechargement...`, puis l'outil le copie dans MEmu
   et le démarre. Compte une minute. Les fois suivantes, c'est immédiat.
4. Quand la fenêtre te dit de naviguer jusqu'à l'écran de commencement,
   ramène le jeu à l'écran de départ du run dans ta base, puis clique sur
   **J'y suis**.

L'outil trouve tout seul l'`adb` fourni avec MEmu : pas besoin d'installer le
SDK Android.

**Vérification :** après **J'y suis**, le run se déroule dans MEmu et la frise
de l'atelier se remplit. Si un message d'erreur apparaît, voir
[Dépannage](#dépannage).

## Utilisation

### L'atelier : poser un run

```
.venv\Scripts\python.exe scripts\atelier.py
.venv\Scripts\python.exe scripts\atelier.py films\mon_run.json
```

Une fenêtre à poser à côté de MEmu. Le bandeau dit toujours l'état du film et
pourquoi : **Brouillon** (sauts modifiés depuis le dernier essai), **Essayé**
(trace à jour depuis une relance, prêt à geler), **Gelé** (enregistré, lecture
seule). Chaque essai relance le jeu ; tu navigues jusqu'à l'écran de
commencement et cliques **J'y suis**. Un film gelé se rejoue deux fois
d'affilée : **Rejouer** (avec relance), puis **Rejouer encore** (sans).

Pour regarder le jeu à une image précise, place le repère puis **⏸ Arrêt au
repère** : Essayer, +10 et Jouer jusqu'au bout s'y figent, et Jouer jusqu'au
bout repart vers l'arrêt suivant. Un arrêt n'est pas dans le film. Pendant un
déroulé, **⏸ Pause** fige le jeu où il en est (à une seconde près).

Tes films s'enregistrent dans `films\` : ils rejouent **ta** base, et restent
chez toi (le dossier est ignoré par git).

### L'éditeur au clavier et la brute force

```
.venv\Scripts\python.exe scripts\tas.py
.venv\Scripts\python.exe scripts\tas.py --film=films\mon_run.json --label="ma base"
```

L'ancien éditeur, en console. L'aide des touches s'affiche au lancement : F1
commence une séance (relance du jeu), F2 rejoue rapidement, F3 valide avec
relance, **F4 cherche seul un couple de sauts qui atteint la cible** (brute
force), F5 enregistre.

### L'autoclic

Tape à intervalle régulier sur un point fixe. Il passe seulement par adb, sans
Frida.

```
.venv\Scripts\python.exe scripts\autoclic.py X Y --intervalle 0.2 --taps 100
.venv\Scripts\python.exe scripts\autoclic.py X Y --intervalle 0.2 --duree 120
```

- `X Y` : le point, en coordonnées de l'**écran Android** (1600 × 900), pas de
  la fenêtre MEmu : dans la fenêtre, retire 33 px en hauteur (la barre
  d'onglets).
- `--intervalle` : secondes entre deux touchers. Un tap adb coûte déjà
  environ 0,15 s : **0,2 s** est la cadence recommandée.
- Une limite est **obligatoire** : `--taps N` (nombre de touchers),
  `--duree S` (secondes), ou les deux.
- **Ctrl+C** l'arrête à tout moment ; il affiche toujours son bilan.

### Rejouer un film et vérifier qu'il est conforme

Un essai se mène en deux commandes, parce que la navigation dans le jeu est
manuelle :

```
.venv\Scripts\python.exe scripts\rejeu.py films\mon_run.json --relance
.venv\Scripts\python.exe scripts\rejeu.py films\mon_run.json
```

La première relance le jeu ; tu navigues jusqu'à l'écran de commencement. La
seconde rejoue le film et dit si le rejeu est identique à l'enregistrement. Au
tout premier essai d'un film, ajoute `--ecrire` à la seconde commande : elle
fixe l'empreinte de référence dans le film, et les essais suivants s'y
comparent.

### Plusieurs instances MEmu

Avec une seule instance ouverte, l'outil la trouve tout seul. Avec plusieurs,
il refuse de deviner et liste les appareils. Choisis l'instance **dans le même
terminal, avant de lancer** :

```
$env:KOT_SERIAL="127.0.0.1:21503"
.venv\Scripts\python.exe scripts\atelier.py
```

La première instance MEmu répond sur `127.0.0.1:21503`, la deuxième sur
`127.0.0.1:21513`, et ainsi de suite (+10 par instance). La variable ne vaut
que pour ce terminal ; pour l'effacer : `Remove-Item Env:KOT_SERIAL`.

### Mettre à jour

Avec Git : `git pull` dans le dossier du projet. Avec le ZIP : télécharge le
nouveau ZIP et remplace les fichiers, en gardant ton dossier `films`. Dans les
deux cas, relance ensuite :

```
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Dépannage

| Message | Cause | Solution |
|---|---|---|
| `python` n'est pas reconnu, ou le Microsoft Store s'ouvre | Python n'est pas dans le PATH | Étape 3 : relance l'installeur, *Modify*, « Add Python to environment variables », puis ouvre un nouveau terminal |
| `frida X est installe, mais l'outil attend 17.18.0` | Une autre version de Frida a été installée dans `.venv` | `.venv\Scripts\python.exe -m pip install "frida==17.18.0"` |
| `adb introuvable (...)` | MEmu n'est pas installé, ou installé d'une façon que l'outil ne reconnaît pas | Installe MEmu (étape 1). Sinon, ajoute au PATH le dossier qui contient `adb.exe` (dans le dossier de MEmu, sous-dossier `MEmu`) |
| `aucun appareil adb connecte : lance MEmu.` | MEmu est fermé, ou pas encore démarré | Lance MEmu, attends l'écran d'accueil, réessaie |
| `plusieurs appareils adb connectes (...)` | Plusieurs instances MEmu sont ouvertes | Ferme celles qui ne servent pas, ou pose `KOT_SERIAL` (voir [Plusieurs instances MEmu](#plusieurs-instances-memu)) |
| `version de jeu inattendue : ...` | King of Thieves n'est pas en 2.84 | L'outil ne marche qu'avec la 2.84 (voir [Limites](#limites)) |
| `com.zeptolab.thieves.google ne tourne pas. Lance le jeu dans MEmu.` | Le jeu est fermé | Lance King of Thieves dans MEmu |
| `frida-server 17.18.0 absent et impossible a telecharger` | Pas d'internet, ou GitHub injoignable | Vérifie ta connexion et réessaie. Sinon, suis les instructions du message : télécharge l'archive à la main, décompresse-la avec 7-Zip, range le fichier à l'endroit indiqué |
| `attache impossible apres 15 essais`, avec `frida-server` ou `closed` dans la dernière erreur | frida-server ne démarre pas : mode Root désactivé, ou ancien frida-server d'une autre version resté dans MEmu | Vérifie le mode Root (étape 1). Sinon, redémarre MEmu puis, dans un terminal, `& "C:\Program Files\Microvirt\MEmu\adb.exe" shell rm /data/local/tmp/frida-server` (adapte le chemin si MEmu est installé ailleurs) : l'outil réinstallera la bonne version |
| `l'agent refuse de demarrer. Symboles absents ou offsets invalides` | Juste après une relance, c'est normal : l'outil réessaie seul. Si ça persiste, le jeu n'est pas exactement la 2.84 | Vérifie la version du jeu (étape 2) |
| Les tests de l'étape 6 échouent | Installation incomplète | Refais l'étape 5, puis l'étape 6 |

## Limites

- **Uniquement King of Thieves 2.84.** L'outil lit la mémoire du jeu à des
  adresses relevées sur cette version ; à chaque mise à jour du jeu, elles
  sont à retrouver.
- **Uniquement MEmu sous Windows, en 1600 × 900.**
- Les commentaires du code renvoient souvent à `NOTES.md` : c'est le carnet de
  rétro-ingénierie de l'auteur, qui n'est pas publié.

## Licence

MIT : voir [LICENSE](LICENSE).
