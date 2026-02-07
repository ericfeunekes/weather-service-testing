from wxbench.trip_brief.sampling import decode_polyline


def test_decode_polyline_example() -> None:
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    points = decode_polyline(encoded)
    assert points == [
        (38.5, -120.2),
        (40.7, -120.95),
        (43.252, -126.453),
    ]
