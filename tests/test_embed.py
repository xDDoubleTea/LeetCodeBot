from unittest.mock import patch

from utils.embed_presenters import parse_problem_desc


def test_parse_problem_desc():
    html_content = "<p>Test <strong>Bold</strong> <em>Italic</em> <code>Code</code></p>"
    parsed = parse_problem_desc(html_content)

    assert "**Bold**" in parsed
    assert "*Italic*" in parsed
    assert "`Code`" in parsed

    complex_html = """
    <p>Intro</p>
    <table><tr><td>SecretData</td></tr></table>
    <img src="test.png">
    <p>Outro</p>
    """
    parsed_complex = parse_problem_desc(complex_html)

    assert "*[Table omitted for preview]*" in parsed_complex
    assert "SecretData" not in parsed_complex
    assert "test.png" not in parsed_complex

    with patch("utils.embed_presenters.PREVIEW_LEN", 30):
        # This string is designed to be cut off in the middle of the bold tags
        long_html = "<p>Prefix text <strong>this is a very long bold text to trigger cutoff</strong></p>"
        parsed_long = parse_problem_desc(long_html)

        assert parsed_long.endswith("...")
        assert parsed_long.count("**") % 2 == 0
        assert parsed_long.count("`") % 2 == 0
