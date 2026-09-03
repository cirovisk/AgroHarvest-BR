from src.pipeline.base import BaseSource


class CacheAwareSource(BaseSource):
    def __init__(self):
        super().__init__()
        self.use_cache = True

    def extract(self, **kwargs):
        return {"use_cache": self.use_cache}

    def clean(self, raw_data):
        return raw_data

    def load(self, clean_data, lookups):
        return clean_data


def test_refresh_disables_cache_before_extract():
    source = CacheAwareSource()

    result = source.run({}, refresh=True)

    assert result == {"use_cache": False}
