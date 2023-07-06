import ape
import pytest

DAY = 24 * 60 * 60
WEEK = 7 * DAY
ALLOWANCE_EXPIRATION_TIME = 30 * DAY
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

def test_set_team_allowances_privilege(alice, discount):
    with ape.reverts():
        discount.set_team_allowances([alice], [UNIT], sender=alice)

def test_set_team_allowances(chain, management, alice, bob, discount):
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    assert discount.team_allowance(alice) == (0, 0)
    assert discount.team_allowance(bob) == (0, 0)
    discount.set_team_allowances([alice, bob], [UNIT, 2 * UNIT], sender=management)
    assert discount.team_allowance(alice) == (UNIT, ts)
    assert discount.team_allowance(bob) == (2 * UNIT, ts)

def test_set_team_allowances_custom_expiration(chain, management, alice, discount):
    ts = chain.pending_timestamp + DAY
    discount.set_team_allowances([alice], [UNIT], ts, sender=management)
    assert discount.team_allowance(alice) == (UNIT, ts)

def test_team_allowance_expiry(chain, management, alice, discount):
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    discount.set_team_allowances([alice], [UNIT], sender=management)
    chain.mine(timestamp=ts - 1)
    assert discount.team_allowance(alice) == (UNIT, ts)
    chain.mine(timestamp=ts)
    assert discount.team_allowance(alice) == (0, 0)

def test_set_contributor_allowances_privilege(alice, bob, discount):
    with ape.reverts():
        discount.set_contributor_allowances([bob], [UNIT], sender=alice)

def test_set_contributor_allowances(chain, management, alice, bob, charlie, discount):
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    assert discount.contributor_allowance(alice, bob) == (0, 0)
    assert discount.contributor_allowance(alice, charlie) == (0, 0)
    discount.set_contributor_allowances([bob, charlie], [UNIT, 2 * UNIT], sender=alice)
    assert discount.team_allowance(alice)[0] == 0
    assert discount.contributor_allowance(alice, bob) == (UNIT, ts)
    assert discount.contributor_allowance(alice, charlie) == (2 * UNIT, ts)

def test_set_contributor_allowances_excess(management, alice, bob, discount):
    discount.set_team_allowances([alice], [UNIT], sender=management)
    with ape.reverts():
        discount.set_contributor_allowances([bob], [2 * UNIT], sender=alice)

def test_set_contributor_allowances_multiple(management, alice, bob, charlie, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    assert discount.team_allowance(alice)[0] == 2 * UNIT
    assert discount.contributor_allowance(alice, bob)[0] == UNIT
    assert discount.contributor_allowance(alice, charlie)[0] == 0
    discount.set_contributor_allowances([charlie], [UNIT], sender=alice)
    assert discount.team_allowance(alice)[0] == UNIT
    assert discount.contributor_allowance(alice, charlie)[0] == UNIT

def test_set_contributor_allowances_add(management, alice, bob, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    assert discount.team_allowance(alice)[0] == 2 * UNIT
    assert discount.contributor_allowance(alice, bob)[0] == UNIT
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    assert discount.team_allowance(alice)[0] == UNIT
    assert discount.contributor_allowance(alice, bob)[0] == 2 * UNIT

def test_set_contributor_allowances_overwrite(chain, management, alice, bob, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    assert discount.team_allowance(alice)[0] == 2 * UNIT
    assert discount.contributor_allowance(alice, bob) == (UNIT, ts)

def test_preview(chain, deployer, alice, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 4 * WEEK, sender=deployer)
    assert discount.preview(alice, UNIT * 18 // 10, False) == UNIT

def test_preview_max(chain, deployer, alice, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    price = (100_000_000 - 59_999_584) * 2 * UNIT // 100_000_000
    assert discount.preview(alice, UNIT, False) == UNIT * UNIT // price

def test_preview_no_lock(chain, deployer, alice, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    
    # no lock
    with ape.reverts():
        discount.preview(alice, UNIT, False)
    
    # expired lock
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK - 2 * WEEK, sender=deployer)
    with ape.reverts():
        discount.preview(alice, UNIT, False)

    # too short lock
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 2 * WEEK, sender=deployer)
    with ape.reverts():
        discount.preview(alice, UNIT, False)

def test_preview_delegate(chain, deployer, alice, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    assert discount.preview(alice, UNIT * 18 // 10, True) == UNIT

def test_preview_delegate_no_lock(chain, deployer, alice, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    
    # no lock
    with ape.reverts():
        discount.preview(alice, UNIT, True)
    
    # expired lock
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK - 2 * WEEK, sender=deployer)
    with ape.reverts():
        discount.preview(alice, UNIT, True)

    # too short lock
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 100 * WEEK, sender=deployer)
    with ape.reverts():
        discount.preview(alice, UNIT, True)
