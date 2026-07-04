import base64
import posixpath
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

from app.core.html_sanitizer import has_readable_chapter_content, sanitize_chapter_html


@dataclass(frozen=True)
class ParsedEpubChapter:
    index: int
    title: str | None
    source_href: str
    html: str
    size_bytes: int
    asset_ids: list[str]


@dataclass(frozen=True)
class ParsedEpubAsset:
    id: str
    source_href: str
    media_type: str


@dataclass(frozen=True)
class ParsedEpub:
    chapters: list[ParsedEpubChapter]
    assets: list[ParsedEpubAsset]


def parse_epub(epub_bytes: bytes) -> ParsedEpub:
    with zipfile.ZipFile(BytesIO(epub_bytes)) as archive:
        opf_path = _get_opf_path(archive)
        opf_dir = posixpath.dirname(opf_path)
        opf_root = ElementTree.fromstring(archive.read(opf_path))
        manifest = _read_manifest(opf_root, opf_dir)
        spine_ids = _read_spine_ids(opf_root)

        if not spine_ids:
            raise ValueError("EPUB spine is empty")

        assets = _read_assets(manifest)
        chapters = []
        for index, item_id in enumerate(spine_ids):
            item = manifest.get(item_id)
            if not item:
                continue
            href = item["href"]
            if href not in archive.namelist():
                continue

            html = _decode_bytes(archive.read(href))
            sanitized_html = sanitize_chapter_html(html)
            if not has_readable_chapter_content(sanitized_html):
                continue
            asset_ids = _extract_asset_ids(sanitized_html, posixpath.dirname(href), manifest)
            chapters.append(
                ParsedEpubChapter(
                    index=len(chapters),
                    title=_extract_chapter_title(sanitized_html),
                    source_href=href,
                    html=sanitized_html,
                    size_bytes=len(sanitized_html.encode("utf-8")),
                    asset_ids=asset_ids,
                )
            )

        if not chapters:
            raise ValueError("EPUB has no readable chapters")

        return ParsedEpub(chapters=chapters, assets=assets)


def encode_asset_id(source_href: str) -> str:
    encoded = base64.urlsafe_b64encode(source_href.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_asset_id(asset_id: str) -> str:
    padding = "=" * (-len(asset_id) % 4)
    return base64.urlsafe_b64decode(f"{asset_id}{padding}").decode("utf-8")


def get_epub_asset(epub_bytes: bytes, asset_id: str) -> tuple[bytes, str]:
    source_href = decode_asset_id(asset_id)
    with zipfile.ZipFile(BytesIO(epub_bytes)) as archive:
        opf_path = _get_opf_path(archive)
        opf_dir = posixpath.dirname(opf_path)
        manifest = _read_manifest(ElementTree.fromstring(archive.read(opf_path)), opf_dir)
        allowed_assets = {item["href"]: item["media_type"] for item in manifest.values()}
        media_type = allowed_assets.get(source_href)
        if not media_type or source_href not in archive.namelist():
            raise KeyError(asset_id)
        return archive.read(source_href), media_type


def _get_opf_path(archive: zipfile.ZipFile) -> str:
    try:
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
    except KeyError as exc:
        raise ValueError("EPUB container.xml not found") from exc

    for element in container.iter():
        if _local_name(element.tag) == "rootfile":
            full_path = element.attrib.get("full-path")
            if full_path:
                return full_path
    raise ValueError("EPUB OPF rootfile not found")


def _read_manifest(root: ElementTree.Element, opf_dir: str) -> dict[str, dict[str, str]]:
    manifest: dict[str, dict[str, str]] = {}
    for element in root.iter():
        if _local_name(element.tag) != "item":
            continue
        item_id = element.attrib.get("id")
        href = element.attrib.get("href")
        if not item_id or not href:
            continue
        manifest[item_id] = {
            "href": _normalize_zip_path(opf_dir, href),
            "media_type": element.attrib.get("media-type", "application/octet-stream"),
            "properties": element.attrib.get("properties", ""),
        }
    return manifest


def _read_spine_ids(root: ElementTree.Element) -> list[str]:
    ids = []
    for element in root.iter():
        if _local_name(element.tag) != "itemref":
            continue
        idref = element.attrib.get("idref")
        if idref:
            ids.append(idref)
    return ids


def _read_assets(manifest: dict[str, dict[str, str]]) -> list[ParsedEpubAsset]:
    assets = []
    for item in manifest.values():
        media_type = item["media_type"]
        if media_type in {"application/xhtml+xml", "text/html"}:
            continue
        assets.append(
            ParsedEpubAsset(
                id=encode_asset_id(item["href"]),
                source_href=item["href"],
                media_type=media_type,
            )
        )
    return assets


def _extract_asset_ids(html: str, chapter_dir: str, manifest: dict[str, dict[str, str]]) -> list[str]:
    manifest_paths = {item["href"] for item in manifest.values()}
    asset_ids = []
    for match in re.finditer(r"\s(?:src|href)\s*=\s*(['\"])(.*?)\1", html, flags=re.IGNORECASE):
        raw_url = match.group(2).strip()
        parsed = urlparse(raw_url)
        if parsed.scheme or raw_url.startswith("#"):
            continue
        asset_path = _normalize_zip_path(chapter_dir, parsed.path)
        if asset_path in manifest_paths:
            asset_ids.append(encode_asset_id(asset_path))
    return sorted(set(asset_ids))


def _extract_chapter_title(html: str) -> str | None:
    for tag in ("h1", "h2", "title"):
        match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            title = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if title:
                return title[:500]
    return None


def _normalize_zip_path(base_dir: str, href: str) -> str:
    parsed_path = unquote(urlparse(href).path)
    joined = posixpath.normpath(posixpath.join(base_dir, parsed_path))
    return joined.lstrip("/")


def _decode_bytes(value: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
