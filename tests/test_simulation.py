"""Simulation sanity checks (small runs, fixed seeds)."""
import numpy as np
import pytest

sim = pytest.importorskip("step5_simulation")


def test_every_line_is_picked_or_late():
    k, _ = sim.simulate([(9, 3), (11, 3)], 1)
    assert k["picked_lines"] + k["late_lines"] == k["lines"] > 0


def test_no_pickers_means_everything_late():
    k, _ = sim.simulate([], 2)
    assert k["late_lines_pct"] == 100 and k["picked_lines"] == 0


def test_big_crew_over_whole_day_has_no_late_lines():
    k, _ = sim.simulate([(6, 15), (12, 15)], 3)
    assert k["late_lines"] == 0


def test_same_day_seed_gives_same_demand_whatever_the_crew():
    a, _ = sim.simulate([(8, 3)], 5)
    b, _ = sim.simulate([(10, 9)], 5)
    assert a["lines"] == b["lines"]


def test_more_pickers_means_fewer_late_lines_when_short_staffed():
    # (beyond ~6 pickers late lines stop falling: the crew finishes early and goes home,
    #  so the few orders arriving after 6 PM wait - a real effect, not tested here)
    late = []
    for crew in (2, 4, 6):
        late.append(np.mean([sim.simulate([(10, crew)], d)[0]["late_lines_pct"] for d in range(20)]))
    assert late[0] > late[1] > late[2]
