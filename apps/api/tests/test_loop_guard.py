from app.agents.graphs.loop_guard import check_loop


def c(name: str, **args):
    return {"name": name, "arguments": args}


def test_short_history_never_loops():
    assert not check_loop([c("a"), c("a")])


def test_identical_call_three_times():
    assert check_loop([c("a", x=1), c("b"), c("a", x=1), c("a", x=1)])


def test_ping_pong():
    assert check_loop([c("a", x=1), c("b", x=1), c("a", x=2), c("b", x=2)])


def test_same_tool_five_times_with_different_args():
    assert check_loop([c("a", x=i) for i in range(5)])


def test_varied_calls_are_fine():
    assert not check_loop([c("a", x=1), c("b"), c("c"), c("a", x=2)])
