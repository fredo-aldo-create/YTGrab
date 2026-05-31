#!/bin/bash
# ============================================================
# YTGrab — Installateur automatique
# Usage :
#   Depuis un clone local : ./install.sh
#   Depuis GitHub (one-liner) :
#     curl -fsSL https://raw.githubusercontent.com/fredo-aldo-create/ytgrab/main/install.sh | bash
# ============================================================

set -e  # Arrêt immédiat en cas d'erreur

# ----- Configuration -----
GITHUB_USER="${YTGRAB_GITHUB_USER:-fredo-aldo-create}"
REPO_NAME="${YTGRAB_REPO:-YTGrab}"
BRANCH="${YTGRAB_BRANCH:-main}"
INSTALL_DIR="${YTGRAB_INSTALL_DIR:-$HOME/.local/share/ytgrab}"
ICON_DIR="$HOME/.local/share/icons"
DESKTOP_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"

# ----- Couleurs pour le terminal -----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log()     { echo -e "${BLUE}[YTGrab]${NC} $1"; }
ok()      { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1" >&2; }
section() { echo -e "\n${BOLD}═══ $1 ═══${NC}"; }

# ----- Vérification : on est bien sous Linux -----
if [[ "$(uname -s)" != "Linux" ]]; then
    error "Ce script est conçu pour Linux uniquement."
    exit 1
fi

# ----- Détection du gestionnaire de paquets -----
detect_pkg_manager() {
    if command -v apt >/dev/null 2>&1; then
        echo "apt"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    elif command -v zypper >/dev/null 2>&1; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

PKG_MANAGER=$(detect_pkg_manager)

# ============================================================
# Étape 1 — Dépendances système
# ============================================================
section "1/5 — Vérification des dépendances système"

NEED_INSTALL=()

# Python 3
if ! command -v python3 >/dev/null 2>&1; then
    NEED_INSTALL+=("python3")
else
    ok "python3 présent ($(python3 --version))"
fi

# pip / venv
if ! python3 -c "import venv" 2>/dev/null; then
    case "$PKG_MANAGER" in
        apt) NEED_INSTALL+=("python3-venv" "python3-full") ;;
        dnf) NEED_INSTALL+=("python3-virtualenv") ;;
        pacman) NEED_INSTALL+=("python") ;;
        *) NEED_INSTALL+=("python3-venv") ;;
    esac
else
    ok "python3-venv présent"
fi

# ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
    NEED_INSTALL+=("ffmpeg")
else
    ok "ffmpeg présent ($(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f1-3))"
fi

# git (pour cloner si nécessaire)
if ! command -v git >/dev/null 2>&1; then
    NEED_INSTALL+=("git")
else
    ok "git présent"
fi

# Installation si nécessaire
if [ ${#NEED_INSTALL[@]} -gt 0 ]; then
    warn "Paquets à installer : ${NEED_INSTALL[*]}"
    case "$PKG_MANAGER" in
        apt)
            sudo apt update
            sudo apt install -y "${NEED_INSTALL[@]}"
            ;;
        dnf)
            sudo dnf install -y "${NEED_INSTALL[@]}"
            ;;
        pacman)
            sudo pacman -S --noconfirm "${NEED_INSTALL[@]}"
            ;;
        zypper)
            sudo zypper install -y "${NEED_INSTALL[@]}"
            ;;
        *)
            error "Gestionnaire de paquets non reconnu. Installe manuellement : ${NEED_INSTALL[*]}"
            exit 1
            ;;
    esac
    ok "Dépendances système installées"
fi

# ============================================================
# Étape 2 — Récupération des fichiers sources
# ============================================================
section "2/5 — Installation des fichiers dans $INSTALL_DIR"

# Détection : mode "exécuté localement depuis un clone" ou "one-liner curl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || SCRIPT_DIR=""

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/ytgrab.py" ]; then
    log "Mode local détecté — copie depuis $SCRIPT_DIR"
    mkdir -p "$INSTALL_DIR"
    cp "$SCRIPT_DIR/ytgrab.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/ytgrab-icon.svg" "$INSTALL_DIR/" 2>/dev/null || true
else
    log "Mode distant — clonage depuis GitHub"
    REPO_URL="https://github.com/$GITHUB_USER/$REPO_NAME.git"
    if [ -d "$INSTALL_DIR/.git" ]; then
        log "Dépôt déjà cloné — mise à jour avec git pull"
        (cd "$INSTALL_DIR" && git pull --ff-only)
    else
        # On retire l'éventuelle ancienne install non-git
        if [ -d "$INSTALL_DIR" ]; then
            warn "Sauvegarde de l'ancienne installation vers $INSTALL_DIR.old"
            mv "$INSTALL_DIR" "$INSTALL_DIR.old.$(date +%s)"
        fi
        git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
    fi
fi

# Vérification que les fichiers clés sont là
if [ ! -f "$INSTALL_DIR/ytgrab.py" ]; then
    error "ytgrab.py introuvable dans $INSTALL_DIR — installation échouée"
    exit 1
fi
ok "Fichiers source en place"

# ============================================================
# Étape 3 — Environnement Python virtuel et dépendances
# ============================================================
section "3/5 — Environnement Python (venv + dépendances)"

if [ ! -d "$INSTALL_DIR/venv" ]; then
    log "Création de l'environnement virtuel"
    python3 -m venv "$INSTALL_DIR/venv"
else
    ok "venv déjà existant"
fi

log "Installation/mise à jour des dépendances Python (yt-dlp, PyQt6, requests)"
"$INSTALL_DIR/venv/bin/pip" install --upgrade --quiet pip
"$INSTALL_DIR/venv/bin/pip" install --upgrade --quiet yt-dlp PyQt6 requests
ok "Dépendances Python installées"

# ============================================================
# Étape 4 — Script de lancement
# ============================================================
section "4/5 — Script de lancement"

cat > "$INSTALL_DIR/lancer.sh" << 'LAUNCHER_EOF'
#!/bin/bash
# Script de lancement YTGrab
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec ./venv/bin/python ytgrab.py "$@"
LAUNCHER_EOF
chmod +x "$INSTALL_DIR/lancer.sh"
ok "Script de lancement créé : $INSTALL_DIR/lancer.sh"

# Lien symbolique dans ~/.local/bin pour lancer 'ytgrab' depuis n'importe où
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/lancer.sh" "$BIN_DIR/ytgrab"
ok "Commande ytgrab disponible dans le terminal (via $BIN_DIR/ytgrab)"

# ============================================================
# Étape 5 — Icône et intégration au menu d'applications
# ============================================================
section "5/5 — Icône et menu d'applications"

mkdir -p "$ICON_DIR" "$DESKTOP_DIR"

# Installation de l'icône SVG
if [ -f "$INSTALL_DIR/ytgrab-icon.svg" ]; then
    cp "$INSTALL_DIR/ytgrab-icon.svg" "$ICON_DIR/ytgrab.svg"
    ok "Icône installée : $ICON_DIR/ytgrab.svg"
else
    warn "Icône SVG non trouvée — utilisation d'une icône système"
fi

# Création du raccourci .desktop
DESKTOP_FILE="$DESKTOP_DIR/ytgrab.desktop"
ICON_PATH="$ICON_DIR/ytgrab.svg"
[ ! -f "$ICON_PATH" ] && ICON_PATH="video-display"

cat > "$DESKTOP_FILE" << DESKTOP_EOF
[Desktop Entry]
Type=Application
Version=1.1
Name=YTGrab
GenericName=Téléchargeur YouTube
Comment=Télécharger des vidéos et de l'audio depuis YouTube
Exec=$INSTALL_DIR/lancer.sh
Icon=$ICON_PATH
Terminal=false
Categories=AudioVideo;
Keywords=youtube;download;video;mp3;mp4;telecharger;
StartupNotify=true
StartupWMClass=YTGrab
DESKTOP_EOF

chmod +x "$DESKTOP_FILE"
ok "Raccourci de menu créé : $DESKTOP_FILE"

# Rafraîchissement des caches
log "Rafraîchissement des caches du système"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f "$ICON_DIR" 2>/dev/null || true
ok "Caches rafraîchis"

# ============================================================
# Fin
# ============================================================
echo
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✓ YTGrab installé avec succès !${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════${NC}"
echo
echo "Pour lancer YTGrab :"
echo "  • Depuis le menu d'applications : cherche 'YTGrab'"
echo "  • Depuis le terminal           : ytgrab"
echo "  • Directement                  : $INSTALL_DIR/lancer.sh"
echo
echo "Pour mettre à jour ultérieurement :"
echo "  cd $INSTALL_DIR && git pull && ./install.sh"
echo
echo "Pour désinstaller :"
echo "  $INSTALL_DIR/uninstall.sh"
echo

# Vérification que ~/.local/bin est dans le PATH
if ! echo "$PATH" | tr ':' '\n' | grep -q "^$BIN_DIR$"; then
    warn "Note : $BIN_DIR n'est pas dans ton PATH."
    warn "Pour pouvoir taper 'ytgrab' dans le terminal, ajoute cette ligne à ~/.bashrc :"
    warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
