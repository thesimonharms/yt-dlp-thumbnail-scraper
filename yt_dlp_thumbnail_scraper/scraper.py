"""Core scraper logic: wraps yt-dlp to fetch thumbnails only."""

from __future__ import annotations

import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Iterable

import yt_dlp


VIDEO_URL_RE = re.compile(r'(?:watch\?v=|youtu\.be/|embed/|shorts/)[A-Za-z0-9_-]{6,}')
CHANNEL_URL_RE = re.compile(
    r'youtube\.com/(?:@[\w.\-]+|channel/[A-Za-z0-9_-]+|user/[A-Za-z0-9_-]+|c/[A-Za-z0-9_-]+)'
)
PLAYLIST_URL_RE = re.compile(r'youtube\.com/playlist\?list=')

# Thumbnails with the highest resolution usually have these preference prefixes
# (yt-dlp returns them ordered, but we keep a sensible fallback preference list).
PREFERRED_IDS = ('maxresdefault', 'sddefault', 'hqdefault', 'mqdefault', 'default')

# YouTube serves a tiny gray placeholder (≈1-2 KB) with HTTP 200 when a
# thumbnail variant does not actually exist for the video. Anything below this
# size is treated as a placeholder and we fall back to the next candidate.
MIN_USEFUL_BYTES = 2050


def _log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, file=sys.stderr, flush=True)


def _safe_name(name: str, fallback: str) -> str:
    name = (name or '').strip()
    if not name:
        return fallback
    # Remove characters that are illegal on Windows/most filesystems
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)


class ThumbnailScraper:
    """Download thumbnails for a YouTube video, channel, or playlist."""

    def __init__(
        self,
        out_dir: str | Path = 'thumbnails',
        all_thumbnails: bool = False,
        skip_existing: bool = True,
        quiet: bool = False,
        retries: int = 3,
        sleep_between: float = 0.0,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.all_thumbnails = all_thumbnails
        self.skip_existing = skip_existing
        self.quiet = quiet
        self.retries = retries
        self.sleep_between = sleep_between

    # Public API ---------------------------------------------------------

    def run(self, url: str) -> int:
        url_type = self._detect_url_type(url)
        _log(f"Detected {url_type} URL: {url}", self.quiet)

        if url_type == 'video':
            return self._process_video(url)
        return self._process_many(url)

    # Detection ----------------------------------------------------------

    def _detect_url_type(self, url: str) -> str:
        if PLAYLIST_URL_RE.search(url):
            return 'playlist'
        if VIDEO_URL_RE.search(url) and not CHANNEL_URL_RE.search(url):
            return 'video'
        if CHANNEL_URL_RE.search(url):
            return 'channel'
        return 'video'

    # Extraction --------------------------------------------------------

    def _extract_flat(self, url: str) -> dict:
        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'forcejson': False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info or {}

    def _entries(self, info: dict) -> Iterable[dict]:
        if not info:
            return []
        if info.get('_type') in ('playlist', 'multi_video'):
            return [e for e in (info.get('entries') or []) if e]
        # A single video extracted flat -> itself
        return [info]

    # Processing --------------------------------------------------------

    def _process_video(self, url: str) -> int:
        info = self._extract_flat(url)
        if not info:
            _log(f"ERROR: no info extracted for {url}", self.quiet)
            return 1
        return self._download_thumbnails(info, parent_dir=self.out_dir)

    def _process_many(self, url: str) -> int:
        info = self._extract_flat(url)
        entries = list(self._entries(info))
        if not entries:
            _log(f"ERROR: no videos found for {url}", self.quiet)
            return 1
        _log(f"Found {len(entries)} videos.", self.quiet)

        # Use channel/playlist name as root, then create dir for each.
        root_name = _safe_name(
            info.get('channel') or info.get('uploader') or info.get('title') or info.get('id') or 'thumbnails',
            fallback=str(info.get('id') or 'thumbnails'),
        )
        root_dir = self.out_dir / root_name

        total_ok = 0
        for i, entry in enumerate(entries, 1):
            vid = entry.get('id') or entry.get('url')
            if not vid:
                continue
            title = entry.get('title') or vid
            uploader = entry.get('uploader') or info.get('channel') or info.get('uploader') or 'unknown'
            uploader_name = _safe_name(uploader, 'unknown')
            video_dir = f"{_safe_name(title, vid)} [{vid}]"
            # Avoid redundant nesting (e.g. channel scraping its own channel).
            if uploader_name == root_name:
                sub_dir = root_dir / video_dir
            else:
                sub_dir = root_dir / uploader_name / video_dir
            _log(f"[{i}/{len(entries)}] {title} [{vid}]")
            total_ok += self._download_thumbnails(entry, parent_dir=sub_dir)
            if self.sleep_between:
                time.sleep(self.sleep_between)
        _log(f"Done. {total_ok} thumbnails saved under {root_dir}", self.quiet)
        return 0

    # Downloading -------------------------------------------------------

    def _pick_thumbnails(self, entry: dict) -> list[dict]:
        thumbs = entry.get('thumbnails') or []
        if not thumbs:
            # Single `thumbnail` field fallback -> wrap as one entry
            single = entry.get('thumbnail')
            if single:
                thumbs = [{'url': single}]
        if not thumbs:
            return []
        if self.all_thumbnails:
            return thumbs
        # Sort best-first: prefer higher declared width, then by id preference.
        def rank(t: dict) -> tuple:
            url = t.get('url', '')
            pref = next((i for i, pid in enumerate(PREFERRED_IDS) if pid in url), len(PREFERRED_IDS))
            return (-int(t.get('width') or 0), pref)
        return sorted(thumbs, key=rank)

    def _download_thumbnails(self, entry: dict, parent_dir: Path) -> int:
        thumbs = self._pick_thumbnails(entry)
        if not thumbs:
            _log(f"  no thumbnails available for {entry.get('id', '?')}", self.quiet)
            return 0
        parent_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        if self.all_thumbnails:
            for i, t in enumerate(thumbs):
                count += self._save_one(t, parent_dir, f"thumbnail_{i:02d}")
            return count

        # Best-one mode: try candidates best-first, accept the first non-placeholder.
        for t in thumbs:
            ok = self._save_one(t, parent_dir, 'thumbnail', require_useful=True)
            if ok:
                return 1
            # else: clean up the placeholder attempt and try next candidate
            for f in parent_dir.glob('thumbnail.*'):
                try:
                    if f.stat().st_size < MIN_USEFUL_BYTES:
                        f.unlink()
                except OSError:
                    pass
        _log(f"  no usable thumbnail for {entry.get('id', '?')}", self.quiet)
        return 0

    def _save_one(
        self, t: dict, parent_dir: Path, name: str, require_useful: bool = False
    ) -> int:
        url = t.get('url')
        if not url:
            return 0
        ext = self._ext_from_url(url)
        target = parent_dir / f"{name}.{ext}"
        if self.skip_existing and target.exists() and target.stat().st_size > 0:
            _log(f"  skip (exists): {target.name}", self.quiet)
            return 1
        if not self._download(url, target):
            return 0
        if require_useful and target.exists() and target.stat().st_size < MIN_USEFUL_BYTES:
            # Placeholder from YouTube; try next candidate.
            return 0
        try:
            rel = target.relative_to(self.out_dir)
            shown = str(rel)
        except ValueError:
            shown = str(target)
        _log(f"  saved: {shown}", self.quiet)
        return 1

    def _ext_from_url(self, url: str) -> str:
        path = url.split('?')[0].split('#')[0]
        ext = Path(path).suffix.lstrip('.')
        return ext or 'jpg'

    def _download(self, url: str, target: Path) -> bool:
        # Try multiple times; YouTube serves some thumbs only when JPEG-pinged.
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; yt-thumb-scraper/1.0)'}
        for attempt in range(1, self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                if not data:
                    raise IOError('empty response')
                target.write_bytes(data)
                return True
            except (urllib.error.URLError, urllib.error.HTTPError, IOError, OSError) as e:
                if attempt == self.retries:
                    _log(f"  failed ({e.__class__.__name__}: {e})", self.quiet)
                    return False
                time.sleep(0.5 * attempt)
        return False