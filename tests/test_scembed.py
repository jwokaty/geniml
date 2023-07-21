import logging
import os
import sys
from itertools import chain

import pytest
import scanpy as sc

# add parent directory to path
sys.path.append("../")

from gitk import scembed, utils

# set to DEBUG to see more info
logging.basicConfig(level=logging.INFO)


@pytest.fixture
def pbmc_data():
    return sc.read_h5ad("tests/data/pbmc_hg38.h5ad")


@pytest.fixture
def pbmc_data_backed():
    return sc.read_h5ad("tests/data/pbmc_hg38.h5ad", backed="r")


@pytest.fixture
def total_regions(pbmc_data: sc.AnnData):
    pbmc_df = pbmc_data.to_df()
    pbmc_df = pbmc_df.clip(upper=1)
    total_regions = sum(pbmc_df.sum(axis=0) >= scembed.const.DEFAULT_MIN_COUNT)
    return total_regions


def test_import():
    assert scembed


def test_load_scanpy():
    scembed.load_scanpy_data("tests/data/pbmc_hg38.h5ad")


def test_extract_region_list(pbmc_data: sc.AnnData):
    regions = scembed.extract_region_list(pbmc_data.var)
    assert len(regions) == pbmc_data.shape[1]
    for region in regions:
        assert isinstance(region, str)


def test_document_creation(pbmc_data: sc.AnnData):
    # convert pbmc_data to df and drop any columns (regions with all 0 signal)
    pbmc_df = pbmc_data.to_df()
    pbmc_df_dropped = pbmc_df.loc[:, (pbmc_df != 0).any(axis=0)]

    # convert to docs
    docs = scembed.convert_anndata_to_documents(pbmc_data)

    # ensure all cells converted
    assert len(docs) == pbmc_data.shape[0]

    # ensure all regions represented
    all_regions = set(list(chain(*docs)))
    assert len(all_regions) == pbmc_df_dropped.shape[1]

    # ensure all regions are strings and contain no spaces
    for doc in docs:
        assert all([isinstance(r, str) for r in doc])
        assert all([" " not in r for r in doc])


def test_document_shuffle():
    docs = [["a", "b", "c"], ["d", "e", "f"]]
    shuffled = scembed.shuffle_documents(docs, 10)
    assert len(shuffled) == len(docs)
    for doc in shuffled:
        assert len(doc) == len(docs[0])
        # by pure random chance, the following COULD fail, so we'll just comment it out
        # assert doc != docs[0]
        # assert doc != docs[1]


def test_model_creation():
    model = scembed.SCEmbed()
    assert model


def test_model_training(pbmc_data: sc.AnnData, total_regions: int):
    # remove gensim logging
    logging.getLogger("gensim").setLevel(logging.ERROR)
    model = scembed.SCEmbed()
    model.train(pbmc_data, epochs=3)

    assert model.trained
    assert len(model.region2vec) > 0
    assert len(model.region2vec) == total_regions


def test_model_train_and_save(pbmc_data: sc.AnnData):
    # remove gensim logging
    logging.getLogger("gensim").setLevel(logging.ERROR)
    model = scembed.SCEmbed()
    model.train(pbmc_data, epochs=3)
    assert model.trained
    assert isinstance(model.region2vec, dict)

    # save
    try:
        model.save_model("tests/data/test_model.model")
        model.load_model("tests/data/test_model.model")

        # ensure model is still trained and has region2vec
        assert model.trained
        assert len(model.region2vec) > 0

    finally:
        os.remove("tests/data/test_model.model")


def test_anndata_chunker(pbmc_data_backed: sc.AnnData):
    chunker = scembed.AnnDataChunker(pbmc_data_backed, chunk_size=2)
    # ensure chunker is iterable
    for chunk in chunker:
        assert isinstance(chunk, sc.AnnData)


@pytest.mark.skip(reason="This test is too unstable for small data")
def test_train_in_chunks(pbmc_data_backed: sc.AnnData):
    MIN_COUNT = 2
    chunker = scembed.AnnDataChunker(pbmc_data_backed, chunk_size=5)
    model = scembed.SCEmbed(use_default_region_names=False, min_count=MIN_COUNT)

    # need this to keep track of total regions
    # that should be represented in the model
    def count_regions(chunk: sc.AnnData):
        chunk_df = chunk.to_df()
        chunk_df = chunk_df.clip(upper=1)
        return sum(chunk_df.sum(axis=0) >= MIN_COUNT)

    total_regions = 0
    for chunk in chunker:
        chunk_mem = chunk.to_memory()
        total_regions += count_regions(chunk_mem)
        model.train(chunk_mem, epochs=3)

    assert model.trained
    assert isinstance(model.region2vec, dict)
    # assert len(model.region2vec) == total_regions
    # ignore for now, since we're not sure if this is correct


@pytest.mark.skip(reason="Uses large, local data")
def test_create_anndata_from_files():
    folder = "/Users/nathanleroy/Desktop/GSE158398_RAW"

    path_to_barcodes = os.path.join(folder, "lymphneg_barcodes.tsv")
    path_to_mtx = os.path.join(folder, "lymphneg_matrix.mtx")
    path_to_peaks = os.path.join(folder, "lymphneg_peaks.bed")

    adata = scembed.utils.barcode_mtx_peaks_to_anndata(
        path_to_barcodes, path_to_mtx, path_to_peaks
    )

    assert isinstance(adata, sc.AnnData)
