import ape
from ape import Contract
import pytest

DAY = 24 * 60 * 60
WEEK = 7 * DAY
UNIT = 10**18
MAX = 2**256 - 1

YFI = '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e'
VEYFI = '0x90c1f9220d90d3966FbeE24045EDd73E1d588aD5'
CHAINLINK_ORACLE = '0x7c5d4F8345e66f68099581Db340cd65B078C41f4'
CURVE_ORACLE = '0xC26b89A667578ec7b3f11b2F98d6Fd15C07C54ba'

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def management(accounts):
    return accounts[1]

@pytest.fixture
def alice(accounts):
    return accounts[2]

@pytest.fixture
def bob(accounts):
    return accounts[3]

@pytest.fixture
def charlie(accounts):
    return accounts[4]

@pytest.fixture
def yfi(accounts, management):
    yfi = Contract(YFI)
    governance = accounts[yfi.governance()]
    yfi.addMinter(management, sender=governance)
    return yfi

@pytest.fixture
def veyfi():
    return Contract(VEYFI)

@pytest.fixture
def chainlink_oracle():
    return Contract(CHAINLINK_ORACLE)

@pytest.fixture
def curve_oracle():
    return Contract(CURVE_ORACLE)

@pytest.fixture
def discount(project, deployer, management, yfi, veyfi):
    return project.Discount.deploy(yfi, veyfi, CHAINLINK_ORACLE, CURVE_ORACLE, management, sender=deployer)

def test_oracle(chainlink_oracle, curve_oracle, discount):
    price = max(chainlink_oracle.latestRoundData().answer, curve_oracle.price_oracle())
    assert discount.spot_price() == price

def test_stale_oracle(chain, curve_oracle, discount):
    chain.pending_timestamp += 2 * 60 * 60
    assert discount.spot_price() == curve_oracle.price_oracle()

def test_buy(chain, management, alice, bob, yfi, veyfi, discount):
    yfi.mint(alice, UNIT, sender=management)
    yfi.mint(discount, 10 * UNIT, sender=management)
    yfi.approve(veyfi, MAX, sender=alice)

    price = discount.spot_price() * 9 // 10
    discount.set_team_allowances([bob], [price], sender=management)
    discount.set_contributor_allowances([alice], [price], sender=bob)

    with ape.reverts():
        discount.buy(0, value=price, sender=alice)

    with chain.isolate():
        veyfi.modify_lock(UNIT, chain.pending_timestamp // WEEK * WEEK + 2 * WEEK, sender=alice)
        with ape.reverts('lock too short'):
            discount.buy(0, value=price, sender=alice)

    veyfi.modify_lock(UNIT, chain.pending_timestamp // WEEK * WEEK + 4 * WEEK, sender=alice)
    assert discount.discount(alice) == UNIT // 10
    assert abs(discount.preview(alice, price, False) / UNIT - 1) < 1e-10
    discount.buy(0, value=price, sender=alice)
    assert abs(veyfi.locked(alice).amount / 2 / UNIT - 1) < 1e-10
