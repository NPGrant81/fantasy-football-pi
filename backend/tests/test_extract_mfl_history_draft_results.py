from backend.scripts.extract_mfl_history import _normalize_draft_results


def test_normalize_draft_results_filters_order_only_rows():
    payload = {
        "draftResults": {
            "draftUnit": {
                "draftPick": [
                    {"round": "01", "pick": "01", "franchise": "0001", "player": ""},
                    {"round": "01", "pick": "02", "franchise": "0002", "player": "1002"},
                ]
            }
        }
    }

    rows = _normalize_draft_results(payload, season=2002, league_id="29721", extracted_at="2026-03-14T00:00:00+00:00")

    assert len(rows) == 1
    assert rows[0]["franchise_id"] == "0002"
    assert rows[0]["player_mfl_id"] == "1002"
    assert rows[0]["round"] == "01"
    assert rows[0]["pick_number"] == "02"
    assert rows[0]["draft_source"] == "draftResults"
    assert rows[0]["draft_style"] == "snake"


def test_normalize_draft_results_reads_static_url_when_inline_missing(monkeypatch):
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    xml_text = """
    <?xml version=\"1.0\" encoding=\"ISO-8859-1\"?>
    <draftResults>
      <draftPick round=\"01\" pick=\"01\" franchise=\"0001\" player=\"\" />
      <draftPick round=\"01\" pick=\"02\" franchise=\"0002\" player=\"1002\" cost=\"15\" />
    </draftResults>
    """.strip()

    def fake_get(url, timeout):
        assert "draft_results.xml" in url
        assert timeout == 20
        return FakeResponse(xml_text)

    monkeypatch.setattr("backend.scripts.extract_mfl_history.requests.get", fake_get)

    payload = {
        "draftResults": {
            "draftUnit": {
                "static_url": "https://example.test/draft_results.xml"
            }
        }
    }

    rows = _normalize_draft_results(payload, season=2003, league_id="39069", extracted_at="2026-03-14T00:00:00+00:00")

    assert len(rows) == 1
    assert rows[0]["franchise_id"] == "0002"
    assert rows[0]["player_mfl_id"] == "1002"
    assert rows[0]["winning_bid"] == "15"
    assert rows[0]["draft_source"] == "draftResults"
    assert rows[0]["draft_style"] == "snake"


def test_normalize_draft_results_uses_auction_results_fallback_when_players_missing():
    payload = {
        "draftResults": {
            "draftUnit": {
                "draftPick": [
                    {"round": "01", "pick": "01", "franchise": "0001", "player": ""},
                    {"round": "01", "pick": "02", "franchise": "0002", "player": ""},
                ]
            }
        },
        "_auction_results_fallback": {
            "auctionResults": {
                "auctionUnit": {
                    "auction": [
                        {
                            "franchise": "0007",
                            "player": "12625",
                            "winningBid": "42",
                            "timeStarted": "1502557689",
                            "lastBidTime": "1502557689",
                        }
                    ]
                }
            }
        },
    }

    rows = _normalize_draft_results(payload, season=2017, league_id="38909", extracted_at="2026-03-14T00:00:00+00:00")

    assert len(rows) == 1
    assert rows[0]["franchise_id"] == "0007"
    assert rows[0]["player_mfl_id"] == "12625"
    assert rows[0]["winning_bid"] == "42"
    assert rows[0]["draft_source"] == "auctionResults"
    assert rows[0]["draft_style"] == "auction"
