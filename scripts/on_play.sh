#!/usr/bin/sh

song_id="$1"
song_path=$(md.py -r "info song $song_id url")
song_name=$(md.py -r "info song $song_id name")
artist_name=$(md.py -r "info song $song_id artist")
ffmpeg -y -i "$song_path" /tmp/song_image.jpg && {
    notify-send -i /tmp/song_image.jpg "$song_name" "$artist_name"
}
