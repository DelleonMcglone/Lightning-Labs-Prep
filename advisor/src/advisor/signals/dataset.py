"""Inter-quartile-range outlier detection, ported from Faraday's `dataset`
package (see ../../repo-reviews/faraday.md §2d).

Faithful to the Go original:
- quartiles use the "exclusive" method — split the sorted data in half,
  excluding the median element when the count is odd;
- a value is a lower outlier when  value < LQ − (IQR × multiplier),
  an upper outlier when            value > UQ + (IQR × multiplier);
- fewer than 3 values → no quartiles → every point reports non-outlier.

Multiplier semantics (from Faraday's docs): 1.5 = aggressive ("weak"
outliers), 3 = cautious ("strong" outliers, the default).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

DEFAULT_OUTLIER_MULTIPLIER = 3.0


@dataclass(frozen=True)
class OutlierResult:
    upper_outlier: bool
    lower_outlier: bool


def _median(sorted_values: list) -> float:
    n = len(sorted_values)
    if n == 0:
        raise ValueError("can't calculate median for zero length array")
    if n % 2 == 0:
        return (sorted_values[(n - 1) // 2] + sorted_values[n // 2]) / 2
    return sorted_values[n // 2]


class Dataset(Dict[str, float]):
    """A labelled set of float values (label → value), e.g. chan_point → sats."""

    def quartiles(self) -> Optional[Tuple[float, float]]:
        """(lower, upper) quartiles, or None if fewer than 3 values."""
        n = len(self)
        if n < 3:
            return None
        values = sorted(self.values())
        if n % 2 == 0:
            cutoff_lower = cutoff_upper = n // 2
        else:
            cutoff_lower = (n - 1) // 2
            cutoff_upper = cutoff_lower + 1
        return _median(values[:cutoff_lower]), _median(values[cutoff_upper:])

    def get_outliers(
        self, multiplier: float = DEFAULT_OUTLIER_MULTIPLIER
    ) -> Dict[str, OutlierResult]:
        """Classify every labelled value as upper/lower/non-outlier."""
        q = self.quartiles()
        if q is None:
            return {
                label: OutlierResult(False, False) for label in self
            }
        lower_q, upper_q = q
        distance = (upper_q - lower_q) * multiplier
        return {
            label: OutlierResult(
                upper_outlier=value > upper_q + distance,
                lower_outlier=value < lower_q - distance,
            )
            for label, value in self.items()
        }

    def get_threshold(
        self, threshold: float, below: bool = True
    ) -> Dict[str, bool]:
        """Flag values <= threshold (below=True) or > threshold (below=False)."""
        if below:
            return {label: value <= threshold for label, value in self.items()}
        return {label: value > threshold for label, value in self.items()}
