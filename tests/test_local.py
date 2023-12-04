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
    return project.Discount.deploy(yfi, veyfi, oracle, management, sender=deployer)

@pytest.fixture
def callback(project, deployer):
    return project.MockCallback.deploy(sender=deployer)

@pytest.mark.parametrize("weeks,target", [(4, 10), (24, 14.9), (52, 21.8), (104, 34.5), (208, 60), (300, 60), (400, 60)])
def test_discount(chain, deployer, alice, veyfi, discount, weeks, target):
    ts = (chain.pending_timestamp // WEEK + weeks) * WEEK
    veyfi.set_locked(alice, 1, ts, sender=deployer)
    assert round(discount.discount(alice)*100/UNIT, 1) == target

def test_chainlink_oracle(project, deployer, management, yfi, veyfi):
    chainlink_oracle = project.MockPriceOracle.deploy(sender=deployer)
    discount = project.Discount.deploy(yfi, veyfi, chainlink_oracle, management, sender=deployer)
    chainlink_oracle.set_price(2 * UNIT, sender=deployer)
    assert discount.spot_price() == 2 * UNIT

def test_stale_chainlink_oracle(project, chain, deployer, management, yfi, veyfi):
    chainlink_oracle = project.MockPriceOracle.deploy(sender=deployer)
    discount = project.Discount.deploy(yfi, veyfi, chainlink_oracle, management, sender=deployer)
    chainlink_oracle.set_price(2 * UNIT, sender=deployer)
    assert discount.spot_price() == 2 * UNIT

    chain.mine(timestamp=chain.pending_timestamp + 2 * 60 * 60)
    with ape.reverts():
        discount.spot_price()

def test_set_team_allowances_privilege(alice, discount):
    with ape.reverts():
        discount.set_team_allowances([alice], [UNIT], sender=alice)

def test_set_team_allowances(chain, management, alice, bob, discount):
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    assert discount.month() == 0
    assert discount.expiration() == 0
    assert discount.team_allowance(alice) == 0
    assert discount.team_allowance(bob) == 0

    discount.set_team_allowances([alice, bob], [UNIT, 2 * UNIT], sender=management)
    assert discount.month() == 1
    assert discount.expiration() == ts
    assert discount.team_allowance(alice) == UNIT
    assert discount.team_allowance(bob) == 2 * UNIT

def test_set_new_team_allowances(chain, management, alice, bob, discount):
    discount.set_team_allowances([alice, bob], [UNIT, 2 * UNIT], sender=management)
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    discount.set_team_allowances([alice], [2 * UNIT], sender=management)
    assert discount.month() == 2
    assert discount.expiration() == ts
    assert discount.team_allowance(alice) == 2 * UNIT
    assert discount.team_allowance(bob) == 0

def test_overwrite_team_allowances(chain, management, alice, bob, discount):
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    discount.set_team_allowances([alice, bob], [UNIT, UNIT], sender=management)
    discount.set_team_allowances([alice], [2 * UNIT], False, sender=management)
    assert discount.month() == 1
    assert discount.expiration() == ts
    assert discount.team_allowance(alice) == 2 * UNIT
    assert discount.team_allowance(bob) == UNIT

def test_team_allowances_expiry(chain, management, alice, bob, discount):
    ts = chain.pending_timestamp + ALLOWANCE_EXPIRATION_TIME
    discount.set_team_allowances([alice], [UNIT], sender=management)
    chain.mine(timestamp=ts - 1)
    assert discount.team_allowance(alice) == UNIT
    chain.mine(timestamp=ts)
    assert discount.team_allowance(alice) == 0

    with ape.reverts('allowance expired'):
        discount.set_contributor_allowances([bob], [UNIT], sender=alice)

def test_team_allowances_new_month(management, alice, bob, charlie, discount):
    discount.set_team_allowances([alice], [UNIT], sender=management)
    discount.set_team_allowances([bob], [UNIT], sender=management)
    assert discount.team_allowance(alice) == 0

    with ape.reverts('allowance expired'):
        discount.set_contributor_allowances([charlie], [UNIT], sender=alice)

def test_set_contributor_allowances_privilege(alice, bob, discount):
    with ape.reverts():
        discount.set_contributor_allowances([bob], [UNIT], sender=alice)

def test_set_contributor_allowances(management, alice, bob, charlie, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    assert discount.contributor_allowance(bob) == 0
    assert discount.contributor_allowance(charlie) == 0
    discount.set_contributor_allowances([bob, charlie], [UNIT, 2 * UNIT], sender=alice)
    assert discount.team_allowance(alice) == 0
    assert discount.contributor_allowance(bob) == UNIT
    assert discount.contributor_allowance(charlie) == 2 * UNIT

def test_set_contributor_allowances_excess(management, alice, bob, discount):
    discount.set_team_allowances([alice], [UNIT], sender=management)
    with ape.reverts():
        discount.set_contributor_allowances([bob], [2 * UNIT], sender=alice)

def test_set_contributor_allowances_multiple(management, alice, bob, charlie, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    assert discount.team_allowance(alice) == 2 * UNIT
    assert discount.contributor_allowance(bob) == UNIT
    assert discount.contributor_allowance(charlie) == 0
    discount.set_contributor_allowances([charlie], [UNIT], sender=alice)
    assert discount.team_allowance(alice) == UNIT
    assert discount.contributor_allowance(charlie) == UNIT

def test_set_contributor_allowances_add(management, alice, bob, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    assert discount.team_allowance(alice) == 2 * UNIT
    assert discount.contributor_allowance(bob) == UNIT
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    assert discount.team_allowance(alice) == UNIT
    assert discount.contributor_allowance(bob) == 2 * UNIT

def test_set_contributor_allowances_add_multiple_teams(management, alice, bob, charlie, discount):
    discount.set_team_allowances([alice, bob], [UNIT, 2 * UNIT], sender=management)
    discount.set_contributor_allowances([charlie], [UNIT], sender=alice)
    discount.set_contributor_allowances([charlie], [2 * UNIT], sender=bob)
    assert discount.contributor_allowance(charlie) == 3 * UNIT

def test_set_contributor_allowances_expiry(management, alice, bob, charlie, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [2 * UNIT], sender=alice)
    discount.set_team_allowances([charlie], [3 * UNIT], sender=management)
    assert discount.contributor_allowance(bob) == 0

def test_set_contributor_allowances_new_month(chain, management, alice, bob, discount):
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [2 * UNIT], sender=alice)
    chain.pending_timestamp += ALLOWANCE_EXPIRATION_TIME
    chain.mine()
    assert discount.contributor_allowance(bob) == 0

def test_preview(chain, deployer, alice, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 4 * WEEK, sender=deployer)
    assert discount.preview(alice, UNIT * 18 // 10, False) == UNIT

def test_preview_max(chain, deployer, alice, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    assert discount.preview(alice, UNIT, False) == DISCOUNT_SCALE * UNIT // (2 * MIN_MULTIPLIER)

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
    with ape.reverts('lock too short'):
        discount.preview(alice, UNIT, False)

def test_min_lock(chain, deployer, alice, bob, veyfi, discount):
    assert discount.min_lock(alice, False, sender=alice) == False
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 2 * WEEK, sender=deployer)
    assert discount.min_lock(alice, False, sender=alice) == False
    veyfi.set_locked(alice, UNIT, chain.pending_timestamp // WEEK * WEEK + 4 * WEEK, sender=deployer)
    assert discount.min_lock(alice, False, sender=alice) == True

    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 2 * WEEK, sender=deployer)
    assert discount.min_lock(bob, True, sender=alice) == False
    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 104 * WEEK, sender=deployer)
    assert discount.min_lock(bob, True, sender=alice) == True

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
    with ape.reverts('delegate lock too short'):
        discount.preview(alice, UNIT, True)

def test_buy(chain, deployer, management, alice, bob, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    value = UNIT * 18 // 10
    discount.set_team_allowances([alice], [value], sender=management)
    discount.set_contributor_allowances([bob], [value], sender=alice)
    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 4 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    with ape.reverts('price change'):
        discount.buy(UNIT + 1, value=UNIT, sender=bob)

    amount = discount.buy(0, value=value, sender=bob).return_value
    assert amount == UNIT
    assert veyfi.locked(bob).amount == 2 * UNIT
    assert discount.contributor_allowance(bob) == 0
    assert yfi.balanceOf(discount) == 9 * UNIT
    assert yfi.balanceOf(veyfi) == UNIT

def test_buy_max(chain, deployer, management, alice, bob, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [3 * UNIT], sender=alice)
    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    expected = DISCOUNT_SCALE * UNIT // (2 * MIN_MULTIPLIER)
    prev = management.balance
    amount = discount.buy(0, value=UNIT, sender=bob).return_value
    assert amount == expected
    assert veyfi.locked(bob).amount == UNIT + expected
    assert discount.contributor_allowance(bob) == 2 * UNIT
    assert yfi.balanceOf(discount) == 10 * UNIT - expected
    assert yfi.balanceOf(veyfi) == expected
    assert management.balance == prev + UNIT

def test_buy_expire(chain, deployer, management, alice, bob, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    discount.set_team_allowances([alice], [UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    chain.pending_timestamp += ALLOWANCE_EXPIRATION_TIME
    with ape.reverts('allowance expired'):
        discount.buy(0, value=UNIT, sender=bob)

def test_buy_new_month(chain, deployer, management, alice, bob, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    discount.set_team_allowances([alice], [UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    discount.set_team_allowances([alice], [UNIT], sender=management)
    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    chain.pending_timestamp += 30 * DAY
    with ape.reverts('allowance expired'):
        discount.buy(0, value=UNIT, sender=bob)

def test_buy_exceed(chain, deployer, management, alice, bob, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    discount.set_team_allowances([alice], [UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    with ape.reverts():
        discount.buy(0, value=2 * UNIT, sender=bob)

def test_buy_no_lock(chain, deployer, management, alice, bob, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [3 * UNIT], sender=alice)
    yfi.mint(discount, 10 * UNIT, sender=deployer)
    now = chain.pending_timestamp // WEEK * WEEK
    
    # no lock
    with ape.reverts():
        discount.buy(0, value=UNIT, sender=bob)
    
    # expired lock
    veyfi.set_locked(bob, UNIT, now - 2 * WEEK, sender=deployer)
    with ape.reverts():
        discount.buy(0, value=UNIT, sender=bob)

    # too short lock
    veyfi.set_locked(bob, UNIT, now + 2 * WEEK, sender=deployer)
    with ape.reverts('lock too short'):
        discount.buy(0, value=UNIT, sender=bob)

    veyfi.set_locked(bob, UNIT, now + 4 * WEEK, sender=deployer)
    discount.buy(0, value=UNIT, sender=bob)

def test_buy_callback(chain, deployer, management, alice, bob, yfi, veyfi, oracle, discount, callback):
    oracle.set_price(2 * UNIT, sender=deployer)
    discount.set_team_allowances([alice], [UNIT], sender=management)
    discount.set_contributor_allowances([bob], [UNIT], sender=alice)
    veyfi.set_locked(bob, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    expected = DISCOUNT_SCALE * UNIT // (2 * MIN_MULTIPLIER)
    discount.buy(0, bob, callback, value=UNIT, sender=bob)
    assert callback.last_lock() == bob
    assert callback.last_account() == bob
    assert callback.last_amount_spent() == UNIT
    assert callback.last_amount_locked() == expected

def test_buy_delegate(chain, deployer, management, alice, bob, charlie, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    value = UNIT * 18 // 10
    discount.set_team_allowances([alice], [value], sender=management)
    discount.set_contributor_allowances([bob], [value], sender=alice)
    veyfi.set_locked(charlie, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    amount = discount.buy(0, charlie, value=value, sender=bob).return_value
    assert amount == UNIT
    assert veyfi.locked(charlie).amount == 2 * UNIT
    assert discount.contributor_allowance(bob) == 0
    assert yfi.balanceOf(discount) == 9 * UNIT
    assert yfi.balanceOf(veyfi) == UNIT

def test_buy_delegate_callback(chain, deployer, management, alice, bob, charlie, yfi, veyfi, oracle, discount, callback):
    oracle.set_price(2 * UNIT, sender=deployer)
    value = UNIT * 18 // 10
    discount.set_team_allowances([alice], [value], sender=management)
    discount.set_contributor_allowances([bob], [value], sender=alice)
    veyfi.set_locked(charlie, UNIT, chain.pending_timestamp // WEEK * WEEK + 5 * 52 * WEEK, sender=deployer)
    yfi.mint(discount, 10 * UNIT, sender=deployer)

    discount.buy(0, charlie, callback, value=value, sender=bob)
    assert callback.last_lock() == charlie
    assert callback.last_account() == bob
    assert callback.last_amount_spent() == value
    assert callback.last_amount_locked() == UNIT

def test_buy_delegate_no_lock(chain, deployer, management, alice, bob, charlie, yfi, veyfi, oracle, discount):
    oracle.set_price(2 * UNIT, sender=deployer)
    discount.set_team_allowances([alice], [3 * UNIT], sender=management)
    discount.set_contributor_allowances([bob], [3 * UNIT], sender=alice)
    yfi.mint(discount, 10 * UNIT, sender=deployer)
    now = chain.pending_timestamp // WEEK * WEEK
    
    # no lock
    with ape.reverts():
        discount.buy(0, charlie, value=UNIT, sender=bob)
    
    # expired lock
    veyfi.set_locked(charlie, UNIT, now - 2 * WEEK, sender=deployer)
    with ape.reverts():
        discount.buy(0, charlie, value=UNIT, sender=bob)

    # too short lock
    veyfi.set_locked(charlie, UNIT, now + 2 * WEEK, sender=deployer)
    with ape.reverts('delegate lock too short'):
        discount.buy(0, charlie, value=UNIT, sender=bob)

    veyfi.set_locked(charlie, UNIT, now + 5 * 52 * WEEK, sender=deployer)
    discount.buy(0, charlie, value=UNIT, sender=bob)
