# yt-dlp-thumbnail-scraper

A small command-line tool that uses [yt-dlp](https://github.com/yt-dlp/yt-dlp)
under the hood to download YouTube thumbnails — without downloading any video
data.

- Pass a **video URL** to grab that video's best thumbnail.
- Pass a **channel, `@handle`, `user/`, `c/`, `channel/`, or playlist URL** to
  walk every video and download thumbnails for all of them.
- Picks the highest-resolution thumbnail available, automatically skipping
  YouTube's gray placeholder image when `maxresdefault` is missing.
- Optional `--all` mode grabs every thumbnail variant per video.
- Resumable: existing thumbnails are skipped by default.
- Retries failed downloads and can sleep between videos to be polite to
  YouTube when scraping large channels.

## Installation

The easiest way is to install directly from GitHub with `pip`:

```bash
pip install git+https://github.com/thesimonharms/yt-dlp-thumbnail-scraper.git
```

This works in any virtualenv, conda env, or system Python, and automatically
installs `yt-dlp` as a dependency.

<details>
<summary>Other install options</summary>

#### From a specific branch / tag / commit

```bash
pip install git+https://github.com/thesimonharms/yt-dlp-thumbnail-scraper.git@v1.0.0
pip install git+https://github.com/thesimonharms/yt-dlp-thumbnail-scraper.git@main
pip install git+https://github.com/thesimonharms/yt-dlp-thumbnail-scraper.git@<commit-sha>
```

#### Clone-and-install

```bash
git clone https://github.com/thesimonharms/yt-dlp-thumbnail-scraper.git
cd yt-dlp-thumbnail-scraper
pip install .
```

#### Editable / dev install

```bash
git clone https://github.com/thesimonharms/yt-dlp-thumbnail-scraper.git
cd yt-dlp-thumbnail-scraper
pip install -e .
```

#### Upgrade an existing install

```bash
pip install --upgrade --force-reinstall git+https://github.com/thesimonharms/yt-dlp-thumbnail-scraper.git
```

</details>

After installation, the `yt-thumb` command is on your `PATH`. You can also run
it as a Python module:

```bash
python -m yt_dlp_thumbnail_scraper <url>
```

## Quick start

```bash
# Single video — saves the best thumbnail
yt-thumb https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Whole channel
yt-thumb https://www.youtube.com/@SomeChannel

# Playlist
yt-thumb "https://www.youtube.com/playlist?list=PLxxxxxxxx"
```

## Usage

### Single video

```bash
yt-thumb https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

```
thumbnails/
└── thumbnail.jpg
```

Also works with `youtu.be/`, `embed/`, and `shorts/` URLs:

```bash
yt-thumb https://youtu.be/dQw4w9WgXcQ
yt-thumb https://www.youtube.com/shorts/abcdef12345
```

### Channels

```bash
# @handle (modern)
yt-thumb https://www.youtube.com/@SomeChannel

# /channel/UCxxxxxxxx (legacy ID)
yt-thumb https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxx

# /user/Name  or  /c/Name (legacy)
yt-thumb https://www.youtube.com/user/SomeUser
yt-thumb https://www.youtube.com/c/SomeChannel
```

### Playlists

```bash
yt-thumb "https://www.youtube.com/playlist?list=PLxxxxxxxx"
```

URLs with shell metacharacters like `?` and `&` should be quoted.

### Save every thumbnail variant per video

By default only the best single thumbnail is saved per video. Use `--all` to
save every variant YouTube provides (maxres, sd, hq, mq, default, storyboards,
etc.):

```bash
yt-thumb --all https://www.youtube.com/@SomeChannel
```

### Custom output directory

```bash
yt-thumb --output ./my-thumbs https://www.youtube.com/@SomeChannel
# or short form:
yt-thumb -o ./my-thumbs https://www.youtube.com/@SomeChannel
```

### Force re-download of existing thumbnails

By default already-downloaded thumbnails are skipped. Disable with:

```bash
yt-thumb --no-skip-existing https://www.youtube.com/@SomeChannel
```

### Be polite on large channels

Sleep N seconds between videos:

```bash
yt-thumb --sleep 0.5 https://www.youtube.com/@SomeChannel
```

### Quiet mode (no progress output)

```bash
yt-thumb --quiet https://www.youtube.com/@SomeChannel
# or: yt-thumb -q ...
```

### Adjust retries

Per-thumbnail download retries (default 3):

```bash
yt-thumb --retries 5 https://www.youtube.com/@SomeChannel
```

### Combine options

```bash
yt-thumb \
  --output ./out \
  --all \
  --sleep 0.25 \
  --retries 5 \
  https://www.youtube.com/@SomeChannel
```

## Command reference

```
yt-thumb [-h] [-o OUTPUT] [-a] [--no-skip-existing] [-q]
         [--retries RETRIES] [--sleep SLEEP] [--version]
         url

positional arguments:
  url                   YouTube video, channel, or playlist URL

options:
  -h, --help            show this help message and exit
  -o, --output DIR      Output directory (default: ./thumbnails)
  -a, --all             Download every available thumbnail per video,
                        not just the best one
  --no-skip-existing    Re-download thumbnails that already exist on disk
  -q, --quiet           Suppress progress output
  --retries N           Number of download retries per thumbnail (default: 3)
  --sleep SECONDS       Seconds to sleep between videos when scraping a
                        channel (default: 0)
  --version             show program's version number and exit
```

Two console commands are installed and are identical:

- `yt-thumb` (short)
- `yt-dlp-thumbnails` (long)

Both can be invoked with the options above.

## Output layout

### Single video

```
thumbnails/
└── thumbnail.jpg
```

### Channel or playlist

```
thumbnails/
└── <channel or playlist name>/
    ├── <video title> [<video id>]/
    │   └── thumbnail.jpg
    ├── <uploader>/                  # only present for playlists mixing uploaders
    │   └── <video title> [<video id>]/
    │       └── thumbnail.jpg
    └── ...
```

With `--all`, each video directory contains multiple files:

```
<video title> [<video id>]/
├── thumbnail_00.jpg
├── thumbnail_01.webp
├── thumbnail_02.jpg
└── ...
```

## How it works

1. The tool calls `yt_dlp.YoutubeDL.extract_info(url, download=False)` with
   `extract_flat=True`, which quickly returns video IDs and their thumbnail
   URLs without downloading any media.
2. For each video the candidate thumbnails are ranked by resolution and YouTube
   id preference (`maxresdefault` > `sddefault` > `hqdefault` > `mqdefault` >
   `default`). Candidates are fetched best-first.
3. YouTube serves a tiny gray placeholder image with HTTP 200 when a higher
   resolution variant does not actually exist for a video — the scraper
   detects this (file size below ~2 KB) and automatically falls back to the
   next candidate.
4. Each thumbnail is downloaded with Python's `urllib` and written to disk.
   No video streams are ever requested.

## Uninstall

```bash
pip uninstall yt-dlp-thumbnail-scraper
```

This leaves the auto-installed `yt-dlp` dependency in place; remove it with
`pip uninstall yt-dlp` if you no longer need it.

## Requirements

- Python 3.9+
- `yt-dlp` (installed automatically as a dependency)

## License

MIT