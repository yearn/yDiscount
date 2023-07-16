# @version 0.3.7

interface DiscountCallback:
    def delegated(_lock: address, _account: address, _amount_spent: uint256, _amount_locked: uint256): nonpayable

implements: DiscountCallback

last_lock: public(address)
last_account: public(address)
last_amount_spent: public(uint256)
last_amount_locked: public(uint256)

@external
def delegated(_lock: address, _account: address, _amount_spent: uint256, _amount_locked: uint256):
    self.last_lock = _lock
    self.last_account = _account
    self.last_amount_spent = _amount_spent
    self.last_amount_locked = _amount_locked
