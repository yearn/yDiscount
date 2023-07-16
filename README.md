# yDiscount

Implementation of [yDiscount segment of YIP-66](https://gov.yearn.finance/t/yip-66-streamlining-contributor-compensation/12247#h-2-contributors-are-rewarded-with-yfi-tokens-through-ydiscount-25), giving contributors opportunity to buy locked YFI at a discount

### Install dependencies
```sh
# Install foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup
# Install ape
pip install eth-ape
# Install required ape plugins
ape plugins install .
```

### Run tests
```sh
ape test
ape test tests/fork.py --network ethereum:mainnet-fork
```

## YIP-66 specification
From [YIP-66](https://gov.yearn.finance/t/yip-66-streamlining-contributor-compensation/12247#h-2-contributors-are-rewarded-with-yfi-tokens-through-ydiscount-25):


> - All contributors being compensated as per the previous point have the option to purchase YFI through a new yDiscount program.
> - Contributors can purchase YFI at discounts to current YFI market price, subject to their current veYFI lock. The longer the ve-YFI lock, the greater the discount.
> - YFI purchased through this program are immediately locked into veYFI according to the duration of their lock.
> - Contributors are only eligible to purchase YFI up to 100% of the compensation amount they received that month, once the discount has been factored in.
> - Once feasible, the intention is to have these operations occuring on chain each month with contributors directly interacting with smart contracts. Until then, manual off-chain calculations are used.
> - Contributors are only allowed to participate with one ethereum wallet address in the program, which can only have one single ve-YFI lock at any time.
> - Changing a participating wallet address is only permitted in exceptional circumstances and requires yPeople approval.
> - The YFI minted with YIP-57 is used to finance this program, and once this has been depleted, yBudget will allocate YFI from treasury buybacks.
> - Funds received from contributors participating in yDiscount is used for more YFI buybacks.
> - yBudget has the power to pause the yDiscount program at their discretion.

### Discount calculation

```
# yfi_discount: discount (%) of purchased YFI
# ve_lock: current weeks locked in veYFI
yfi_discount = 0.00245 * ve_lock + 0.0902
```

|% of max lock| duration| 	ve_lock| 	yfi_discount|
|---|---|---:|---:|
|1.92%| 1 month| 	4| 	10%
11.5% |6 months| 	24| 	14.9%
25% |1 year |	52| 	21.8%
50% |	2 years |	104| 	34.5%
100% |	4 years| 	208 |	60%

### YFI purchase allowance

```
# yfi_allowed: total YFI allowed to purchase this month
# comp: contributor compensation in stables this month
# yfi_price: current YFI price in stables
yfi_allowed = comp / ((1 - yfi_discount) * yfi_price)
```

## Adjustments to the spec

### 1. Relax one global address per contributor

> - Contributors are only allowed to participate with one ethereum wallet address in the program, which can only have one single ve-YFI lock at any time.

With the transition into teams we should enforce one address per contributor per team. I.e. it's acceptable for one contributor to be member of many teams and use one address, but also ok for one contributor to have many addresses for many teams. But NOT many addresses for one team.

### 2. Relax address changes

> - Changing a participating wallet address is only permitted in exceptional circumstances and requires yPeople approval.

While we should not encourage address (and thereby veYFI lock) rotation, we propose we relax the policing of this.

### 3. Allow min_discount delegated locking

The YIP sets veYFI `min_lock` duration in order to be eligible for yDiscount to 4 weeks, which gives the contributor right to purchase YFI at 10% discount which is then locked for 4 weeks.

However, the `early_exit` scheme of veYFI that was introduced after this YIP introduces a theoretical loophole, where a contributor can: 
* lock min amount of 1 YFI for 4 weeks
* buy YFI at 10% discount that also gets locked for 4 weeks
* exit early immediately thereafter and pay 1.92%  penalty on the total amount resulting in an `8.08% - 0.0192` YFI profit if sold immediately on the market

The incentives are there for this to be maximized by rational contributors, encouraging low locking and increased YFI sell pressure.

To mitigate this, we propose to allow for delegated locking to third parties, effectively "selling" their yDiscount, at the minimum discount, if the third parties have long locks.

Contributors can delegate their yDiscount to third parties, _as long as the third party's lock duration is greater or equal to 2 years_, for a flat 10% discount.

Rationale: This is net equal or better for Yearn, as it removes the incentive to min lock, exit early, and dump. Instead conributors can earn the min discount by delegating to a third party that has a longer lock than they have. Income stays the same, and YFI does not hit the market. 

## Implementation requirements

### General
- All contracts immutable, non-upgradeable
- Updates require contract redeployment

### yDiscount allowances 
- At the beginning of a month, yBudget gives yDiscount allowances to teams (team gnosis safe), in ETH. These amounts refer to the _previous_ month
    - For revenue sharing teams, the allowance is equal to the team's share of the revenue of the past month
    - For teams with a budget, the allowance is equal to the sum of the total contributor compensation of the past month
    - For teams that have both, the allowance is the sum of the above two
- Teams then distribute this allowance amongst their contributors (individual addresses)
- A contributor allowance is not allowed to exceed its received compensation, though this is not enforced on a smart contract level
- All allowances expire after 30 days or whenever a new allowance is set, whichever happens first
- Any non-ETH compensation amounts are converted to ETH using the average price of the assets in the past month

### YFI purchases

* Once a contributor has been given an allowance to purchase YFI, they may interact with yDiscount smart contracts to do so.
* The yDiscount contracts looks up the veYFI lock duration of the address to determine the applicable discount.
* In accordance with the YIP, total amount available for purchase [is influenced by the discount](#YFI-purchase-allowance).
* YFI price is current spot price, using Chainlink oracle for YFI/ETH.
* Contributor has the option to purchase any granular amount up to the max.
* Contributor may make multiple purchases during the month, until allowance expires.
* yBudget keeps yDiscount topped up by transferring YFI to the contract.
* If the Contributor elects to delegate to a third party address, the discount is hard coded to 10%. The transaction reverts if the third party's address has a lock duration that is less than 2 years (104 weeks).

### Abuse
- Any party, whether individual contributor or entire team, found abusing yDiscount will be disqualified from the program
- Examples of abuse include but are not limited to:
   - Locking small quantities and using early exit to manipulate returns
   - Using multiple addresses to manage lock durations
   - Inflating or pooling individual allowances

### Future possibilities

- Extend protocol to handle team veYFI bonus program
