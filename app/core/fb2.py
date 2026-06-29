import base64
import html
from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(frozen=True)
class ParsedFb2Chapter:
    index: int
    title: str | None
    source_href: str
    html: str
    size_bytes: int
    asset_ids: list[str]


@dataclass(frozen=True)
class ParsedFb2Asset:
    id: str
    source_id: str
    media_type: str


@dataclass(frozen=True)
class ParsedFb2:
    chapters: list[ParsedFb2Chapter]
    assets: list[ParsedFb2Asset]


def parse_fb2(fb2_bytes: bytes) -> ParsedFb2:
    root = ElementTree.fromstring(_decode_bytes(fb2_bytes))
    binaries = _read_binaries(root)
    body = _find_first(root, "body")
    if body is None:
        raise ValueError("FB2 body not found")

    sections = [child for child in list(body) if _local_name(child.tag) == "section"]
    if not sections:
        sections = [body]

    chapters = []
    for section in sections:
        chapter_html, title, asset_ids = _section_to_html(section)
        if not chapter_html:
            continue
        chapters.append(
            ParsedFb2Chapter(
                index=len(chapters),
                title=title,
                source_href=f"section_{len(chapters)}",
                html=chapter_html,
                size_bytes=len(chapter_html.encode("utf-8")),
                asset_ids=sorted(asset_ids),
            )
        )

    if not chapters:
        raise ValueError("FB2 has no readable chapters")

    return ParsedFb2(chapters=chapters, assets=list(binaries.values()))


def encode_fb2_asset_id(source_id: str) -> str:
    encoded = base64.urlsafe_b64encode(source_id.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_fb2_asset_id(asset_id: str) -> str:
    padding = "=" * (-len(asset_id) % 4)
    return base64.urlsafe_b64decode(f"{asset_id}{padding}").decode("utf-8")


def get_fb2_asset(fb2_bytes: bytes, asset_id: str) -> tuple[bytes, str]:
    source_id = decode_fb2_asset_id(asset_id)
    root = ElementTree.fromstring(_decode_bytes(fb2_bytes))
    for binary in root.iter():
        if _local_name(binary.tag) != "binary":
            continue
        if binary.attrib.get("id") != source_id:
            continue
        media_type = binary.attrib.get("content-type", "application/octet-stream")
        content = "".join(binary.itertext()).strip()
        return base64.b64decode(content), media_type
    raise KeyError(asset_id)


def _read_binaries(root: ElementTree.Element) -> dict[str, ParsedFb2Asset]:
    binaries = {}
    for binary in root.iter():
        if _local_name(binary.tag) != "binary":
            continue
        source_id = binary.attrib.get("id")
        if not source_id:
            continue
        binaries[source_id] = ParsedFb2Asset(
            id=encode_fb2_asset_id(source_id),
            source_id=source_id,
            media_type=binary.attrib.get("content-type", "application/octet-stream"),
        )
    return binaries


def _section_to_html(section: ElementTree.Element) -> tuple[str, str | None, list[str]]:
    parts = ["<section>"]
    title = _extract_title(section)
    asset_ids = []
    if title:
        parts.append(f"<h1>{html.escape(title)}</h1>")

    for child in list(section):
        local_name = _local_name(child.tag)
        if local_name == "title":
            continue
        if local_name == "section":
            nested_html, _, nested_asset_ids = _section_to_html(child)
            parts.append(nested_html)
            asset_ids.extend(nested_asset_ids)
        elif local_name == "p":
            text = _element_text(child)
            if text:
                parts.append(f"<p>{html.escape(text)}</p>")
        elif local_name == "subtitle":
            text = _element_text(child)
            if text:
                parts.append(f"<h2>{html.escape(text)}</h2>")
        elif local_name == "empty-line":
            parts.append("<br />")
        elif local_name == "image":
            asset_id = _image_asset_id(child)
            if asset_id:
                asset_ids.append(asset_id)
                parts.append(f'<img src="#{asset_id}" data-asset-id="{asset_id}" />')
        elif local_name == "poem":
            poem = _poem_to_html(child)
            if poem:
                parts.append(poem)

    parts.append("</section>")
    return "".join(parts), title, asset_ids


def _poem_to_html(poem: ElementTree.Element) -> str:
    lines = []
    for child in poem.iter():
        if _local_name(child.tag) != "v":
            continue
        text = _element_text(child)
        if text:
            lines.append(html.escape(text))
    if not lines:
        return ""
    return f"<blockquote>{'<br />'.join(lines)}</blockquote>"


def _extract_title(section: ElementTree.Element) -> str | None:
    for child in list(section):
        if _local_name(child.tag) != "title":
            continue
        text = _element_text(child)
        if text:
            return text[:500]
    return None


def _image_asset_id(image: ElementTree.Element) -> str | None:
    href = None
    for key, value in image.attrib.items():
        if _local_name(key) == "href":
            href = value
            break
    if not href:
        return None
    source_id = href.removeprefix("#")
    if not source_id:
        return None
    return encode_fb2_asset_id(source_id)


def _find_first(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for element in root.iter():
        if _local_name(element.tag) == name:
            return element
    return None


def _element_text(element: ElementTree.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _decode_bytes(value: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
