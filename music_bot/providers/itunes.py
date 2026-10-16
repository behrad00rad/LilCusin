"""Independent public music catalogue search; metadata only, no media previews."""
from .common import TrackCandidate, request_json, items, text, number


class ITunesClient:
    def __init__(self, session):
        self.session = session

    async def search_titles(self, query):
        data = await request_json(self.session, 'https://itunes.apple.com/search',
            params={'term': query, 'entity': 'song', 'media': 'music', 'limit': 50})
        rows = []
        for raw in items(data.get('results'))[:50]:
            artist, title = text(raw.get('artistName')), text(raw.get('trackName'))
            if artist and title:
                duration = number(raw.get('trackTimeMillis'))
                rows.append(TrackCandidate(artist=artist, title=title, source='itunes',
                    album=text(raw.get('collectionName')), duration=duration / 1000 if duration else None))
        return rows

    async def search_tracks(self, artist, title):
        return await self.search_titles(artist + ' ' + title)
