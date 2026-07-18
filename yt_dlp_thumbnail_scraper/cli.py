"""Command-line interface for yt-dlp-thumbnail-scraper."""

from __future__ import annotations

import argparse
import sys

from .scraper import ThumbnailScraper
from . import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='yt-thumb',
        description=(
            'Download YouTube thumbnails. Pass a video URL to grab a single '
            'thumbnail, or a channel/playlist URL to grab thumbnails for every '
            'video in it. Powered by yt-dlp.'
        ),
    )
    p.add_argument('url', help='YouTube video, channel, or playlist URL')
    p.add_argument(
        '-o', '--output', default='thumbnails',
        help='Output directory (default: ./thumbnails)',
    )
    p.add_argument(
        '-a', '--all', action='store_true',
        help='Download every available thumbnail per video, not just the best one',
    )
    p.add_argument(
        '-f', '--flat', action='store_true',
        help=(
            'Save every thumbnail directly inside the output directory, named '
            'after the video title (no per-video subdirectories). Combine with '
            '-o . to drop them in the current directory.'
        ),
    )
    p.add_argument(
        '--template', metavar='TEMPLATE', default=None,
        help=(
            'Custom filename template in --flat mode. Implies --flat. '
            'Placeholders: {title}, {id}, {uploader}, {channel}, {playlist}, '
            '{idx}. Example: "{idx:03d} - {title}". Collisions are '
            'automatically disambiguated with the video id.'
        ),
    )
    p.add_argument(
        '--limit', type=int, default=None,
        help='Process at most N videos when scraping a channel/playlist',
    )
    p.add_argument(
        '--no-skip-existing', dest='skip_existing', action='store_false',
        help='Re-download thumbnails that already exist on disk',
    )
    p.add_argument(
        '-q', '--quiet', action='store_true',
        help='Suppress progress output',
    )
    p.add_argument(
        '--retries', type=int, default=3,
        help='Number of download retries per thumbnail (default: 3)',
    )
    p.add_argument(
        '--sleep', type=float, default=0.0,
        help='Seconds to sleep between videos when scraping a channel (default: 0)',
    )
    p.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scraper = ThumbnailScraper(
        out_dir=args.output,
        all_thumbnails=args.all,
        skip_existing=args.skip_existing,
        quiet=args.quiet,
        retries=args.retries,
        sleep_between=args.sleep,
        flat=args.flat,
        filename_template=args.template,
        limit=args.limit,
    )
    return scraper.run(args.url)


if __name__ == '__main__':
    sys.exit(main())