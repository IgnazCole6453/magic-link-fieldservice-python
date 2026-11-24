from src.magic_link_service import can_send_follow_up


def test_follow_up_is_allowed_only_after_dispatch_reaches_technician():
    assert can_send_follow_up("onsite") is True
    assert can_send_follow_up("queued") is False
