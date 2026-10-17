"""Synthetic homepage fixture; never reads runtime feeds or contacts providers.

For manual browser checks: python3 tests/home_fixture.py /tmp/mayor-home-fixture
then serve that directory with a loopback-only HTTP server.
"""
import datetime as dt
import json
from pathlib import Path
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render import home


class HomeData:
    def __init__(self, per_city=75):
        self.generated_at = dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc)
        self.candidates = [
            {"id": city + "-fixture", "city": city, "name": home.S.city_label(city) + "測試候選人",
             "party": "", "avatarUrl": "/assets/logo.svg"}
            for city in home.S.CITY_ORDER
        ]
        self.by_id = {candidate["id"]: candidate for candidate in self.candidates}
        self.posts = {}
        for candidate in self.candidates:
            self.posts[candidate["id"]] = [
                {"id": candidate["id"] + "-" + str(i), "candidateId": candidate["id"],
                 "platform": "website" if i % 2 else "facebook", "url": "https://example.invalid/post/" + str(i),
                 "postedAt": (self.generated_at - dt.timedelta(hours=i)).isoformat(),
                 "text": "離線測試公開貼文 " + str(i) + "。" + "政策說明與來源查證，測試文字不屬於真實候選人。" * 8,
                 "imageUrl": "/assets/logo.svg", "imageAspect": 1.5, "topics": ["住宅"],
                 "postingIntent": {"type": "self_initiated", "label": "主動發文", "confidence": 0.9, "reason": "測試"}}
                for i in range(per_city)
            ]

    def all_posts(self):
        return sorted([post for posts in self.posts.values() for post in posts],
                      key=lambda post: post["postedAt"], reverse=True)

    def posts_for(self, candidate_id):
        return self.posts[candidate_id]

    def post_ctx(self, **kwargs):
        return {"by_id": self.by_id, **kwargs}


def build_fixture(directory, data=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    assets = directory / "assets"
    if not assets.exists():
        assets.symlink_to(ROOT / "site" / "assets", target_is_directory=True)
    with mock.patch.object(home.S, "SITE_ROOT", directory), \
         mock.patch.object(home, "FEED_DIR", directory / "data" / "feed"):
        home.render(data or HomeData())
    return directory / "index.html"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tests/home_fixture.py OUTPUT_DIRECTORY")
    path = build_fixture(sys.argv[1])
    print(json.dumps({"path": str(path), "decodedBytes": path.stat().st_size}))
