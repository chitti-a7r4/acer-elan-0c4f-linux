"""Fit on labeled scores, then evaluate a frozen threshold on fresh touches."""
import hashlib
import json
import math
from pathlib import Path

STEPS = [
    ("right pinky", 3), ("second false-matching", 3),
    ("right index", 5), ("right pinky", 5), ("second false-matching", 5),
]

class Trial:
    def __init__(self, directory, template, maps, baseline):
        self.path = Path(directory) / "finger-challenge.json"
        self.baseline = baseline
        self.key = hashlib.sha256(template.read_bytes() + maps.read_bytes()).hexdigest()
        self.scores = []
        self.index_reference = []
        self.other_reference = []
        if self.path.exists():
            record = json.loads(self.path.read_text())
            if record["profile"] == self.key:
                self.scores = record["scores"]
                self.index_reference = record["index_reference"]
                self.other_reference = record["other_reference"]

    def target(self):
        offset = len(self.scores)
        for name, count in STEPS:
            if offset < count:
                return name, offset, count
            offset -= count
        return None

    def cutoff(self):
        if len(self.scores) < 6 or not self.index_reference:
            return None
        highest_other = max(self.other_reference + self.scores[:6])
        # Allow one of the five reference index touches to be rejected.
        supported_index = sorted(self.index_reference)[1]
        if highest_other >= supported_index or supported_index < self.baseline:
            return None
        return max(self.baseline, (highest_other + supported_index) / 2)

    def validated(self):
        c = self.cutoff()
        return (len(self.scores)==21 and c is not None
                and sum(v>=c for v in self.scores[6:11])>=4
                and max(self.scores[11:21])<c)

    def finished(self):
        return len(self.scores)==21 or (len(self.scores)>=6 and self.cutoff() is None)

    def add(self, value):
        if not math.isfinite(value) or self.finished():
            raise ValueError("Invalid trial result")
        self.scores.append(float(value))
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"profile":self.key,"scores":self.scores,"index_reference":self.index_reference,"other_reference":self.other_reference}))
        tmp.replace(self.path)

    def summary(self):
        if len(self.scores)==21:
            c = self.cutoff()
            return (f"Fresh touches at {c:.2f}: right index accepted {sum(x>=c for x in self.scores[6:11])}/5, "
                    f"right pinky accepted {sum(x>=c for x in self.scores[11:16])}/5, "
                    f"second other finger accepted {sum(x>=c for x in self.scores[16:21])}/5. "
                    + ("Cutoff active in this test app." if self.validated() else "Cutoff failed the test."))
        return "Scores overlap too much to reject these other fingers while accepting four of the five reference index touches."
