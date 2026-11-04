from laser_counter.laps import MAX_LAPS, MAX_NAME_LENGTH, Lap, Laps, ShotTally


def names(laps: Laps) -> list[str]:
    return [lap.name for lap in laps]


def test_starts_with_one_running_lap():
    laps = Laps()
    assert names(laps) == ["Lap1"]
    assert laps[0].count == 0 and laps[0].running


def test_new_laps_count_from_zero_and_stop_at_nine():
    laps = Laps()
    for _ in range(MAX_LAPS - 1):
        lap = laps.add()
        assert lap.count == 0 and lap.running
    assert names(laps) == [f"Lap{n}" for n in range(1, 10)]
    assert not laps.can_add
    assert laps.add() is None
    assert len(laps) == MAX_LAPS


def test_default_name_follows_position_else_lowest_free_number():
    laps = Laps()
    lap2, lap3 = laps.add(), laps.add()
    laps.rename(laps[0], "Sample A")
    assert laps.add().name == "Lap4"
    laps.remove(lap2)
    laps.remove(lap3)
    assert names(laps) == ["Sample A", "Lap4"]
    assert laps.add().name == "Lap3"
    assert laps.add().name == "Lap1"  # position 4 is taken by Lap4, and Lap1 is free


def test_last_lap_cannot_be_deleted():
    laps = Laps()
    assert not laps.can_remove
    assert not laps.remove(laps[0])
    second = laps.add()
    assert laps.remove(laps[0])
    assert names(laps) == [second.name]
    assert not laps.remove(second)


def test_remove_picks_the_exact_lap_even_when_two_look_alike():
    first, second = Lap("Same", 5), Lap("Same", 5)
    laps = Laps([first, second])
    assert laps.remove(second)
    assert laps[0] is first


def test_rename_trims_and_ignores_blank_names():
    laps = Laps()
    assert laps.rename(laps[0], "  Sample   B  ") == "Sample B"
    assert laps.rename(laps[0], "   ") == "Sample B"
    assert laps.rename(laps[0], "x" * 40) == "x" * MAX_NAME_LENGTH


def test_shots_go_to_running_laps_only():
    laps = Laps()
    second = laps.add()
    laps.add_shots(3)
    laps[0].running = False
    laps.add_shots(2)
    assert [lap.count for lap in laps] == [3, 5]
    assert laps.any_running
    second.running = False
    assert not laps.any_running


def test_save_and_restore_round_trip():
    laps = Laps([Lap("Sample A", 12, False), Lap("Lap2", 4, True)])
    restored = Laps.from_list(laps.to_list())
    assert [(lap.name, lap.count, lap.running) for lap in restored] == [("Sample A", 12, False), ("Lap2", 4, True)]


def test_restore_skips_malformed_entries():
    saved = [{"name": "Good", "count": 3, "running": True}, {"name": "", "count": 1, "running": True},
             {"name": "Neg", "count": -1, "running": True}, {"count": 2}, "junk"]
    assert names(Laps.from_list(saved)) == ["Good"]
    assert names(Laps.from_list("not a list")) == ["Lap1"]
    assert len(Laps.from_list([{"name": f"L{n}", "count": 0, "running": True} for n in range(12)])) == MAX_LAPS


def test_tally_counts_new_shots_from_the_box_total():
    tally = ShotTally()
    assert tally.update(count=40, t_us=1_000, running=True) == 0  # first reading only sets the starting point
    assert tally.update(count=41, t_us=2_000, running=True) == 1
    assert tally.update(count=44, t_us=3_000, running=True) == 3  # a missed EVT line still gets counted
    assert tally.update(count=44, t_us=4_000, running=True) == 0


def test_tally_catches_up_on_shots_counted_while_the_app_was_closed():
    tally = ShotTally(mark=(100, 5_000_000))
    tally.reconnected()
    assert tally.update(count=130, t_us=9_000_000, running=True) == 30
    assert tally.update(count=131, t_us=9_100_000, running=True) == 1


def test_tally_ignores_the_old_total_after_the_box_restarts():
    for count, t_us, running in ((0, 2_000_000, False), (130, 1_000_000, True), (50, 9_000_000, True)):
        tally = ShotTally(mark=(100, 5_000_000))
        tally.reconnected()
        assert tally.update(count, t_us, running) == 0
