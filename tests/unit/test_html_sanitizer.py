from app.core.html_sanitizer import sanitize_chapter_html


def test_sanitize_chapter_html_removes_executable_tags_and_handlers():
    html = """
    <section>
      <h1 onclick="alert(1)">Title</h1>
      <script>alert(1)</script>
      <iframe src="https://evil.test"></iframe>
      <p onmouseover="alert(2)">Hello</p>
    </section>
    """

    sanitized = sanitize_chapter_html(html)

    assert "<script" not in sanitized
    assert "alert(1)" not in sanitized
    assert "<iframe" not in sanitized
    assert "onclick" not in sanitized
    assert "onmouseover" not in sanitized
    assert "<h1>Title</h1>" in sanitized
    assert "<p>Hello</p>" in sanitized


def test_sanitize_chapter_html_removes_unsafe_urls_and_styles():
    html = """
    <a href="javascript:alert(1)" style="color: red">bad</a>
    <img src="data:image/svg+xml,<svg onload=alert(1)>" onerror="alert(1)" />
    <img src="../images/pic.png" data-asset-id="asset1" />
    <a href="#chapter-2">toc</a>
    """

    sanitized = sanitize_chapter_html(html)

    assert "javascript:" not in sanitized
    assert "data:image" not in sanitized
    assert "style=" not in sanitized
    assert "onerror" not in sanitized
    assert "<img src=\"../images/pic.png\" data-asset-id=\"asset1\" />" in sanitized
    assert "<a href=\"#chapter-2\">toc</a>" in sanitized


def test_sanitize_chapter_html_escapes_unknown_tags_as_text_content_only():
    sanitized = sanitize_chapter_html("<custom><b>Safe</b><svg><title>x</title></svg></custom>")

    assert "<custom" not in sanitized
    assert "<svg" not in sanitized
    assert "<b>Safe</b>" in sanitized
    assert "x" not in sanitized
