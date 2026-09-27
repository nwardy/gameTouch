from tactile.event_patterns import description_for, run_event_pattern


class FakeOutput:
    def __init__(self):
        self.events = []

    def set_cell(self, row, column):
        self.events.append(("cell", row, column))

    def all_on(self):
        self.events.append(("all_on",))

    def all_off(self):
        self.events.append(("all_off",))


def test_goal_uses_three_full_board_blinks():
    output = FakeOutput()
    assert run_event_pattern(output, "goal", None, sleep=lambda _: None)
    assert output.events.count(("all_on",)) == 3
    assert output.events.count(("all_off",)) == 3


def test_yellow_card_is_two_ball_cell_taps():
    output = FakeOutput()
    assert run_event_pattern(output, "yellow_card", (2, 4), sleep=lambda _: None)
    assert output.events == [
        ("cell", 2, 4), ("all_off",), ("cell", 2, 4), ("all_off",),
    ]


def test_unknown_event_is_not_played():
    assert not run_event_pattern(FakeOutput(), "none", (2, 4), sleep=lambda _: None)
    assert description_for("none") == "no tactile event pattern"
