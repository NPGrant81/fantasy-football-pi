import pytest
from jinja2 import Environment, DictLoader, StrictUndefined
from jinja2.exceptions import UndefinedError

# template copied from templates/email/keeper_deadline_reminder.html
KEEPER_TEMPLATE_HTML = """
<html>
<body>
<p>Reminder: the keeper selection window will close in 24 hours.</p>
<p>Visit the <a href="{{ url }}">keeper page</a> to finalize your list.</p>
</body>
</html>
"""

@pytest.fixture
def email_env():
    """
    Return a Jinja2 environment configured with StrictUndefined so that any
    missing variable produces an exception instead of silent empty string.
    """
    loader = DictLoader({"keeper_reminder.html": KEEPER_TEMPLATE_HTML})
    return Environment(loader=loader, undefined=StrictUndefined)


def test_keeper_email_renders_successfully(email_env):
    """Happy path: url is provided and replaced in output."""
    template = email_env.get_template("keeper_reminder.html")
    test_url = "https://example.com/keepers"

    html_output = template.render(url=test_url)

    assert "{{ url }}" not in html_output
    assert test_url in html_output
    assert "keeper selection window will close" in html_output.lower()


def test_keeper_email_fails_if_url_missing(email_env):
    """Failure path: rendering without url should raise UndefinedError."""
    template = email_env.get_template("keeper_reminder.html")
    with pytest.raises(UndefinedError) as exc_info:
        template.render()  # omit the url parameter
    assert "'url' is undefined" in str(exc_info.value)
