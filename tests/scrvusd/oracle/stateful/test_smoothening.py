import functools

import boa
from hypothesis import settings
from hypothesis.stateful import invariant, run_state_machine_as_test

from tests.scrvusd.oracle.stateful.crvusd_state_machine import SoracleStateMachine
import pytest


PERIOD_CHECK_DURATION = 4 * 7 * 86400  # in seconds


class SmootheningStateMachine(SoracleStateMachine):
    """
    State machine for testing price smoothening.

    Decomposed smoothening since it impacts on price and makes hard to check actual values.
    It is still possible to reach value without smoothening via `.raw_price()`,
    though the purpose is to test final methods.
    """

    # # Force-including 0 and 1 as basic values to check
    # st_period_timestamps = st.lists(
    #     st.integers(min_value=2, max_value=PERIOD_CHECK_DURATION),
    #     unique=True,
    #     min_size=5,
    #     max_size=5,
    # ).map(sorted)
    # st_iterate_over_period = st_period_timestamps.map(
    #     lambda lst: [0, 1] + list(map(lambda x: x[1] - x[0], zip([0] + lst, lst + [PERIOD_CHECK_DURATION])))
    # )  # generates ts_delta

    st_period_timestamps = [0, 1, 2, 60, 3600, 86400, PERIOD_CHECK_DURATION // 10]
    st_iterate_over_period = [
        x[1] - x[0]
        for x in zip([0] + st_period_timestamps, st_period_timestamps + [PERIOD_CHECK_DURATION])
    ]

    def __init__(
        self, crvusd, scrvusd, admin, soracle, verifier, soracle_slots, max_price_increment
    ):
        super().__init__(crvusd, scrvusd, admin, soracle, verifier, soracle_slots)

        self.max_price_increment = max_price_increment

    @invariant(check_during_init=True)
    def smoothed_price(self):
        """
        Test that price moves within limits set.
        """
        for get_soracle_price in [
            getattr(self.soracle, price_fn)
            for price_fn in [
                "price_v0",
                "price_v1",
                "price_v2",
            ]
        ]:
            with boa.env.anchor():
                prev_price, prev_ts = get_soracle_price(), boa.env.evm.patch.timestamp
                for ts_delta in self.st_iterate_over_period:
                    boa.env.time_travel(seconds=ts_delta)
                    new_price, new_ts = get_soracle_price(), boa.env.evm.patch.timestamp

                    # Upper bound
                    # In fact, linear approximation is strictly less except new_ts - prev_ts == 1
                    assert (new_price / prev_price) <= (
                        1.0 + (self.max_price_increment / 10**18)
                    ) ** (new_ts - prev_ts)

                    # TODO: Lower bound

                    prev_price, prev_ts = new_price, new_ts


@pytest.fixture(scope="module", params=[10**11, 10**12, 10**13])
def max_price_increment(soracle, admin, request):
    with boa.env.prank(admin):
        soracle.set_max_price_increment(request.param)
    return request.param


def test_smoothening_simple(
    crvusd, scrvusd, admin, max_price_increment, soracle, soracle_price_slots, verifier
):
    machine = SmootheningStateMachine(
        # ScrvusdStateMachine
        crvusd=crvusd,
        scrvusd=scrvusd,
        admin=admin,
        # SoracleStateMachine
        soracle=soracle,
        verifier=verifier,
        soracle_slots=soracle_price_slots,
        # Smoothening test
        max_price_increment=max_price_increment,
    )
    machine.smoothed_price()

    machine.user_changes(4444 * 10**18)
    machine.smoothed_price()

    machine.add_rewards(666_666 * 10**18)
    machine.smoothed_price()

    machine.wait(86400 * 2)
    machine.smoothed_price()


@pytest.mark.slow
def test_scrvusd_oracle(
    crvusd, scrvusd, admin, max_price_increment, soracle, soracle_price_slots, verifier
):
    run_state_machine_as_test(
        functools.partial(
            SmootheningStateMachine,
            # ScrvusdStateMachine
            crvusd=crvusd,
            scrvusd=scrvusd,
            admin=admin,
            # SoracleStateMachine
            soracle=soracle,
            verifier=verifier,
            soracle_slots=soracle_price_slots,
            # Smoothening test
            max_price_increment=max_price_increment,
        ),
        settings=settings(
            max_examples=10,
            stateful_step_count=20,
            deadline=None,
        ),
    )
