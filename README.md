# Custom Tools

For development use within Pycharm.

## setup

Add the following lines to Pycharm's start up script.

```python
import sys

sys.path.append('/Users/Maximillion/Developer/pycharm/custom-tools')
import mytools  # mytools.inline_src

```

## usage

```python
import mytools


def break_even_win_rate(profit_to_loss_ratio: float) -> float:
    return 1 / (1 + profit_to_loss_ratio)


mytools.inline_src(break_even_win_rate(2))
# prints out the following:
# # ------------------------ original def: 
# def break_even_win_rate(profit_to_loss_ratio: float) -> float:
#     return 1 / (1 + profit_to_loss_ratio)
# # ------------------ inlined code block:
# profit_to_loss_ratio = 2
# break_even_win_rate_ret = 1 / (1 + profit_to_loss_ratio)
# # --------------------------------------
```

## other integrations

* [sorcery](https://github.com/alexmojaki/sorcery) for magic spell
* [incant](https://github.com/Tinche/incant) for dependency injection
* [tree-sitter](https://tree-sitter.github.io/tree-sitter/) for parsing with sample
  usage [auto-code-rover](https://github.com/nus-apr/auto-code-rover)
