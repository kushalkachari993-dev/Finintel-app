from backend.utils.json_parser import JSONParser


def test_json_parser_extracts_object_from_surrounding_text():

    parsed = JSONParser.parse(
        'Here is the result: {"success": true, "value": 1}'
    )

    assert parsed == {
        "success": True,
        "value": 1
    }


def test_json_parser_returns_none_for_invalid_output():

    assert JSONParser.parse(
        "not json"
    ) is None
