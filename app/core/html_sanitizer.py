from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse


ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "hr",
    "html",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "section",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "title",
    "tr",
    "u",
    "ul",
}

VOID_TAGS = {"br", "hr", "img"}

GLOBAL_ATTRS = {"class", "id", "title", "lang", "dir"}
TAG_ATTRS = {
    "a": {"href"},
    "img": {"src", "alt", "width", "height", "data-asset-id"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
URI_ATTRS = {"href", "src"}
ALLOWED_URI_SCHEMES = {"", "http", "https", "mailto"}
SKIP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "svg", "math", "template"}
NON_READER_TEXT_TAGS = {"head", "title"}


def sanitize_chapter_html(html: str) -> str:
    parser = _ChapterHTMLSanitizer()
    parser.feed(html)
    parser.close()
    return parser.value.strip()


def has_readable_chapter_content(html: str) -> bool:
    parser = _ReadableContentParser()
    parser.feed(html)
    parser.close()
    return parser.has_content


class _ChapterHTMLSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    @property
    def value(self) -> str:
        return "".join(self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_CONTENT_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in ALLOWED_TAGS:
            return

        rendered_attrs = self._sanitize_attrs(tag, attrs)
        suffix = f" {rendered_attrs}" if rendered_attrs else ""
        self._parts.append(f"<{tag}{suffix}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._skip_depth or tag not in ALLOWED_TAGS:
            return
        rendered_attrs = self._sanitize_attrs(tag, attrs)
        suffix = f" {rendered_attrs}" if rendered_attrs else ""
        self._parts.append(f"<{tag}{suffix} />")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_CONTENT_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        self._parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self._skip_depth:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._skip_depth:
            self._parts.append(f"&#{name};")

    def _sanitize_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        allowed_attrs = GLOBAL_ATTRS | TAG_ATTRS.get(tag, set())
        clean_attrs = []
        for raw_name, raw_value in attrs:
            name = raw_name.lower()
            if name.startswith("on") or name == "style" or name not in allowed_attrs:
                continue
            value = "" if raw_value is None else raw_value.strip()
            if name in URI_ATTRS and not _is_safe_uri(value):
                continue
            clean_attrs.append(f'{name}="{escape(value, quote=True)}"')
        return " ".join(clean_attrs)


def _is_safe_uri(value: str) -> bool:
    if not value:
        return False
    if value.startswith("#"):
        return True
    parsed = urlparse(value)
    return parsed.scheme.lower() in ALLOWED_URI_SCHEMES


class _ReadableContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_content = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_CONTENT_TAGS or tag in NON_READER_TEXT_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_CONTENT_TAGS or tag in NON_READER_TEXT_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.has_content = True
