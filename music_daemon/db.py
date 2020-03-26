import sqlite3
import os.path
import os
import psutil
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor 

from music_daemon.ffmpeg import get_audio_format
from music_daemon.music import Song, Album, Artist
from music_daemon.utils import current_time

lock = threading.Lock()
AUDIO_FILE_EXTENSIONS = ['mp3', 'flac', 'opus', 'm4a']

def get_cache_dir():
    path = str(Path.home()) + '/.cache/music_daemon/'
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def get_db_path():
    return get_cache_dir() + 'music.db'

def get_schema_buffer():
    project_directory_path = os.path.realpath(
                os.path.join(os.getcwd(), os.path.dirname(__file__)))
    with open(os.path.join(project_directory_path, 'schema.sql')) as schema_file:
        return schema_file.read()

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class DBProvider:
    def __init__(self, db_path=get_cache_dir()+'music.db'):
        self.path = db_path
        should_create_db = False
        if not Path(self.path).is_file():
            should_create_db = True
        self.conn = self.get_new_conn()
        if should_create_db:
            self.create_db()

    def create_db(self):
        self.conn.executescript(get_schema_buffer())

    def cursor(self):
        return self.conn.cursor()

    def add_song(self, name, audio_url, duration):
        c = self.cursor()
        c.execute('INSERT INTO songs\
                   (name, audio_url, duration, time)\
                   VALUES (?, ?, ?, ?)',
                   (name, audio_url, duration, current_time()))
        self.commit()
        return c.lastrowid

    def add_song_artist(self, song_id, artist_id):
        c = self.cursor()
        c.execute('INSERT INTO song_artists\
                   (artist_id, song_id)\
                   VALUES (?, ?)',
                   (artist_id, song_id))

    def add_album_artist(self, album_id, artist_id):
        c = self.cursor()
        c.execute('INSERT INTO album_artists\
                   (artist_id, album_id)\
                   VALUES (?, ?)',
                   (artist_id, album_id))

    def add_album_song(self, song_id, album_id, index_in_album):
        c = self.cursor()
        c.execute('INSERT INTO album_songs\
                   (song_id, album_id, index_in_album)\
                   VALUES (?, ?, ?)',
                   (song_id, album_id, index_in_album))

    def add_single_song(self, row_id, song_id, image_file_id, year, time_added):
        c = self.cursor()
        c.execute('INSERT INTO single_songs\
                   (id, song_id, image_file_id, year, time_added)\
                   VALUES (?, ?, ?, ?, ?)',
                   (row_id, song_id, image_file_id, year, time_added))

    def add_album(self, name, year):
        c = self.cursor()
        c.execute('INSERT INTO albums\
                   (name, year, time)\
                   VALUES (?, ?, ?)',
                   (name, year, current_time()))
        self.commit()
        return c.lastrowid

    def add_artist(self, name):
        c = self.cursor()
        c.execute('INSERT INTO artists\
                   (name, time)\
                   VALUES (?, ?)',
                   (name, current_time()))
        self.commit()
        return c.lastrowid

    def add_artist_image(self, row_id, artist_id, image_file_id):
        c = self.cursor()
        c.execute('INSERT INTO artist_images\
                   (id, image_file_id, artist_id)\
                   VALUES (?, ?, ?)',
                   (row_id, image_file_id, artist_id))

    def add_liked_song(self, song_id):
        c = self.cursor()
        c.execute('INSERT INTO liked_songs\
                   (song_id, time)\
                   VALUES (?, ?)',
                   (song_id, current_time()))

    def add_playback(self, time_started, time_ended, song_id):
        c = self.cursor()
        c.execute('INSERT INTO playbacks\
                   (time_started, time_ended, song_id)\
                   VALUES (?, ?, ?)',
                  (time_started, time_ended, song_id))
        # i guess gotta commit to get the lastrowid since we need it
        self.conn.commit()
        return c.lastrowid

    def add_pause(self, time, playback_id):
        # see note for update_playback_time_ended function
        conn = self.get_new_conn()
        c = conn.cursor()
        c.execute('INSERT INTO pauses\
                   (time, playback_id)\
                   VALUES (?, ?)',
                  (time, playback_id))
        conn.commit()

    def add_resume(self, time, playback_id):
        # see note for update_playback_time_ended function
        conn = self.get_new_conn()
        c = conn.cursor()
        c.execute('INSERT INTO resumes\
                   (time, playback_id)\
                   VALUES (?, ?)',
                  (time, playback_id))
        conn.commit()

    def add_seek(self, time, position, playback_id):
        # see note for update_playback_time_ended function
        conn = self.get_new_conn()
        c = conn.cursor()
        c.execute('INSERT INTO seeks\
                   (time, position, playback_id)\
                   VALUES (?, ?, ?)',
                  (time, position, playback_id))
        conn.commit()

    def get_playbacks(self, song_id):
        c = self.cursor()
        return c.execute('SELECT * FROM playbacks WHERE song_id = ?',
                         (song_id,)).fetchall()

    def get_pauses(self, playback_id):
        c = self.cursor()
        return c.execute('SELECT * FROM pauses WHERE playback_id = ?',
                         (playback_id,)).fetchall()

    def get_resumes(self, playback_id):
        c = self.cursor()
        return c.execute('SELECT * FROM resumes WHERE playback_id = ?',
                         (playback_id,)).fetchall()

    def get_seeks(self, playback_id):
        c = self.cursor()
        return c.execute('SELECT * FROM seeks WHERE playback_id = ?',
                         (playback_id,)).fetchall()

    def get_new_conn(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = dict_factory
        return conn

    """
    always use a new connection when updating playbacks because this
    function is only run from a seperate thread (the AudioTask thread)
    and sqlite3 connections can only be used from the thread they
    were created in
    same goes for add_seek, add_pause, add_resume functions
    """
    def update_playback_time_ended(self, playback_id, time_ended):
        conn = self.get_new_conn()
        c = conn.cursor()
        c.execute('UPDATE playbacks SET\
                   time_ended = ?\
                   WHERE id = ?',
                  (time_ended, playback_id))
        conn.commit()

    def get_artist(self, artist_id):
        c = self.cursor()
        return c.execute('SELECT * FROM artists WHERE id = ?',
                         (artist_id,)).fetchone()

    def get_album(self, album_id):
        c = self.cursor()
        return c.execute('SELECT * FROM albums WHERE id = ?',
                         (album_id,)).fetchone()

    def get_artist_by_name(self, artist_name):
        return self.cursor().execute('SELECT * FROM artists WHERE name = ?',
                                     (artist_name,)).fetchone()

    def get_album_by_name(self, album_name, artist_id):
        return self.cursor().execute('SELECT * FROM albums WHERE name = ? AND\
                                      id IN (select album_id from album_artists\
                                      WHERE artist_id = ?)',
                                     (album_name, artist_id)).fetchone()

    def get_song_by_url(self, url):
        return self.cursor().execute('SELECT * FROM songs WHERE audio_url = ?',
                                     (url,)).fetchone()

    def get_songs(self):
        return self.cursor().execute('SELECT * FROM songs').fetchall()

    def get_artists(self):
        return self.cursor().execute('SELECT * FROM artists').fetchall()

    def get_albums(self):
        return self.cursor().execute('SELECT * FROM albums').fetchall()

    def get_album_artists(self):
        return self.cursor().execute('SELECT * FROM album_artists').fetchall()

    def get_song_artists(self):
        return self.cursor().execute('SELECT * FROM song_artists').fetchall()

    def get_album_songs(self):
        return self.cursor().execute('SELECT * FROM album_songs').fetchall()

    def is_song_liked(self, song_id):
        return self.cursor().execute('SELECT * FROM liked_songs\
                                      WHERE song_id = ?', (song_id,)) is not None

    def commit(self):
        self.conn.commit()

class MusicProvider:
    def __init__(self, music_dir):
        self.dir = music_dir
        self.db_provider = DBProvider()
        self.songs = {}
        self.albums = {}
        self.singles = {}
        self.artists = {}

    def load_music(self):
        db_songs = self.db_provider.get_songs()
        db_artists = self.db_provider.get_artists()
        db_albums = self.db_provider.get_albums()
        db_song_artists = self.db_provider.get_song_artists()
        db_album_artists = self.db_provider.get_album_artists()
        db_album_songs = self.db_provider.get_album_songs()

        for db_artist in db_artists:
            artist = Artist(db_artist['id'], db_artist['name'], [], [])
            self.artists[artist.id] = artist

        for db_song in db_songs:
            song = Song(db_song['id'], db_song['audio_url'], db_song['name'],
                        [], db_song['duration'])
            self.songs[song.id] = song

        for db_album in db_albums:
            album = Album(db_album['id'], db_album['name'], [],
                          [], db_album['year'])
            self.albums[album.id] = album

        for db_album_artist in db_album_artists:
            album_id = db_album_artist['album_id']
            artist_id = db_album_artist['artist_id']
            self.artists[artist_id].albums.append(self.albums[album_id])
            self.albums[album_id].artists.append(self.artists[artist_id])

        for db_song_artist in db_song_artists:
            song_id = db_song_artist['song_id']
            artist_id = db_song_artist['artist_id']
            self.songs[song_id].artists.append(self.artists[artist_id])

        for db_album_song in db_album_songs:
            song_id = db_album_song['song_id']
            album_id = db_album_song['album_id']
            self.albums[album_id].songs.append(self.songs[song_id])
            self.songs[song_id].album = self.albums[album_id]

    def on_audio_file_found(self, filepath):
        print(filepath)
        audio_format = get_audio_format(filepath)
        if not 'tags' in audio_format:
            return
        tags = audio_format['tags']
        if not 'artist' in tags or not 'title' in tags:
            return

        artist_name = tags['artist']
        song_name = tags['title']

        lock.acquire()
        db_artist = self.db_provider.get_artist_by_name(artist_name)
        if db_artist is None:
            print('adding artist {}'.format(artist_name))
            self.db_provider.add_artist(artist_name)
            db_artist = self.db_provider.get_artist_by_name(artist_name)

        if 'album' in tags:
            album_name = tags['album']
            album_year = None
            if 'year' in tags:
                album_year = tags['year']
            db_album = self.db_provider.get_album_by_name(album_name,
                                                          db_artist['id'])
            album_id = None
            if db_album is None:
                album_id = self.db_provider.add_album(album_name, album_year)
                self.db_provider.add_album_artist(album_id, db_artist['id'])
                self.db_provider.commit()
                print('added album {}'.format(album_name))
            else:
                album_id = db_album['id']
            idx_in_album = None
            if 'track' in tags:
                idx_in_album = tags['track']
            if idx_in_album is not None:
                idx_in_album = idx_in_album.split('/')[0]
            song_id = self.db_provider.add_song(song_name, filepath, audio_format['duration'])
            self.db_provider.add_song_artist(song_id, db_artist['id'])
            self.db_provider.add_album_song(song_id, album_id, idx_in_album)
        else:
            print('adding single {}'.format(song_name))
        lock.release()

    def find_music(self):
        with ThreadPoolExecutor(max_workers=psutil.cpu_count()) as executor:
            for folder, subs, files in os.walk(self.dir):
                for filename in files:
                    is_audio_file = False
                    for audio_ext in AUDIO_FILE_EXTENSIONS:
                        if filename.endswith('.' + audio_ext):
                            is_audio_file = True
                    if not is_audio_file:
                        continue
                    filepath = os.path.join(folder, filename)
                    if self.db_provider.get_song_by_url(filepath) is None:
                        executor.submit(self.on_audio_file_found, filepath)
        self.db_provider.commit()

    def get_seconds_listened_to_song(self, song_id):
        playbacks = self.db_provider.get_playbacks(song_id)
        total_milliseconds = 0
        for playback in playbacks:
            if playback['time_ended'] == -1:
                continue
            pauses = self.db_provider.get_pauses(playback['id'])
            resumes = self.db_provider.get_resumes(playback['id'])
            if abs(len(pauses) - len(resumes)) > 1:
                continue
            milliseconds = playback['time_ended'] - playback['time_started']
            for i in range(len(resumes)):
                pause = pauses[i]
                resume = resumes[i]
                milliseconds -= resume['time'] - pause['time']
            if len(pauses) > len(resumes):
                milliseconds -= playback['time_ended'] - pauses[-1]['time']
            total_milliseconds += milliseconds
        return total_milliseconds / 1000

    def get_songs_list(self):
        return list(self.songs.values())

    def get_albums_list(self):
        return list(self.albums.values())

    def like_song(self, song):
        if self.db_provider.is_song_liked(song.id):
            return
        self.db_provider.add_liked_song(song.id)
        self.db_provider.commit()
        song.is_liked = True
