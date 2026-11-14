"""Handle untitled artist carousels in ytmusicapi 1.12.3 locally.

Keep this adapter covered by the real upstream parser when upgrading ytmusicapi.
"""
from copy import copy

from .diagnostics import current_trace


def get_artist(api, browse_id):
    # Reads may run concurrently: never patch the shared client or parser.
    client = copy(api)
    parser = copy(api.parser)
    parse = parser.parse_channel_contents

    def parse_sections(results):
        filtered = []
        skipped = 0
        for row in results:
            shelf = row.get("musicCarouselShelfRenderer")
            if isinstance(shelf, dict) and "header" not in shelf:
                # Without a title this carousel cannot identify a category.
                skipped += 1
            else:
                filtered.append(row)
        trace = current_trace()
        if skipped and trace:
            trace.event("artist.untitled_carousels", count=skipped)
        return parse(filtered)

    parser.parse_channel_contents = parse_sections
    client.parser = parser
    return client.get_artist(browse_id)
