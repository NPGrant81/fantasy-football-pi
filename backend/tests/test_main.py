from backend import main


def test_read_root_returns_message():
    """Call the `read_root` function directly to avoid startup side effects."""
    assert main.read_root() == {"message": "Fantasy Football API is Running!"}
