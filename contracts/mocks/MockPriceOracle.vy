struct LatestRoundData:
    round_id: uint80
    answer: int256
    started: uint256
    updated: uint256
    answered_round: uint80

decimals: public(constant(uint256)) = 18
price: uint256
updated: uint256

@external
def set_price(_price: uint256, _updated: uint256 = block.timestamp):
    self.price = _price
    self.updated = _updated

@external
@view
def latestRoundData() -> LatestRoundData:
    return LatestRoundData({round_id: 1, answer: convert(self.price, int256), started: self.updated, updated: self.updated, answered_round: 1})

@external
@view
def price_oracle() -> uint256:
    return self.price
