from dataclasses import dataclass, field
import numpy as np

@dataclass
class FunctionState:
    belief: np.ndarray
    target: float
    bounds: tuple
    scale: float = 1.
    last_turn: int = -1
    context: np.ndarray | None = None  # simulator diagnostics only
    center: float = 0.
    amplitude: float = 0.
    mode: str = 'free'
    identification_valid: bool = False
    rank: int = 0
    condition: float | None = None
