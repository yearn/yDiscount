# @version 0.3.7
"""
@title yDiscount
@author Yearn Finance
@license AGPLv3
"""

from vyper.interfaces import ERC20

struct LockedBalance:
    amount: uint256
    end: uint256

struct LatestRoundData:
    round_id: uint80
    answer: int256
    started: uint256
    updated: uint256
    answered_round: uint80

interface VotingEscrow:
    def locked(_account: address) -> LockedBalance: view
    def modify_lock(_amount: uint256, _unlock_time: uint256, _account: address) -> LockedBalance: nonpayable

interface ChainlinkOracle:
    def latestRoundData() -> LatestRoundData: view

interface CurveOracle:
    def price_oracle() -> uint256: view

interface DiscountCallback:
    def delegated(_lock: address, _account: address, _amount_spent: uint256, _amount_locked: uint256): nonpayable

yfi: public(immutable(ERC20))
veyfi: public(immutable(VotingEscrow))
chainlink_oracle: public(immutable(ChainlinkOracle))
curve_oracle: public(immutable(CurveOracle))
management: public(immutable(address))

team_allowances: HashMap[address, uint256] # team -> allowance
contributor_allowances: HashMap[address, HashMap[address, uint256]] # team -> contributor -> allowance

SCALE: constant(uint256) = 10**18
CHAINLINK_PRICE_SCALE: constant(uint256) = 10**10
PRICE_DISCOUNT_SLOPE: constant(uint256) = 245096 * 10**10
PRICE_DISCOUNT_BIAS: constant(uint256) = 9019616 * 10**10
DELEGATE_DISCOUNT: constant(uint256) = 10**17

ALLOWANCE_EXPIRATION_TIME: constant(uint256) = 30 * 24 * 60 * 60
ORACLE_STALE_TIME: constant(uint256) = 2 * 60 * 60
WEEK: constant(uint256) = 7 * 24 * 60 * 60
MIN_LOCK_WEEKS: constant(uint256) = 4
DELEGATE_MIN_LOCK_WEEKS: constant(uint256) = 104
CAP_DISCOUNT_WEEKS: constant(uint256) = 208

ALLOWANCE_MASK: constant(uint256) = 2**192 - 1
EXPIRATION_SHIFT: constant(int128) = -192
EXPIRATION_MASK: constant(uint256) = 2**64 - 1

event TeamAllowance:
    team: indexed(address)
    allowance: uint256
    expiration: uint256

event ContributorAllowance:
    team: indexed(address)
    contributor: indexed(address)
    allowance: uint256
    expiration: uint256

event Buy:
    contributor: indexed(address)
    amount_in: uint256
    amount_out: uint256
    discount: uint256
    lock: address

@external
def __init__(_yfi: address, _veyfi: address, _chainlink_oracle: address, _curve_oracle: address, _management: address):
    yfi = ERC20(_yfi)
    veyfi = VotingEscrow(_veyfi)
    chainlink_oracle = ChainlinkOracle(_chainlink_oracle)
    curve_oracle = CurveOracle(_curve_oracle)
    management = _management
    assert ERC20(_yfi).approve(_veyfi, max_value(uint256), default_return_value=True)

@external
@view
def team_allowance(_team: address) -> (uint256, uint256):
    allowance: uint256 = 0
    expiration: uint256 = 0
    allowance, expiration = self._unpack_allowance(self.team_allowances[_team])
    if block.timestamp >= expiration:
        return 0, 0
    return allowance, expiration

@external
@view
def contributor_allowance(_team: address, _contributor: address) -> (uint256, uint256):
    allowance: uint256 = 0
    expiration: uint256 = 0
    allowance, expiration = self._unpack_allowance(self.contributor_allowances[_team][_contributor])
    if block.timestamp >= expiration:
        return 0, 0
    return allowance, expiration

@external
def set_team_allowances(_teams: DynArray[address, 256], _allowances: DynArray[uint256, 256], _expiration: uint256 = 0):
    assert msg.sender == management
    assert len(_teams) == len(_allowances)

    expiration: uint256 = _expiration
    if _expiration == 0:
        expiration = block.timestamp + ALLOWANCE_EXPIRATION_TIME
    else:
        assert _expiration > block.timestamp

    for i in range(256):
        if i == len(_teams):
            break
        self.team_allowances[_teams[i]] = self._pack_allowance(_allowances[i], expiration)
        log TeamAllowance(_teams[i], _allowances[i], expiration)

@external
def set_contributor_allowances(_contributors: DynArray[address, 256], _allowances: DynArray[uint256, 256]):
    assert len(_contributors) == len(_allowances)

    team_allowance: uint256 = 0
    expiration: uint256 = 0
    team_allowance, expiration = self._unpack_allowance(self.team_allowances[msg.sender])
    assert team_allowance > 0
    assert expiration > block.timestamp

    for i in range(256):
        if i == len(_contributors):
            break
        team_allowance -= _allowances[i]
        contributor_allowance: uint256 = 0
        contributor_expiration: uint256 = 0
        contributor_allowance, contributor_expiration = self._unpack_allowance(self.contributor_allowances[msg.sender][_contributors[i]])
        if contributor_expiration != expiration:
            contributor_allowance = 0
        contributor_allowance += _allowances[i]

        self.contributor_allowances[msg.sender][_contributors[i]] = self._pack_allowance(contributor_allowance, expiration)
        log ContributorAllowance(msg.sender, _contributors[i], contributor_allowance, expiration)

    self.team_allowances[msg.sender] = self._pack_allowance(team_allowance, expiration)

@internal
@view
def _spot_price() -> uint256:
    data: LatestRoundData = chainlink_oracle.latestRoundData()
    price: uint256 = 0
    if block.timestamp < data.updated + ORACLE_STALE_TIME:
        price = convert(data.answer, uint256) * CHAINLINK_PRICE_SCALE
    return max(price, curve_oracle.price_oracle())

@external
@view
def spot_price() -> uint256:
    return self._spot_price()

@internal
@view
def _discount(_account: address) -> (uint256, uint256):
    locked: LockedBalance = veyfi.locked(_account)
    assert locked.amount > 0
    weeks: uint256 = min(locked.end / WEEK - block.timestamp / WEEK, CAP_DISCOUNT_WEEKS)
    return weeks, PRICE_DISCOUNT_BIAS + PRICE_DISCOUNT_SLOPE * weeks

@external
@view
def discount(_account: address) -> uint256:
    weeks: uint256 = 0
    discount: uint256 = 0
    weeks, discount = self._discount(_account)
    return discount

@internal
@view
def _preview(_lock: address, _amount_in: uint256, _delegate: bool) -> (uint256, uint256):
    locked: LockedBalance = veyfi.locked(_lock)
    assert locked.amount > 0

    weeks: uint256 = 0
    discount: uint256 = 0
    weeks, discount = self._discount(_lock)
    price: uint256 = self._spot_price()
    if _delegate:
        assert weeks >= DELEGATE_MIN_LOCK_WEEKS, "delegate lock too short"
        discount = DELEGATE_DISCOUNT
    else:
        assert weeks >= MIN_LOCK_WEEKS, "lock too short"
    price = price * (SCALE - discount) / SCALE
    return _amount_in * SCALE / price, discount

@external
@view
def preview(_lock: address, _amount_in: uint256, _delegate: bool) -> uint256:
    amount: uint256 = 0
    discount: uint256 = 0
    amount, discount = self._preview(_lock, _amount_in, _delegate)
    return amount

@external
@payable
def buy(_teams: DynArray[address, 16], _min_locked: uint256, _lock: address = msg.sender, _callback: address = empty(address)):
    left: uint256 = msg.value
    assert left > 0
    for i in range(16):
        if i == len(_teams):
            break
        allowance: uint256 = 0
        expiration: uint256 = 0
        allowance, expiration = self._unpack_allowance(self.contributor_allowances[_teams[i]][msg.sender])
        if block.timestamp >= expiration:
            continue
        if allowance > left:
            allowance -= left
            left = 0
        else:
            allowance = 0
            expiration = 0 # clear entire slot
            left -= allowance
        self.contributor_allowances[_teams[i]][msg.sender] = self._pack_allowance(allowance, expiration)
        if left == 0:
            break
    assert left == 0, "insufficient allowance"

    # reverts if user has no lock or duration is too short
    locked: uint256 = 0
    discount: uint256 = 0
    locked, discount = self._preview(_lock, msg.value, _lock != msg.sender)
    assert locked >= _min_locked

    veyfi.modify_lock(locked, 0, _lock)
    if _callback != empty(address):
        DiscountCallback(_callback).delegated(_lock, msg.sender, msg.value, locked)

    raw_call(management, b"", value=msg.value)
    log Buy(msg.sender, msg.value, locked, discount, _lock)

@external
def withdraw(_token: address, _amount: uint256):
    assert msg.sender == management
    assert ERC20(_token).transfer(msg.sender, _amount, default_return_value=True)

@internal
@pure
def _pack_allowance(_allowance: uint256, _expiration: uint256) -> uint256:
    assert _allowance <= ALLOWANCE_MASK and _expiration <= EXPIRATION_MASK
    return _allowance | shift(_expiration, -EXPIRATION_SHIFT)

@internal
@pure
def _unpack_allowance(_packed: uint256) -> (uint256, uint256):
    return _packed & ALLOWANCE_MASK, shift(_packed, EXPIRATION_SHIFT)
