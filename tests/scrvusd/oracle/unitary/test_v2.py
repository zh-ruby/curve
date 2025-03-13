import pytest
import boa

from tests.scrvusd.conftest import DEFAULT_MAX_PRICE_INCREMENT, DEFAULT_MAX_V2_DURATION


@pytest.fixture(scope="module")
def soracle(admin):
    with boa.env.prank(admin):
        contract = boa.load("contracts/scrvusd/oracles/ScrvusdOracleV2.vy", 10**18)
    return contract


def test_ownership(soracle, admin, anne):
    admin_role = soracle.DEFAULT_ADMIN_ROLE()

    assert soracle.hasRole(admin_role, admin)

    # Reachable for admin
    with boa.env.prank(admin):
        soracle.set_max_price_increment(DEFAULT_MAX_PRICE_INCREMENT + 1)
        soracle.set_max_v2_duration(DEFAULT_MAX_V2_DURATION + 1)

    # Not reachable for third party
    with boa.env.prank(anne):
        with boa.reverts():
            soracle.set_max_price_increment(DEFAULT_MAX_PRICE_INCREMENT + 2)
        with boa.reverts():
            soracle.set_max_v2_duration(DEFAULT_MAX_V2_DURATION + 2)

    # Transferable
    with boa.env.prank(admin):
        soracle.grantRole(admin_role, anne)
        soracle.revokeRole(admin_role, admin)
    assert soracle.hasRole(admin_role, anne)
    assert not soracle.hasRole(admin_role, admin)

    # Reachable for new owner
    with boa.env.prank(anne):
        soracle.set_max_price_increment(DEFAULT_MAX_PRICE_INCREMENT + 2)
        soracle.set_max_v2_duration(DEFAULT_MAX_V2_DURATION + 2)

    # Renounceable, making it immutable
    with boa.env.prank(anne):
        soracle.revokeRole(admin_role, anne)
        with boa.reverts():
            soracle.set_max_price_increment(DEFAULT_MAX_PRICE_INCREMENT + 1)
        with boa.reverts():
            soracle.set_max_v2_duration(DEFAULT_MAX_V2_DURATION + 1)


def test_setters(soracle, admin):
    with boa.env.prank(admin):
        soracle.set_max_price_increment(DEFAULT_MAX_PRICE_INCREMENT + 1)
        assert soracle.max_price_increment() == DEFAULT_MAX_PRICE_INCREMENT + 1

        soracle.set_max_v2_duration(DEFAULT_MAX_V2_DURATION + 1)
        assert soracle.max_v2_duration() == DEFAULT_MAX_V2_DURATION + 1


def test_update_profit_max_unlock_time(soracle, verifier, anne):
    # Not available to a third party
    with boa.env.prank(anne):
        with boa.reverts():
            soracle.update_profit_max_unlock_time(
                8 * 86400,  # new value
                10,  # block number
            )

    with boa.env.prank(verifier):
        soracle.update_profit_max_unlock_time(
            8 * 86400,  # new value
            10,  # block number
        )
        assert soracle.last_block_number() == 10

        # Linearizability by block number
        with boa.reverts():
            soracle.update_profit_max_unlock_time(
                8 * 86400,  # new value
                8,  # block number
            )

        # "Breaking" resubmit at same block
        soracle.update_profit_max_unlock_time(
            6 * 86400,  # new value
            10,  # block number
        )


def test_update_price(soracle, verifier, anne):
    ts = boa.env.evm.patch.timestamp
    price_1_5_parameters = [3, 0, 2, ts + 7 * 86400, 0, 0, 0]
    price_0_5_parameters = [2, 0, 3, ts + 7 * 86400, 0, 0, 0]

    # Not available to a third party
    with boa.env.prank(anne):
        with boa.reverts():
            soracle.update_price(
                price_1_5_parameters,
                ts + 100,  # timestamp
                10,  # block number
            )

    with boa.env.prank(verifier):
        soracle.update_price(
            price_1_5_parameters,
            ts + 100,  # timestamp
            10,  # block number
        )
        assert soracle.last_block_number() == 10

        # Linearizability by block number
        with boa.reverts():
            soracle.update_price(
                price_1_5_parameters,
                ts + 101,  # timestamp
                8,  # block number
            )

        # "Breaking" resubmit at same block
        soracle.update_price(
            price_0_5_parameters,
            ts + 99,  # timestamp
            10,  # block number
        )
