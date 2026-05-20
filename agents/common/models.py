from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_type: str = "web_search_result"
    relevance_reason: str = ""
