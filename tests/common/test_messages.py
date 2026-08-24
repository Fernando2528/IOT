
import time
from common.messages import create_schedule


def test_schedule_at_specific_time():
    msg = create_schedule("test_name", 5.5)
    
    assert len(msg)==4
    assert "action" in msg
    assert "name" in msg
    assert "next_exec_epoch_s" in msg
    assert "next_exec_ns" in msg
    assert msg["action"] == "schedule"
    assert msg["name"] == "test_name"
    assert isinstance(msg["next_exec_epoch_s"], int)
    assert msg["next_exec_epoch_s"] > time.time()
    assert isinstance(msg["next_exec_ns"], int)
    assert 0 <= msg["next_exec_ns"] < 1_000_000_000

