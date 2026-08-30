from db import grievances


def test_code_format_and_increment(memstore):
    c1 = grievances.next_code()
    c2 = grievances.next_code()
    assert c1 == "GLB-CAMP-00001"
    assert c2 == "GLB-CAMP-00002"
