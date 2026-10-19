"""dub-shard.py <id> — the public release a lesson's dub lives in: dub-00 … dub-15 (2026-10-19; a release
holds at most 1,000 files, so the library is spread over 16 by the same hash as the lanes; the site
reads the same rule from its manifest)."""
import sys

h = 7
for ch in sys.argv[1]:
    h = (h * 31 + ord(ch)) & 0xFFFFFFFF
print(f'dub-{h % 16:02d}')
