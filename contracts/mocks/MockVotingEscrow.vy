# @version 0.3.7

from vyper.interfaces import ERC20

struct LockedBalance:
    amount: uint256
    end: uint256

yfi: ERC20
locked: public(HashMap[address, LockedBalance])

@external
def __init__(_yfi: address):
    self.yfi = ERC20(_yfi)

@external
def set_locked(_account: address, _amount: uint256, _end: uint256):
    self.locked[_account] = LockedBalance({amount: _amount, end: _end})

@external
def modify_lock(_amount: uint256, _unlock_time: uint256, _account: address) -> LockedBalance:
    assert _unlock_time == 0
    locked: LockedBalance = self.locked[_account]
    assert locked.amount > 0 and locked.end > block.timestamp
    self.locked[_account].amount += _amount
    assert self.yfi.transferFrom(msg.sender, self, _amount, default_return_value=True)
    return locked
