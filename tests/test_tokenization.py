import pytest
import scanpy as sc


from geniml.io.io import Region, RegionSet
from geniml.tokenization.main import InMemTokenizer


@pytest.fixture
def pbmc_data():
    return sc.read_h5ad("tests/data/pbmc_hg38.h5ad")


@pytest.fixture
def pbmc_data_backed():
    return sc.read_h5ad("tests/data/pbmc_hg38.h5ad", backed="r")


@pytest.fixture
def universe_bed_file():
    return "tests/data/universe.bed"


def test_create_universe(universe_bed_file: str):
    u = RegionSet(universe_bed_file)
    assert u is not None
    assert len(u) == 2_433


def test_make_in_mem_tokenizer_from_file(universe_bed_file: str):
    t = InMemTokenizer(universe_bed_file)
    assert len(t.universe) == 2_433
    assert t is not None


def test_make_in_mem_tokenizer_from_region_set(universe_bed_file: str):
    u = RegionSet(universe_bed_file)
    t = InMemTokenizer(u)
    assert t is not None


def test_tokenize_bed_file(universe_bed_file: str):
    """
    Use the in memory tokenizer to tokenize a bed file.

    The bed file contains 13 regions, 10 of which are in the universe. None
    of them should be the original regions in the file.
    """
    t = InMemTokenizer(universe_bed_file)
    assert t is not None

    # tokenize a bed file
    bed_file = "tests/data/to_tokenize.bed"

    # read in the bed file to test
    with open(bed_file, "r") as f:
        lines = f.readlines()
        regions = []
        for line in lines:
            chr, start, stop = line.strip().split("\t")
            regions.append(Region(chr, int(start), int(stop)))

    tokens = t.tokenize(bed_file, return_all=True)

    # ensure that the tokens are unqiue from the original regions
    assert len(set(tokens).intersection(set(regions))) == 0
    assert len([t for t in tokens if t is not None]) == 3


def test_tokenize_list_of_regions(universe_bed_file: str):
    """
    Use the in memory tokenizer to tokenize a list of regions.

    The bed file contains 13 regions, 10 of which are in the universe. None
    of them should be the original regions in the file.
    """
    t = InMemTokenizer(universe_bed_file)
    assert t is not None

    # tokenize a bed file
    bed_file = "tests/data/to_tokenize.bed"

    # read in each and cast as a region
    with open(bed_file, "r") as f:
        lines = f.readlines()
        regions = []
        for line in lines:
            chr, start, stop = line.strip().split("\t")
            regions.append(Region(chr, int(start), int(stop)))

    tokens = t.tokenize(regions, return_all=True)

    # ensure that the tokens are unqiue from the original regions
    assert len(set(tokens).intersection(set(regions))) == 0
    assert len([t for t in tokens if t is not None]) == 3


def test_convert_to_ids(universe_bed_file: str):
    t = InMemTokenizer(universe_bed_file)
    assert t is not None

    # tokenize a bed file
    bed_file = "tests/data/to_tokenize.bed"

    # read in each and cast as a region
    with open(bed_file, "r") as f:
        lines = f.readlines()
        regions = []
        for line in lines:
            chr, start, stop = line.strip().split("\t")
            regions.append(Region(chr, int(start), int(stop)))

    tokens = t.tokenize(regions)
    ids = t.convert_tokens_to_ids(tokens)

    assert len(ids) == len(tokens)
    assert all(isinstance(i, int) or i is None for i in ids)


def test_tokenize_anndata(universe_bed_file: str, pbmc_data: sc.AnnData):
    t = InMemTokenizer(universe_bed_file)
    assert t is not None

    tokens = t.tokenize(pbmc_data, return_all=True)

    # returns list of regions for each cell
    assert len(tokens) == pbmc_data.shape[0]


@pytest.mark.skip(reason="This test is not working yet")
def test_tokenize_anndata_backed(universe_bed_file: str, pbmc_data_backed: sc.AnnData):
    t = InMemTokenizer(universe_bed_file)
    assert t is not None

    tokens = t.tokenize(pbmc_data_backed)

    assert len(tokens) == pbmc_data_backed.shape[0]
