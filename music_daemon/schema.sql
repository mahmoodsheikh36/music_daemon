--PRAGMA foreign_keys = OFF;
--
--CREATE TABLE songs (
--  name TEXT NOT NULL,
--  audio_file_id INTEGER NOT NULL
--  duration REAL,
--  bitrate int,
--  codec TEXT NOT NULL
--);
--
--CREATE TABLE song_artists (
--  id INTEGER PRIMARY KEY,
--  artist_id INTEGER NOT NULL,
--  song_id INTEGER NOT NULL,
--  FOREIGN KEY (artist_id) REFERENCES artists (id),
--  FOREIGN KEY (song_id) REFERENCES songs (id)
--);
--
--CREATE TABLE album_artists (
--  id INTEGER PRIMARY KEY,
--  artist_id INTEGER NOT NULL,
--  album_id INTEGER NOT NULL,
--  FOREIGN KEY (album_id) REFERENCES albums (id),
--  FOREIGN KEY (artist_id) REFERENCES artists (id)
--);
--
--CREATE TABLE album_songs (
--  id INTEGER PRIMARY KEY,
--  song_id INTEGER NOT NULL,
--  album_id INTEGER NOT NULL,
--  index_in_album int,
--  FOREIGN KEY (album_id) REFERENCES albums (id),
--  FOREIGN KEY (song_id) REFERENCES songs (id)
--);
--
--CREATE TABLE single_songs (
--  id INTEGER PRIMARY KEY,
--  song_id INTEGER NOT NULL,
--  image_file_id INTEGER NOT NULL
--  year INTEGER NOT NULL,
--  time_added int,
--  FOREIGN KEY (song_id) REFERENCES songs (id)
--);
--
--CREATE TABLE albums (
--  id INTEGER PRIMARY KEY,
--  name TEXT NOT NULL,
--  year INTEGER NOT NULL,
--  image_file_id INTEGER NOT NULL,
--  time_added int
--);
--
--CREATE TABLE artists (
--  id INTEGER PRIMARY KEY,
--  name TEXT NOT NULL
--);
--
--CREATE TABLE artist_images (
--  id INTEGER PRIMARY KEY,
--  image_file_id INTEGER NOT NULL,
--  artist_id INTEGER NOT NULL,
--  FOREIGN KEY (artist_id) REFERENCES artists (id),
--  FOREIGN KEY (image_file_id) REFERENCES image_file_id (id)
--);
--
--CREATE TABLE liked_songs (
--  id INTEGER PRIMARY KEY,
--  song_id INTEGER NOT NULL,
--  time_added int,
--  FOREIGN KEY (song_id) REFERENCES songs (id)
--);

CREATE TABLE playbacks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  time_started INTEGER NOT NULL,
  time_ended INTEGER NOT NULL,
  song_id INTEGER NOT NULL
);

CREATE TABLE pauses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  time INTEGER NOT NULL,
  playback_id INTEGER NOT NULL,
  FOREIGN KEY (playback_id) REFERENCES playbacks (id)
);

CREATE TABLE resumes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  time INTEGER NOT NULL,
  playback_id INTEGER NOT NULL,
  FOREIGN KEY (playback_id) REFERENCES playbacks (id)
);

CREATE TABLE seeks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  time INTEGER NOT NULL,
  position INTEGER NOT NULL,
  playback_id INTEGER NOT NULL,
  FOREIGN KEY (playback_id) REFERENCES playbacks (id)
);