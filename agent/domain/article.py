from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    title: str
    feed: str
    published_at: str
    url: str
    text: str

    @property
    def metadata(self) -> str:
        return (
            f"Title: {self.title}\n"
            f"Feed: {self.feed}\n"
            f"Published: {self.published_at}\n"
            f"URL: {self.url}"
        )
