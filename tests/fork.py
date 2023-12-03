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
YFIUSD_CHAINLINK_ORACLE = '0xA027702dbb89fbd58938e4324ac03B58d812b0E1'
ETHUSD_CHAINLINK_ORACLE = '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419'
YCHAD = '0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52'

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
def ychad(accounts):
    return accounts[YCHAD]

@pytest.fixture
def yfi():
    return Contract(YFI)

@pytest.fixture
def veyfi():
    return Contract(VEYFI)

@pytest.fixture
def chainlink_oracle(project, deployer):
    return project.DoubleChainlinkOracle.deploy(YFIUSD_CHAINLINK_ORACLE, ETHUSD_CHAINLINK_ORACLE, sender=deployer)

@pytest.fixture
def discount(project, deployer, management, yfi, veyfi, chainlink_oracle):
    return project.Discount.deploy(yfi, veyfi, chainlink_oracle, management, sender=deployer)

def test_oracle(chainlink_oracle, discount):
    assert discount.spot_price() == chainlink_oracle.latestRoundData().answer

def test_stale_oracle(chain, discount):
    chain.pending_timestamp += 2 * 60 * 60
    chain.mine()
    with ape.reverts():
        discount.spot_price()

def test_buy(chain, management, alice, bob, ychad, yfi, veyfi, discount):
    yfi.transfer(alice, UNIT, sender=ychad)
    yfi.transfer(discount, 10 * UNIT, sender=ychad)
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

def test_double_oracle(chainlink_oracle):
    oracle = Contract(CHAINLINK_ORACLE)
    a = oracle.latestRoundData()[1]
    b = chainlink_oracle.latestRoundData()[1]
    assert abs(a-b)/a < 0.01
