"""PyCharm entry point: prepare a pilot plan without starting a long study."""
from pathlib import Path
from rsi_game.v05.experiments import plan
from rsi_game.v05.storage import atomic
if __name__ == '__main__':
    root=Path(__file__).resolve().parent
    target=root/'results/v05/pilot-plan.json'
    atomic(target,plan('core','pilot'))
    print(f'Prepared {target}')
    print('Run from this project directory:')
    print(f'{root / ".venv/bin/python"} -m rsi_game.v05 suite --plan results/v05/pilot-plan.json --output results/v05/pilot/core --workers 2')
