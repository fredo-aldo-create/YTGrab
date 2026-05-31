#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YTGrab — Téléchargeur YouTube pour Zorin OS
Interface PyQt6 sobre, look natif système.

Dépendances :
    pip install --user yt-dlp PyQt6 requests
    sudo apt install ffmpeg

Auteur : Fred (fredo-aldo-create)
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QPixmap, QIcon, QDesktopServices, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QComboBox, QFileDialog, QProgressBar,
    QTableWidget, QTableWidgetItem, QTabWidget, QMessageBox, QHeaderView,
    QGroupBox, QFormLayout, QCheckBox, QStatusBar, QMenu, QSplitter,
    QAbstractItemView
)

try:
    import yt_dlp
except ImportError:
    print("ERREUR : yt-dlp n'est pas installé.")
    print("Installez-le avec : pip install --user yt-dlp")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None  # La miniature est optionnelle


# ============================================================
# Constantes
# ============================================================

APP_NAME = "YTGrab"
APP_VERSION = "1.1.0"
CONFIG_DIR = Path.home() / ".config" / "ytgrab"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Téléchargements" / "YTGrab")

RESOLUTIONS = ["Meilleure qualité", "2160p (4K)", "1440p (2K)", "1080p", "720p", "480p", "360p"]
FORMATS = ["MP4 (vidéo)", "MP3 (audio)", "M4A (audio)", "WEBM (vidéo)"]


# ============================================================
# Utilitaire : nettoyage des URLs YouTube
# ============================================================

def clean_youtube_url(url):
    """
    Nettoie une URL YouTube en retirant les paramètres parasites :
    - Playlists Mix/Radio auto-générées (list=RD*) qui font ramer yt-dlp
    - start_radio, index, t (timestamp), pp, si, feature, etc.

    PRÉSERVE les vraies playlists (list=PL*, UU*, OL*, FL*, LL*) et
    les URLs courtes (youtu.be).

    Retourne (url_nettoyée, a_été_modifiée).
    """
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    try:
        parsed = urlparse(url)
        if 'youtube.com' not in parsed.netloc and 'youtu.be' not in parsed.netloc:
            return url, False

        # URL courte youtu.be : on enlève juste les paramètres de tracking
        if 'youtu.be' in parsed.netloc:
            params = parse_qs(parsed.query)
            # On retire les paramètres parasites
            for junk in ['si', 'feature', 't', 'pp']:
                params.pop(junk, None)
            new_query = urlencode(params, doseq=True)
            cleaned = urlunparse(parsed._replace(query=new_query))
            return cleaned, cleaned != url

        # URL classique youtube.com
        params = parse_qs(parsed.query)
        modified = False

        # Mix / Radio auto-générée : list commence par RD (sauf RDCMU et RDGM qui sont des vrais mix éditoriaux mais traités pareil pour éviter les blocages)
        if 'list' in params:
            list_id = params['list'][0]
            if list_id.startswith('RD'):
                params.pop('list', None)
                params.pop('index', None)
                params.pop('start_radio', None)
                modified = True

        # Paramètres parasites toujours retirables
        for junk in ['start_radio', 'pp', 'si', 'feature', 't', 'ab_channel']:
            if junk in params:
                params.pop(junk, None)
                modified = True

        if modified:
            new_query = urlencode(params, doseq=True)
            cleaned = urlunparse(parsed._replace(query=new_query))
            return cleaned, True

        return url, False
    except Exception:
        return url, False


# ============================================================
# Worker : récupération d'infos vidéo (titre, durée, miniature)
# ============================================================

class InfoFetchWorker(QThread):
    info_ready = pyqtSignal(dict)
    info_error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            # Détection si l'URL pointe vers une playlist légitime
            # (paramètre list=... encore présent après nettoyage)
            is_playlist_url = 'list=' in self.url

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                # extract_flat='in_playlist' = ne pas résoudre chaque vidéo de la playlist,
                # ce qui accélère ÉNORMÉMENT (de plusieurs minutes à quelques secondes)
                'extract_flat': 'in_playlist' if is_playlist_url else False,
                'socket_timeout': 15,
                # Limite le nombre d'entrées remontées pour l'aperçu (sécurité)
                'playlistend': 500,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            # Cas d'une playlist
            if info.get('_type') == 'playlist':
                self.info_ready.emit({
                    'is_playlist': True,
                    'title': info.get('title', 'Playlist sans nom'),
                    'count': len(info.get('entries', [])),
                    'thumbnail': info.get('thumbnails', [{}])[-1].get('url', '') if info.get('thumbnails') else '',
                    'entries': [
                        {'title': e.get('title', '?'), 'duration': e.get('duration', 0)}
                        for e in info.get('entries', []) if e
                    ]
                })
            else:
                self.info_ready.emit({
                    'is_playlist': False,
                    'title': info.get('title', 'Sans titre'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Inconnu'),
                    'thumbnail': info.get('thumbnail', ''),
                    'view_count': info.get('view_count', 0),
                })
        except Exception as e:
            self.info_error.emit(str(e))


# ============================================================
# Worker : téléchargement
# ============================================================

class DownloadWorker(QThread):
    progress = pyqtSignal(float, str)  # pourcentage, texte d'état
    finished_ok = pyqtSignal(str, str)  # titre, chemin
    finished_err = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, url, output_dir, fmt, resolution, is_playlist=False):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.fmt = fmt
        self.resolution = resolution
        self.is_playlist = is_playlist
        self._cancel = False
        self.current_title = ""
        self.current_file = ""

    def cancel(self):
        self._cancel = True

    def _progress_hook(self, d):
        if self._cancel:
            raise Exception("Téléchargement annulé par l'utilisateur")

        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                pct = (downloaded / total) * 100
                speed = d.get('speed', 0) or 0
                speed_str = self._format_speed(speed)
                eta = d.get('eta', 0) or 0
                eta_str = self._format_eta(eta)
                self.progress.emit(pct, f"Téléchargement… {pct:.1f}% • {speed_str} • ETA {eta_str}")
            else:
                self.progress.emit(0, "Téléchargement en cours…")
        elif d['status'] == 'finished':
            self.current_file = d.get('filename', '')
            self.progress.emit(100, "Post-traitement (conversion)…")

    @staticmethod
    def _format_speed(b_per_s):
        if b_per_s <= 0:
            return "?"
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if b_per_s < 1024:
                return f"{b_per_s:.1f} {unit}"
            b_per_s /= 1024
        return f"{b_per_s:.1f} TB/s"

    @staticmethod
    def _format_eta(s):
        if s <= 0:
            return "?"
        m, s = divmod(int(s), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h{m:02d}"
        return f"{m}m{s:02d}s"

    def _build_options(self):
        os.makedirs(self.output_dir, exist_ok=True)
        outtmpl = os.path.join(self.output_dir, '%(title)s.%(ext)s')
        if self.is_playlist:
            outtmpl = os.path.join(self.output_dir, '%(playlist_title)s', '%(playlist_index)s - %(title)s.%(ext)s')

        opts = {
            'outtmpl': outtmpl,
            'progress_hooks': [self._progress_hook],
            'noplaylist': not self.is_playlist,
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': False,
        }

        # Format vidéo
        if self.fmt == "MP4 (vidéo)":
            if self.resolution == "Meilleure qualité":
                opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            else:
                # ex : "1080p" -> 1080
                max_h = int(re.search(r'\d+', self.resolution).group())
                opts['format'] = f'bestvideo[height<={max_h}][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_h}][ext=mp4]/best'
            opts['merge_output_format'] = 'mp4'

        elif self.fmt == "WEBM (vidéo)":
            if self.resolution == "Meilleure qualité":
                opts['format'] = 'bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best'
            else:
                max_h = int(re.search(r'\d+', self.resolution).group())
                opts['format'] = f'bestvideo[height<={max_h}][ext=webm]+bestaudio[ext=webm]/best[height<={max_h}]/best'
            opts['merge_output_format'] = 'webm'

        elif self.fmt == "MP3 (audio)":
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        elif self.fmt == "M4A (audio)":
            opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192',
            }]

        return opts

    def run(self):
        try:
            opts = self._build_options()
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                title = info.get('title', 'Sans titre') if not self.is_playlist else info.get('title', 'Playlist')
                self.current_title = title

            # Chemin final (yt-dlp renomme après conversion)
            final_path = self.current_file
            if self.fmt in ["MP3 (audio)", "M4A (audio)"]:
                ext = '.mp3' if self.fmt == "MP3 (audio)" else '.m4a'
                final_path = os.path.splitext(self.current_file)[0] + ext

            self.finished_ok.emit(self.current_title, final_path or self.output_dir)
        except Exception as e:
            self.finished_err.emit(str(e))


# ============================================================
# Worker : récupération de miniature
# ============================================================

class ThumbnailWorker(QThread):
    thumb_ready = pyqtSignal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        if not requests or not self.url:
            return
        try:
            r = requests.get(self.url, timeout=5)
            if r.status_code == 200:
                self.thumb_ready.emit(r.content)
        except Exception:
            pass


# ============================================================
# Fenêtre principale
# ============================================================

class YTGrabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Téléchargeur YouTube")
        self.resize(900, 650)

        self.config = self.load_config()
        self.history = self.load_history()

        self.info_worker = None
        self.thumb_worker = None
        self.download_worker = None
        self.current_info = None

        self.build_ui()
        self.refresh_history_table()

    # ------------- Persistance -------------

    def load_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {'download_dir': DEFAULT_DOWNLOAD_DIR, 'last_format': FORMATS[0], 'last_resolution': RESOLUTIONS[0]}

    def save_config(self):
        try:
            CONFIG_FILE.write_text(json.dumps(self.config, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception as e:
            print(f"Erreur sauvegarde config: {e}")

    def load_history(self):
        if HISTORY_FILE.exists():
            try:
                return json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
            except Exception:
                pass
        return []

    def save_history(self):
        try:
            HISTORY_FILE.write_text(json.dumps(self.history, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception as e:
            print(f"Erreur sauvegarde historique: {e}")

    # ------------- UI -------------

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_download_tab(), "Télécharger")
        self.tabs.addTab(self.build_history_tab(), "Historique")
        main_layout.addWidget(self.tabs)

        self.status = QStatusBar()
        self.status.showMessage(f"{APP_NAME} {APP_VERSION} — Prêt")
        self.setStatusBar(self.status)

    def build_download_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # ----- URL -----
        url_group = QGroupBox("URL de la vidéo ou playlist YouTube")
        url_layout = QHBoxLayout(url_group)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_edit.returnPressed.connect(self.fetch_info)
        self.paste_btn = QPushButton("Coller")
        self.paste_btn.clicked.connect(self.paste_url)
        self.preview_btn = QPushButton("Aperçu")
        self.preview_btn.clicked.connect(self.fetch_info)
        url_layout.addWidget(self.url_edit, 1)
        url_layout.addWidget(self.paste_btn)
        url_layout.addWidget(self.preview_btn)
        layout.addWidget(url_group)

        # ----- Aperçu (miniature + infos) -----
        preview_group = QGroupBox("Aperçu")
        preview_layout = QHBoxLayout(preview_group)
        self.thumb_label = QLabel("Aucun aperçu")
        self.thumb_label.setFixedSize(240, 135)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("border: 1px solid palette(mid); background: palette(base);")
        preview_layout.addWidget(self.thumb_label)

        info_layout = QVBoxLayout()
        self.info_title = QLabel("<i>Saisissez une URL puis cliquez sur Aperçu…</i>")
        self.info_title.setWordWrap(True)
        self.info_title.setTextFormat(Qt.TextFormat.RichText)
        self.info_duration = QLabel("")
        self.info_uploader = QLabel("")
        self.info_views = QLabel("")
        info_layout.addWidget(self.info_title)
        info_layout.addWidget(self.info_uploader)
        info_layout.addWidget(self.info_duration)
        info_layout.addWidget(self.info_views)
        info_layout.addStretch()
        preview_layout.addLayout(info_layout, 1)
        layout.addWidget(preview_group)

        # ----- Options -----
        opts_group = QGroupBox("Options de téléchargement")
        opts_layout = QFormLayout(opts_group)
        opts_layout.setSpacing(8)

        self.format_combo = QComboBox()
        self.format_combo.addItems(FORMATS)
        self.format_combo.setCurrentText(self.config.get('last_format', FORMATS[0]))
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        opts_layout.addRow("Format :", self.format_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        self.resolution_combo.setCurrentText(self.config.get('last_resolution', RESOLUTIONS[0]))
        opts_layout.addRow("Résolution :", self.resolution_combo)

        # Emplacement
        dir_layout = QHBoxLayout()
        self.dir_edit = QLineEdit(self.config.get('download_dir', DEFAULT_DOWNLOAD_DIR))
        self.dir_edit.setReadOnly(True)
        self.browse_btn = QPushButton("Parcourir…")
        self.browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(self.dir_edit, 1)
        dir_layout.addWidget(self.browse_btn)
        opts_layout.addRow("Emplacement :", dir_layout)

        self.playlist_check = QCheckBox("Télécharger la playlist entière (si l'URL en est une)")
        opts_layout.addRow("", self.playlist_check)

        layout.addWidget(opts_group)

        self.on_format_changed(self.format_combo.currentText())

        # ----- Action + progression -----
        action_layout = QHBoxLayout()
        self.download_btn = QPushButton("⬇  Télécharger")
        self.download_btn.setMinimumHeight(36)
        self.download_btn.clicked.connect(self.start_download)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_download)
        action_layout.addWidget(self.download_btn, 1)
        action_layout.addWidget(self.cancel_btn)
        layout.addLayout(action_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("En attente")
        layout.addWidget(self.progress_bar)

        layout.addStretch()
        return w

    def build_history_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Barre d'actions
        toolbar = QHBoxLayout()
        self.clear_history_btn = QPushButton("Vider l'historique")
        self.clear_history_btn.clicked.connect(self.clear_history)
        self.open_folder_btn = QPushButton("Ouvrir le dossier de téléchargements")
        self.open_folder_btn.clicked.connect(self.open_download_folder)
        toolbar.addWidget(self.open_folder_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_history_btn)
        layout.addLayout(toolbar)

        # Tableau
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Titre", "Format", "Statut", "Fichier"])
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setAlternatingRowColors(True)
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.history_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_table.customContextMenuRequested.connect(self.history_context_menu)
        self.history_table.doubleClicked.connect(self.open_history_file)
        layout.addWidget(self.history_table)

        return w

    # ------------- Callbacks UI -------------

    def paste_url(self):
        cb = QApplication.clipboard()
        text = cb.text().strip()
        if text:
            self.url_edit.setText(text)
            self.fetch_info()

    def on_format_changed(self, fmt):
        # La résolution n'a de sens que pour la vidéo
        is_audio = "audio" in fmt.lower()
        self.resolution_combo.setEnabled(not is_audio)

    def browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)
            self.config['download_dir'] = d
            self.save_config()

    # ------------- Aperçu vidéo -------------

    def fetch_info(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, "Info", "Saisissez une URL d'abord.")
            return
        if not self.is_valid_youtube_url(url):
            reply = QMessageBox.question(
                self, "URL inhabituelle",
                "Cette URL ne ressemble pas à une URL YouTube classique. Tenter quand même ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Nettoyage automatique de l'URL (Mix/Radio, paramètres parasites)
        cleaned_url, was_cleaned = clean_youtube_url(url)
        if was_cleaned:
            self.url_edit.setText(cleaned_url)
            self.status.showMessage("URL nettoyée (paramètres Mix/Radio retirés)")
            url = cleaned_url

        # Annule un worker précédent éventuel
        if self.info_worker and self.info_worker.isRunning():
            self.info_worker.quit()
            self.info_worker.wait(500)

        self.preview_btn.setEnabled(False)
        self.status.showMessage("Récupération des informations…")
        self.info_title.setText("<i>Chargement…</i>")
        self.info_duration.setText("")
        self.info_uploader.setText("")
        self.info_views.setText("")
        self.thumb_label.setText("Chargement…")
        self.thumb_label.setPixmap(QPixmap())

        self.info_worker = InfoFetchWorker(url)
        self.info_worker.info_ready.connect(self.on_info_ready)
        self.info_worker.info_error.connect(self.on_info_error)
        self.info_worker.start()

        # Watchdog : si après 30s on n'a toujours pas de réponse, on signale à l'utilisateur
        from PyQt6.QtCore import QTimer
        self._info_timeout = QTimer(self)
        self._info_timeout.setSingleShot(True)
        self._info_timeout.timeout.connect(self._on_info_timeout)
        self._info_timeout.start(30000)

    def _on_info_timeout(self):
        if self.info_worker and self.info_worker.isRunning():
            self.info_worker.quit()
            self.info_worker.wait(500)
            self.preview_btn.setEnabled(True)
            self.status.showMessage("Délai dépassé — vérifiez l'URL")
            self.info_title.setText("<i>Délai dépassé. L'URL contient peut-être une playlist trop longue ou un Mix YouTube.</i>")
            self.thumb_label.setText("Aucun aperçu")
            QMessageBox.warning(
                self, "Délai dépassé",
                "La récupération des informations a pris plus de 30 secondes.\n\n"
                "Cela arrive souvent avec les URLs contenant un Mix YouTube (playlist auto-générée).\n\n"
                "Essayez avec l'URL courte de la vidéo seule, par exemple :\n"
                "https://www.youtube.com/watch?v=ID_VIDEO"
            )

    def on_info_ready(self, info):
        if hasattr(self, '_info_timeout'):
            self._info_timeout.stop()
        self.current_info = info
        self.preview_btn.setEnabled(True)
        self.status.showMessage("Informations récupérées")

        if info.get('is_playlist'):
            self.info_title.setText(f"<b>📋 Playlist : {info['title']}</b>")
            self.info_uploader.setText(f"{info['count']} vidéos")
            self.info_duration.setText("")
            self.info_views.setText("")
            self.playlist_check.setChecked(True)
        else:
            self.info_title.setText(f"<b>{info['title']}</b>")
            self.info_uploader.setText(f"Chaîne : {info.get('uploader', '?')}")
            dur = info.get('duration', 0)
            if dur:
                m, s = divmod(int(dur), 60)
                h, m = divmod(m, 60)
                dur_str = f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"
                self.info_duration.setText(f"Durée : {dur_str}")
            views = info.get('view_count', 0)
            if views:
                self.info_views.setText(f"Vues : {views:,}".replace(',', ' '))
            self.playlist_check.setChecked(False)

        # Miniature
        thumb_url = info.get('thumbnail', '')
        if thumb_url and requests:
            self.thumb_worker = ThumbnailWorker(thumb_url)
            self.thumb_worker.thumb_ready.connect(self.on_thumb_ready)
            self.thumb_worker.start()
        else:
            self.thumb_label.setText("(miniature indisponible)")

    def on_thumb_ready(self, data):
        pix = QPixmap()
        if pix.loadFromData(data):
            scaled = pix.scaled(
                self.thumb_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumb_label.setPixmap(scaled)
            self.thumb_label.setText("")

    def on_info_error(self, err):
        if hasattr(self, '_info_timeout'):
            self._info_timeout.stop()
        self.preview_btn.setEnabled(True)
        self.status.showMessage("Erreur lors de la récupération")
        self.info_title.setText("<i>Impossible de récupérer les informations</i>")
        self.thumb_label.setText("Aucun aperçu")
        QMessageBox.warning(self, "Erreur", f"Impossible de récupérer les informations :\n\n{err}")

    @staticmethod
    def is_valid_youtube_url(url):
        return bool(re.match(r'^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/', url, re.IGNORECASE))

    # ------------- Téléchargement -------------

    def start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, "Info", "Saisissez une URL d'abord.")
            return

        # Nettoyage automatique de l'URL au cas où l'utilisateur n'a pas fait d'aperçu avant
        cleaned_url, was_cleaned = clean_youtube_url(url)
        if was_cleaned:
            self.url_edit.setText(cleaned_url)
            url = cleaned_url

        out_dir = self.dir_edit.text().strip() or DEFAULT_DOWNLOAD_DIR
        fmt = self.format_combo.currentText()
        res = self.resolution_combo.currentText()
        is_playlist = self.playlist_check.isChecked()

        # Sauvegarde des préférences
        self.config['last_format'] = fmt
        self.config['last_resolution'] = res
        self.config['download_dir'] = out_dir
        self.save_config()

        # Verrouillage UI
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.preview_btn.setEnabled(False)
        self.url_edit.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Démarrage…")

        self.download_worker = DownloadWorker(url, out_dir, fmt, res, is_playlist)
        self.download_worker.progress.connect(self.on_dl_progress)
        self.download_worker.finished_ok.connect(self.on_dl_ok)
        self.download_worker.finished_err.connect(self.on_dl_err)
        self.download_worker.start()

    def cancel_download(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.status.showMessage("Annulation demandée…")

    def on_dl_progress(self, pct, text):
        self.progress_bar.setValue(int(pct))
        self.progress_bar.setFormat(text)
        self.status.showMessage(text)

    def on_dl_ok(self, title, path):
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Terminé ✓")
        self.status.showMessage(f"Téléchargé : {title}")
        self.unlock_ui()

        self.add_to_history({
            'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'title': title,
            'format': self.format_combo.currentText(),
            'status': 'OK',
            'path': path,
            'url': self.url_edit.text().strip(),
        })

        QMessageBox.information(self, "Terminé", f"Téléchargement terminé :\n\n{title}")

    def on_dl_err(self, err):
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Erreur")
        self.status.showMessage("Erreur de téléchargement")
        self.unlock_ui()

        self.add_to_history({
            'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'title': self.url_edit.text().strip(),
            'format': self.format_combo.currentText(),
            'status': 'ERREUR',
            'path': '',
            'url': self.url_edit.text().strip(),
        })

        QMessageBox.critical(self, "Erreur", f"Le téléchargement a échoué :\n\n{err}")

    def unlock_ui(self):
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.preview_btn.setEnabled(True)
        self.url_edit.setEnabled(True)

    # ------------- Historique -------------

    def add_to_history(self, entry):
        self.history.insert(0, entry)
        # Garde 200 entrées max
        self.history = self.history[:200]
        self.save_history()
        self.refresh_history_table()

    def refresh_history_table(self):
        self.history_table.setRowCount(len(self.history))
        for row, entry in enumerate(self.history):
            self.history_table.setItem(row, 0, QTableWidgetItem(entry.get('date', '')))
            self.history_table.setItem(row, 1, QTableWidgetItem(entry.get('title', '')))
            self.history_table.setItem(row, 2, QTableWidgetItem(entry.get('format', '')))
            status_item = QTableWidgetItem(entry.get('status', ''))
            if entry.get('status') == 'ERREUR':
                status_item.setForeground(Qt.GlobalColor.red)
            else:
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            self.history_table.setItem(row, 3, status_item)
            self.history_table.setItem(row, 4, QTableWidgetItem(entry.get('path', '')))

    def clear_history(self):
        reply = QMessageBox.question(
            self, "Vider l'historique",
            "Effacer toutes les entrées de l'historique ?\n(les fichiers téléchargés ne seront PAS supprimés)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history = []
            self.save_history()
            self.refresh_history_table()

    def history_context_menu(self, pos):
        row = self.history_table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        open_file = QAction("Ouvrir le fichier", self)
        open_folder = QAction("Ouvrir le dossier contenant", self)
        copy_url = QAction("Copier l'URL", self)
        redownload = QAction("Retélécharger", self)
        remove = QAction("Supprimer de l'historique", self)
        menu.addAction(open_file)
        menu.addAction(open_folder)
        menu.addSeparator()
        menu.addAction(copy_url)
        menu.addAction(redownload)
        menu.addSeparator()
        menu.addAction(remove)

        action = menu.exec(self.history_table.viewport().mapToGlobal(pos))
        if action == open_file:
            self.open_history_file(self.history_table.model().index(row, 0))
        elif action == open_folder:
            entry = self.history[row]
            path = entry.get('path', '')
            if path and os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
            elif path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.config['download_dir']))
        elif action == copy_url:
            QApplication.clipboard().setText(self.history[row].get('url', ''))
            self.status.showMessage("URL copiée")
        elif action == redownload:
            self.url_edit.setText(self.history[row].get('url', ''))
            self.tabs.setCurrentIndex(0)
            self.fetch_info()
        elif action == remove:
            del self.history[row]
            self.save_history()
            self.refresh_history_table()

    def open_history_file(self, index):
        row = index.row()
        if row < 0 or row >= len(self.history):
            return
        path = self.history[row].get('path', '')
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.information(self, "Introuvable", "Le fichier est introuvable (déplacé ou supprimé ?).")

    def open_download_folder(self):
        d = self.config.get('download_dir', DEFAULT_DOWNLOAD_DIR)
        os.makedirs(d, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(d))


# ============================================================
# Main
# ============================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    # Style natif système (sobre), pas de feuille de style globale
    win = YTGrabWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
