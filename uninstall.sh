#!/bin/bash
# ============================================================
# YTGrab — Désinstallateur
# ============================================================

set -e

INSTALL_DIR="${YTGRAB_INSTALL_DIR:-$HOME/.local/share/ytgrab}"
ICON_FILE="$HOME/.local/share/icons/ytgrab.svg"
DESKTOP_FILE="$HOME/.local/share/applications/ytgrab.desktop"
BIN_LINK="$HOME/.local/bin/ytgrab"
CONFIG_DIR="$HOME/.config/ytgrab"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo
echo "Désinstallation de YTGrab"
echo "Vont être supprimés :"
echo "  • $INSTALL_DIR (application et venv)"
echo "  • $ICON_FILE (icône)"
echo "  • $DESKTOP_FILE (raccourci menu)"
echo "  • $BIN_LINK (commande terminal)"
echo
read -p "Veux-tu aussi supprimer la config et l'historique ($CONFIG_DIR) ? [o/N] " ANSWER
DELETE_CONFIG=false
[[ "$ANSWER" =~ ^[oOyY]$ ]] && DELETE_CONFIG=true

echo
read -p "Confirmer la désinstallation ? [o/N] " CONFIRM
if [[ ! "$CONFIRM" =~ ^[oOyY]$ ]]; then
    echo "Annulé."
    exit 0
fi

echo
[ -d "$INSTALL_DIR" ] && rm -rf "$INSTALL_DIR" && echo -e "${GREEN}✓${NC} $INSTALL_DIR supprimé"
[ -f "$ICON_FILE" ] && rm -f "$ICON_FILE" && echo -e "${GREEN}✓${NC} Icône supprimée"
[ -f "$DESKTOP_FILE" ] && rm -f "$DESKTOP_FILE" && echo -e "${GREEN}✓${NC} Raccourci menu supprimé"
[ -L "$BIN_LINK" ] && rm -f "$BIN_LINK" && echo -e "${GREEN}✓${NC} Commande terminal supprimée"

if $DELETE_CONFIG && [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    echo -e "${GREEN}✓${NC} Config et historique supprimés"
fi

# Rafraîchir les caches
update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
gtk-update-icon-cache -f "$HOME/.local/share/icons/" 2>/dev/null || true

echo
echo -e "${GREEN}YTGrab a été désinstallé.${NC}"
echo
