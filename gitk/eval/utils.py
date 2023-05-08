import pickle
import os
import numpy as np
import time
import argparse
import time
import multiprocessing as mp
import glob
from gensim.models import Word2Vec


class BaseEmbeddings:
    def __init__(self, embeddings, vocab):
        self.embeddings = embeddings
        self.vocab = vocab


def get_bin_embeddings(universe_file, tokenized_files):
    vocab = []
    with open(universe_file, "r") as f:
        for line in f:
            eles = line.strip().split("\t")
            region = "{}:{}-{}".format(*eles)
            vocab.append(region)
    vocab_dict = {v: i for i, v in enumerate(vocab)}
    print("vocab size is", len(vocab))
    bin_embeds = np.zeros((len(vocab), len(tokenized_files)))
    for i, token_file in enumerate(tokenized_files):
        with open(token_file, "r") as f:
            for line in f:
                eles = line.strip().split("\t")
                region = "{}:{}-{}".format(*eles)
                if region in vocab_dict:
                    bin_embeds[vocab_dict[region]][i] = 1
    bin_embed_obj = BaseEmbeddings(bin_embeds, vocab)
    return bin_embed_obj


def get_pca_embeddings(bin_embed_obj, dim, kwargs={}):
    from sklearn.decomposition import PCA

    embeds = PCA(n_components=dim, **kwargs).fit_transform(bin_embed_obj.embeddings)
    pca_embed_obj = BaseEmbeddings(embeds, bin_embed_obj.vocab)
    return pca_embed_obj


def get_umap_embeddings(bin_embed_obj, dim, kwargs={}):
    import umap

    embeds = umap.UMAP(n_components=dim, **kwargs).fit_transform(
        bin_embed_obj.embeddings
    )
    umap_embed_obj = BaseEmbeddings(embeds, bin_embed_obj.vocab)
    return umap_embed_obj


def save_base_embeddings(base_embed_obj, file_name):
    with open(file_name, "wb") as f:
        pickle.dump(base_embed_obj, f)


def load_base_embeddings(path):
    with open(path, "rb") as f:
        base_embed_obj = pickle.load(f)
    return base_embed_obj.embeddings, base_embed_obj.vocab


def load_genomic_embeddings(model_path, embed_type="region2vec"):
    if embed_type == "region2vec":
        model = Word2Vec.load(model_path)
        regions_r2v = model.wv.index_to_key
        embed_rep = model.wv.vectors
        return embed_rep, regions_r2v
    elif embed_type == "base":
        embed_rep, regions_r2v = load_base_embeddings(model_path)
        return embed_rep, regions_r2v


def get_vocab(model_path, type="base", ordered=True):
    def sort_key(x):
        eles = x.split(":")
        chr_idx = eles[0][3:]
        try:
            idx = int(chr_idx)
        except ValueError:
            idx = 23
            for c in chr_idx:
                idx += ord(c)
        start = int(eles[1].split("-")[0].strip())
        return idx, start

    if type == "region2vec":
        model = Word2Vec.load(model_path)
        regions_r2v = model.wv.index_to_key
    elif type == "base":
        _, regions_r2v = load_base_embeddings(model_path)
    if ordered:
        regions_r2v = sorted(regions_r2v, key=sort_key)
    return regions_r2v


def write_vocab(vocab, file_name):
    with open(file_name, "w") as f:
        for v in vocab:
            eles = v.split(":")
            chr = eles[0].strip()
            s, e = eles[1].split("-")
            s = s.strip()
            e = e.strip()
            f.write("{}\t{}\t{}\n".format(chr, s, e))
