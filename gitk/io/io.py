from ..utils import *
from typing import List

from intervaltree import Interval


class Region(Interval):
    def __new__(cls, chr: str, start: int, stop: int, data=None):
        return super(Region, cls).__new__(cls, start, stop, data)

    def __init__(self, chr: str, start: int, stop: int, data=None):
        # no need to call super().__init__() because namedtuple doesn't have __init__()
        self.chr = chr

    @property
    def start(self):
        return self.begin

    def __repr__(self):
        return f"Region({self.chr}, {self.start}, {self.end})"


# TODO: This belongs somewhere else
class RegionSet(object):
    def __init__(self, path: str, backed: bool = False):
        self.backed = backed
        self.regions: List[Region] = []
        self.path = path
        if backed:
            self.regions = None
            # https://stackoverflow.com/a/32607817/13175187
            with open(self.path, "r") as file:
                self.length = sum(1 for line in file if line.strip())
        else:
            with open(path, "r") as f:
                lines = f.readlines()
                for line in lines:
                    chr, start, stop = line.split("\t")
                    self.regions.append(Region(chr, int(start), int(stop)))
                self.length = len(self.regions)

    def __len__(self):
        return self.length

    def __getitem__(self, key):
        return self.regions[key]

    def __repr__(self):
        return f"RegionSet({self.path})"

    def __iter__(self):
        if self.backed:
            with open(self.path, "r") as f:
                for line in f:
                    chr, start, stop = line.split("\t")
                    yield Region(chr, int(start), int(stop))
        else:
            for region in self.regions:
                yield region


# TODO: This belongs somewhere else; does it even make sense?
class TokenizedRegionSet(object):
    """Represents a tokenized region set"""

    def __init__(self, tokens: np.ndarray, universe: RegionSet):
        self.tokens = tokens
        self.universe = universe


# Write a class representing a collection of RegionSets
# TODO: This shouldn't read in the actual files, it should just represent the files and use lazy loading
class RegionSetCollection(object):
    """Represents a collection of RegionSets"""

    def __init__(self, region_sets: List[RegionSet] = None, file_globs: List[str] = None):
        if region_sets:
            self.region_sets = region_sets
        elif file_globs:
            self.region_sets = []
            for glob in file_globs:
                self.region_sets.extend([RegionSet(path) for path in glob.glob(glob)])

    def __getitem__(self, key):
        return self.region_sets[key]

    def __len__(self):
        return len(self.region_sets)


# Do we need an EmbeddingSet class?
class EmbeddingSet(object):
    """Represents embeddings and labels"""

    embeddings: np.ndarray
    labels: list
