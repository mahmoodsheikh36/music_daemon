import sounddevice
import subprocess
import threading

from music_daemon.music import Song
from music_daemon.utils import current_time
from music_daemon.db import DBProvider

CHUNK = 1024    # number of bytes to read on each iteration
SAMPLE_SIZE = 2 # each sample is 2 bytes (-f s16le with ffmpeg)

class AudioTask():
    def __init__(self):
        self.running = True

    def terminate(self):
        self.running = False

    def run(self, url, sample_rate, channels, initial_position,
            on_progress, on_complete):
        # idk why but some audio files at 96k become distorted, temporary fix
        if sample_rate > 48000:
            sample_rate = 48000
        ffmpeg_stream = subprocess.Popen(["ffmpeg", "-ss", str(initial_position),
                                 "-i", url, "-loglevel", "panic", "-vn",
                                 "-f", "s16le", "-acodec", "pcm_s16le", "-ar",
                                  str(sample_rate), "pipe:1"],
                                  stdout=subprocess.PIPE)

        audio_stream = sounddevice.RawOutputStream(samplerate=sample_rate,
                                                   channels=channels,
                                                   dtype='int16')

        audio_stream.start()

        data = ffmpeg_stream.stdout.read(CHUNK)

        progress = initial_position
        while self.running and len(data) > 0:
            audio_stream.write(data)
            increase_in_progress =\
                len(data) / SAMPLE_SIZE / channels / sample_rate
            progress = progress + increase_in_progress
            if self.running:
                on_progress(progress)
            data = ffmpeg_stream.stdout.read(CHUNK)

        audio_stream.close()
        ffmpeg_stream.terminate()
        if self.running:
            on_complete()

class MusicPlayer:
    def __init__(self):
        self.song_queue = []
        self.ended_song_queue = []
        self.audio_task = None
        self.audio_task_thread = None
        self.music_monitor = MusicMonitor(self, DBProvider())
        self.progress = None
        self.playing = False

    def play_album(self, album):
        self.song_queue.clear()
        self.ended_song_queue.clear()
        self.play(album.songs[0])
        for song in album.songs[1:]:
            self.add_to_queue(song)

    def play_clear_queue(self, song):
        self.song_queue.clear()
        self.ended_song_queue.clear()
        self.play(song)

    def play(self, song, initial_progress=0, resumed=False):
        if self.song_queue:
            self.ended_song_queue.append(self.song_queue.pop())
        self.song_queue.append(song)
        self.play_url(song.audio_url, song.sample_rate,
                      song.channels, initial_progress)
        self.playing = True
        if not resumed:
            self.music_monitor.on_play()

    def add_to_queue(self, song):
        was_empty = not self.song_queue
        self.song_queue.insert(0, song)
        if was_empty:
            self.play_url(song.audio_url, song.sample_rate, song.channels, 0)
            self.playing = True
            self.music_monitor.on_play()

    def clear_queue(self):
        current_song = self.current_song()
        self.song_queue.clear()
        self.ended_song_queue.clear()
        self.song_queue.append(current_song)

    def pause(self):
        if not self.playing:
            return
        self.terminate_audio_task()
        self.music_monitor.on_pause()
        self.playing = False

    def resume(self):
        if self.playing or self.current_song() is None:
            return
        self.play(self.current_song(), self.progress, resumed=True)
        self.music_monitor.on_resume()
        self.playing = True

    def seek(self, position_in_seconds):
        if not self.current_song():
            return
        self.play_url(self.current_song().audio_url,
                      self.current_song().sample_rate,
                      self.current_song().channels,
                      position_in_seconds)
        self.music_monitor.on_seek()

    def play_url(self, url, sample_rate, channels, initial_position=0):
        self.progress = initial_position
        self.start_audio_task(url, sample_rate, channels, initial_position)

    def start_audio_task(self, url, sample_rate, channels, initial_position):
        self.terminate_audio_task()
        self.audio_task = AudioTask()
        t = threading.Thread(target = self.audio_task.run,
                             args = (url, sample_rate, channels,
                                     initial_position,
                                     self.on_audio_task_progress,
                                     self.on_song_complete))
        t.start()
        self.audio_task_thread = t

    def on_audio_task_progress(self, progress):
        self.progress = progress

    def terminate_audio_task(self):
        if self.audio_task:
            self.audio_task.terminate()
            """
            if we arent terminating from main thread then we are terminating
            from the same thread that called this function and therefore
            calling audio_task_thread.join() would throw an error
            so we only call join() when terminating from main thread
            """
            if threading.current_thread() is threading.main_thread():
                self.audio_task_thread.join()

    def terminate(self):
        print('terminating player')
        self.terminate_audio_task()
        self.music_monitor.terminate()

    def on_song_complete(self):
        self.skip_to_next()

    def skip_to_next(self):
        if not self.song_queue:
            return
        self.ended_song_queue.insert(0, self.song_queue.pop())
        if not self.song_queue:
            self.song_queue.append(self.ended_song_queue.pop())
        self.play_url(self.song_queue[-1].audio_url,
                      self.song_queue[-1].sample_rate,
                      self.song_queue[-1].channels)
        self.playing = True
        self.music_monitor.on_skip()

    def skip_to_prev(self):
        if not self.ended_song_queue:
            return
        song_to_play = self.ended_song_queue[0]
        self.ended_song_queue[0] = self.song_queue.pop()
        self.song_queue.append(song_to_play)
        self.play_url(self.song_queue[-1].audio_url,
                      self.song_queue[-1].sample_rate,
                      self.song_queue[-1].channels)
        self.playing = True
        self.music_monitor.on_skip()

    def current_song(self):
        if self.song_queue:
            return self.song_queue[-1]
        return None

class MusicMonitor:
    def __init__(self, music_player, db_provider):
        self.music_player = music_player
        self.db_provider = db_provider
        self.playback = None

    def on_play(self):
        song_id = self.music_player.current_song().id
        now = current_time()
        self.update_current_playback_time_ended(now)
        playback_time_started = now
        playback_time_ended = -1
        playback_id = self.db_provider.add_playback(playback_time_started,
                                                    playback_time_ended,
                                                    song_id)
        self.playback = {'time_started': playback_time_started,
                         'time_ended': playback_time_ended,
                         'id': playback_id}

    def update_current_playback_time_ended(self, time_ended):
        if self.playback:
            self.db_provider.update_playback_time_ended(self.playback['id'],
                                                        time_ended)

    def terminate(self):
        self.update_current_playback_time_ended(current_time())

    def on_skip(self):
        self.on_play()

    def on_pause(self):
        self.db_provider.add_pause(current_time(), self.playback['id'])

    def on_resume(self):
        self.db_provider.add_resume(current_time(), self.playback['id'])

    def on_seek(self):
        self.db_provider.add_seek(current_time(),
                                  self.music_player.progress,
                                  self.playback['id'])