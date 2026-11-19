from clipper import _fps_de


def test_fps_fraccion():
    assert _fps_de("60000/1001") == 59.94
    assert _fps_de("30/1") == 30.0
    assert _fps_de("0/0") == 60.0
    assert _fps_de("120/1") == 60.0
