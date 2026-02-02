import sys
import os
import json
from pathlib import Path

# Suppress Qt multimedia debug output
os.environ['QT_LOGGING_RULES'] = 'qt.multimedia*=false'

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
							 QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
							 QTableWidget, QTableWidgetItem, QFileDialog, QSlider,
							 QLabel, QSplitter, QGridLayout)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QUrl, QSize
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

class ClickableSlider(QSlider):
	"""Slider that jumps to position when clicked"""
	def mousePressEvent(self, event):
		"""Jump to click position"""
		if event.button() == Qt.MouseButton.LeftButton:
			value = QSlider.minimum(self) + ((QSlider.maximum(self) - QSlider.minimum(self)) * event.position().x()) / self.width()
			self.setValue(int(value))
			self.sliderPressed.emit()
		super().mousePressEvent(event)

class MusicPlayer(QMainWindow):
	def __init__(self):
		super().__init__()
	
		self.setWindowTitle("Languorian's Simple Music Player")

		# Default size (will be overridden by load_settings if saved geometry exists)
		self.setGeometry(100, 100, 1200, 720)

		# Music library structure: {genre: {artist: {album: [songs]}}}
		self.library = {}
		self.current_songs = []
		self.watched_folders = []

		# Config file location
		self.config_dir = Path.home() / '.config' / 'simple-music-player'
		self.config_dir.mkdir(parents=True, exist_ok=True)
		self.library_file = self.config_dir / 'library.json'
		self.settings_file = self.config_dir / 'settings.json'

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

		self.init_ui()
		self.load_library()
		self.load_settings()

	def init_ui(self):
		# Main widget and layout
		main_widget = QWidget()
		self.setCentralWidget(main_widget)
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
		self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color))
		self.add_folder_btn.setIconSize(self.icon_size)
		self.add_folder_btn.setToolTip("Add folder to library")
		self.add_folder_btn.setFlat(True)
		self.add_folder_btn.clicked.connect(self.add_folder)
		left_controls.addWidget(self.add_folder_btn)

		# Rescan library button
		self.rescan_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.rescan_btn.setIcon(self.load_icon('rescan.svg', icon_color))
		self.rescan_btn.setIconSize(self.icon_size)
		self.rescan_btn.setToolTip("Rescan library for new files")
		self.rescan_btn.setFlat(True)
		self.rescan_btn.clicked.connect(self.rescan_library)
		left_controls.addWidget(self.rescan_btn)

		# Dark/Light Mode button
		self.darkmode_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.darkmode_btn.setIcon(self.load_icon('mode-dark.svg', icon_color))
		self.darkmode_btn.setIconSize(self.icon_size)
		self.darkmode_btn.setToolTip("Toggle dark/light mode")
		self.darkmode_btn.setFlat(True)
		self.darkmode_btn.clicked.connect(self.toggle_theme)
		left_controls.addWidget(self.darkmode_btn)

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
		self.prev_btn.setIcon(self.load_icon('previous.svg', icon_color))
		self.prev_btn.setIconSize(self.icon_size)
		self.prev_btn.setToolTip("Go to previous track")
		self.prev_btn.setFlat(True)
		self.prev_btn.clicked.connect(self.previous_track)
		center_controls.addWidget(self.prev_btn)

		# Play/Pause button
		self.play_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.play_btn.setIcon(self.load_icon('play.svg', icon_color))
		self.play_btn.setIconSize(self.icon_size)
		self.play_btn.setToolTip("Play/Pause")
		self.play_btn.setFlat(True)
		self.play_btn.clicked.connect(self.play_pause)
		center_controls.addWidget(self.play_btn)

		# Stop button
		self.stop_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color))
		self.stop_btn.setIconSize(self.icon_size)
		self.stop_btn.setToolTip("Stop the current playing track")
		self.stop_btn.setFlat(True)
		self.stop_btn.clicked.connect(self.stop)
		center_controls.addWidget(self.stop_btn)

		# Next track button
		self.next_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.next_btn.setIcon(self.load_icon('next.svg', icon_color))
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
		self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color))
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
		self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color))
		self.repeat_btn.setIconSize(self.icon_size)
		self.repeat_btn.setToolTip("Repeat/Loop (Off, Song, Album)")
		self.repeat_btn.setFlat(True)
		self.repeat_btn.clicked.connect(self.cycle_repeat_mode)
		right_controls.addWidget(self.repeat_btn)

		# Shuffle button
		self.shuffle_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color))
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

		# Row 1: Genre/Artist/Album columns
		top_widget = QWidget()
		top_layout = QHBoxLayout(top_widget)

		# Genre column
		self.genre_tree = QTreeWidget()
		self.genre_tree.setHeaderLabel("Genre")
		self.genre_tree.itemClicked.connect(self.on_genre_selected)
		self.genre_tree.itemDoubleClicked.connect(self.on_genre_double_clicked)
		top_layout.addWidget(self.genre_tree)

		# Artist column
		self.artist_tree = QTreeWidget()
		self.artist_tree.setHeaderLabel("Artist")
		self.artist_tree.itemClicked.connect(self.on_artist_selected)
		self.artist_tree.itemDoubleClicked.connect(self.on_artist_double_clicked)
		top_layout.addWidget(self.artist_tree)

		# Album column
		self.album_tree = QTreeWidget()
		self.album_tree.setHeaderLabel("Album")
		self.album_tree.itemClicked.connect(self.on_album_selected)
		self.album_tree.itemDoubleClicked.connect(self.on_album_double_clicked)
		top_layout.addWidget(self.album_tree)

		self.splitter.addWidget(top_widget)

		#==============================================
		#==============     ROW 3    ================== 
		#==============================================
		# Song list
		self.song_table = QTableWidget()
		self.song_table.setColumnCount(4)
		self.song_table.setHorizontalHeaderLabels(["Track #", "Title", "Year", "Time"])
		self.song_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
		self.song_table.verticalHeader().setVisible(False)  # Remove row numbers
		self.song_table.itemDoubleClicked.connect(self.on_song_double_clicked)
		self.song_table.horizontalHeader().sectionResized.connect(self.save_settings)
		self.splitter.addWidget(self.song_table)

		# Set stretch factors: 0 for row 2 (don't stretch), 1 for row 3 (take all extra space)
		self.splitter.setStretchFactor(0, 0)  # top_widget (genre/artist/album) - no stretch
		self.splitter.setStretchFactor(1, 1)  # song_table - gets all the stretch

		layout.addWidget(self.splitter)

	def add_folder(self):
		folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
		if folder:
			if folder not in self.watched_folders:
				self.watched_folders.append(folder)

			self.scan_folder(folder)
			self.populate_genre_tree()
			self.save_library()  # Save after adding

	def load_library(self):
		"""Load library from JSON on startup"""
		if not self.library_file.exists():
			print("No saved library found")
			return

		try:
			with open(self.library_file, 'r') as f:
				data = json.load(f)

			self.library = data.get('library', {})
			self.watched_folders = data.get('watched_folders', [])

			self.populate_genre_tree()
			print(f"Library loaded: {len(self.watched_folders)} folders")
		except Exception as e:
			print(f"Error loading library: {e}")

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
		"""Populate the genre column"""
		self.genre_tree.clear()
		for genre in sorted(self.library.keys()):
			QTreeWidgetItem(self.genre_tree, [genre])

	def on_genre_selected(self, item):
		"""When genre is selected, show artists"""
		genre = item.text(0)
		self.artist_tree.clear()
		self.album_tree.clear()
		self.song_table.setRowCount(0)

		if genre in self.library:
			for artist in sorted(self.library[genre].keys()):
				QTreeWidgetItem(self.artist_tree, [artist])

		#self.save_settings()

	def on_artist_selected(self, item):
		"""When artist is selected, show albums"""
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
		"""When album is selected, show songs"""
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
				self.song_table.setItem(i, 2, QTableWidgetItem(str(year)))
				self.song_table.setItem(i, 3, QTableWidgetItem(time_str))

				# Store the file path invisibly for playback
				self.song_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, song_path)

	def on_song_double_clicked(self, item):
		"""Play song when double-clicked"""
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
			"""Play the specified audio file"""
			from mutagen import File
			
			icon_color = 'white' if self.dark_mode else 'black'
	
			self.player.setSource(QUrl.fromLocalFile(file_path))
			self.player.play()
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color))
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
		"""Toggle play/pause"""
		icon_color = 'white' if self.dark_mode else 'black'
		
		# Check if there's a song loaded
		if self.player.source().isEmpty():
			# No song loaded, do nothing
			return

		if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.player.pause()
			self.play_btn.setIcon(self.load_icon('play.svg', icon_color))
			self.play_btn.setToolTip("Play")
		else:
			self.player.play()
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color))
			self.play_btn.setToolTip("Pause")

	def stop(self):
		"""Stop playback"""
		icon_color = 'white' if self.dark_mode else 'black'
		
		self.player.stop()
		self.play_btn.setIcon(self.load_icon('play.svg', icon_color))
		self.play_btn.setToolTip("Play")
		self.now_playing_text.setText("---")

	def next_track(self):
		"""Play next track in current playlist"""
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
		"""Play previous track in current playlist"""
		if not self.current_playlist:
			return
		
		self.current_track_index -= 1
		
		if self.current_track_index < 0:
			self.current_track_index = 0
		
		song_path = self.current_playlist[self.current_track_index]
		self.play_song(song_path)
		self.highlight_current_song()

	def highlight_current_song(self):
		"""Highlight the currently playing song in the table"""
		if not self.current_playlist:
			return
		
		# Find and select the current song in the table
		for row in range(self.song_table.rowCount()):
			song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
			if song_path == self.current_playlist[self.current_track_index]:
				self.song_table.selectRow(row)
				break

	def save_settings(self):
		"""Save UI settings like column widths"""

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
				self.song_table.columnWidth(3)
			],
			'splitter_sizes': self.splitter.sizes(),
			'window_geometry': [self.x(), self.y(), self.width(), self.height()],
			'window_maximized': self.isMaximized(),
			'selected_genre': genre_item.text(0) if genre_item else None,
			'selected_artist': artist_item.text(0) if artist_item else None,
			'selected_album': album_item.text(0) if album_item else None,
			'selected_song': selected_song_path,
			'repeat_mode': self.repeat_mode,
			'repeat_mode': self.repeat_mode,
			'shuffle_enabled': self.shuffle_enabled,
			'volume': self.volume_slider.value()
		}

		try:
			with open(self.settings_file, 'w') as f:
				json.dump(settings, f, indent=2)
		except Exception as e:
			print(f"Error saving settings: {e}")

	def load_settings(self):
		"""Load UI settings"""
		if not self.settings_file.exists():
			# Set default column widths
			self.song_table.setColumnWidth(0, 80)   # Track #
			self.song_table.setColumnWidth(1, 300)  # Title
			self.song_table.setColumnWidth(2, 80)   # Year
			self.song_table.setColumnWidth(3, 80)   # Time
			return

		try:
			with open(self.settings_file, 'r') as f:
				settings = json.load(f)

			#print(f"DEBUG - Loaded settings: {settings}")  # ADD THIS

			# Restore column widths
			widths = settings.get('column_widths', [80, 300, 80, 80])
			for i, width in enumerate(widths):
				self.song_table.setColumnWidth(i, width)

			# Restore splitter sizes
			splitter_sizes = settings.get('splitter_sizes')
			if splitter_sizes:
				self.splitter.setSizes(splitter_sizes)
			
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
			
			# Restore repeat mode
			self.repeat_mode = settings.get('repeat_mode', 0)
			icon_color = 'white' if self.dark_mode else 'black'
			
			if self.repeat_mode == 0:
				self.repeat_song = False
				self.repeat_album = False
				self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color))
				self.repeat_btn.setToolTip("Repeat Off")
			elif self.repeat_mode == 1:
				self.repeat_song = True
				self.repeat_album = False
				self.repeat_btn.setIcon(self.load_icon('repeat-song.svg', icon_color))
				self.repeat_btn.setToolTip("Repeat Song")
			elif self.repeat_mode == 2:
				self.repeat_song = False
				self.repeat_album = True
				self.repeat_btn.setIcon(self.load_icon('repeat-album.svg', icon_color))
				self.repeat_btn.setToolTip("Repeat Album")

			# Restore shuffle state
			self.shuffle_enabled = settings.get('shuffle_enabled', False)
			if self.shuffle_enabled:
				self.shuffle_btn.setIcon(self.load_icon('shuffle-on.svg', icon_color))
				self.shuffle_btn.setToolTip("Shuffle On")
			else:
				self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color))
				self.shuffle_btn.setToolTip("Shuffle Off")
			
			# Restore selected genre/artist/album/song
			selected_genre = settings.get('selected_genre')
			selected_artist = settings.get('selected_artist')
			selected_album = settings.get('selected_album')
			selected_song = settings.get('selected_song')

			# print(f"DEBUG - About to restore: genre={selected_genre}, artist={selected_artist}, album={selected_album}")  # ADD THIS
			
			if selected_genre:
				self.restore_selection(selected_genre, selected_artist, selected_album, selected_song)
					
		except Exception as e:
			print(f"Error loading settings: {e}")

	def rescan_library(self):
		"""Rescan all watched folders for changes"""
		if not self.watched_folders:
			print("No folders to rescan")
			return

		# Clear library and rescan from scratch
		self.library = {}

		for folder in self.watched_folders:
			if os.path.exists(folder):
				print(f"Rescanning {folder}...")
				self.scan_folder(folder)
			else:
				print(f"Folder no longer exists: {folder}")

		self.populate_genre_tree()
		self.save_library()
		print("Rescan complete")

	def handle_player_error(self, error):
		"""Handle playback errors"""
		if error != QMediaPlayer.Error.NoError:
			print(f"Playback error: {self.player.errorString()}")

	def update_progress(self, position):
		"""Update progress bar as song plays"""
		if not self.progress_slider_pressed:
			duration = self.player.duration()
			if duration > 0:
				self.progress_slider.setValue(int((position / duration) * 1000))

			# Update time label
			minutes = int(position / 60000)
			seconds = int((position % 60000) / 1000)
			self.progress_label.setText(f"{minutes}:{seconds:02d}")

	def update_duration(self, duration):
		"""Update duration label when song loads"""
		minutes = int(duration / 60000)
		seconds = int((duration % 60000) / 1000)
		self.duration_label.setText(f"{minutes}:{seconds:02d}")

	def change_volume(self, value):
		"""Change playback volume"""
		icon_color = 'white' if self.dark_mode else 'black'
		
		self.audio_output.setVolume(value / 100.0)
		
		# Update mute state and icon based on slider value
		if value == 0:
			self.is_muted = True
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color))
			self.mute_btn.setToolTip("Unmute")
		else:
			self.is_muted = False
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color))
			self.mute_btn.setToolTip("Mute")
		
		self.save_settings()

	def on_media_status_changed(self, status):
		"""Handle when a song ends"""
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
		"""Play all songs in genre"""
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
		"""Play all songs by artist"""
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
		"""Play all songs in album"""
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
			"""Populate the song table with songs from current playlist"""
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
				self.song_table.setItem(i, 2, QTableWidgetItem(str(year)))
				self.song_table.setItem(i, 3, QTableWidgetItem(time_str))
				
				# Store the file path invisibly for playback
				self.song_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, song_path)

	def restore_selection(self, genre, artist, album, song=None):
		"""Restore previously selected genre/artist/album/song"""
		from PyQt6.QtCore import QTimer
		
		# print(f"DEBUG - Scheduling restore: Genre={genre}, Artist={artist}, Album={album}, Song={song}")
		
		# Store song for later restoration
		self._restore_song_path = song
		
		# Use a timer to delay restoration until after all initialization is complete
		QTimer.singleShot(100, lambda: self._do_restore(genre, artist, album))

	def _do_restore(self, genre, artist, album):
		"""Actually perform the restoration"""
		# print(f"DEBUG - Executing restore: Genre={genre}, Artist={artist}, Album={album}")
		
		# Find and select genre
		for i in range(self.genre_tree.topLevelItemCount()):
			item = self.genre_tree.topLevelItem(i)
			if item.text(0) == genre:
				# print(f"DEBUG - Found genre: {genre}")
				self.genre_tree.setCurrentItem(item)
				self.on_genre_selected(item)
				
				# Delay artist selection slightly
				if artist:
					from PyQt6.QtCore import QTimer
					QTimer.singleShot(50, lambda: self._restore_artist(genre, artist, album))
				break

	def _restore_artist(self, genre, artist, album):
		"""Restore artist selection"""
		# print(f"DEBUG - Restoring artist: {artist}")
		for j in range(self.artist_tree.topLevelItemCount()):
			artist_item = self.artist_tree.topLevelItem(j)
			if artist_item.text(0) == artist:
				# print(f"DEBUG - Found artist: {artist}")
				self.artist_tree.setCurrentItem(artist_item)
				self.on_artist_selected(artist_item)
				
				# Delay album selection slightly
				if album:
					from PyQt6.QtCore import QTimer
					QTimer.singleShot(50, lambda: self._restore_album(genre, artist, album))
				break

	def _restore_album(self, genre, artist, album):
		"""Restore album selection"""
		# print(f"DEBUG - Restoring album: {album}")
		for k in range(self.album_tree.topLevelItemCount()):
			album_item = self.album_tree.topLevelItem(k)
			if album_item.text(0) == album:
				# print(f"DEBUG - Found album: {album}")
				self.album_tree.setCurrentItem(album_item)
				self.on_album_selected(album_item)
				# print(f"DEBUG - Album restored successfully")
				
				# Restore selected song if present
				if hasattr(self, '_restore_song_path') and self._restore_song_path:
					from PyQt6.QtCore import QTimer
					QTimer.singleShot(50, lambda: self._restore_song(self._restore_song_path))
				break

	def _restore_song(self, song_path):
		"""Restore song selection"""
		# print(f"DEBUG - Restoring song: {song_path}")
		for row in range(self.song_table.rowCount()):
			current_song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
			if current_song_path == song_path:
				# print(f"DEBUG - Found song at row {row}")
				self.song_table.selectRow(row)
				break

	def closeEvent(self, event):
		"""Save settings when app closes"""
		# print("DEBUG - closeEvent called! About to save settings...")
		self.save_settings()
		event.accept()

	def load_icon(self, filename, color=None):
		"""Load an SVG icon and optionally recolor it"""

		icon_path = Path.home() / 'Documents' / 'simple-music-player' / 'icons' / filename
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
		
	def toggle_theme(self):
		"""Switch between dark and light mode"""
		self.dark_mode = not self.dark_mode
		icon_color = 'white' if self.dark_mode else 'black'
		
		# Reload all icons with new color
		self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color))
		#self.play_btn.setIcon(self.load_icon('play.svg', icon_color))
		# ... etc for all buttons

	def toggle_mute(self):
		"""Toggle mute on/off"""
		icon_color = 'white' if self.dark_mode else 'black'
		
		if self.is_muted:
			# Unmute - restore previous volume
			self.is_muted = False
			self.volume_slider.setValue(self.volume_before_mute)
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color))
			self.mute_btn.setToolTip("Mute")
		else:
			# Mute - save current volume and set to 0
			self.is_muted = True
			self.volume_before_mute = self.volume_slider.value()
			self.volume_slider.setValue(0)
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color))
			self.mute_btn.setToolTip("Unmute")

	def cycle_repeat_mode(self):
		"""Cycle through repeat modes: off -> song -> album -> off"""
		icon_color = 'white' if self.dark_mode else 'black'
		
		self.repeat_mode = (self.repeat_mode + 1) % 3
		
		if self.repeat_mode == 0:
			# Repeat off
			self.repeat_song = False
			self.repeat_album = False
			self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color))
			self.repeat_btn.setToolTip("Repeat Off")
		elif self.repeat_mode == 1:
			# Repeat song
			self.repeat_song = True
			self.repeat_album = False
			self.repeat_btn.setIcon(self.load_icon('repeat-song.svg', icon_color))
			self.repeat_btn.setToolTip("Repeat Song")
		elif self.repeat_mode == 2:
			# Repeat album
			self.repeat_song = False
			self.repeat_album = True
			self.repeat_btn.setIcon(self.load_icon('repeat-album.svg', icon_color))
			self.repeat_btn.setToolTip("Repeat Album")
		
		self.save_settings()

	def on_progress_slider_moved(self, position):
		"""Seek when user clicks or drags on the progress bar"""
		duration = self.player.duration()
		if duration > 0:
			new_position = int((position / 1000) * duration)
			self.player.setPosition(new_position)

	def on_progress_slider_pressed(self):
		"""User started interacting with the slider"""
		self.progress_slider_pressed = True
		# Seek immediately when clicking anywhere on the bar
		duration = self.player.duration()
		if duration > 0:
			position = int((self.progress_slider.value() / 1000) * duration)
			self.player.setPosition(position)

	def on_progress_slider_released(self):
		"""User released the slider"""
		self.progress_slider_pressed = False

	def toggle_shuffle(self):
		"""Toggle shuffle on/off"""
		import random
		icon_color = 'white' if self.dark_mode else 'black'
		
		self.shuffle_enabled = not self.shuffle_enabled
		
		if self.shuffle_enabled:
			# Shuffle on
			self.shuffle_btn.setIcon(self.load_icon('shuffle-on.svg', icon_color))
			self.shuffle_btn.setToolTip("Shuffle On")
			
			# Save original playlist order
			self.unshuffled_playlist = self.current_playlist.copy()
			
			# Shuffle the playlist
			if self.current_playlist:
				random.shuffle(self.current_playlist)
				self.current_track_index = 0
		else:
			# Shuffle off
			self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color))
			self.shuffle_btn.setToolTip("Shuffle Off")
			
			# Restore original order
			if self.unshuffled_playlist:
				self.current_playlist = self.unshuffled_playlist.copy()
				self.current_track_index = 0
		
		self.save_settings()

	def sort_playlist(self, playlist):
		"""Sort playlist by track number, then by title"""
		from mutagen import File
		
		def get_sort_key(song_path):
			"""Get sorting key for a song (track_number, title)"""
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
		"""Handle window state changes"""
		if event.type() == event.Type.WindowStateChange:
			# Check if we just un-maximized
			if not self.isMaximized() and event.oldState() == Qt.WindowState.WindowMaximized:
				# Restore to default size instead of previous size
				self.setGeometry(100, 100, 1200, 720)
		
		super().changeEvent(event)

if __name__ == '__main__':
	app = QApplication(sys.argv)

	player = MusicPlayer()

	# Set window icon using the same path as other icons
	icon_path = Path.home() / 'Documents' / 'simple-music-player' / 'icons' / 'logo.svg'
	player.setWindowIcon(QIcon(str(icon_path)))

	player.show()

	sys.exit(app.exec())
