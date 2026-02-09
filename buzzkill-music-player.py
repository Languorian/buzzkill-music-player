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
							 QStatusBar, QListWidget, QListWidgetItem, QMenu,
							 QStackedWidget, QTextEdit, QGraphicsOpacityEffect, QCheckBox)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QFontDatabase
from PyQt6.QtCore import (Qt, QUrl, QSize, QRect, QThread, pyqtSignal, 
						  QPropertyAnimation, QEasingCurve, QVariantAnimation)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

class ClickableSlider(QSlider):
	scrolled = pyqtSignal(int)

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			value = QSlider.minimum(self) + ((QSlider.maximum(self) - QSlider.minimum(self)) * event.position().x()) / self.width()
			self.setValue(int(value))
			self.sliderPressed.emit()
		super().mousePressEvent(event)

	def wheelEvent(self, event):
		# Emit scrolled signal with the wheel delta
		self.scrolled.emit(event.angleDelta().y())
		event.accept()

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
							title = audio.get('title', [Path(file).stem])[0] if audio.get('title') else Path(file).stem
							track_num = audio.get('tracknumber', [''])[0] if audio.get('tracknumber') else ''
							if track_num == '0' or track_num == '00':
								track_num = ''
							year = audio.get('date', [''])[0] if audio.get('date') else ''
							duration = audio.info.length if hasattr(audio, 'info') else 0

							song_data = {
								'path': full_path,
								'title': title,
								'artist': artist,
								'album': album,
								'genre': genre,
								'tracknumber': track_num,
								'year': year,
								'duration': duration
							}

							# Build library structure
							if genre not in new_library:
								new_library[genre] = {}
							if artist not in new_library[genre]:
								new_library[genre][artist] = {}
							if album not in new_library[genre][artist]:
								new_library[genre][artist][album] = []

							new_library[genre][artist][album].append(song_data)

						except:
							continue

		self.finished.emit(new_library)

class ColorPickerDialog(QDialog):
	def __init__(self, parent=None, initial_color="#0E47A1", dynamic_enabled=False, dynamic_color="#0E47A1", dark_mode=True):
		super().__init__(parent)
		self.setWindowTitle("Select Accent Color")
		self.setFixedWidth(300)
		self.dynamic_color = dynamic_color
		self.dark_mode = dark_mode
		self.last_manual_color = QColor(initial_color)

		layout = QVBoxLayout(self)

		# Current color preview
		if dynamic_enabled:
			self.color = QColor(dynamic_color)
		else:
			self.color = QColor(initial_color)
		
		self.preview = QWidget()
		self.preview.setFixedHeight(80)
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

		# Dynamic Toggle
		dynamic_layout = QHBoxLayout()
		self.dynamic_checkbox = QCheckBox("Dynamic Accent (from art)")
		self.dynamic_checkbox.setChecked(dynamic_enabled)
		self.dynamic_checkbox.toggled.connect(self.on_dynamic_toggled)
		dynamic_layout.addWidget(self.dynamic_checkbox)
		layout.addLayout(dynamic_layout)

		# Initialize enabled state of manual controls
		self.r_slider.setEnabled(not dynamic_enabled)
		self.g_slider.setEnabled(not dynamic_enabled)
		self.b_slider.setEnabled(not dynamic_enabled)
		self.hex_input.setEnabled(not dynamic_enabled)

		# Buttons
		btn_layout = QHBoxLayout()
		ok_btn = QPushButton("OK")
		ok_btn.clicked.connect(self.accept)
		cancel_btn = QPushButton("Cancel")
		cancel_btn.clicked.connect(self.reject)
		self.default_btn = QPushButton("Default")
		self.default_btn.clicked.connect(lambda: self.hex_input.setText("#0E47A1"))
		self.default_btn.setEnabled(not dynamic_enabled)

		btn_layout.addWidget(ok_btn)
		btn_layout.addWidget(cancel_btn)
		btn_layout.addWidget(self.default_btn)
		layout.addLayout(btn_layout)

		# Now that everything is created, update preview and styles
		self.update_preview()

	def on_dynamic_toggled(self, checked):
		# Block signals to avoid partial color updates while setting RGB sliders
		# which would corrupt last_manual_color
		self.r_slider.blockSignals(True)
		self.g_slider.blockSignals(True)
		self.b_slider.blockSignals(True)

		self.r_slider.setEnabled(not checked)
		self.g_slider.setEnabled(not checked)
		self.b_slider.setEnabled(not checked)
		self.hex_input.setEnabled(not checked)
		self.default_btn.setEnabled(not checked)
		
		if checked:
			# Update sliders to the dynamic artwork color
			color = QColor(self.dynamic_color)
			self.r_slider.setValue(color.red())
			self.g_slider.setValue(color.green())
			self.b_slider.setValue(color.blue())
		else:
			# Restore to last used manual color
			self.r_slider.setValue(self.last_manual_color.red())
			self.g_slider.setValue(self.last_manual_color.green())
			self.b_slider.setValue(self.last_manual_color.blue())

		self.r_slider.blockSignals(False)
		self.g_slider.blockSignals(False)
		self.b_slider.blockSignals(False)

		# Manually trigger one update to sync self.color and preview
		self.on_slider_changed()

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
		color_name = self.color.name()
		self.preview.setStyleSheet(f"background-color: {color_name}; border: 1px solid #3d3d3d; border-radius: 4px;")
		
		if self.dark_mode:
			slider_subpage = color_name
			text_color = "#ffffff"
			border_color = "#3d3d3d"
		else:
			slider_subpage = self.color.lighter(120).name()
			text_color = "#1a1a1a"
			border_color = "#c0c0c0"

		slider_style = f"""
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
		"""
		self.r_slider.setStyleSheet(slider_style)
		self.g_slider.setStyleSheet(slider_style)
		self.b_slider.setStyleSheet(slider_style)

	def on_slider_changed(self):
		self.color = QColor(self.r_slider.value(), self.g_slider.value(), self.b_slider.value())
		
		# Keep track of the last manual color choice
		if not self.dynamic_checkbox.isChecked():
			self.last_manual_color = self.color

		self.hex_input.blockSignals(True)
		self.hex_input.setText(self.color.name().upper())
		self.hex_input.blockSignals(False)
		self.update_preview()

	def on_hex_changed(self, text):
		if QColor.isValidColorName(text):
			self.color = QColor(text)
			
			# Update last used manual color if dynamic is off
			if not self.dynamic_checkbox.isChecked():
				self.last_manual_color = self.color

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

	def get_dynamic_enabled(self):
		return self.dynamic_checkbox.isChecked()

	def update_dynamic_color(self, new_color):
		self.dynamic_color = new_color
		if self.dynamic_checkbox.isChecked():
			color = QColor(new_color)
			self.r_slider.blockSignals(True)
			self.g_slider.blockSignals(True)
			self.b_slider.blockSignals(True)
			self.r_slider.setValue(color.red())
			self.g_slider.setValue(color.green())
			self.b_slider.setValue(color.blue())
			self.r_slider.blockSignals(False)
			self.g_slider.blockSignals(False)
			self.b_slider.blockSignals(False)
			self.on_slider_changed()

class LibraryFoldersDialog(QDialog):
	def __init__(self, watched_folders, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Manage Music Folders")
		self.resize(500, 350)
		self.watched_folders = list(watched_folders) # Copy

		layout = QVBoxLayout(self)

		label = QLabel("Folders included in your music library:")
		layout.addWidget(label)

		self.list_widget = QListWidget()
		for folder in self.watched_folders:
			self.list_widget.addItem(folder)
		layout.addWidget(self.list_widget)

		btn_layout = QHBoxLayout()
		add_btn = QPushButton("Add Folder")
		add_btn.clicked.connect(self.add_folder)
		remove_btn = QPushButton("Remove Selected")
		remove_btn.clicked.connect(self.remove_folder)

		btn_layout.addWidget(add_btn)
		btn_layout.addWidget(remove_btn)
		layout.addLayout(btn_layout)

		# Standard dialog buttons
		buttons = QHBoxLayout()
		ok_btn = QPushButton("Save and Rescan")
		ok_btn.clicked.connect(self.accept)
		cancel_btn = QPushButton("Cancel")
		cancel_btn.clicked.connect(self.reject)
		buttons.addStretch()
		buttons.addWidget(ok_btn)
		buttons.addWidget(cancel_btn)
		layout.addLayout(buttons)

	def add_folder(self):
		folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
		if folder and folder not in self.watched_folders:
			self.watched_folders.append(folder)
			self.list_widget.addItem(folder)

	def remove_folder(self):
		current_item = self.list_widget.currentItem()
		if current_item:
			folder = current_item.text()
			if folder in self.watched_folders:
				self.watched_folders.remove(folder)
			self.list_widget.takeItem(self.list_widget.row(current_item))

	def get_folders(self):
		return self.watched_folders

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

	def clear(self):
		self._original_pixmap = None
		super().clear()

	def setText(self, text):
		self._original_pixmap = None
		super().setText(text)

	def resizeEvent(self, event):
		if self._original_pixmap and not self._original_pixmap.isNull():
			scaled = self._original_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
			super().setPixmap(scaled)
		super().resizeEvent(event)

class NumericTableWidgetItem(QTableWidgetItem):
	def __lt__(self, other):
		if isinstance(other, QTableWidgetItem):
			data = self.data(Qt.ItemDataRole.UserRole)
			other_data = other.data(Qt.ItemDataRole.UserRole)
			if data is not None and other_data is not None:
				return data < other_data
		return super().__lt__(other)

class EditMetadataDialog(QDialog):
	def __init__(self, song_path, parent=None):
		super().__init__(parent)
		self.song_path = song_path
		self.setWindowTitle("Edit Metadata")
		self.setFixedWidth(500)

		self.new_artwork_data = None
		self.mime_type = "image/jpeg"

		from mutagen import File
		try:
			self.audio = File(song_path, easy=True)
			if self.audio is None:
				# Try without easy=True if easy failed to even return an object
				self.audio = File(song_path)
		except Exception as e:
			print(f"Error loading metadata for editing: {e}")
			self.audio = None

		layout = QVBoxLayout(self)

		# Metadata fields
		form_layout = QGridLayout()
		self.fields = {}

		metadata_keys = [
			("Title", "title"),
			("Artist", "artist"),
			("Album", "album"),
			("Year", "date"),
			("Track #", "tracknumber"),
			("Genre", "genre")
		]

		for i, (label_text, key) in enumerate(metadata_keys):
			form_layout.addWidget(QLabel(label_text), i, 0)
			line_edit = QLineEdit()
			if self.audio and key in self.audio:
				val = self.audio[key][0] if isinstance(self.audio[key], list) and self.audio[key] else str(self.audio[key])
				line_edit.setText(val)
			form_layout.addWidget(line_edit, i, 1)
			self.fields[key] = line_edit

		layout.addLayout(form_layout)

		# Album Art Section
		art_group = QHBoxLayout()

		self.art_label = QLabel()
		self.art_label.setFixedSize(120, 120)
		self.art_label.setScaledContents(True)
		self.art_label.setStyleSheet("border: 1px solid #555; background-color: #222;")
		self.art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

		self.load_current_art()
		art_group.addWidget(self.art_label)

		art_btn_layout = QVBoxLayout()
		change_art_btn = QPushButton("Change Album Art")
		change_art_btn.clicked.connect(self.change_art)
		art_btn_layout.addWidget(change_art_btn)
		art_btn_layout.addStretch()
		art_group.addLayout(art_btn_layout)

		layout.addLayout(art_group)

		# Buttons
		btn_layout = QHBoxLayout()
		btn_layout.addStretch()
		save_btn = QPushButton("Save Changes")
		save_btn.clicked.connect(self.save_metadata)
		save_btn.setStyleSheet("padding: 5px 15px; font-weight: bold;")
		cancel_btn = QPushButton("Cancel")
		cancel_btn.clicked.connect(self.reject)
		btn_layout.addWidget(save_btn)
		btn_layout.addWidget(cancel_btn)
		layout.addLayout(btn_layout)

	def load_current_art(self):
		from mutagen import File
		try:
			audio = File(self.song_path)
			artwork = None
			if audio:
				# Handle different tag formats
				if hasattr(audio, 'tags') and audio.tags:
					# Try APIC for ID3
					for key in audio.tags.keys():
						if key.startswith('APIC'):
							artwork = audio.tags[key].data
							break

				if not artwork and 'APIC:' in audio:  # Fallback
					artwork = audio['APIC:'].data
				elif not artwork and hasattr(audio, 'pictures') and audio.pictures:  # FLAC
					artwork = audio.pictures[0].data
				elif not artwork and 'covr' in audio:  # MP4
					artwork = audio['covr'][0]

			if artwork:
				pixmap = QPixmap()
				pixmap.loadFromData(artwork)
				self.art_label.setPixmap(pixmap)
			else:
				self.art_label.setText("No Art")
		except Exception as e:
			print(f"Error loading art in dialog: {e}")
			self.art_label.setText("Error")

	def change_art(self):
		file_path, _ = QFileDialog.getOpenFileName(
			self, "Select Album Art", "", "Images (*.jpg *.jpeg *.png *.bmp)"
		)
		if file_path:
			try:
				with open(file_path, 'rb') as f:
					self.new_artwork_data = f.read()

				# Simple mime detection
				ext = Path(file_path).suffix.lower()
				if ext in ['.jpg', '.jpeg']:
					self.mime_type = "image/jpeg"
				elif ext == '.png':
					self.mime_type = "image/png"
				elif ext == '.bmp':
					self.mime_type = "image/bmp"

				pixmap = QPixmap()
				pixmap.loadFromData(self.new_artwork_data)
				self.art_label.setPixmap(pixmap)
			except Exception as e:
				from PyQt6.QtWidgets import QMessageBox
				QMessageBox.warning(self, "Error", f"Could not load image: {e}")

	def save_metadata(self):
		from mutagen import File
		try:
			# Save text metadata
			audio = File(self.song_path, easy=True)
			if audio is not None:
				for key, line_edit in self.fields.items():
					audio[key] = [line_edit.text()]
				audio.save()

			# Save artwork if changed
			if self.new_artwork_data:
				ext = Path(self.song_path).suffix.lower()
				if ext == '.mp3':
					from mutagen.id3 import ID3, APIC
					try:
						tags = ID3(self.song_path)
					except:
						tags = ID3()

					# Clear existing APIC tags
					keys_to_delete = [k for k in tags.keys() if k.startswith('APIC')]
					for k in keys_to_delete:
						del tags[k]

					tags.add(APIC(
						encoding=3,
						mime=self.mime_type,
						type=3,
						desc=u'Cover',
						data=self.new_artwork_data
					))
					tags.save(self.song_path)
				elif ext == '.flac':
					from mutagen.flac import Picture, FLAC
					audio = FLAC(self.song_path)
					picture = Picture()
					picture.data = self.new_artwork_data
					picture.type = 3
					picture.mime = self.mime_type
					# Remove existing pictures
					audio.clear_pictures()
					audio.add_picture(picture)
					audio.save()
				elif ext in ['.m4a', '.mp4']:
					from mutagen.mp4 import MP4, MP4Cover
					audio = MP4(self.song_path)
					fmt = MP4Cover.FORMAT_JPEG if self.mime_type == "image/jpeg" else MP4Cover.FORMAT_PNG
					audio['covr'] = [MP4Cover(self.new_artwork_data, imageformat=fmt)]
					audio.save()
				# Add more formats as needed if required

			self.accept()
		except Exception as e:
			from PyQt6.QtWidgets import QMessageBox
			QMessageBox.critical(self, "Error", f"Failed to save metadata: {e}")

class SearchDialog(QDialog):
	result_selected = pyqtSignal(dict)

	def __init__(self, library, parent=None):
		super().__init__(parent)
		self.library = library
		self.setWindowTitle("Search Library")
		self.setMinimumSize(600, 450)

		layout = QVBoxLayout(self)

		self.search_bar = QLineEdit()
		self.search_bar.setPlaceholderText("Search for artists, albums, or songs...")
		self.search_bar.textChanged.connect(self.perform_search)
		self.search_bar.setMinimumHeight(35)
		layout.addWidget(self.search_bar)

		self.results_tree = QTreeWidget()
		self.results_tree.setHeaderLabels(["Result", "Type", "Info"])
		self.results_tree.setIndentation(20)
		self.results_tree.setColumnWidth(0, 250)
		self.results_tree.setColumnWidth(1, 80)
		self.results_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
		layout.addWidget(self.results_tree)

		# Top-level items
		self.artists_root = QTreeWidgetItem(self.results_tree, ["Artists"])
		self.albums_root = QTreeWidgetItem(self.results_tree, ["Albums"])
		self.songs_root = QTreeWidgetItem(self.results_tree, ["Songs"])

		# Bold the root items
		root_font = self.results_tree.font()
		root_font.setBold(True)
		root_font.setPointSize(root_font.pointSize() + 1)
		for root in [self.artists_root, self.albums_root, self.songs_root]:
			root.setFont(0, root_font)
			root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsSelectable) # Make roots non-selectable

		self.artists_root.setExpanded(True)
		self.albums_root.setExpanded(True)
		self.songs_root.setExpanded(True)

		# Set focus to search bar
		self.search_bar.setFocus()

	def changeEvent(self, event):
		from PyQt6.QtCore import QEvent
		if event.type() == QEvent.Type.ActivationChange:
			if not self.isActiveWindow():
				self.reject()
		super().changeEvent(event)

	def on_item_double_clicked(self, item, column):
		# Don't do anything if it's one of the root items
		if item in [self.artists_root, self.albums_root, self.songs_root]:
			return

		data = item.data(0, Qt.ItemDataRole.UserRole)
		if data:
			self.result_selected.emit(data)
			self.accept()

	def perform_search(self, query):
		# Clear previous results
		self.artists_root.takeChildren()
		self.albums_root.takeChildren()
		self.songs_root.takeChildren()

		if not query or len(query.strip()) < 2:
			# Hide roots if query too short
			self.artists_root.setHidden(True)
			self.albums_root.setHidden(True)
			self.songs_root.setHidden(True)
			return

		query = query.lower().strip()

		found_artists = set()
		found_albums = set() # (album_name, artist_name)
		found_songs = [] # list of song dicts

		for genre in self.library:
			for artist in self.library[genre]:
				if query in artist.lower():
					found_artists.add(artist)

				for album in self.library[genre][artist]:
					if query in album.lower():
						found_albums.add((album, artist))

					for song in self.library[genre][artist][album]:
						if query in song['title'].lower():
							found_songs.append(song)

		# Populate Artists
		for artist in sorted(found_artists):
			item = QTreeWidgetItem(self.artists_root, [artist, "Artist", ""])
			item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'artist', 'artist': artist})

		# Populate Albums
		for album, artist in sorted(found_albums):
			item = QTreeWidgetItem(self.albums_root, [album, "Album", f"by {artist}"])
			item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'album', 'album': album, 'artist': artist})

		# Populate Songs
		for song in found_songs:
			item = QTreeWidgetItem(self.songs_root, [song['title'], "Song", f"{song['artist']} - {song['album']}"])
			item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'song', 'song': song})

		# Show root items only if they have children
		self.artists_root.setHidden(self.artists_root.childCount() == 0)
		self.albums_root.setHidden(self.albums_root.childCount() == 0)
		self.songs_root.setHidden(self.songs_root.childCount() == 0)

class MusicPlayer(QMainWindow):
	dynamic_color_updated = pyqtSignal(str)

	def __init__(self):
		super().__init__()

		self.setWindowTitle("Buzzkill Music Player")

		# Default size (will be overridden by load_settings if saved geometry exists)
		self.setGeometry(100, 100, 1200, 720)

		# Music library structure: {genre: {artist: {album: [songs]}}}
		self.library = {}
		self.current_songs = []
		self.watched_folders = []

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

		# Connect player signals
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
		self.icon_size = QSize(20, 20)
		self.is_muted = False
		self.volume_before_mute = 50
		self.repeat_mode = 0	# 0=off, 1=song, 2=album
		self.shuffle_enabled = False
		self.unshuffled_playlist = []
		self.remember_position = False
		self.accent_color = "#0E47A1"
		self.manual_accent_color = "#0E47A1"
		self.dynamic_accent_color_enabled = False
		self.show_album_art = False
		self.is_shrunk = False
		self.expanded_geometry = None
		self.is_restoring = False
		self.detected_dynamic_color = "#0E47A1"
		self.sync_lyrics = []
		self.last_lyric_index = -1

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
		layout.addSpacing(10)

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
		self.left_container = QWidget()
		self.left_container.setMinimumWidth(200)
		# We remove MaximumWidth so it can expand if needed to balance the grid,
		# but the layout inside keeps buttons to the left.

		left_controls = QHBoxLayout(self.left_container)
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

		# Remember position toggle button
		self.remember_position_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.remember_position_btn.setIcon(self.load_icon('bookmark-off.svg', icon_color))
		self.remember_position_btn.setIconSize(self.icon_size)
		self.remember_position_btn.setToolTip("Remember playback position (Off)")
		self.remember_position_btn.setFlat(True)
		self.remember_position_btn.clicked.connect(self.toggle_remember_position)
		left_controls.addWidget(self.remember_position_btn)

		# Show album art toggle button
		self.show_album_art_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.show_album_art_btn.setIcon(self.load_icon('album-art.svg', icon_color))
		self.show_album_art_btn.setIconSize(self.icon_size)
		self.show_album_art_btn.setToolTip("Show album artwork")
		self.show_album_art_btn.setFlat(True)
		self.show_album_art_btn.clicked.connect(self.toggle_album_art)
		left_controls.addWidget(self.show_album_art_btn)

		# Dark/Light Mode button
		self.darkmode_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.darkmode_btn.setIcon(self.load_icon('mode-dark.svg', icon_color))
		self.darkmode_btn.setIconSize(self.icon_size)
		self.darkmode_btn.setToolTip("Toggle dark/light mode")
		self.darkmode_btn.setFlat(True)
		self.darkmode_btn.clicked.connect(self.toggle_theme)
		left_controls.addWidget(self.darkmode_btn)

		# Shrink/Expand button
		self.shrink_expand_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.shrink_expand_btn.setIcon(self.load_icon('shrink.svg', icon_color))
		self.shrink_expand_btn.setIconSize(self.icon_size)
		self.shrink_expand_btn.setToolTip("Shrink/Expand the Interface")
		self.shrink_expand_btn.setFlat(True)
		self.shrink_expand_btn.clicked.connect(self.shrink_and_expand)
		left_controls.addWidget(self.shrink_expand_btn)

		# Accent Color button
		self.accent_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.accent_btn.setIcon(self.load_icon('paint.svg', icon_color))
		self.accent_btn.setIconSize(self.icon_size)
		self.accent_btn.setToolTip("Change accent color")
		self.accent_btn.setFlat(True)
		self.accent_btn.clicked.connect(self.choose_accent_color)
		left_controls.addWidget(self.accent_btn)

		# ===========================
		# 2. CENTER SECTION
		# ===========================
		center_container = QWidget()
		# No specific width limits needed here; the Grid Layout handles centering.

		center_controls = QHBoxLayout(center_container)
		center_controls.setContentsMargins(0, 0, 0, 0)
		center_controls.setSpacing(28)
		center_controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

		# Shuffle button
		self.shuffle_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color))
		self.shuffle_btn.setIconSize(self.icon_size)
		self.shuffle_btn.setToolTip("Shuffle")
		self.shuffle_btn.setFlat(True)
		self.shuffle_btn.clicked.connect(self.toggle_shuffle)
		center_controls.addWidget(self.shuffle_btn)

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
		self.play_btn.setIconSize(QSize(36, 36))
		self.play_btn.setToolTip("Play/Pause")
		self.play_btn.setFlat(True)
		self.play_btn.clicked.connect(self.play_pause)
		center_controls.addWidget(self.play_btn)

		# Stop button
		# self.stop_btn = QPushButton()
		# icon_color = 'white' if self.dark_mode else 'black'
		# self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color))
		# self.stop_btn.setIconSize(self.icon_size)
		# self.stop_btn.setToolTip("Stop the current playing track")
		# self.stop_btn.setFlat(True)
		# self.stop_btn.clicked.connect(self.stop)
		# center_controls.addWidget(self.stop_btn)

		# Next track button
		self.next_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.next_btn.setIcon(self.load_icon('next.svg', icon_color))
		self.next_btn.setIconSize(self.icon_size)
		self.next_btn.setToolTip("Go to next track")
		self.next_btn.setFlat(True)
		self.next_btn.clicked.connect(self.next_track)
		center_controls.addWidget(self.next_btn)

		# Repeat button
		self.repeat_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color))
		self.repeat_btn.setIconSize(self.icon_size)
		self.repeat_btn.setToolTip("Repeat/Loop (Off, Song, Album)")
		self.repeat_btn.setFlat(True)
		self.repeat_btn.clicked.connect(self.cycle_repeat_mode)
		center_controls.addWidget(self.repeat_btn)

		# ===========================
		# 3. RIGHT SECTION
		# ===========================
		self.right_container = QWidget()
		self.right_container.setMinimumWidth(200)

		right_controls = QHBoxLayout(self.right_container)
		right_controls.setContentsMargins(0, 0, 0, 0)

		right_controls.addStretch()

		# Search button
		self.search_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.search_btn.setIcon(self.load_icon('search.svg', icon_color))
		self.search_btn.setIconSize(self.icon_size)
		self.search_btn.setToolTip("Search your library")
		self.search_btn.setFlat(True)
		self.search_btn.clicked.connect(self.search_library)
		right_controls.addWidget(self.search_btn)

		# Lyrics button
		self.lyrics_btn = QPushButton()
		icon_color = 'white' if self.dark_mode else 'black'
		self.lyrics_btn.setIcon(self.load_icon('lyrics.svg', icon_color))
		self.lyrics_btn.setIconSize(self.icon_size)
		self.lyrics_btn.setToolTip("Show lyrics")
		self.lyrics_btn.setFlat(True)
		self.lyrics_btn.clicked.connect(self.show_lyrics)
		right_controls.addWidget(self.lyrics_btn)

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

		# ===========================
		# ASSEMBLE GRID
		# ===========================
		# Add widgets to the grid.
		# (Widget, Row, Column, Alignment)

		# Left container in Col 0, Aligned Left
		controls_layout.addWidget(self.left_container, 0, 0, Qt.AlignmentFlag.AlignLeft)

		# Center container in Col 1, Aligned Center
		controls_layout.addWidget(center_container, 0, 1, Qt.AlignmentFlag.AlignCenter)

		# Right container in Col 2, Aligned Right
		controls_layout.addWidget(self.right_container, 0, 2, Qt.AlignmentFlag.AlignRight)

		# Add the controls grid to the main layout
		layout.addLayout(controls_layout)

		# Set initial volume
		self.audio_output.setVolume(0.5)


		#==========================================================
		# Now Playing section
		now_playing_layout = QHBoxLayout()
		now_playing_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.now_playing_label = QLabel("Now Playing:")
		now_playing_layout.addWidget(self.now_playing_label)

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
		self.progress_slider.scrolled.connect(self.on_progress_slider_wheeled)
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
		self.song_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
		self.song_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
		self.song_table.customContextMenuRequested.connect(self.show_context_menu)
		self.song_table.setSortingEnabled(True)
		self.song_table.verticalHeader().setVisible(False)  # Remove row numbers
		self.song_table.itemDoubleClicked.connect(self.on_song_double_clicked)
		self.song_table.horizontalHeader().sectionResized.connect(self.save_settings)
		self.splitter.addWidget(self.song_table)
		self.splitter.splitterMoved.connect(lambda: self.save_settings())

		# Set stretch factors: 0 for row 2 (don't stretch), 1 for row 3 (take all extra space)
		self.splitter.setStretchFactor(0, 0)  # top_widget (genre/artist/album) - no stretch
		self.splitter.setStretchFactor(1, 1)  # song_table - gets all the stretch

		# Content stack to toggle between library and lyrics
		self.content_stack = QStackedWidget()
		self.content_stack.addWidget(self.splitter)

		# Lyrics panel
		self.lyrics_view = QTextEdit()
		self.lyrics_view.setReadOnly(True)
		self.lyrics_view.setFrameStyle(0) # No frame

		# Load and set the Propo-Black font for lyrics
		font_path_black = self.app_dir / 'fonts' / 'SauceCodeProNerdFontPropo-Black.ttf'
		font_id_black = QFontDatabase.addApplicationFont(str(font_path_black))
		if font_id_black != -1:
			families = QFontDatabase.applicationFontFamilies(font_id_black)
			if families:
				# Use a larger size for lyrics
				lyrics_font = QFont(families[0], 18)
				self.lyrics_view.setFont(lyrics_font)

		self.content_stack.addWidget(self.lyrics_view)
		layout.addWidget(self.content_stack)

		# Status Bar
		self.setStatusBar(QStatusBar())
		self.statusBar().showMessage("Ready")

	def add_folder(self):
		dialog = LibraryFoldersDialog(self.watched_folders, self)
		if dialog.exec():
			self.watched_folders = dialog.get_folders()
			self.save_library()
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
						title = audio.get('title', [Path(file).stem])[0] if audio.get('title') else Path(file).stem
						track_num = audio.get('tracknumber', [''])[0] if audio.get('tracknumber') else ''
						if track_num == '0' or track_num == '00':
							track_num = ''
						year = audio.get('date', [''])[0] if audio.get('date') else ''
						duration = audio.info.length if hasattr(audio, 'info') else 0

						song_data = {
							'path': full_path,
							'title': title,
							'artist': artist,
							'album': album,
							'genre': genre,
							'tracknumber': track_num,
							'year': year,
							'duration': duration
						}

						# Build library structure
						if genre not in self.library:
							self.library[genre] = {}
						if artist not in self.library[genre]:
							self.library[genre][artist] = {}
						if album not in self.library[genre][artist]:
							self.library[genre][artist][album] = []

						# Check if song already exists in this album
						exists = False
						for s in self.library[genre][artist][album]:
							if isinstance(s, dict) and s['path'] == full_path:
								exists = True
								break
							elif s == full_path: # Handle old format
								exists = True
								break

						if not exists:
							self.library[genre][artist][album].append(song_data)

					except Exception as e:
						print(f"Error reading {full_path}: {e}")
						continue

	def populate_genre_tree(self):
		self.genre_tree.clear()
		genre_count = len(self.library.keys())
		QTreeWidgetItem(self.genre_tree, [f"All Genres ({genre_count})"])
		for genre in sorted(self.library.keys()):
			QTreeWidgetItem(self.genre_tree, [genre])

	def on_genre_selected(self, item):
		genre = item.text(0)
		self.artist_tree.clear()
		self.album_tree.clear()
		self.song_table.setRowCount(0)
		self.song_table.setSortingEnabled(False)

		all_songs = []
		artists = set()

		if genre.startswith("All Genres"):
			for g in self.library:
				for a in self.library[g]:
					artists.add(a)
					for alb in self.library[g][a]:
						all_songs.extend(self.library[g][a][alb])
		elif genre in self.library:
			for a in self.library[genre]:
				artists.add(a)
				for alb in self.library[genre][a]:
					all_songs.extend(self.library[genre][a][alb])

		if artists:
			QTreeWidgetItem(self.artist_tree, [f"All Artists ({len(artists)})"])
			for artist in sorted(list(artists)):
				QTreeWidgetItem(self.artist_tree, [artist])

		if all_songs:
			self.current_playlist = self.sort_playlist(all_songs)
			self.populate_song_table_from_playlist()

		self.song_table.setSortingEnabled(True)

	def on_artist_selected(self, item):
		genre_item = self.genre_tree.currentItem()
		if not genre_item:
			return

		genre = genre_item.text(0)
		artist = item.text(0)

		self.album_tree.clear()
		self.song_table.setRowCount(0)
		self.song_table.setSortingEnabled(False)

		all_songs = []
		albums = set()

		if artist.startswith("All Artists"):
			# Get all albums for the selected genre(s)
			if genre.startswith("All Genres"):
				for g in self.library:
					for a in self.library[g]:
						for alb in self.library[g][a]:
							albums.add(alb)
							all_songs.extend(self.library[g][a][alb])
			elif genre in self.library:
				for a in self.library[genre]:
					for alb in self.library[genre][a]:
						albums.add(alb)
						all_songs.extend(self.library[genre][a][alb])
		else:
			# Specific artist
			if genre.startswith("All Genres"):
				for g in self.library:
					if artist in self.library[g]:
						for alb in self.library[g][artist]:
							albums.add(alb)
							all_songs.extend(self.library[g][artist][alb])
			elif genre in self.library and artist in self.library[genre]:
				for alb in self.library[genre][artist]:
					albums.add(alb)
					all_songs.extend(self.library[genre][artist][alb])

		if albums:
			QTreeWidgetItem(self.album_tree, [f"All Albums ({len(albums)})"])
			for album in sorted(list(albums)):
				QTreeWidgetItem(self.album_tree, [album])

		if all_songs:
			self.current_playlist = self.sort_playlist(all_songs)
			self.populate_song_table_from_playlist()

		self.song_table.setSortingEnabled(True)

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
		self.song_table.setSortingEnabled(False)

		all_songs = []

		if album.startswith("All Albums"):
			# Get all songs for the selected artist(s) and genre(s)
			if genre.startswith("All Genres"):
				if artist.startswith("All Artists"):
					for g in self.library:
						for a in self.library[g]:
							for alb in self.library[g][a]:
								all_songs.extend(self.library[g][a][alb])
				else:
					for g in self.library:
						if artist in self.library[g]:
							for alb in self.library[g][artist]:
								all_songs.extend(self.library[g][artist][alb])
			else:
				if artist.startswith("All Artists"):
					for a in self.library[genre]:
						for alb in self.library[genre][a]:
							all_songs.extend(self.library[genre][a][alb])
				else:
					for alb in self.library[genre][artist]:
						all_songs.extend(self.library[genre][artist][alb])
		else:
			# Specific album
			if genre.startswith("All Genres"):
				if artist.startswith("All Artists"):
					# This is tricky - album might exist in multiple genres/artists
					for g in self.library:
						for a in self.library[g]:
							if album in self.library[g][a]:
								all_songs.extend(self.library[g][a][album])
				else:
					for g in self.library:
						if artist in self.library[g] and album in self.library[g][artist]:
							all_songs.extend(self.library[g][artist][album])
			else:
				if artist.startswith("All Artists"):
					for a in self.library[genre]:
						if album in self.library[genre][a]:
							all_songs.extend(self.library[genre][a][album])
				else:
					if album in self.library[genre][artist]:
						all_songs.extend(self.library[genre][artist][album])

		if all_songs:
			self.current_playlist = self.sort_playlist(all_songs)
			self.populate_song_table_from_playlist()

		self.song_table.setSortingEnabled(True)

	def on_song_double_clicked(self, item):
		row = item.row()
		song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)

		# Build playlist from current song table to preserve current sorting/filtering
		self.current_playlist = []
		for i in range(self.song_table.rowCount()):
			# Extract all metadata from table columns to maintain consistency
			path = self.song_table.item(i, 0).data(Qt.ItemDataRole.UserRole + 1)
			track_num = self.song_table.item(i, 0).text()
			title = self.song_table.item(i, 1).text()
			artist = self.song_table.item(i, 2).text()
			album = self.song_table.item(i, 3).text()
			year = self.song_table.item(i, 4).text()
			duration = self.song_table.item(i, 5).data(Qt.ItemDataRole.UserRole)
			genre = self.song_table.item(i, 6).text()

			self.current_playlist.append({
				'path': path,
				'tracknumber': track_num,
				'title': title,
				'artist': artist,
				'album': album,
				'year': year,
				'duration': duration,
				'genre': genre
			})

		self.current_track_index = row
		self.play_song(song_path)

	def show_context_menu(self, position):
		item = self.song_table.itemAt(position)
		if not item:
			return

		menu = QMenu(self)
		edit_action = menu.addAction("Edit Metadata")

		action = menu.exec(self.song_table.viewport().mapToGlobal(position))

		if action == edit_action:
			self.open_edit_metadata_dialog(item.row())

	def open_edit_metadata_dialog(self, row):
		# Path is stored in UserRole+1 of the first column
		song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)

		if not song_path or not os.path.exists(song_path):
			self.statusBar().showMessage("Error: Song file not found.")
			return

		dialog = EditMetadataDialog(song_path, self)
		if dialog.exec():
			# Refresh the library and UI
			self.statusBar().showMessage("Metadata saved. Refreshing library...")

			# If the edited song is the one currently playing, refresh the album art
			current_source = self.player.source().toLocalFile()
			if current_source == song_path:
				self.update_album_art()

			self.rescan_library()

	def play_song(self, file_path):
			icon_color = 'white' if self.dark_mode else 'black'

			self.player.setSource(QUrl.fromLocalFile(file_path))
			self.player.play()
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color))
			self.play_btn.setToolTip("Pause")

			# Update now playing display
			# Try to find metadata in current_playlist first (much faster than disk)
			found_metadata = False
			for song in self.current_playlist:
				if isinstance(song, dict) and song.get('path') == file_path:
					artist = song.get('artist', 'Unknown Artist')
					title = song.get('title', Path(file_path).stem)
					self.now_playing_text.setText(f"{artist} - {title}")
					found_metadata = True
					break

			if not found_metadata:
				from mutagen import File
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
			self.play_btn.setIcon(self.load_icon('play.svg', icon_color))
			self.play_btn.setToolTip("Play")
		else:
			self.player.play()
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color))
			self.play_btn.setToolTip("Pause")

	def stop(self):
		icon_color = 'white' if self.dark_mode else 'black'

		self.player.stop()
		self.play_btn.setIcon(self.load_icon('play.svg', icon_color))
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

		song = self.current_playlist[self.current_track_index]
		song_path = song['path'] if isinstance(song, dict) else song
		self.play_song(song_path)
		self.highlight_current_song()

	def previous_track(self):
		if not self.current_playlist:
			return

		self.current_track_index -= 1

		if self.current_track_index < 0:
			self.current_track_index = 0

		song = self.current_playlist[self.current_track_index]
		song_path = song['path'] if isinstance(song, dict) else song
		self.play_song(song_path)
		self.highlight_current_song()

	def highlight_current_song(self):
		if not self.current_playlist:
			return

		# Get current song path for comparison
		current_song = self.current_playlist[self.current_track_index]
		current_path = current_song['path'] if isinstance(current_song, dict) else current_song

		# Find and select the current song in the table
		for row in range(self.song_table.rowCount()):
			# Path is stored in UserRole+1 in populate_song_table_from_playlist
			row_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
			if row_path == current_path:
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
			selected_song_path = self.song_table.item(current_song_row, 0).data(Qt.ItemDataRole.UserRole + 1)

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
			'accent_color': self.manual_accent_color,
			'dynamic_accent_color_enabled': self.dynamic_accent_color_enabled,
			'show_album_art': self.show_album_art,
			'is_shrunk': self.is_shrunk,
			'progress_slider_min_width': self.progress_slider.minimumWidth(),
			'progress_slider_max_width': self.progress_slider.maximumWidth(),
			'play_btn_icon_size': [self.play_btn.iconSize().width(), self.play_btn.iconSize().height()],
			'expanded_geometry': [
				self.expanded_geometry.x(),
				self.expanded_geometry.y(),
				self.expanded_geometry.width(),
				self.expanded_geometry.height()
			] if self.expanded_geometry else None
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

			# Restore accent color
			self.accent_color = settings.get('accent_color', "#1976d2")
			self.manual_accent_color = self.accent_color

			# Restore dynamic accent color state
			self.dynamic_accent_color_enabled = settings.get('dynamic_accent_color_enabled', False)

			# Restore slider widths and play button size
			slider_min = settings.get('progress_slider_min_width')
			slider_max = settings.get('progress_slider_max_width')
			if slider_min: self.progress_slider.setMinimumWidth(slider_min)
			if slider_max: self.progress_slider.setMaximumWidth(slider_max)

			play_icon_size = settings.get('play_btn_icon_size')
			if play_icon_size:
				self.play_btn.setIconSize(QSize(*play_icon_size))

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

			# Restore remember position state
			self.remember_position = settings.get('remember_position', False)
			if self.remember_position:
				self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg', icon_color))
				self.remember_position_btn.setToolTip("Remember playback position (On)")
			else:
				self.remember_position_btn.setIcon(self.load_icon('bookmark-off.svg', icon_color))
				self.remember_position_btn.setToolTip("Remember playback position (Off)")

			# Restore album art state
			self.show_album_art = settings.get('show_album_art', False)
			if self.show_album_art:
				self.album_art_label.show()
				self.update_album_art()
			else:
				self.album_art_label.hide()

			# Restore shrink state
			self.is_shrunk = settings.get('is_shrunk', False)
			expanded_geo = settings.get('expanded_geometry')
			if expanded_geo:
				self.expanded_geometry = QRect(*expanded_geo)

			icon_color = 'white' if self.dark_mode else 'black'
			if self.is_shrunk:
				# Hide non-essential sections
				self.content_stack.hide()
				self.right_container.hide()
				self.now_playing_label.hide()
				self.statusBar().hide()

				# Hide all buttons in left section EXCEPT shrink/expand
				self.add_folder_btn.hide()
				self.rescan_btn.hide()
				self.remember_position_btn.hide()
				self.show_album_art_btn.hide()
				self.darkmode_btn.hide()
				self.accent_btn.hide()

				# Remove minimum width constraint temporarily
				self.left_container.setMinimumWidth(0)

				# Adjust progress slider width for mini mode
				self.progress_slider.setMinimumWidth(200)
				self.progress_slider.setMaximumWidth(350)

				# Set fixed size for mini mode
				self.setFixedSize(400, 107)

				shrink_icon = 'expand.svg'
				self.shrink_expand_btn.setToolTip("Expand the Interface")
			else:
				self.content_stack.show()
				shrink_icon = 'shrink.svg'
				self.shrink_expand_btn.setToolTip("Shrink the Interface")

			self.shrink_expand_btn.setIcon(self.load_icon(shrink_icon, icon_color))

			# Apply theme after loading all settings
			self.apply_theme()
			# Reload all style-affected icons with the restored button style
			self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color))
			self.rescan_btn.setIcon(self.load_icon('rescan.svg', icon_color))
			self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg' if self.remember_position else 'bookmark-off.svg', icon_color))
			self.show_album_art_btn.setIcon(self.load_icon('album-art.svg', icon_color))
			self.lyrics_btn.setIcon(self.load_icon('lyrics.svg', icon_color))
			self.search_btn.setIcon(self.load_icon('search.svg', icon_color))
			self.prev_btn.setIcon(self.load_icon('previous.svg', icon_color))
			self.next_btn.setIcon(self.load_icon('next.svg', icon_color))
			# self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color))

			# Update play/pause based on state
			if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
				self.play_btn.setIcon(self.load_icon('pause.svg', icon_color))
			else:
				self.play_btn.setIcon(self.load_icon('play.svg', icon_color))

			# Update volume/mute button
			if self.is_muted or self.volume_slider.value() == 0:
				self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color))
			else:
				self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color))

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
				sel_song = self.song_table.item(curr_row, 0).data(Qt.ItemDataRole.UserRole + 1)

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

		# Synchronized lyrics highlighting and scrolling
		if self.sync_lyrics and self.content_stack.currentIndex() == 1:
			# Find the current line based on position
			current_index = -1
			for i, (time_ms, _) in enumerate(self.sync_lyrics):
				if position >= time_ms:
					current_index = i
				else:
					break

			if current_index != -1 and current_index != self.last_lyric_index:
				self.last_lyric_index = current_index

				# Highlight the current line
				from PyQt6.QtGui import QTextCursor, QTextCharFormat

				# Reset all formatting to inactive color
				cursor = self.lyrics_view.textCursor()
				cursor.select(QTextCursor.SelectionType.Document)
				format_reset = QTextCharFormat()
				inactive_color = QColor("#555555") if self.dark_mode else QColor("#aaaaaa")
				format_reset.setForeground(inactive_color)
				cursor.setCharFormat(format_reset)

				# Apply highlight to current line
				cursor.movePosition(QTextCursor.MoveOperation.Start)
				for _ in range(current_index):
					cursor.movePosition(QTextCursor.MoveOperation.NextBlock)

				cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
				format_highlight = QTextCharFormat()
				# Active color: light gray for dark theme, black for light theme
				active_color = QColor("#eeeeee") if self.dark_mode else QColor("#000000")
				format_highlight.setForeground(active_color)
				format_highlight.setFontWeight(QFont.Weight.Bold)
				cursor.setCharFormat(format_highlight)

				# Ensure visible and center it
				self.lyrics_view.setTextCursor(cursor)

				# Center the current line in the view
				scrollbar = self.lyrics_view.verticalScrollBar()
				if scrollbar:
					# Get the position of the current block
					block = cursor.block()
					block_pos = self.lyrics_view.document().documentLayout().blockBoundingRect(block).top()

					# Calculate the center position
					viewport_height = self.lyrics_view.viewport().height()
					center_offset = (viewport_height - self.lyrics_view.document().documentLayout().blockBoundingRect(block).height()) / 2

					scrollbar.setValue(int(block_pos - center_offset))

				# Clear selection so it doesn't look like user selection
				cursor.clearSelection()
				self.lyrics_view.setTextCursor(cursor)

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
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color))
			self.mute_btn.setToolTip("Unmute")
		else:
			self.is_muted = False
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color))
			self.mute_btn.setToolTip("Mute")

		self.save_settings()

	def on_media_status_changed(self, status):
		from PyQt6.QtMultimedia import QMediaPlayer

		if status == QMediaPlayer.MediaStatus.EndOfMedia:
			if self.is_restoring:
				return

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

		if genre.startswith("All Genres"):
			for g in self.library:
				for a in self.library[g]:
					for alb in self.library[g][a]:
						self.current_playlist.extend(self.library[g][a][alb])
		elif genre in self.library:
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
			first_song = self.current_playlist[0]
			path = first_song['path'] if isinstance(first_song, dict) else first_song
			self.play_song(path)

	def on_artist_double_clicked(self, item):
		import random

		genre_item = self.genre_tree.currentItem()
		if not genre_item:
			return

		genre = genre_item.text(0)
		artist = item.text(0)
		self.current_playlist = []

		if artist.startswith("All Artists"):
			if genre.startswith("All Genres"):
				for g in self.library:
					for a in self.library[g]:
						for alb in self.library[g][a]:
							self.current_playlist.extend(self.library[g][a][alb])
			elif genre in self.library:
				for a in self.library[genre]:
					for alb in self.library[genre][a]:
						self.current_playlist.extend(self.library[genre][a][alb])
		else:
			# Collect all songs by this artist
			if genre.startswith("All Genres"):
				for g in self.library:
					if artist in self.library[g]:
						for album in self.library[g][artist].values():
							self.current_playlist.extend(album)
			elif genre in self.library and artist in self.library[genre]:
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
			first_song = self.current_playlist[0]
			path = first_song['path'] if isinstance(first_song, dict) else first_song
			self.play_song(path)

	def on_album_double_clicked(self, item):
		import random

		genre_item = self.genre_tree.currentItem()
		artist_item = self.artist_tree.currentItem()

		if not genre_item or not artist_item:
			return

		genre = genre_item.text(0)
		artist = artist_item.text(0)
		album = item.text(0)
		self.current_playlist = []

		if album.startswith("All Albums"):
			if genre.startswith("All Genres"):
				if artist.startswith("All Artists"):
					for g in self.library:
						for a in self.library[g]:
							for alb in self.library[g][a]:
								self.current_playlist.extend(self.library[g][a][alb])
				else:
					for g in self.library:
						if artist in self.library[g]:
							for alb in self.library[g][artist]:
								self.current_playlist.extend(self.library[g][artist][alb])
			else:
				if artist.startswith("All Artists"):
					for a in self.library[genre]:
						for alb in self.library[genre][a]:
							self.current_playlist.extend(self.library[genre][a][alb])
				else:
					for alb in self.library[genre][artist]:
						self.current_playlist.extend(self.library[genre][artist][alb])
		else:
			# Specific album
			if genre.startswith("All Genres"):
				if artist.startswith("All Artists"):
					for g in self.library:
						for a in self.library[g]:
							if album in self.library[g][a]:
								self.current_playlist.extend(self.library[g][a][album])
				else:
					for g in self.library:
						if artist in self.library[g] and album in self.library[g][artist]:
							self.current_playlist.extend(self.library[g][artist][album])
			else:
				if artist.startswith("All Artists"):
					for a in self.library[genre]:
						if album in self.library[genre][a]:
							self.current_playlist.extend(self.library[genre][a][album])
				else:
					if album in self.library[genre][artist]:
						self.current_playlist.extend(self.library[genre][artist][album])

		if self.current_playlist:
			# Sort by track number/title
			self.current_playlist = self.sort_playlist(self.current_playlist)

			# Save original order and shuffle if enabled
			self.unshuffled_playlist = self.current_playlist.copy()
			if self.shuffle_enabled:
				random.shuffle(self.current_playlist)

			self.populate_song_table_from_playlist()
			self.current_track_index = 0
			first_song = self.current_playlist[0]
			path = first_song['path'] if isinstance(first_song, dict) else first_song
			self.play_song(path)

	def populate_song_table_from_playlist(self):
			self.song_table.setRowCount(0)
			self.song_table.setSortingEnabled(False)

			for i, song in enumerate(self.current_playlist):
				self.song_table.insertRow(i)

				if isinstance(song, dict):
					# Use cached metadata
					song_path = song.get('path', '')
					track_num_raw = song.get('tracknumber', '')
					title = song.get('title', Path(song_path).stem)
					artist_name = song.get('artist', '')
					album_name = song.get('album', '')
					genre_name = song.get('genre', '')
					year_raw = song.get('year', '')
					duration = song.get('duration', 0)
				else:
					# Fallback for old format
					song_path = song
					track_num_raw = ''
					title = Path(song_path).stem
					artist_name = ''
					album_name = ''
					genre_name = ''
					year_raw = ''
					duration = 0

				# Track number processing
				track_num_display = str(track_num_raw).strip()
				if '/' in track_num_display:
					track_num_display = track_num_display.split('/')[0]

				if track_num_display == '0' or track_num_display == '00' or not track_num_display:
					track_num_display = ""

				try:
					track_num_sort = int(track_num_display) if track_num_display else 999
				except:
					track_num_sort = 999

				# Year processing
				if '-' in str(year_raw):
					year_display = str(year_raw).split('-')[0]
				else:
					year_display = str(year_raw)

				try:
					year_sort = int(year_display)
				except:
					year_sort = 0

				# Duration processing
				if duration >= 3600:
					hours = int(duration // 3600)
					minutes = int((duration % 3600) // 60)
					seconds = int(duration % 60)
					time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
				else:
					minutes = int(duration // 60)
					seconds = int(duration % 60)
					time_str = f"{minutes}:{seconds:02d}"

				# Populate columns
				track_item = NumericTableWidgetItem(str(track_num_display))
				track_item.setData(Qt.ItemDataRole.UserRole, track_num_sort)
				# Store path in UserRole+1 of the first column for internal use
				track_item.setData(Qt.ItemDataRole.UserRole + 1, song_path)
				self.song_table.setItem(i, 0, track_item)

				title_item = QTableWidgetItem(title)
				# Also store in title column for redundancy if needed
				title_item.setData(Qt.ItemDataRole.UserRole + 1, song_path)
				self.song_table.setItem(i, 1, title_item)

				self.song_table.setItem(i, 2, QTableWidgetItem(artist_name))
				self.song_table.setItem(i, 3, QTableWidgetItem(album_name))

				year_item = NumericTableWidgetItem(str(year_display))
				year_item.setData(Qt.ItemDataRole.UserRole, year_sort)
				self.song_table.setItem(i, 4, year_item)

				time_item = NumericTableWidgetItem(time_str)
				time_item.setData(Qt.ItemDataRole.UserRole, duration)
				self.song_table.setItem(i, 5, time_item)

				self.song_table.setItem(i, 6, QTableWidgetItem(genre_name))

			self.song_table.setSortingEnabled(True)

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
			# Match exact text OR both are "All Genres" (ignoring count)
			if item.text(0) == genre or (genre.startswith("All Genres") and item.text(0).startswith("All Genres")):
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
			# Match exact text OR both are "All Artists" (ignoring count)
			if artist_item.text(0) == artist or (artist.startswith("All Artists") and artist_item.text(0).startswith("All Artists")):
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
			# Match exact text OR both are "All Albums" (ignoring count)
			if album_item.text(0) == album or (album.startswith("All Albums") and album_item.text(0).startswith("All Albums")):
				self.album_tree.setCurrentItem(album_item)
				self.on_album_selected(album_item)

				# Restore selected song if present
				if hasattr(self, '_restore_song_path') and self._restore_song_path:
					from PyQt6.QtCore import QTimer
					QTimer.singleShot(50, lambda: self._restore_song(self._restore_song_path))
				break

	def _restore_song(self, song_path):
		# Handle both dict and string paths
		target_path = song_path['path'] if isinstance(song_path, dict) else song_path

		for row in range(self.song_table.rowCount()):
			current_song_path = self.song_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
			if current_song_path == target_path:
				# Highlight only, do NOT play
				self.song_table.selectRow(row)
				# Scroll to it if needed
				self.song_table.scrollToItem(self.song_table.item(row, 0))
				break

	def closeEvent(self, event):
		self.save_settings()

		# Save playback position if feature is enabled
		if self.remember_position and self.current_playlist and self.current_track_index < len(self.current_playlist):
			# Only save if there's actually a song loaded that matches our current track index.
			# This prevents saving a "stale" or never-played song when just browsing the library.
			current_source = self.player.source().toLocalFile()
			if current_source:
				song = self.current_playlist[self.current_track_index]
				song_path = song['path'] if isinstance(song, dict) else song

				if os.path.normpath(current_source) == os.path.normpath(song_path):
					position_data = {
						'song_path': song,
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

	def load_icon(self, filename, color=None):
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

	def choose_accent_color(self):
		dialog = ColorPickerDialog(self, self.manual_accent_color, self.dynamic_accent_color_enabled, self.detected_dynamic_color, self.dark_mode)
		# Connect real-time updates while dialog is open
		self.dynamic_color_updated.connect(dialog.update_dynamic_color)
		
		if dialog.exec():
			self.manual_accent_color = dialog.get_color()
			self.dynamic_accent_color_enabled = dialog.get_dynamic_enabled()
			
			if self.dynamic_accent_color_enabled:
				# Trigger an update immediately
				self.update_album_art()
			else:
				# Restore the manually chosen accent color (which is blue if they just unchecked dynamic)
				self.accent_color = self.manual_accent_color
				self.apply_theme()

		# Disconnect to avoid memory leaks/stale references
		self.dynamic_color_updated.disconnect(dialog.update_dynamic_color)
		self.save_settings()

	def extract_vibrant_color(self, image):
		if image.isNull():
			return None

		# Scale down for faster processing and automatic averaging of some noise
		small_image = image.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)

		color_counts = {}
		max_count = 0
		best_color = None

		for y in range(small_image.height()):
			for x in range(small_image.width()):
				pixel = small_image.pixelColor(x, y)
				# Ignore very dark/black areas (Value < 50) and very desaturated/gray areas (Saturation < 50)
				# Also ignore very bright/white areas (Value > 240 and Saturation < 30)
				h, s, v, a = pixel.getHsv()

				if v > 50 and s > 50 and not (v > 240 and s < 30):
					# Simplify color space to group similar colors (round Hue to nearest 10)
					rounded_h = (h // 10) * 10
					# Also round S and V slightly
					rounded_s = (s // 20) * 20
					rounded_v = (v // 20) * 20
					key = (rounded_h, rounded_s, rounded_v)

					color_counts[key] = color_counts.get(key, 0) + 1
					if color_counts[key] > max_count:
						max_count = color_counts[key]
						best_color = pixel

		return best_color

	def update_album_art(self):
		# We always need to know if we have art, even if the label is hidden, for dynamic accent color
		source = self.player.source().toLocalFile()
		artwork_found = False
		pixmap = None

		if source and Path(source).exists():
			from mutagen import File
			try:
				audio = File(source)
				artwork_data = None

				if audio:
					if hasattr(audio, 'tags') and audio.tags:
						for key in audio.tags.keys():
							if key.startswith('APIC'):
								artwork_data = audio.tags[key].data
								break
					if not artwork_data and 'APIC:' in audio:
						artwork_data = audio['APIC:'].data
					elif not artwork_data and hasattr(audio, 'pictures') and audio.pictures:
						artwork_data = audio.pictures[0].data
					elif not artwork_data and 'covr' in audio:
						artwork_data = audio['covr'][0]

				if artwork_data:
					pixmap = QPixmap()
					pixmap.loadFromData(artwork_data)
					artwork_found = True
			except Exception as e:
				print(f"Error loading album art: {e}")

		if artwork_found and pixmap:
			vibrant = self.extract_vibrant_color(pixmap.toImage())
			if vibrant:
				self.detected_dynamic_color = vibrant.name()
				self.dynamic_color_updated.emit(self.detected_dynamic_color)

		# Handle Dynamic Accent Color
		if self.dynamic_accent_color_enabled:
			if artwork_found and pixmap:
				if vibrant:
					self.accent_color = self.detected_dynamic_color
					self.apply_theme()
				else:
					# Fallback to manual color if extraction fails or art is too "boring"
					self.restore_manual_accent_color()
			else:
				# Fallback to manual color if no art
				self.restore_manual_accent_color()

		# Update UI Label if visible
		if self.show_album_art:
			if artwork_found and pixmap:
				self.album_art_label.setPixmap(pixmap)
			else:
				self.album_art_label.clear()
				if not source:
					self.album_art_label.setText("No track playing")
				else:
					self.album_art_label.setText("No artwork found")

	def restore_manual_accent_color(self):
		if self.accent_color != self.manual_accent_color:
			self.accent_color = self.manual_accent_color
			self.apply_theme()

	def show_lyrics(self):
		# Toggle back to library if already showing lyrics
		if self.content_stack.currentIndex() == 1:
			self.content_stack.setCurrentIndex(0)
			return

		source = self.player.source().toLocalFile()
		if not source or not os.path.exists(source):
			self.statusBar().showMessage("No track playing")
			return

		from mutagen import File
		try:
			audio = File(source)
			lyrics_text = None
			self.sync_lyrics = []
			self.last_lyric_index = -1

			if audio:
				# Check for different formats
				ext = Path(source).suffix.lower()

				if ext == '.mp3':
					# Check USLT (Unsynchronized lyrics) in ID3 tags
					if hasattr(audio, 'tags') and audio.tags:
						from mutagen.id3 import USLT, SYLT
						for tag in audio.tags.values():
							if isinstance(tag, USLT):
								lyrics_text = tag.text
								break
							elif isinstance(tag, SYLT):
								# Mutagen SYLT data is a list of (text, timestamp)
								# SYLT timestamps are usually in frames or milliseconds
								# For now, let's just try to extract the text part
								self.sync_lyrics = [(t, text) for text, t in tag.lyrics]
								self.sync_lyrics.sort()
								lyrics_text = "\n".join([item[1] for item in self.sync_lyrics])
								break
				elif ext == '.flac':
					# FLAC vorbis comments
					for tag in ['lyrics', 'unsyncedlyrics', 'unsynced lyrics']:
						val = audio.get(tag)
						if val:
							lyrics_text = val[0]
							break
				elif ext in ['.m4a', '.mp4']:
					# MP4 lyrics tag
					val = audio.get('\xa9lyr')
					if val:
						lyrics_text = val[0]

			# Search for external lyric files if metadata didn't have sync lyrics
			if not self.sync_lyrics:
				song_path = Path(source)
				lrc_path = song_path.with_suffix('.lrc')
				txt_path = song_path.with_suffix('.txt')

				target_file = None
				if lrc_path.exists():
					target_file = lrc_path
				elif txt_path.exists():
					target_file = txt_path

				if target_file:
					try:
						with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
							lyrics_text = f.read()

						# Parse LRC for sync if it's an .lrc file
						if target_file.suffix.lower() == '.lrc':
							import re
							lines = lyrics_text.splitlines()
							self.sync_lyrics = []
							for line in lines:
								# Match [mm:ss.xx] or [mm:ss:xx] or [mm:ss]
								matches = re.findall(r'\[(\d+):(\d+)([.:](\d+))?\]', line)
								if matches:
									pure_text = re.sub(r'\[\d+:\d+([.:]\d+)?\]', '', line).strip()
									for m in matches:
										minutes = int(m[0])
										seconds = int(m[1])
										msec = int(m[3]) if m[3] else 0
										if m[3] and len(m[3]) == 2: msec *= 10
										elif m[3] and len(m[3]) == 1: msec *= 100

										total_ms = (minutes * 60 + seconds) * 1000 + msec
										self.sync_lyrics.append((total_ms, pure_text))

							if self.sync_lyrics:
								self.sync_lyrics.sort()
								lyrics_text = "\n".join([item[1] for item in self.sync_lyrics])
					except Exception as e:
						print(f"Error reading external lyric file: {e}")

			if not lyrics_text:
				self.statusBar().showMessage("No lyrics found in metadata or directory", 5000)
			else:
				# Clean up timestamps from raw text if we aren't using sync
				if not self.sync_lyrics:
					import re
					lyrics_text = re.sub(r'\[\d{2,}:\d{2}[.:]\d{2,}\]', '', lyrics_text)

				# Format and show lyrics
				self.lyrics_view.setPlainText(lyrics_text.strip())
				self.lyrics_view.selectAll()
				self.lyrics_view.setAlignment(Qt.AlignmentFlag.AlignCenter)

				# If sync lyrics, set initial inactive color
				if self.sync_lyrics:
					from PyQt6.QtGui import QTextCharFormat
					inactive_color = QColor("#555555") if self.dark_mode else QColor("#aaaaaa")
					fmt = QTextCharFormat()
					fmt.setForeground(inactive_color)
					self.lyrics_view.textCursor().setCharFormat(fmt)

				# Deselect and scroll to top
				cursor = self.lyrics_view.textCursor()
				cursor.clearSelection()
				cursor.movePosition(cursor.MoveOperation.Start)
				self.lyrics_view.setTextCursor(cursor)

				self.content_stack.setCurrentIndex(1)

		except Exception as e:
			import traceback
			traceback.print_exc()
			print(f"Error checking for lyrics: {e}")
			self.statusBar().showMessage("Error reading lyrics")

	def search_library(self):
		self.search_dialog = SearchDialog(self.library, self)
		self.search_dialog.result_selected.connect(self.handle_search_selection)
		self.search_dialog.show()

	def handle_search_selection(self, data):
		# Navigate to the selected item in the library
		# We use "All Genres" as a safe starting point for search results
		genre = "All Genres"
		artist = None
		album = None
		song = None

		if data['type'] == 'artist':
			artist = data['artist']
			album = "All Albums"
		elif data['type'] == 'album':
			artist = data['artist']
			album = data['album']
		elif data['type'] == 'song':
			artist = data['song']['artist']
			album = data['song']['album']
			song = data['song']

		# Use restore_selection to navigate the trees and populate the table
		self.restore_selection(genre, artist, album, song)

	def toggle_theme(self):
		# Take a screenshot before switching for cross-fade animation
		pixmap = self.grab()

		# Create an overlay label to show the old theme
		overlay = QLabel(self)
		overlay.setPixmap(pixmap)
		overlay.setGeometry(0, 0, self.width(), self.height())
		overlay.show()

		self.dark_mode = not self.dark_mode
		icon_color = 'white' if self.dark_mode else 'black'

		# Reload all button icons with new color
		self.add_folder_btn.setIcon(self.load_icon('add-folder.svg', icon_color))
		self.rescan_btn.setIcon(self.load_icon('rescan.svg', icon_color))
		self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg' if self.remember_position else 'bookmark-off.svg', icon_color))
		self.show_album_art_btn.setIcon(self.load_icon('album-art.svg', icon_color))
		self.lyrics_btn.setIcon(self.load_icon('lyrics.svg', icon_color))
		self.search_btn.setIcon(self.load_icon('search.svg', icon_color))
		self.accent_btn.setIcon(self.load_icon('paint.svg', icon_color))

		# Update theme toggle button icon
		theme_icon = 'mode-dark.svg' if self.dark_mode else 'mode-light.svg'
		self.darkmode_btn.setIcon(self.load_icon(theme_icon, icon_color))

		# Update shrink/expand button icon
		shrink_icon = 'expand.svg' if self.is_shrunk else 'shrink.svg'
		self.shrink_expand_btn.setIcon(self.load_icon(shrink_icon, icon_color))

		self.prev_btn.setIcon(self.load_icon('previous.svg', icon_color))
		self.next_btn.setIcon(self.load_icon('next.svg', icon_color))
		# self.stop_btn.setIcon(self.load_icon('stop.svg', icon_color))

		# Update play/pause button based on current state
		if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.play_btn.setIcon(self.load_icon('pause.svg', icon_color))
		else:
			self.play_btn.setIcon(self.load_icon('play.svg', icon_color))

		# Update volume/mute button
		if self.is_muted or self.volume_slider.value() == 0:
			self.mute_btn.setIcon(self.load_icon('volume-mute.svg', icon_color))
		else:
			self.mute_btn.setIcon(self.load_icon('volume.svg', icon_color))

		# Update repeat button based on mode
		if self.repeat_mode == 0:
			self.repeat_btn.setIcon(self.load_icon('repeat-off.svg', icon_color))
		elif self.repeat_mode == 1:
			self.repeat_btn.setIcon(self.load_icon('repeat-song.svg', icon_color))
		elif self.repeat_mode == 2:
			self.repeat_btn.setIcon(self.load_icon('repeat-album.svg', icon_color))

		# Update shuffle button
		if self.shuffle_enabled:
			self.shuffle_btn.setIcon(self.load_icon('shuffle-on.svg', icon_color))
		else:
			self.shuffle_btn.setIcon(self.load_icon('shuffle-off.svg', icon_color))

		# Apply color scheme
		self.apply_theme()

		# Setup and start fade animation
		opacity_effect = QGraphicsOpacityEffect(overlay)
		overlay.setGraphicsEffect(opacity_effect)

		self.theme_anim = QPropertyAnimation(opacity_effect, b"opacity")
		self.theme_anim.setDuration(400) # 400ms cross-fade
		self.theme_anim.setStartValue(1.0)
		self.theme_anim.setEndValue(0.0)
		self.theme_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
		self.theme_anim.finished.connect(overlay.deleteLater)
		self.theme_anim.start()

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
				outline: 0;
			}}
			QTreeWidget::item:selected {{
				background-color: {selection_bg};
				outline: none;
				border: none;
			}}
			QTableWidget {{
				background-color: {secondary_bg};
				color: {text_color};
				border: 1px solid {border_color};
				gridline-color: {border_color};
				outline: 0;
			}}
			QTableWidget::item:selected {{
				background-color: {selection_bg};
				outline: none;
				border: none;
			}}
			QTextEdit {{
				background-color: {bg_color};
				color: {text_color};
				border: none;
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

	def on_progress_slider_wheeled(self, delta):
		# Scrub 5 seconds per wheel notch
		scrub_amount = 5000  # 5 seconds in milliseconds
		current_pos = self.player.position()
		duration = self.player.duration()

		if duration > 0:
			if delta > 0:
				new_pos = min(current_pos + scrub_amount, duration)
			else:
				new_pos = max(current_pos - scrub_amount, 0)

			self.player.setPosition(new_pos)
			# Update slider immediately for feedback
			self.progress_slider.setValue(int((new_pos / duration) * 1000))

	def toggle_shuffle(self):
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
		def get_sort_key(song):
			# Handle both new dict format and old path format
			if isinstance(song, dict):
				track_num_raw = song.get('tracknumber', '9999')
				title = song.get('title', Path(song['path']).stem)
				path = song['path']
			else:
				# Fallback for old library format during transition
				return (9999, Path(song).stem.lower())

			try:
				# Handle "1/12" format
				track_num_str = str(track_num_raw).strip()
				if '/' in track_num_str:
					track_num = track_num_str.split('/')[0]
				else:
					track_num = track_num_str

				try:
					track_num = int(track_num)
					if track_num == 0:
						track_num = 9999
				except:
					track_num = 9999  # Put tracks without numbers at the end

				return (track_num, title.lower())
			except:
				return (9999, Path(path).stem.lower())

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
				self.remember_position_btn.setIcon(self.load_icon('bookmark-on.svg', icon_color))
				self.remember_position_btn.setToolTip("Remember playback position (On)")
			else:
				self.remember_position_btn.setIcon(self.load_icon('bookmark-off.svg', icon_color))
				self.remember_position_btn.setToolTip("Remember playback position (Off)")
				# Clear saved position when disabled
				if self.playback_position_file.exists():
					self.playback_position_file.unlink()

			self.save_settings()

	def toggle_album_art(self):
		if hasattr(self, 'art_anim') and self.art_anim.state() == QVariantAnimation.State.Running:
			return

		self.show_album_art = not self.show_album_art

		total_width = self.horizontal_splitter.width()
		start_sizes = self.horizontal_splitter.sizes()

		if self.show_album_art:
			self.album_art_label.show()
			self.update_album_art()
			# Target: 4 equal columns
			equal_width = total_width // 4
			end_sizes = [equal_width] * 4
			easing = QEasingCurve.Type.OutQuad
		else:
			# Target: 3 equal columns, 4th is 0
			equal_width = total_width // 3
			end_sizes = [equal_width, equal_width, equal_width, 0]
			easing = QEasingCurve.Type.InQuad

		self.art_anim = QVariantAnimation(self)
		self.art_anim.setDuration(350)
		self.art_anim.setStartValue(0.0)
		self.art_anim.setEndValue(1.0)
		self.art_anim.setEasingCurve(easing)

		def animate_splitter(progress):
			current_sizes = []
			for start, end in zip(start_sizes, end_sizes):
				current_sizes.append(int(start + (end - start) * progress))
			self.horizontal_splitter.setSizes(current_sizes)

		self.art_anim.valueChanged.connect(animate_splitter)

		if not self.show_album_art:
			self.art_anim.finished.connect(self.album_art_label.hide)

		self.art_anim.start()
		self.save_settings()

	def restore_playback_position(self):
		if not self.remember_position or not self.playback_position_file.exists():
			return

		# If we already have a playlist (from restore_selection), we might just want to seek
		# but if we're restoring the WHOLE state from playback_position.json, we do it here.

		try:
			with open(self.playback_position_file, 'r') as f:
				position_data = json.load(f)

			song_data = position_data.get('song_path')
			position = position_data.get('position', 0)
			playlist = position_data.get('playlist', [])
			track_index = position_data.get('track_index', 0)

			# Extract actual path if it's stored as a dict or string
			actual_path = song_data['path'] if isinstance(song_data, dict) else song_data

			# Verify the song still exists
			if actual_path and Path(actual_path).exists():
				# If we don't have a playlist yet, or it's different, restore it
				if not self.current_playlist or len(self.current_playlist) != len(playlist):
					self.current_playlist = playlist
					self.current_track_index = track_index
					self.populate_song_table_from_playlist()

				self.highlight_current_song()

				# Store the position to restore after media loads
				self._pending_seek_position = position

				# Connect to mediaStatusChanged to seek after loading
				def on_media_loaded(status):
					from PyQt6.QtMultimedia import QMediaPlayer
					if status == QMediaPlayer.MediaStatus.LoadedMedia and hasattr(self, '_pending_seek_position'):
						# Delay seek slightly to ensure player is ready
						from PyQt6.QtCore import QTimer
						QTimer.singleShot(100, lambda: self._finish_restore())
						# Disconnect this handler
						self.player.mediaStatusChanged.disconnect(on_media_loaded)

				self.player.mediaStatusChanged.connect(on_media_loaded)

				# Load the song
				self.is_restoring = True
				self.player.setSource(QUrl.fromLocalFile(actual_path))

				# Update UI Now Playing
				found_metadata = False
				for song in self.current_playlist:
					s_path = song['path'] if isinstance(song, dict) else song
					if s_path == actual_path:
						artist = song.get('artist', 'Unknown Artist') if isinstance(song, dict) else 'Unknown Artist'
						title = song.get('title', Path(actual_path).stem) if isinstance(song, dict) else Path(actual_path).stem
						self.now_playing_text.setText(f"{artist} - {title}")
						found_metadata = True
						break

				if not found_metadata:
					self.now_playing_text.setText(Path(actual_path).stem)

				if self.show_album_art:
					self.update_album_art()

				print(f"Restoring playback position: {position/1000:.1f}s")
			else:
				print(f"DEBUG - Song path doesn't exist or is empty: {actual_path}")

		except Exception as e:
			self.is_restoring = False
			print(f"Error restoring playback position: {e}")
			import traceback
			traceback.print_exc()

	def _finish_restore(self):
		if hasattr(self, '_pending_seek_position'):
			print(f"Seeking to {self._pending_seek_position}ms")
			self.player.setPosition(self._pending_seek_position)
			delattr(self, '_pending_seek_position')

		# Give it a moment before allowing normal status changes to process EndOfMedia
		from PyQt6.QtCore import QTimer
		QTimer.singleShot(500, self._clear_restoring_flag)

	def _clear_restoring_flag(self):
		self.is_restoring = False
		print("Restoration complete")

	def shrink_and_expand(self):
		self.is_shrunk = not self.is_shrunk
		icon_color = 'white' if self.dark_mode else 'black'

		if self.is_shrunk:
			# Shrinking to mini-player
			self.expanded_geometry = self.geometry()

			# Hide non-essential sections
			self.content_stack.hide()
			self.right_container.hide()
			self.now_playing_label.hide()
			self.statusBar().hide()

			# Hide all buttons in left section EXCEPT shrink/expand
			self.add_folder_btn.hide()
			self.rescan_btn.hide()
			self.remember_position_btn.hide()
			self.show_album_art_btn.hide()
			self.darkmode_btn.hide()
			self.accent_btn.hide()

			# Remove minimum width constraint temporarily
			self.left_container.setMinimumWidth(0)

			# Adjust progress slider width for mini mode
			self.progress_slider.setMinimumWidth(200)
			self.progress_slider.setMaximumWidth(350)

			# Adjust play button size for mini mode
			self.play_btn.setIconSize(QSize(20, 20))

			# Set fixed size for mini mode
			self.setFixedSize(400, 107)

			self.shrink_expand_btn.setIcon(self.load_icon('expand.svg', icon_color))
			self.shrink_expand_btn.setToolTip("Expand the Interface")
		else:
			# Expanding to full view
			self.setMinimumSize(400, 400)
			self.setMaximumSize(16777215, 16777215)

			# Show all sections
			self.content_stack.show()
			self.right_container.show()
			self.now_playing_label.show()
			self.statusBar().show()

			# Show all buttons in left section
			self.add_folder_btn.show()
			self.rescan_btn.show()
			self.remember_position_btn.show()
			self.show_album_art_btn.show()
			self.darkmode_btn.show()
			self.accent_btn.show()

			# Restore minimum width constraint
			self.left_container.setMinimumWidth(200)

			# Restore progress slider width
			self.progress_slider.setMinimumWidth(600)
			self.progress_slider.setMaximumWidth(950)

			# Restore play button size
			self.play_btn.setIconSize(QSize(36, 36))

			self.shrink_expand_btn.setIcon(self.load_icon('shrink.svg', icon_color))
			self.shrink_expand_btn.setToolTip("Shrink the Interface")

			if self.expanded_geometry:
				self.setGeometry(self.expanded_geometry)
			else:
				self.resize(1200, 720)
		self.save_settings()

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

	# Load and set default font
	font_path = Path(__file__).parent.resolve() / 'fonts' / 'SauceCodeProNerdFont-Regular.ttf'
	font_id = QFontDatabase.addApplicationFont(str(font_path))

	if font_id != -1:
		font_families = QFontDatabase.applicationFontFamilies(font_id)
		if font_families:
			font = QFont(font_families[0], 10)
			app.setFont(font)
		else:
			# Fallback if font loaded but family not found
			font = app.font()
			font.setPointSize(10)
			app.setFont(font)
	else:
		print(f"Warning: Could not load font from {font_path}")
		font = app.font()
		font.setPointSize(10)
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