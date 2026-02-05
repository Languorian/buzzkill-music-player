import sys
import os
import json
from pathlib import Path

# Suppress Qt multimedia debug output
os.environ['QT_LOGGING_RULES'] = 'qt.multimedia*=false'

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
							 QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
							 QTableWidget, QTableWidgetItem, QFileDialog, QSlider,
							 QLabel, QSplitter, QGridLayout, QDialog, QLineEdit,
							 QStatusBar)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QUrl, QSize, QThread, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

class ClickableSlider(QSlider):
	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			value = QSlider.minimum(self) + ((QSlider.maximum(self) - QSlider.minimum(self)) * event.position().x()) / self.width()
			self.setValue(int(value))
			self.sliderPressed.emit()
		super().mousePressEvent(event)

class LibraryScanner(QThread):
	finished = pyqtSignal(dict)

	def __init__(self, watched_folders):
		super().__init__()
		self.watched_folders = watched_folders

	def run(self):
		from mutagen import File
		new_library = {}
		audio_extensions = {'.mp3', '.flac', '.ogg', '.wav', '.m4a', '.wma'}

		for folder_path in self.watched_folders:
			if not os.path.exists(folder_path):
				continue

			for root, dirs, files in os.walk(folder_path):
				for file in files:
					if Path(file).suffix.lower() in audio_extensions:
						full_path = os.path.join(root, file)

						try:
							# Read metadata
							audio = File(full_path, easy=True)

							if audio is None:
								continue

							# Extract metadata with fallbacks
							genre = audio.get('genre', ['Unknown Genre'])[0] if audio.get('genre') else 'Unknown Genre'
							artist = audio.get('artist', ['Unknown Artist'])[0] if audio.get('artist') else 'Unknown Artist'
							album = audio.get('album', ['Unknown Album'])[0] if audio.get('album') else 'Unknown Album'

							# Build library structure
							if genre not in new_library:
								new_library[genre] = {}
							if artist not in new_library[genre]:
								new_library[genre][artist] = {}
							if album not in new_library[genre][artist]:
								new_library[genre][artist][album] = []

							new_library[genre][artist][album].append(full_path)

						except:
							continue

		self.finished.emit(new_library)

class ColorPickerDialog(QDialog):
	def __init__(self, parent=None, initial_color="#1976d2"):
		super().__init__(parent)
		self.setWindowTitle("Select Accent Color")
		self.setFixedWidth(300)

		layout = QVBoxLayout(self)

		# Current color preview
		self.color = QColor(initial_color)
		self.preview = QWidget()
		self.preview.setFixedHeight(80)
		self.update_preview()
		layout.addWidget(self.preview)

		# RGB Sliders
		self.r_slider = self.create_slider("R", self.color.red(), layout)
		self.g_slider = self.create_slider("G", self.color.green(), layout)
		self.b_slider = self.create_slider("B", self.color.blue(), layout)

		# HEX Input
		hex_layout = QHBoxLayout()
		hex_layout.addWidget(QLabel("HEX:"))
		self.hex_input = QLineEdit(self.color.name().upper())
		self.hex_input.textChanged.connect(self.on_hex_changed)
		hex_layout.addWidget(self.hex_input)
		layout.addLayout(hex_layout)

		# Buttons
		btn_layout = QHBoxLayout()
		ok_btn = QPushButton("OK")
		ok_btn.clicked.connect(self.accept)
		cancel_btn = QPushButton("Cancel")
		cancel_btn.clicked.connect(self.reject)
		default_btn = QPushButton("Default")
		default_btn.clicked.connect(lambda: self.hex_input.setText("#0E47A1"))

		btn_layout.addWidget(ok_btn)
		btn_layout.addWidget(cancel_btn)
		btn_layout.addWidget(default_btn)
		layout.addLayout(btn_layout)

	def create_slider(self, label, value, parent_layout):
		layout = QHBoxLayout()
		layout.addWidget(QLabel(label))
		slider = QSlider(Qt.Orientation.Horizontal)
		slider.setRange(0, 255)
		slider.setValue(value)
		slider.valueChanged.connect(self.on_slider_changed)
		layout.addWidget(slider)

		val_label = QLabel(str(value))
		val_label.setFixedWidth(30)
		layout.addWidget(val_label)
		slider.valueChanged.connect(lambda v: val_label.setText(str(v)))

		parent_layout.addLayout(layout)
		return slider

	def update_preview(self):
		self.preview.setStyleSheet(f"background-color: {self.color.name()}; border: 1px solid #3d3d3d; border-radius: 4px;")

	def on_slider_changed(self):
		self.color = QColor(self.r_slider.value(), self.g_slider.value(), self.b_slider.value())
		self.hex_input.blockSignals(True)
		self.hex_input.setText(self.color.name().upper())
		self.hex_input.blockSignals(False)
		self.update_preview()

	def on_hex_changed(self, text):
		if QColor.isValidColorName(text):
			self.color = QColor(text)
			self.r_slider.blockSignals(True)
			self.g_slider.blockSignals(True)
			self.b_slider.blockSignals(True)
			self.r_slider.setValue(self.color.red())
			self.g_slider.setValue(self.color.green())
			self.b_slider.setValue(self.color.blue())
			self.r_slider.blockSignals(False)
			self.g_slider.blockSignals(False)
			self.b_slider.blockSignals(False)
			self.update_preview()

	def get_color(self):
		return self.color.name()

class ScalableLabel(QLabel):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setMinimumSize(1, 1)
		self._original_pixmap = None

	def setPixmap(self, pixmap):
		self._original_pixmap = pixmap
		if pixmap and not pixmap.isNull():
			# Use current size, but fallback to sizeHint if size is too small
			target_size = self.size()
			if target_size.width() < 10 or target_size.height() < 10:
				target_size = QSize(300, 300)

			scaled = pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
			super().setPixmap(scaled)
		else:
			super().setPixmap(QPixmap())

	def resizeEvent(self, event):
		if self._original_pixmap and not self._original_pixmap.isNull():
			scaled = self._original_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
			super().setPixmap(scaled)
		super().resizeEvent(event)

class MusicPlayer(QMainWindow):
	def __init__(self):
		super().__init__()

		self.setWindowTitle("Buzzkill Music Player")

		# Default size (will be overridden by load_settings if saved geometry exists)
		self.setGeometry(100, 100, 1200, 720)

		# Music library structure: {genre: {artist: {album: [songs]}}}
		self.library = {}
		self.current_songs = []
		self.watched_folders = []

		# self.app_dir = Path(__file__).parent.resolve()

		# More robust cross-platform solution
		try:
			# Try to get the script's directory
			if getattr(sys, 'frozen', False):
				# Running as compiled executable
				self.app_dir = Path(sys.executable).parent.resolve()
			else:
				# Running as script
				self.app_dir = Path(__file__).parent.resolve()
		except:
			# Fallback to current working directory
			self.app_dir = Path.cwd()

		self.config_dir = self.app_dir / 'config'
		self.config_dir.mkdir(parents=True, exist_ok=True)
		self.library_file = self.config_dir / 'library.json'
		self.settings_file = self.config_dir / 'settings.json'
		self.playback_position_file = self.config_dir / 'playback_position.json'

		# Audio player setup
		self.player = QMediaPlayer()
		self.audio_output = QAudioOutput()
		self.player.setAudioOutput(self.audio_output)

		# Connect error handling
		self.player.errorOccurred.connect(self.handle_player_error)

		# Connect error handling and progress updates
		self.player.errorOccurred.connect(self.handle_player_error)
		self.player.positionChanged.connect(self.update_progress)
		self.player.durationChanged.connect(self.update_duration)
		self.player.mediaStatusChanged.connect(self.on_media_status_changed)

		self.progress_slider_pressed = False  # Track if user is dragging slider
		self.repeat_song = False
		self.repeat_album = False
		self.current_playlist = []  # Tracks for current selection
		self.current_track_index = 0
		self.dark_mode = True
		self.icon_size = QSize(24, 24)
		self.is_muted = False
		self.volume_before_mute = 50
		self.repeat_mode = 0	# 0=off, 1=song, 2=album
		self.shuffle_enabled = False
		self.unshuffled_playlist = []
		self.remember_position = False
		self.rounded_buttons = True
		self.accent_color = "#1976d2"
		self.show_album_art = False

		self.init_ui()
		self.load_library()

		# Background rescan on startup if we have folders saved
		if self.watched_folders:
			self.rescan_library()

		self.load_settings()
		self.restore_playback_position()

	def init_ui(self):
		# Main widget and layout
		main_widget = QWidget()
		self.setCentralWidget(main_widget)

		# Apply initial theme
		self.apply_theme()

		layout = QVBoxLayout(main_widget)

		#==============================================
		#==============     ROW 1    ==================
		#==============================================

		# Use QGridLayout instead of QHBoxLayout for the main row.
		# This allows us to balance the left and right sides perfectly so the center stays in the window center.
		controls_layout = QGridLayout()

		# Set column stretch: Column 0 (Left) and Column 2 (Right) get equal weight (1).
		# Column 1 (Center) gets 0 weight (it only takes the space it needs).
		controls_layout.setColumnStretch(0, 1)
		controls_layout.setColumnStretch(1, 0)
		controls_layout.setColumnStretch(2, 1)

		# ===========================
		# 1. LEFT SECTION
		# ===========================
		left_container = QWidget()
		left_container.setMinimumWidth(200)
		# We remove MaximumWidth so it can expand if needed to balance the grid,
		# but the layout inside keeps buttons to the left.

		left_controls = QHBoxLayout(left_container)
		left_controls.setContentsMargins(0, 0, 0, 0)
		left_controls.setAlignment(Qt.AlignmentFlag.AlignLeft)

		# Add folder button
		self.add_folder_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color, use_style_path=True))
		self.add_folder_btn.setIconSize(self.icon_size)
		self.add_folder_btn.setToolTip("Add folder to library")
		self.add_folder_btn.setFlat(True)
		self.add_folder_btn.clicked.connect(self.add_folder)
		left_controls.addWidget(self.add_folder_btn)

		# Rescan library button
		self.rescan_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.rescan_btn.setIcon(self.load_icon('rescan.svg', icon_color, use_style_path=True))
		self.rescan_btn.setIconSize(self.icon_size)
		self.rescan_btn.setToolTip("Rescan library for new files")
		self.rescan_btn.setFlat(True)
		self.rescan_btn.clicked.connect(self.rescan_library)
		left_controls.addWidget(self.rescan_btn)

		# Remember position toggle button
		self.remember_position_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.remember_position_btn.setIcon(self.load_icon('bookmark-off.svg', icon_color, use_style_path=True))
		self.remember_position_btn.setIconSize(self.icon_size)
		self.remember_position_btn.setToolTip("Remember playback position (Off)")
		self.remember_position_btn.setFlat(True)
		self.remember_position_btn.clicked.connect(self.toggle_remember_position)
		left_controls.addWidget(self.remember_position_btn)

		# Show album art toggle button
		self.show_album_art_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.show_album_art_btn.setIcon(self.load_icon('album-art.svg', icon_color, use_style_path=True))
		self.show_album_art_btn.setIconSize(self.icon_size)
		self.show_album_art_btn.setToolTip("Show album artwork")
		self.show_album_art_btn.setFlat(True)
		self.show_album_art_btn.clicked.connect(self.toggle_album_art)
		left_controls.addWidget(self.show_album_art_btn)

		# Button style toggle button (straight/rounded)
		self.button_style_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		style_icon = 'rounded.svg' if self.rounded_buttons else 'straight.svg'
		self.button_style_btn.setIcon(self.load_icon(style_icon, icon_color, use_style_path=False))
		self.button_style_btn.setIconSize(self.icon_size)
		self.button_style_btn.setToolTip("Toggle button style (Rounded/Straight)")
		self.button_style_btn.setFlat(True)
		self.button_style_btn.clicked.connect(self.toggle_button_style)
		left_controls.addWidget(self.button_style_btn)

		# Dark/Light Mode button
		self.darkmode_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.darkmode_btn.setIcon(self.load_icon('mode-dark.svg', icon_color, use_style_path=False))
		self.darkmode_btn.setIconSize(self.icon_size)
		self.darkmode_btn.setToolTip("Toggle dark/light mode")
		self.darkmode_btn.setFlat(True)
		self.darkmode_btn.clicked.connect(self.toggle_theme)
		left_controls.addWidget(self.darkmode_btn)

		# Accent Color button
		self.accent_btn = QPushButton()
		self.accent_btn.setIconSize(self.icon_size)
		self.accent_btn.setToolTip("Change accent color")
		self.accent_btn.setFlat(True)
		self.update_accent_icon()
		self.accent_btn.clicked.connect(self.choose_accent_color)
		left_controls.addWidget(self.accent_btn)

		# ===========================
		# 2. CENTER SECTION
		# ===========================
		center_container = QWidget()
		# No specific width limits needed here; the Grid Layout handles centering.

		center_controls = QHBoxLayout(center_container)
		center_controls.setContentsMargins(0, 0, 0, 0)
		center_controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

		# Previous track button
		self.prev_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.prev_btn.setIcon(self.load_icon('previous.svg', icon_color, use_style_path=True))
		self.prev_btn.setIconSize(self.icon_size)
		self.prev_btn.setToolTip("Go to previous track")
		self.prev_btn.setFlat(True)
		self.prev_btn.clicked.connect(self.previous_track)
		center_controls.addWidget(self.prev_btn)

		# Play/Pause button
		self.play_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.play_btn.setIcon(self.load_icon('play.svg', icon_color, use_style_path=True))
		self.play_btn.setIconSize(self.icon_size)
		self.play_btn.setToolTip("Play/Pause")
		self.play_btn.setFlat(True)
		self.play_btn.clicked.connect(self.play_pause)
		center_controls.addWidget(self.play_btn)

		# Stop button
		self.stop_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color, use_style_path=True))
		self.stop_btn.setIconSize(self.icon_size)
		self.stop_btn.setToolTip("Stop the current playing track")
		self.stop_btn.setFlat(True)
		self.stop_btn.clicked.connect(self.stop)
		center_controls.addWidget(self.stop_btn)

		# Next track button
		self.next_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.next_btn.setIcon(self.load_icon('next.svg', icon_color, use_style_path=True))
		self.next_btn.setIconSize(self.icon_size)
		self.next_btn.setToolTip("Go to next track")
		self.next_btn.setFlat(True)
		self.next_btn.clicked.connect(self.next_track)
		center_controls.addWidget(self.next_btn)

		# ===========================
		# 3. RIGHT SECTION
		# ===========================
		right_container = QWidget()
		right_container.setMinimumWidth(200)

		right_controls = QHBoxLayout(right_container)
		right_controls.setContentsMargins(0, 0, 0, 0)

		# KEY FIX: Add a stretch FIRST. This acts as a spring that pushes
		# all subsequent widgets to the Right, keeping them packed together.
		right_controls.addStretch()

		# Volume mute button
		self.mute_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color, use_style_path=True))
		self.mute_btn.setIconSize(self.icon_size)
		self.mute_btn.setToolTip("Mute/Unmute")
		self.mute_btn.setFlat(True)
		self.mute_btn.clicked.connect(self.toggle_mute)
		right_controls.addWidget(self.mute_btn)

		# Volume control
		self.volume_slider = QSlider(Qt.Orientation.Horizontal)
		self.volume_slider.setMinimum(0)
		self.volume_slider.setMaximum(100)
		self.volume_slider.setValue(50)
		self.volume_slider.setFixedWidth(150) # Use FixedWidth to prevent slider from flexing too much
		self.volume_slider.valueChanged.connect(self.change_volume)
		right_controls.addWidget(self.volume_slider)

		# Repeat button
		self.repeat_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color, use_style_path=False))
		self.repeat_btn.setIconSize(self.icon_size)
		self.repeat_btn.setToolTip("Repeat/Loop (Off, Song, Album)")
		self.repeat_btn.setFlat(True)
		self.repeat_btn.clicked.connect(self.cycle_repeat_mode)
		right_controls.addWidget(self.repeat_btn)

		# Shuffle button
		self.shuffle_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color, use_style_path=False))
		self.shuffle_btn.setIconSize(self.icon_size)
		self.shuffle_btn.setToolTip("Shuffle")
		self.shuffle_btn.setFlat(True)
		self.shuffle_btn.clicked.connect(self.toggle_shuffle)
		right_controls.addWidget(self.shuffle_btn)

		# ===========================
		# ASSEMBLE GRID
		# ===========================
		# Add widgets to the grid.
		# (Widget, Row, Column, Alignment)

		# Left container in Col 0, Aligned Left
		controls_layout.addWidget(left_container, 0, 0, Qt.AlignmentFlag.AlignLeft)

		# Center container in Col 1, Aligned Center
		controls_layout.addWidget(center_container, 0, 1, Qt.AlignmentFlag.AlignCenter)

		# Right container in Col 2, Aligned Right
		controls_layout.addWidget(right_container, 0, 2, Qt.AlignmentFlag.AlignRight)

		# Add the controls grid to the main layout
		layout.addLayout(controls_layout)

		# Set initial volume
		self.audio_output.setVolume(0.5)


		#==========================================================
		# Now Playing section
		now_playing_layout = QHBoxLayout()
		now_playing_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
		now_playing_label = QLabel("Now Playing:")
		now_playing_layout.addWidget(now_playing_label)

		self.now_playing_text = QLabel("---")
		self.now_playing_text.setStyleSheet("font-weight: bold;")
		now_playing_layout.addWidget(self.now_playing_text)

		layout.addLayout(now_playing_layout)

		# Progress bar section
		packed_layout = QHBoxLayout()
		packed_layout.setSpacing(8)

		self.progress_label = QLabel("0:00")
		packed_layout.addWidget(self.progress_label)

		self.progress_slider = ClickableSlider(Qt.Orientation.Horizontal)
		self.progress_slider.setMinimum(0)
		self.progress_slider.setMaximum(1000)
		self.progress_slider.setMinimumWidth(600)
		self.progress_slider.setMaximumWidth(950)
		self.progress_slider.sliderPressed.connect(self.on_progress_slider_pressed)
		self.progress_slider.sliderReleased.connect(self.on_progress_slider_released)
		self.progress_slider.sliderMoved.connect(self.on_progress_slider_moved)
		packed_layout.addWidget(self.progress_slider)

		self.duration_label = QLabel("0:00")
		packed_layout.addWidget(self.duration_label)

		progress_layout = QHBoxLayout()
		progress_layout.addStretch()
		progress_layout.addLayout(packed_layout)
		progress_layout.addStretch()

		layout.addLayout(progress_layout)

		#==============================================
		#==============     ROW 2    ==================
		#==============================================

		# Library browser (2 rows)
		self.splitter = QSplitter(Qt.Orientation.Vertical)

		# Row 1: Genre/Artist/Album columns (Resizable Splitter)
		self.horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)

		# Genre column
		self.genre_tree = QTreeWidget()
		self.genre_tree.setHeaderLabel("Genre")
		self.genre_tree.itemClicked.connect(self.on_genre_selected)
		self.genre_tree.itemDoubleClicked.connect(self.on_genre_double_clicked)
		self.horizontal_splitter.addWidget(self.genre_tree)

		# Artist column
		self.artist_tree = QTreeWidget()
		self.artist_tree.setHeaderLabel("Artist")
		self.artist_tree.itemClicked.connect(self.on_artist_selected)
		self.artist_tree.itemDoubleClicked.connect(self.on_artist_double_clicked)
		self.horizontal_splitter.addWidget(self.artist_tree)

		# Album column
		self.album_tree = QTreeWidget()
		self.album_tree.setHeaderLabel("Album")
		self.album_tree.itemClicked.connect(self.on_album_selected)
		self.album_tree.itemDoubleClicked.connect(self.on_album_double_clicked)
		self.horizontal_splitter.addWidget(self.album_tree)

		# Album artwork column
		self.album_art_label = ScalableLabel()
		self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.album_art_label.setStyleSheet("border: 1px solid #3d3d3d; background-color: #000000;")
		self.horizontal_splitter.addWidget(self.album_art_label)
		self.album_art_label.hide()

		self.splitter.addWidget(self.horizontal_splitter)
		self.horizontal_splitter.splitterMoved.connect(lambda: self.save_settings())

		# Connect source change to update album art
		self.player.sourceChanged.connect(self.update_album_art)

		#==============================================
		#==============     ROW 3    ==================
		#==============================================
		# Song list
		self.song_table = QTableWidget()
		self.song_table.setColumnCount(7)
		self.song_table.setHorizontalHeaderLabels(["Track #", "Title", "Artist", "Album", "Year", "Time", "Genre"])
		self.song_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
		self.song_table.verticalHeader().setVisible(False)  # Remove row numbers
		self.song_table.itemDoubleClicked.connect(self.on_song_double_clicked)
		self.song_table.horizontalHeader().sectionResized.connect(self.save_settings)
		self.splitter.addWidget(self.song_table)
		self.splitter.splitterMoved.connect(lambda: self.save_settings())

		# Set stretch factors: 0 for row 2 (don't stretch), 1 for row 3 (take all extra space)
		self.splitter.setStretchFactor(0, 0)  # top_widget (genre/artist/album) - no stretch
		self.splitter.setStretchFactor(1, 1)  # song_table - gets all the stretch

		layout.addWidget(self.splitter)

		# Status Bar
		self.setStatusBar(QStatusBar())
		self.statusBar().showMessage("Ready")

	def add_folder(self):
		folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
		if folder:
			if folder not in self.watched_folders:
				self.watched_folders.append(folder)

			# Trigger a background rescan which will also update the status bar
			self.rescan_library()

	def load_library(self):
		if not self.library_file.exists():
			self.statusBar().showMessage("No library found. Add your music library with the ADD FOLDER button located in the top-left.")
			print("No saved library found")
			return

		try:
			with open(self.library_file, 'r') as f:
				data = json.load(f)

			self.library = data.get('library', {})
			self.watched_folders = data.get('watched_folders', [])

			if not self.watched_folders:
				self.statusBar().showMessage("No library found. Add your music library with the ADD FOLDER button located in the top-left.")
			else:
				self.statusBar().showMessage("Ready")

			self.populate_genre_tree()
			print(f"Library loaded: {len(self.watched_folders)} folders")
		except Exception as e:
			print(f"Error loading library: {e}")

	def save_library(self):
		data = {
			'library': self.library,
			'watched_folders': self.watched_folders
		}

		try:
			with open(self.library_file, 'w') as f:
				json.dump(data, f, indent=2)
			print(f"Library saved: {len(self.watched_folders)} folders")
		except Exception as e:
			print(f"Error saving library: {e}")

	def scan_folder(self, folder_path):
		# Scan folder for audio files and organize by metadata
		from mutagen import File

		audio_extensions = {'.mp3', '.flac', '.ogg', '.wav', '.m4a', '.wma'}

		for root, dirs, files in os.walk(folder_path):
			for file in files:
				if Path(file).suffix.lower() in audio_extensions:
					full_path = os.path.join(root, file)

					try:
						# Read metadata
						audio = File(full_path, easy=True)

						if audio is None:
							continue

						# Extract metadata with fallbacks
						genre = audio.get('genre', ['Unknown Genre'])[0] if audio.get('genre') else 'Unknown Genre'
						artist = audio.get('artist', ['Unknown Artist'])[0] if audio.get('artist') else 'Unknown Artist'
						album = audio.get('album', ['Unknown Album'])[0] if audio.get('album') else 'Unknown Album'

						# Build library structure
						if genre not in self.library:
							self.library[genre] = {}
						if artist not in self.library[genre]:
							self.library[genre][artist] = {}
						if album not in self.library[genre][artist]:
							self.library[genre][artist][album] = []

						self.library[genre][artist][album].append(full_path)

					except Exception as e:
						print(f"Error reading {full_path}: {e}")
						continue

	def populate_genre_tree(self):
		self.genre_tree.clear()
		for genre in sorted(self.library.keys()):
			QTreeWidgetItem(self.genre_tree, [genre])

	def on_genre_selected(self, item):
		genre = item.text(0)
		self.artist_tree.clear()
		self.album_tree.clear()
		self.song_table.setRowCount(0)

		if genre in self.library:
			for artist in sorted(self.library[genre].keys()):
				QTreeWidgetItem(self.artist_tree, [artist])

		#self.save_settings()

	def on_artist_selected(self, item):
		genre_item = self.genre_tree.currentItem()
		if not genre_item:
			return

		genre = genre_item.text(0)
		artist = item.text(0)

		self.album_tree.clear()
		self.song_table.setRowCount(0)

		if artist in self.library[genre]:
			for album in sorted(self.library[genre][artist].keys()):
				QTreeWidgetItem(self.album_tree, [album])

		#self.save_settings()

	def on_album_selected(self, item):
		from mutagen import File

		genre_item = self.genre_tree.currentItem()
		artist_item = self.artist_tree.currentItem()

		if not genre_item or not artist_item:
			return

		genre = genre_item.text(0)
		artist = artist_item.text(0)
		album = item.text(0)

		self.song_table.setRowCount(0)

		if album in self.library[genre][artist]:
			self.current_songs = self.library[genre][artist][album]

			# Sort songs by track number/title
			self.current_songs = self.sort_playlist(self.current_songs)

			for i, song_path in enumerate(self.current_songs):
				self.song_table.insertRow(i)

				# Read metadata for track info
				try:
					audio = File(song_path, easy=True)

					if audio:
						# Track number
						track_num = audio.get('tracknumber', [''])[0] if audio.get('tracknumber') else ''
						# Handle "1/12" format, just take first number
						if '/' in str(track_num):
							track_num = track_num.split('/')[0]

						# Title
						title = audio.get('title', [Path(song_path).stem])[0] if audio.get('title') else Path(song_path).stem

						# Year
						year = audio.get('date', [''])[0] if audio.get('date') else ''
						# Handle full dates like "2015-01-01", just take year
						if '-' in str(year):
							year = year.split('-')[0]

						# Duration
						duration = audio.info.length if hasattr(audio, 'info') else 0
						minutes = int(duration // 60)
						seconds = int(duration % 60)
						time_str = f"{minutes}:{seconds:02d}"

						# Artist
						artist_name = audio.get('artist', [''])[0] if audio.get('artist') else ''

						# Album
						album_name = audio.get('album', [''])[0] if audio.get('album') else ''

						# Genre
						genre_name = audio.get('genre', [''])[0] if audio.get('genre') else ''


					else:
						track_num = ''
						title = Path(song_path).stem
						year = ''
						time_str = ''
				except:
					track_num = ''
					title = Path(song_path).stem
					artist_name = ''
					album_name = ''
					year = ''
					time_str = ''
					genre_name = ''

				# Populate columns
				self.song_table.setItem(i, 0, QTableWidgetItem(str(track_num)))
				self.song_table.setItem(i, 1, QTableWidgetItem(title))
				self.song_table.setItem(i, 2, QTableWidgetItem(artist_name))
				self.song_table.setItem(i, 3, QTableWidgetItem(album_name))
				self.song_table.setItem(i, 4, QTableWidgetItem(str(year)))
				self.song_table.setItem(i, 5, QTableWidgetItem(time_str))
				self.song_table.setItem(i, 6, QTableWidgetItem(genre_name))

				# Store the file path invisibly for playback
				self.song_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, song_path)

	def on_song_double_clicked(self, item):
		row = item.row()
		song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

		# Build playlist from current song table
		self.current_playlist = []
		for i in range(self.song_table.rowCount()):
			path = self.song_table.item(i, 0).data(Qt.ItemDataRole.UserRole)
			self.current_playlist.append(path)

		self.current_track_index = row
		self.play_song(song_path)

	def play_song(self, file_path):
			from mutagen import File

			icon_color = 'white' if self.dark_mode else 'black'

			self.player.setSource(QUrl.fromLocalFile(file_path))
			self.player.play()
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color, use_style_path=True))
			self.play_btn.setToolTip("Pause")

			# Update now playing display
			try:
				audio = File(file_path, easy=True)
				if audio:
					artist = audio.get('artist', ['Unknown Artist'])[0] if audio.get('artist') else 'Unknown Artist'
					title = audio.get('title', [Path(file_path).stem])[0] if audio.get('title') else Path(file_path).stem
					self.now_playing_text.setText(f"{artist} - {title}")
				else:
					self.now_playing_text.setText(Path(file_path).stem)
			except:
				self.now_playing_text.setText(Path(file_path).stem)

	def play_pause(self):
		icon_color = 'white' if self.dark_mode else 'black'

		# Check if there's a song loaded
		if self.player.source().isEmpty():
			return

		if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.player.pause()
			self.play_btn.setIcon(self.load_icon('play.svg', icon_color, use_style_path=True))
			self.play_btn.setToolTip("Play")
		else:
			self.player.play()
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color, use_style_path=True))
			self.play_btn.setToolTip("Pause")

	def stop(self):
		icon_color = 'white' if self.dark_mode else 'black'

		self.player.stop()
		self.play_btn.setIcon(self.load_icon('play.svg', icon_color, use_style_path=True))
		self.play_btn.setToolTip("Play")
		self.now_playing_text.setText("---")

	def next_track(self):
		if not self.current_playlist:
			return

		self.current_track_index += 1

		if self.current_track_index >= len(self.current_playlist):
			if self.repeat_album:
				self.current_track_index = 0
			else:
				self.stop()
				return

		song_path = self.current_playlist[self.current_track_index]
		self.play_song(song_path)
		self.highlight_current_song()

	def previous_track(self):
		if not self.current_playlist:
			return

		self.current_track_index -= 1

		if self.current_track_index < 0:
			self.current_track_index = 0

		song_path = self.current_playlist[self.current_track_index]
		self.play_song(song_path)
		self.highlight_current_song()

	def highlight_current_song(self):
		if not self.current_playlist:
			return

		# Find and select the current song in the table
		for row in range(self.song_table.rowCount()):
			song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
			if song_path == self.current_playlist[self.current_track_index]:
				self.song_table.selectRow(row)
				break

	def save_settings(self):
		# Get currently selected items
		genre_item = self.genre_tree.currentItem()
		artist_item = self.artist_tree.currentItem()
		album_item = self.album_tree.currentItem()

		# Get currently selected song
		current_song_row = self.song_table.currentRow()
		selected_song_path = None
		if current_song_row >= 0:
			selected_song_path = self.song_table.item(current_song_row, 0).data(Qt.ItemDataRole.UserRole)

		settings = {
			'column_widths': [
				self.song_table.columnWidth(0),
				self.song_table.columnWidth(1),
				self.song_table.columnWidth(2),
				self.song_table.columnWidth(3),
				self.song_table.columnWidth(4),
				self.song_table.columnWidth(5),
				self.song_table.columnWidth(6)
			],
			'splitter_sizes': self.splitter.sizes(),
			'horizontal_splitter_sizes': self.horizontal_splitter.sizes(),
			'window_geometry': [self.x(), self.y(), self.width(), self.height()],
			'window_maximized': self.isMaximized(),
			'selected_genre': genre_item.text(0) if genre_item else None,
			'selected_artist': artist_item.text(0) if artist_item else None,
			'selected_album': album_item.text(0) if album_item else None,
			'selected_song': selected_song_path,
			'repeat_mode': self.repeat_mode,
			'shuffle_enabled': self.shuffle_enabled,
			'remember_position': self.remember_position,
			'volume': self.volume_slider.value(),
			'rounded_buttons': self.rounded_buttons,
			'accent_color': self.accent_color,
			'show_album_art': self.show_album_art
		}

		try:
			with open(self.settings_file, 'w') as f:
				json.dump(settings, f, indent=2)
		except Exception as e:
			print(f"Error saving settings: {e}")

	def load_settings(self):
		if not self.settings_file.exists():
			# Set default column widths
			self.song_table.setColumnWidth(0, 80)   # Track #
			self.song_table.setColumnWidth(1, 300)  # Title
			self.song_table.setColumnWidth(2, 200)  # Artist
			self.song_table.setColumnWidth(3, 200)  # Album
			self.song_table.setColumnWidth(4, 80)   # Year
			self.song_table.setColumnWidth(5, 80)   # Time
			self.song_table.setColumnWidth(6, 150)  # Genre
			return

		try:
			with open(self.settings_file, 'r') as f:
				settings = json.load(f)

			# Restore column widths
			widths = settings.get('column_widths', [80, 300, 200, 200, 80, 80, 150])
			for i, width in enumerate(widths):
				self.song_table.setColumnWidth(i, width)

			# Restore splitter sizes
			splitter_sizes = settings.get('splitter_sizes')
			if splitter_sizes:
				self.splitter.setSizes(splitter_sizes)

			# Restore horizontal splitter sizes
			horizontal_splitter_sizes = settings.get('horizontal_splitter_sizes')
			if horizontal_splitter_sizes:
				self.horizontal_splitter.setSizes(horizontal_splitter_sizes)

			# Restore window geometry
			window_geometry = settings.get('window_geometry')
			if window_geometry:
				x, y, width, height = window_geometry
				self.setGeometry(x, y, width, height)

			# Restore maximized state
			window_maximized = settings.get('window_maximized', False)
			if window_maximized:
				self.showMaximized()

			# Restore volume
			volume = settings.get('volume', 50)
			self.volume_slider.setValue(volume)
			self.audio_output.setVolume(volume / 100.0)

			# Restore button style
			self.rounded_buttons = settings.get('rounded_buttons', True)

			# Restore accent color
			self.accent_color = settings.get('accent_color', "#1976d2")
			self.update_accent_icon()

			# Restore repeat mode
			self.repeat_mode = settings.get('repeat_mode', 0)
			icon_color = 'white' if self.dark_mode else 'black'

			if self.repeat_mode == 0:
				self.repeat_song = False
				self.repeat_album = False
				self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color, use_style_path=False))
				self.repeat_btn.setToolTip("Repeat Off")
			elif self.repeat_mode == 1:
				self.repeat_song = True
				self.repeat_album = False
				self.repeat_btn.setIcon(self.load_icon('repeat-song.svg', icon_color, use_style_path=False))
				self.repeat_btn.setToolTip("Repeat Song")
			elif self.repeat_mode == 2:
				self.repeat_song = False
				self.repeat_album = True
				self.repeat_btn.setIcon(self.load_icon('repeat-album.svg', icon_color, use_style_path=False))
				self.repeat_btn.setToolTip("Repeat Album")

			# Restore shuffle state
			self.shuffle_enabled = settings.get('shuffle_enabled', False)
			if self.shuffle_enabled:
				self.shuffle_btn.setIcon(self.load_icon('shuffle-on.svg', icon_color, use_style_path=False))
				self.shuffle_btn.setToolTip("Shuffle On")
			else:
				self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color, use_style_path=False))
				self.shuffle_btn.setToolTip("Shuffle Off")

			# Restore remember position state
			self.remember_position = settings.get('remember_position', False)
			if self.remember_position:
				self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg', icon_color, use_style_path=True))
				self.remember_position_btn.setToolTip("Remember playback position (On)")
			else:
				self.remember_position_btn.setIcon(self.load_icon('bookmark-off.svg', icon_color, use_style_path=True))
				self.remember_position_btn.setToolTip("Remember playback position (Off)")

			# Restore album art state
			self.show_album_art = settings.get('show_album_art', False)
			if self.show_album_art:
				self.album_art_label.show()
				self.update_album_art()
			else:
				self.album_art_label.hide()

			# Apply theme after loading all settings
			self.apply_theme()

			# Reload all style-affected icons with the restored button style
			self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color, use_style_path=True))
			self.rescan_btn.setIcon(self.load_icon('rescan.svg', icon_color, use_style_path=True))
			self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg' if self.remember_position else 'bookmark-off.svg', icon_color, use_style_path=True))
			self.show_album_art_btn.setIcon(self.load_icon('album-art.svg', icon_color, use_style_path=True))
			self.prev_btn.setIcon(self.load_icon('previous.svg', icon_color, use_style_path=True))
			self.next_btn.setIcon(self.load_icon('next.svg', icon_color, use_style_path=True))
			self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color, use_style_path=True))

			# Update play/pause based on state
			if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
				self.play_btn.setIcon(self.load_icon('pause.svg', icon_color, use_style_path=True))
			else:
				self.play_btn.setIcon(self.load_icon('play.svg', icon_color, use_style_path=True))

			# Update volume/mute button
			if self.is_muted or self.volume_slider.value() == 0:
				self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color, use_style_path=True))
			else:
				self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color, use_style_path=True))

			# Update button style toggle icon
			style_icon = 'rounded.svg' if self.rounded_buttons else 'straight.svg'
			self.button_style_btn.setIcon(self.load_icon(style_icon, icon_color, use_style_path=False))

			# Restore selected genre/artist/album/song
			selected_genre = settings.get('selected_genre')
			selected_artist = settings.get('selected_artist')
			selected_album = settings.get('selected_album')
			selected_song = settings.get('selected_song')

			if selected_genre:
				self.restore_selection(selected_genre, selected_artist, selected_album, selected_song)

		except Exception as e:
			print(f"Error loading settings: {e}")

	def rescan_library(self):
		if not self.watched_folders:
			print("No folders to rescan")
			return

		# Update UI to show we are rescanning
		self.rescan_btn.setEnabled(False)
		self.add_folder_btn.setEnabled(False)
		self.rescan_btn.setToolTip("Scanning library in background...")
		self.statusBar().showMessage("Scanning library...")

		# Create and start the background scanner
		self.scanner = LibraryScanner(self.watched_folders)
		self.scanner.finished.connect(self.on_scan_finished)
		self.scanner.start()

	def on_scan_finished(self, new_library):
		# Re-enable buttons
		self.rescan_btn.setEnabled(True)
		self.add_folder_btn.setEnabled(True)
		self.rescan_btn.setToolTip("Rescan library for new files")

		# Update library and refresh UI
		if new_library:
			# Capture current selection to restore it after refresh
			genre_item = self.genre_tree.currentItem()
			artist_item = self.artist_tree.currentItem()
			album_item = self.album_tree.currentItem()

			sel_genre = genre_item.text(0) if genre_item else None
			sel_artist = artist_item.text(0) if artist_item else None
			sel_album = album_item.text(0) if album_item else None

			# Capture currently selected song path
			sel_song = None
			curr_row = self.song_table.currentRow()
			if curr_row >= 0:
				sel_song = self.song_table.item(curr_row, 0).data(Qt.ItemDataRole.UserRole)

			self.library = new_library
			self.populate_genre_tree()
			self.save_library()

			# Restore selection if it still exists in the new library
			if sel_genre:
				self.restore_selection(sel_genre, sel_artist, sel_album, sel_song)

			self.statusBar().showMessage("Library scan complete", 5000)
			print("Background rescan complete")
		else:
			self.statusBar().showMessage("Library scan finished: No files found", 5000)
			print("Background rescan finished with no files found")

	def handle_player_error(self, error):
		if error != QMediaPlayer.Error.NoError:
			print(f"Playback error: {self.player.errorString()}")

	def update_progress(self, position):
		if not self.progress_slider_pressed:
			duration = self.player.duration()
			if duration > 0:
				self.progress_slider.setValue(int((position / duration) * 1000))

			# Update time label
			if duration >= 3600000:
				hours = int(position / 3600000)
				minutes = int((position % 3600000) / 60000)
				seconds = int((position % 60000) / 1000)
				self.progress_label.setText(f"{hours}:{minutes:02d}:{seconds:02d}")
			else:
				minutes = int(position / 60000)
				seconds = int((position % 60000) / 1000)
				self.progress_label.setText(f"{minutes}:{seconds:02d}")

	def update_duration(self, duration):
		if duration >= 3600000:
			hours = int(duration / 3600000)
			minutes = int((duration % 3600000) / 60000)
			seconds = int((duration % 60000) / 1000)
			self.duration_label.setText(f"{hours}:{minutes:02d}:{seconds:02d}")
		else:
			minutes = int(duration / 60000)
			seconds = int((duration % 60000) / 1000)
			self.duration_label.setText(f"{minutes}:{seconds:02d}")

	def change_volume(self, value):
		icon_color = 'white' if self.dark_mode else 'black'

		self.audio_output.setVolume(value / 100.0)

		# Update mute state and icon based on slider value
		if value == 0:
			self.is_muted = True
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color, use_style_path=True))
			self.mute_btn.setToolTip("Unmute")
		else:
			self.is_muted = False
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color, use_style_path=True))
			self.mute_btn.setToolTip("Mute")

		self.save_settings()

	def on_media_status_changed(self, status):
		from PyQt6.QtMultimedia import QMediaPlayer

		if status == QMediaPlayer.MediaStatus.EndOfMedia:
			if self.repeat_song:
				# Replay current song
				self.player.setPosition(0)
				self.player.play()
			elif self.repeat_album or self.current_track_index < len(self.current_playlist) - 1:
				# Play next track in playlist
				self.next_track()
			else:
				# Playlist finished, stop
				self.stop()

	def on_genre_double_clicked(self, item):
		import random
		genre = item.text(0)
		self.current_playlist = []

		# Collect all songs in this genre
		if genre in self.library:
			for artist in self.library[genre].values():
				for album in artist.values():
					self.current_playlist.extend(album)

		if self.current_playlist:
			# Sort by track number/title
			self.current_playlist = self.sort_playlist(self.current_playlist)

			self.unshuffled_playlist = self.current_playlist.copy()
			if self.shuffle_enabled:
				random.shuffle(self.current_playlist)
			self.populate_song_table_from_playlist()
			self.current_track_index = 0
			self.play_song(self.current_playlist[0])

	def on_artist_double_clicked(self, item):
		import random

		genre_item = self.genre_tree.currentItem()
		if not genre_item:
			return

		genre = genre_item.text(0)
		artist = item.text(0)
		self.current_playlist = []

		# Collect all songs by this artist
		if genre in self.library and artist in self.library[genre]:
			for album in self.library[genre][artist].values():
				self.current_playlist.extend(album)

		if self.current_playlist:
			# Sort by track number/title
			self.current_playlist = self.sort_playlist(self.current_playlist)

			# Save original order and shuffle if enabled
			self.unshuffled_playlist = self.current_playlist.copy()
			if self.shuffle_enabled:
				random.shuffle(self.current_playlist)

			self.populate_song_table_from_playlist()
			self.current_track_index = 0
			self.play_song(self.current_playlist[0])

	def on_album_double_clicked(self, item):
		import random

		genre_item = self.genre_tree.currentItem()
		artist_item = self.artist_tree.currentItem()

		if not genre_item or not artist_item:
			return

		genre = genre_item.text(0)
		artist = artist_item.text(0)
		album = item.text(0)

		if album in self.library[genre][artist]:
			self.current_playlist = self.library[genre][artist][album].copy()

			# Sort by track number/title
			self.current_playlist = self.sort_playlist(self.current_playlist)

			# Save original order and shuffle if enabled
			self.unshuffled_playlist = self.current_playlist.copy()
			if self.shuffle_enabled:
				random.shuffle(self.current_playlist)

			self.populate_song_table_from_playlist()
			self.current_track_index = 0
			self.play_song(self.current_playlist[0])

	def populate_song_table_from_playlist(self):
			from mutagen import File

			self.song_table.setRowCount(0)

			for i, song_path in enumerate(self.current_playlist):
				self.song_table.insertRow(i)

				# Read metadata for track info
				try:
					audio = File(song_path, easy=True)

					if audio:
						# Track number
						track_num = audio.get('tracknumber', [''])[0] if audio.get('tracknumber') else ''
						if '/' in str(track_num):
							track_num = track_num.split('/')[0]

						# Title
						title = audio.get('title', [Path(song_path).stem])[0] if audio.get('title') else Path(song_path).stem

						# Year
						year = audio.get('date', [''])[0] if audio.get('date') else ''
						if '-' in str(year):
							year = year.split('-')[0]

						# Duration
						duration = audio.info.length if hasattr(audio, 'info') else 0
						minutes = int(duration // 60)
						seconds = int(duration % 60)
						time_str = f"{minutes}:{seconds:02d}"

						# Artist
						artist_name = audio.get('artist', [''])[0] if audio.get('artist') else ''

						# Album
						album_name = audio.get('album', [''])[0] if audio.get('album') else ''

						# Genre
						genre_name = audio.get('genre', [''])[0] if audio.get('genre') else ''

					else:
						track_num = ''
						title = Path(song_path).stem
						year = ''
						time_str = ''
				except:
					track_num = ''
					title = Path(song_path).stem
					year = ''
					time_str = ''

				# Populate columns
				self.song_table.setItem(i, 0, QTableWidgetItem(str(track_num)))
				self.song_table.setItem(i, 1, QTableWidgetItem(title))
				self.song_table.setItem(i, 2, QTableWidgetItem(artist_name))
				self.song_table.setItem(i, 3, QTableWidgetItem(album_name))
				self.song_table.setItem(i, 4, QTableWidgetItem(str(year)))
				self.song_table.setItem(i, 5, QTableWidgetItem(time_str))
				self.song_table.setItem(i, 6, QTableWidgetItem(genre_name))

				# Store the file path invisibly for playback
				self.song_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, song_path)

	def restore_selection(self, genre, artist, album, song=None):
		from PyQt6.QtCore import QTimer

		# Store song for later restoration
		self._restore_song_path = song

		# Use a timer to delay restoration until after all initialization is complete
		QTimer.singleShot(100, lambda: self._do_restore(genre, artist, album))

	def _do_restore(self, genre, artist, album):
		# Find and select genre
		for i in range(self.genre_tree.topLevelItemCount()):
			item = self.genre_tree.topLevelItem(i)
			if item.text(0) == genre:
				self.genre_tree.setCurrentItem(item)
				self.on_genre_selected(item)

				# Delay artist selection slightly
				if artist:
					from PyQt6.QtCore import QTimer
					QTimer.singleShot(50, lambda: self._restore_artist(genre, artist, album))
				break

	def _restore_artist(self, genre, artist, album):
		for j in range(self.artist_tree.topLevelItemCount()):
			artist_item = self.artist_tree.topLevelItem(j)
			if artist_item.text(0) == artist:
				self.artist_tree.setCurrentItem(artist_item)
				self.on_artist_selected(artist_item)

				# Delay album selection slightly
				if album:
					from PyQt6.QtCore import QTimer
					QTimer.singleShot(50, lambda: self._restore_album(genre, artist, album))
				break

	def _restore_album(self, genre, artist, album):
		for k in range(self.album_tree.topLevelItemCount()):
			album_item = self.album_tree.topLevelItem(k)
			if album_item.text(0) == album:
				self.album_tree.setCurrentItem(album_item)
				self.on_album_selected(album_item)

				# Restore selected song if present
				if hasattr(self, '_restore_song_path') and self._restore_song_path:
					from PyQt6.QtCore import QTimer
					QTimer.singleShot(50, lambda: self._restore_song(self._restore_song_path))
				break

	def _restore_song(self, song_path):
		for row in range(self.song_table.rowCount()):
			current_song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
			if current_song_path == song_path:
				self.song_table.selectRow(row)
				break

	def closeEvent(self, event):
		self.save_settings()

		# Save playback position if feature is enabled
		if self.remember_position and self.current_playlist and self.current_track_index < len(self.current_playlist):
			position_data = {
				'song_path': self.current_playlist[self.current_track_index],
				'position': self.player.position(),
				'playlist': self.current_playlist,
				'track_index': self.current_track_index
			}
			try:
				with open(self.playback_position_file, 'w') as f:
					json.dump(position_data, f, indent=2)
			except Exception as e:
				print(f"Error saving playback position: {e}")

		event.accept()

	def load_icon(self, filename, color=None, use_style_path=True):
		# Determine the icon path based on whether it should use style-specific folder
		if use_style_path:
			style_folder = 'rounded' if self.rounded_buttons else 'straight'
			icon_path = self.app_dir / 'icons' / style_folder / filename
		else:
			# Use icons directory relative to script location (portable)
			icon_path = self.app_dir / 'icons' / filename

		if not icon_path.exists():
			print(f"Icon not found: {icon_path}")
			return QIcon()

		if color:
			# Load SVG and recolor it
			pixmap = QPixmap(str(icon_path))

			# Create a new pixmap with the desired color
			colored_pixmap = QPixmap(pixmap.size())
			colored_pixmap.fill(Qt.GlobalColor.transparent)

			painter = QPainter(colored_pixmap)
			painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
			painter.drawPixmap(0, 0, pixmap)
			painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
			painter.fillRect(colored_pixmap.rect(), QColor(color))
			painter.end()

			return QIcon(colored_pixmap)
		else:
			return QIcon(str(icon_path))

	def update_accent_icon(self):
		pixmap = QPixmap(self.icon_size)
		pixmap.fill(Qt.GlobalColor.transparent)
		painter = QPainter(pixmap)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		painter.setBrush(QColor(self.accent_color))
		painter.setPen(Qt.PenStyle.NoPen)
		painter.drawEllipse(2, 2, self.icon_size.width()-4, self.icon_size.height()-4)
		painter.end()
		self.accent_btn.setIcon(QIcon(pixmap))

	def choose_accent_color(self):
		dialog = ColorPickerDialog(self, self.accent_color)
		if dialog.exec():
			self.accent_color = dialog.get_color()
			self.update_accent_icon()
			self.apply_theme()
			self.save_settings()

	def toggle_theme(self):
		self.dark_mode = not self.dark_mode
		icon_color = 'white' if self.dark_mode else 'black'

		# Reload all button icons with new color
		self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color, use_style_path=True))
		self.rescan_btn.setIcon(self.load_icon('rescan.svg', icon_color, use_style_path=True))
		self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg' if self.remember_position else 'bookmark-off.svg', icon_color, use_style_path=True))
		self.show_album_art_btn.setIcon(self.load_icon('album-art.svg', icon_color, use_style_path=True))

		style_icon = 'rounded.svg' if self.rounded_buttons else 'straight.svg'
		self.button_style_btn.setIcon(self.load_icon(style_icon, icon_color, use_style_path=False))

		# Update theme toggle button icon
		theme_icon = 'mode-dark.svg' if self.dark_mode else 'mode-light.svg'
		self.darkmode_btn.setIcon(self.load_icon(theme_icon, icon_color, use_style_path=False))

		self.prev_btn.setIcon(self.load_icon('previous.svg', icon_color, use_style_path=True))
		self.next_btn.setIcon(self.load_icon('next.svg', icon_color, use_style_path=True))
		self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color, use_style_path=True))

		# Update play/pause button based on current state
		if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color, use_style_path=True))
		else:
			self.play_btn.setIcon(self.load_icon('play.svg', icon_color, use_style_path=True))

		# Update volume/mute button
		if self.is_muted or self.volume_slider.value() == 0:
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color, use_style_path=True))
		else:
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color, use_style_path=True))

		# Update repeat button based on mode
		if self.repeat_mode == 0:
			self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color, use_style_path=False))
		elif self.repeat_mode == 1:
			self.repeat_btn.setIcon(self.load_icon('repeat-song.svg', icon_color, use_style_path=False))
		elif self.repeat_mode == 2:
			self.repeat_btn.setIcon(self.load_icon('repeat-album.svg', icon_color, use_style_path=False))

		# Update shuffle button
		if self.shuffle_enabled:
			self.shuffle_btn.setIcon(self.load_icon('shuffle-on.svg', icon_color, use_style_path=False))
		else:
			self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color, use_style_path=False))

		# Apply color scheme
		self.apply_theme()

	def toggle_button_style(self):
		self.rounded_buttons = not self.rounded_buttons
		icon_color = 'white' if self.dark_mode else 'black'

		# Update the toggle button itself
		style_icon = 'rounded.svg' if self.rounded_buttons else 'straight.svg'
		self.button_style_btn.setIcon(self.load_icon(style_icon, icon_color, use_style_path=False))

		# Reload all style-affected icons
		self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color, use_style_path=True))
		self.rescan_btn.setIcon(self.load_icon('rescan.svg', icon_color, use_style_path=True))
		self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg' if self.remember_position else 'bookmark-off.svg', icon_color, use_style_path=True))
		self.show_album_art_btn.setIcon(self.load_icon('album-art.svg', icon_color, use_style_path=True))
		self.prev_btn.setIcon(self.load_icon('previous.svg', icon_color, use_style_path=True))
		self.next_btn.setIcon(self.load_icon('next.svg', icon_color, use_style_path=True))
		self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color, use_style_path=True))

		# Update play/pause button based on current state
		if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color, use_style_path=True))
		else:
			self.play_btn.setIcon(self.load_icon('play.svg', icon_color, use_style_path=True))

		# Update volume/mute button
		if self.is_muted or self.volume_slider.value() == 0:
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color, use_style_path=True))
		else:
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color, use_style_path=True))

		self.save_settings()

	def apply_theme(self):
		if self.dark_mode:
			# Dark mode colors
			bg_color = "#1e1e1e"
			secondary_bg = "#2d2d2d"
			text_color = "#ffffff"
			secondary_text = "#b0b0b0"
			border_color = "#3d3d3d"
		else:
			# Light mode colors
			bg_color = "#e8e8e8"
			secondary_bg = "#f5f5f5"
			text_color = "#1a1a1a"
			secondary_text = "#4a4a4a"
			border_color = "#c0c0c0"

		# Accent variants
		accent_base = QColor(self.accent_color)
		if self.dark_mode:
			selection_bg = accent_base.darker(150).name()
			slider_subpage = accent_base.name()
		else:
			selection_bg = accent_base.name()
			slider_subpage = accent_base.lighter(120).name()

		# Apply stylesheet
		self.setStyleSheet(f"""
			QMainWindow {{
				background-color: {bg_color};
				color: {text_color};
			}}
			QWidget {{
				background-color: {bg_color};
				color: {text_color};
			}}
			QPushButton[flat="true"] {{
				background-color: transparent;
				border: none;
				color: {text_color};
			}}
			QPushButton[flat="true"]:hover {{
				background-color: rgba(128, 128, 128, 0.2);
				border-radius: 4px;
			}}
			QPushButton[flat="true"]:pressed {{
				background-color: rgba(128, 128, 128, 0.3);
			}}
			QTreeWidget {{
				background-color: {secondary_bg};
				color: {text_color};
				border: 1px solid {border_color};
			}}
			QTreeWidget::item:selected {{
				background-color: {selection_bg};
			}}
			QTableWidget {{
				background-color: {secondary_bg};
				color: {text_color};
				border: 1px solid {border_color};
				gridline-color: {border_color};
			}}
			QTableWidget::item:selected {{
				background-color: {selection_bg};
			}}
			QHeaderView::section {{
				background-color: {bg_color};
				color: {text_color};
				border: 1px solid {border_color};
				padding: 4px;
			}}
			QLabel {{
				color: {text_color};
			}}
			QSlider::groove:horizontal {{
				background: {border_color};
				height: 4px;
				border-radius: 2px;
			}}
			QSlider::handle:horizontal {{
				background: {text_color};
				width: 12px;
				margin: -4px 0;
				border-radius: 6px;
			}}
			QSlider::sub-page:horizontal {{
				background: {slider_subpage};
				border-radius: 2px;
			}}
			QSplitter::handle {{
				background-color: {border_color};
			}}
		""")

	def toggle_mute(self):
		icon_color = 'white' if self.dark_mode else 'black'

		if self.is_muted:
			# Unmute - restore previous volume
			self.is_muted = False
			self.volume_slider.setValue(self.volume_before_mute)
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color, use_style_path=True))
			self.mute_btn.setToolTip("Mute")
		else:
			# Mute - save current volume and set to 0
			self.is_muted = True
			self.volume_before_mute = self.volume_slider.value()
			self.volume_slider.setValue(0)
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color, use_style_path=True))
			self.mute_btn.setToolTip("Unmute")

	def cycle_repeat_mode(self):
		icon_color = 'white' if self.dark_mode else 'black'

		self.repeat_mode = (self.repeat_mode + 1) % 3

		if self.repeat_mode == 0:
			# Repeat off
			self.repeat_song = False
			self.repeat_album = False
			self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color, use_style_path=False))
			self.repeat_btn.setToolTip("Repeat Off")
		elif self.repeat_mode == 1:
			# Repeat song
			self.repeat_song = True
			self.repeat_album = False
			self.repeat_btn.setIcon(self.load_icon('repeat-song.svg', icon_color, use_style_path=False))
			self.repeat_btn.setToolTip("Repeat Song")
		elif self.repeat_mode == 2:
			# Repeat album
			self.repeat_song = False
			self.repeat_album = True
			self.repeat_btn.setIcon(self.load_icon('repeat-album.svg', icon_color, use_style_path=False))
			self.repeat_btn.setToolTip("Repeat Album")

		self.save_settings()

	def on_progress_slider_moved(self, position):
		duration = self.player.duration()
		if duration > 0:
			new_position = int((position / 1000) * duration)
			self.player.setPosition(new_position)

	def on_progress_slider_pressed(self):
		self.progress_slider_pressed = True
		# Seek immediately when clicking anywhere on the bar
		duration = self.player.duration()
		if duration > 0:
			position = int((self.progress_slider.value() / 1000) * duration)
			self.player.setPosition(position)

	def on_progress_slider_released(self):
		self.progress_slider_pressed = False

	def toggle_shuffle(self):
		import random
		icon_color = 'white' if self.dark_mode else 'black'

		self.shuffle_enabled = not self.shuffle_enabled

		if self.shuffle_enabled:
			# Shuffle on
			self.shuffle_btn.setIcon(self.load_icon('shuffle-on.svg', icon_color, use_style_path=False))
			self.shuffle_btn.setToolTip("Shuffle On")

			# Save original playlist order
			self.unshuffled_playlist = self.current_playlist.copy()

			# Shuffle the playlist
			if self.current_playlist:
				random.shuffle(self.current_playlist)
				self.current_track_index = 0
		else:
			# Shuffle off
			self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color, use_style_path=False))
			self.shuffle_btn.setToolTip("Shuffle Off")

			# Restore original order
			if self.unshuffled_playlist:
				self.current_playlist = self.unshuffled_playlist.copy()
				self.current_track_index = 0

		self.save_settings()

	def sort_playlist(self, playlist):
		from mutagen import File

		def get_sort_key(song_path):
			try:
				audio = File(song_path, easy=True)
				if audio:
					# Get track number
					track_num = audio.get('tracknumber', ['9999'])[0]
					# Handle "1/12" format
					if '/' in str(track_num):
						track_num = track_num.split('/')[0]
					try:
						track_num = int(track_num)
					except:
						track_num = 9999  # Put tracks without numbers at the end

					# Get title for secondary sort
					title = audio.get('title', [Path(song_path).stem])[0]
					if not title:
						title = Path(song_path).stem

					return (track_num, title.lower())
				else:
					# No metadata, sort by filename
					return (9999, Path(song_path).stem.lower())
			except:
				return (9999, Path(song_path).stem.lower())

		return sorted(playlist, key=get_sort_key)

	def changeEvent(self, event):
		if event.type() == event.Type.WindowStateChange:
			# Check if we just un-maximized
			if not self.isMaximized() and event.oldState() == Qt.WindowState.WindowMaximized:
				# Restore to default size instead of previous size
				self.setGeometry(100, 100, 1200, 720)

		super().changeEvent(event)

	def toggle_remember_position(self):
			self.remember_position = not self.remember_position
			icon_color = 'white' if self.dark_mode else 'black'

			if self.remember_position:
				self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg', icon_color, use_style_path=True))
				self.remember_position_btn.setToolTip("Remember playback position (On)")
			else:
				self.remember_position_btn.setIcon(self.load_icon('bookmark-off.svg', icon_color, use_style_path=True))
				self.remember_position_btn.setToolTip("Remember playback position (Off)")
				# Clear saved position when disabled
				if self.playback_position_file.exists():
					self.playback_position_file.unlink()

			self.save_settings()

	def toggle_album_art(self):
		self.show_album_art = not self.show_album_art

		if self.show_album_art:
			self.album_art_label.show()
			self.update_album_art()
			# Equalize 4 columns
			total_width = self.horizontal_splitter.width()
			equal_width = total_width // 4
			self.horizontal_splitter.setSizes([equal_width] * 4)
		else:
			self.album_art_label.hide()
			# Equalize 3 columns
			total_width = self.horizontal_splitter.width()
			equal_width = total_width // 3
			self.horizontal_splitter.setSizes([equal_width, equal_width, equal_width, 0])

		self.save_settings()

	def update_album_art(self):
		if not self.show_album_art:
			return

		source = self.player.source().toLocalFile()
		if not source or not Path(source).exists():
			self.album_art_label.clear()
			self.album_art_label.setText("No track playing")
			return

		from mutagen import File
		try:
			audio = File(source)
			artwork = None

			if audio:
				# Handle different tag formats
				if 'APIC:' in audio: # ID3 (MP3)
					artwork = audio['APIC:'].data
				elif audio.pictures: # FLAC
					artwork = audio.pictures[0].data
				elif 'covr' in audio: # MP4/M4A
					artwork = audio['covr'][0]

			if artwork:
				pixmap = QPixmap()
				pixmap.loadFromData(artwork)
				self.album_art_label.setPixmap(pixmap)
			else:
				self.album_art_label.clear()
				self.album_art_label.setText("No artwork found")
		except Exception as e:
			print(f"Error loading album art: {e}")
			self.album_art_label.clear()
			self.album_art_label.setText("Error loading art")

	def restore_playback_position(self):
		#print(f"DEBUG - Remember position enabled: {self.remember_position}")
		#print(f"DEBUG - Position file exists: {self.playback_position_file.exists()}")

		if not self.remember_position or not self.playback_position_file.exists():
			return

		try:
			with open(self.playback_position_file, 'r') as f:
				position_data = json.load(f)

			print(f"DEBUG - Loaded position data: {position_data.get('song_path')}, position: {position_data.get('position')}")

			song_path = position_data.get('song_path')
			position = position_data.get('position', 0)
			playlist = position_data.get('playlist', [])
			track_index = position_data.get('track_index', 0)

			# Verify the song still exists
			if song_path and Path(song_path).exists():
				print(f"DEBUG - Song exists, restoring...")
				self.current_playlist = playlist
				self.current_track_index = track_index

				# Populate the song table with the playlist
				self.populate_song_table_from_playlist()

				# Store the position to restore after media loads
				self._pending_seek_position = position

				# Connect to mediaStatusChanged to seek after loading
				def on_media_loaded(status):
					from PyQt6.QtMultimedia import QMediaPlayer
					if status == QMediaPlayer.MediaStatus.LoadedMedia and hasattr(self, '_pending_seek_position'):
						print(f"DEBUG - Media loaded, seeking to {self._pending_seek_position}ms")
						self.player.setPosition(self._pending_seek_position)
						delattr(self, '_pending_seek_position')
						# Disconnect this handler
						self.player.mediaStatusChanged.disconnect(on_media_loaded)

				self.player.mediaStatusChanged.connect(on_media_loaded)

				# Load the song
				self.player.setSource(QUrl.fromLocalFile(song_path))

				# Update UI
				from mutagen import File
				try:
					audio = File(song_path, easy=True)
					if audio:
						artist = audio.get('artist', ['Unknown Artist'])[0]
						title = audio.get('title', [Path(song_path).stem])[0]
						self.now_playing_text.setText(f"{artist} - {title}")
					else:
						self.now_playing_text.setText(f"{Path(song_path).stem}")
				except:
					self.now_playing_text.setText(f"{Path(song_path).stem}")

				print(f"Restored playback position: {position/1000:.1f}s")
			else:
				print(f"DEBUG - Song path doesn't exist: {song_path}")

		except Exception as e:
			print(f"Error restoring playback position: {e}")
			import traceback
			traceback.print_exc()

if __name__ == '__main__':
	# Windows-specific: Set App User Model ID for custom taskbar icon
	# This prevents Windows from grouping the app with python.exe
	if sys.platform == 'win32':
		try:
			import ctypes
			# Set a unique App User Model ID
			app_id = 'Buzzkill.Music.Player.1.0'
			ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
		except Exception as e:
			print(f"Could not set App User Model ID: {e}")

	app = QApplication(sys.argv)

	# Set application-wide font size
	font = app.font()
	font.setPointSize(11)
	app.setFont(font)

	player = MusicPlayer()

	# Set window icon using relative path (portable)
	icon_dir = Path(__file__).parent.resolve() / 'icons'

	# On Windows, prefer .ico format if available (better quality)
	if sys.platform == 'win32' and (icon_dir / 'logo.ico').exists():
		icon_path = icon_dir / 'logo.ico'
	else:
		icon_path = icon_dir / 'logo.svg'

	player.setWindowIcon(QIcon(str(icon_path)))

	player.show()

	sys.exit(app.exec())