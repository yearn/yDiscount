import ape
import pytest

DAY = 24 * 60 * 60
WEEK = 7 * DAY
ALLOWANCE_EXPIRATION_TIME = 30 * DAY
UNIT = 10**18
MAX_DISCOUNT = 59_999_584
DISCOUNT_SCALE = 100_000_000
MIN_MULTIPLIER = DISCOUNT_SCALE - MAX_DISCOUNT

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

@pytest.fixture
def callback(project, deployer):
    return project.MockCallback.deploy(sender=deployer)

def test_accounts(deployer, management):
    print(deployer, management, alice, bob, charlie)
