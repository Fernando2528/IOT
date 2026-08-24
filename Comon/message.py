import time


def create_schedule(name: str, delay_s: float) -> dict:
    """
    Create a schedule message.

    delay_s: number of seconds to wait before execution.
    """

    now_ns = time.time_ns()
    next_exec_ns = now_ns + int(delay_s * 1_000_000_000)

    return {
        "action": "schedule",
        "name": name,
        "next_exec_epoch_s": next_exec_ns // 1_000_000_000,
        "next_exec_ns": next_exec_ns % 1_000_000_000,
    }

