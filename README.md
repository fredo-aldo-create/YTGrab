# YTGrab

> Téléchargeur YouTube simple et efficace pour Linux, avec interface graphique PyQt6.

YTGrab est un téléchargeur YouTube léger conçu pour **Zorin OS** (et compatible avec toute distribution Linux récente : Ubuntu, Debian, Fedora, Arch). Interface sobre, look natif système, propulsé par [yt-dlp](https://github.com/yt-dlp/yt-dlp).

---

## Installation

### Installation automatique (recommandée)

Une seule commande dans le terminal :

```bash
curl -fsSL https://raw.githubusercontent.com/fredo-aldo-create/YTGrab/main/install.sh | bash
```

L'installateur s'occupe de tout :
- Installation des dépendances système (`python3-venv`, `ffmpeg`, `git`)
- Création d'un environnement Python isolé
- Installation de `yt-dlp`, `PyQt6` et `requests`
- Mise en place de l'icône et du raccourci dans le menu d'applications
- Création de la commande `ytgrab` dans le terminal

Après installation, lance YTGrab depuis :
- Le **menu d'applications** (cherche "YTGrab")
- Le **terminal** avec la commande `ytgrab`

### Installation manuelle :

```bash
git clone https://github.com/fredo-aldo-create/YTGrab.git
cd YTGrab
chmod +x install.sh
./install.sh
```
---

## Fonctionnalités

- **Formats vidéo** : MP4, WEBM
- **Formats audio** : MP3, M4A
- **Résolutions** : meilleure qualité, 4K, 2K, 1080p, 720p, 480p, 360p
- **Aperçu** avant téléchargement (titre, chaîne, durée, vues, miniature)
- **Support des playlists** YouTube complètes (un sous-dossier par playlist)
- **Nettoyage automatique des URLs** : retire les paramètres parasites (Mix/Radio, tracking) qui faisaient ramer les autres téléchargeurs
- **Barre de progression** avec vitesse et ETA
- **Historique persistant** des 200 derniers téléchargements
  - Double-clic : ouvrir le fichier
  - Clic droit : menu (ouvrir, dossier, copier URL, retélécharger, supprimer)
- **Annulation** propre d'un téléchargement en cours
- **Mémorisation** des préférences (dossier, format, résolution)

---

## Compatibilité

Testé sur **Zorin OS 18.1**. Devrait fonctionner sur toute distribution Linux fournissant :
- Python 3.10 ou plus récent
- `apt`, `dnf`, `pacman` ou `zypper` comme gestionnaire de paquets
- Un environnement de bureau supportant les fichiers `.desktop` (GNOME, KDE, XFCE, Cinnamon…)

---

## Utilisation

1. Colle l'URL d'une vidéo ou playlist YouTube (bouton **Coller** pour la prendre dans le presse-papiers)
2. Clique sur **Aperçu** pour voir le titre, la miniature, la durée
3. Choisis le **format** et la **résolution**
4. Choisis l'**emplacement** (mémorisé pour la prochaine fois)
5. Coche **« Télécharger la playlist entière »** si l'URL est une playlist
6. Clique sur **⬇ Télécharger**

---

## Mise à jour

```bash
cd ~/.local/share/YTGrab && git pull && ./install.sh
```

Pour mettre à jour uniquement `yt-dlp` (utile car YouTube change souvent son API) :

```bash
~/.local/share/YTGrab/venv/bin/pip install --upgrade yt-dlp
```

---

## Désinstallation

```bash
~/.local/share/YTGrab/uninstall.sh
```

Le script propose en option de supprimer la configuration et l'historique.

---

## Emplacement des fichiers

| Fichier | Emplacement |
|---|---|
| Application | `~/.local/share/YTGrab/` |
| Configuration | `~/.config/ytgrab/config.json` |
| Historique | `~/.config/ytgrab/history.json` |
| Icône | `~/.local/share/icons/ytgrab.svg` |
| Raccourci menu | `~/.local/share/applications/ytgrab.desktop` |
| Commande terminal | `~/.local/bin/ytgrab` |
| Téléchargements par défaut | `~/Téléchargements/YTGrab/` |

---

## Dépannage

**L'icône n'apparaît pas dans le menu**
Déconnecte-toi et reconnecte-toi à ta session. Sinon :
```bash
update-desktop-database ~/.local/share/applications/
gtk-update-icon-cache -f ~/.local/share/icons/
```

**La commande `ytgrab` n'est pas trouvée dans le terminal**
Ajoute `~/.local/bin` à ton PATH dans `~/.bashrc` :
```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Téléchargement échoue avec une erreur d'extraction**
YouTube a probablement changé son API. Mets à jour yt-dlp :
```bash
~/.local/share/YTGrab/venv/bin/pip install --upgrade yt-dlp
```

**Le MP4 1080p+ ne contient pas de son**
`ffmpeg` n'est pas installé ou pas accessible. Vérifie avec `ffmpeg -version`.

---

## Pourquoi YTGrab ?

J'ai créé YTGrab parce que les téléchargeurs YouTube disponibles sous Linux ne me satisfaisaient pas : interfaces lourdes, dépendances bizarres, ou logiciels propriétaires douteux. YTGrab fait une seule chose, simplement : télécharger une vidéo YouTube en quelques clics.

---

## Notes légales

À utiliser uniquement pour télécharger du contenu pour lequel vous avez les droits : vos propres vidéos, contenus du domaine public, vidéos sous Creative Commons, ou téléchargement personnel autorisé par les conditions générales d'utilisation de la plateforme dans votre juridiction.

---

## Crédits

- Propulsé par [yt-dlp](https://github.com/yt-dlp/yt-dlp) et [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- Conversion audio/vidéo par [FFmpeg](https://ffmpeg.org/)

---

## Licence

[MIT](LICENSE) — Libre de réutilisation, modification et redistribution.
