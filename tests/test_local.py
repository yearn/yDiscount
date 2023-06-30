import ape
import pytest

WEEK = 7 * 24 * 60 * 60
UNIT = 10**18

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
def yfi(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def veyfi(project, deployer, yfi):
    return project.MockVotingEscrow.deploy(yfi, sender=deployer)

@pytest.fixture
def oracle(project, deployer):
    return project.MockPriceOracle.deploy(sender=deployer)

@pytest.fixture
def discount(project, deployer, management, yfi, veyfi, oracle):
    return project.Discount.deploy(yfi, veyfi, oracle, oracle, management, sender=deployer)

@pytest.mark.parametrize("weeks,target", [(4, 10), (24, 14.9), (52, 21.8), (104, 34.5), (208, 60), (300, 60), (400, 60)])
def test_discount(chain, deployer, alice, veyfi, discount, weeks, target):
    ts = (chain.pending_timestamp // WEEK + weeks) * WEEK
    veyfi.set_locked(alice, 1, ts, sender=deployer)
    assert round(discount.discount(alice)*100/UNIT, 1) == target

def test_chainlink_oracle(project, deployer, management, yfi, veyfi):
    chainlink_oracle = project.MockPriceOracle.deploy(sender=deployer)
    curve_oracle = project.MockPriceOracle.deploy(sender=deployer)
    discount = project.Discount.deploy(yfi, veyfi, chainlink_oracle, curve_oracle, management, sender=deployer)

    chainlink_oracle.set_price(2 * UNIT, sender=deployer)
    curve_oracle.set_price(UNIT, sender=deployer)
    assert discount.spot_price() == 2 * UNIT

def test_stale_chainlink_oracle(project, chain, deployer, management, yfi, veyfi):
    chainlink_oracle = project.MockPriceOracle.deploy(sender=deployer)
    curve_oracle = project.MockPriceOracle.deploy(sender=deployer)
    discount = project.Discount.deploy(yfi, veyfi, chainlink_oracle, curve_oracle, management, sender=deployer)

    chainlink_oracle.set_price(2 * UNIT, sender=deployer)
    curve_oracle.set_price(UNIT, sender=deployer)
    assert discount.spot_price() == 2 * UNIT

    chain.mine(timestamp=chain.pending_timestamp + 2 * 60 * 60)
    assert discount.spot_price() == UNIT

def test_curve_oracle(project, deployer, management, yfi, veyfi):
    chainlink_oracle = project.MockPriceOracle.deploy(sender=deployer)
    curve_oracle = project.MockPriceOracle.deploy(sender=deployer)
    discount = project.Discount.deploy(yfi, veyfi, chainlink_oracle, curve_oracle, management, sender=deployer)

    chainlink_oracle.set_price(UNIT, sender=deployer)
    curve_oracle.set_price(2 * UNIT, sender=deployer)
    assert discount.spot_price() == 2 * UNIT
