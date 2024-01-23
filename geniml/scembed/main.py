import os
from logging import getLogger
from typing import Union, List

import numpy as np
import scanpy as sc
import torch
from huggingface_hub import hf_hub_download
from rich.progress import track
from tqdm import tqdm

from ..region2vec.utils import (
    LearningRateScheduler,
    export_region2vec_model,
    load_local_region2vec_model,
)
from ..region2vec.main import Region2Vec
from ..tokenization import ITTokenizer, Tokenizer
from ..region2vec.const import (
    POOLING_TYPES,
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_MIN_COUNT,
    DEFAULT_EPOCHS,
    MODEL_FILE_NAME,
    UNIVERSE_FILE_NAME,
    CONFIG_FILE_NAME,
    POOLING_METHOD_KEY,
)
from ..region2vec.utils import Region2VecDataset

from .const import MODULE_NAME

_GENSIM_LOGGER = getLogger("gensim")
_LOGGER = getLogger(MODULE_NAME)

# demote gensim logger to warning
_GENSIM_LOGGER.setLevel("WARNING")


class ScEmbed:
    def __init__(
        self,
        model_path: str = None,
        tokenizer: ITTokenizer = None,
        device: str = None,
        pooling_method: POOLING_TYPES = "mean",
        **kwargs,
    ):
        """
        Initialize ScEmbed.

        :param str model_path: Path to the pre-trained model on huggingface.
        :param embedding_dim: Dimension of the embedding.
        :param kwargs: Additional keyword arguments to pass to the model.
        """
        super().__init__()
        self.model_path: str = model_path
        self.tokenizer: ITTokenizer
        self.trained: bool = False
        self._model: Region2Vec = None
        self.pooling_method: POOLING_TYPES = pooling_method

        if model_path is not None:
            self._init_from_huggingface(model_path)
            self.trained = True

        elif tokenizer is not None:
            self._init_model(tokenizer, **kwargs)

        # set the device
        self._target_device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )

    def _init_tokenizer(self, tokenizer: Union[ITTokenizer, str]):
        """
        Initialize the tokenizer.

        :param tokenizer: Tokenizer to add to the model.
        """
        if isinstance(tokenizer, str):
            if os.path.exists(tokenizer):
                self.tokenizer = ITTokenizer(tokenizer)
            else:
                self.tokenizer = ITTokenizer.from_pretrained(
                    tokenizer
                )  # download from huggingface (or at least try to)
        elif isinstance(tokenizer, ITTokenizer):
            self.tokenizer = tokenizer
        else:
            raise TypeError("tokenizer must be of type ITTokenizer or str.")

    def _init_model(self, tokenizer, **kwargs):
        """
        Initialize the core model. This will initialize the model from scratch.

        :param kwargs: Additional keyword arguments to pass to the model.
        """
        self._init_tokenizer(tokenizer)

        self._model = Region2Vec(
            len(self.tokenizer),
            embedding_dim=kwargs.get("embedding_dim", DEFAULT_EMBEDDING_DIM),
        )

    @property
    def model(self):
        """
        Get the core Region2Vec model.
        """
        return self._model

    def add_tokenizer(self, tokenizer: Tokenizer, **kwargs):
        """
        Add a tokenizer to the model. This should be use when the model
        is not initialized with a tokenizer.

        :param tokenizer: Tokenizer to add to the model.
        :param kwargs: Additional keyword arguments to pass to the model.
        """
        if self._model is not None:
            raise RuntimeError("Cannot add a tokenizer to a model that is already initialized.")

        self.tokenizer = tokenizer
        if not self.trained:
            self._init_model(**kwargs)

    def _load_local_model(self, model_path: str, vocab_path: str, config_path: str):
        """
        Load the model from a checkpoint.

        :param str model_path: Path to the model checkpoint.
        :param str vocab_path: Path to the vocabulary file.
        """
        _model, tokenizer, config = load_local_region2vec_model(
            model_path, vocab_path, config_path
        )
        self._model = _model
        self.tokenizer = tokenizer
        if POOLING_METHOD_KEY in config:
            self.pooling_method = config[POOLING_METHOD_KEY]

    def _init_from_huggingface(
        self,
        model_path: str,
        model_file_name: str = MODEL_FILE_NAME,
        universe_file_name: str = UNIVERSE_FILE_NAME,
        config_file_name: str = CONFIG_FILE_NAME,
        **kwargs,
    ):
        """
        Initialize the model from a huggingface model. This uses the model path
        to download the necessary files and then "build itself up" from those. This
        includes both the actual model and the tokenizer.

        :param str model_path: Path to the pre-trained model on huggingface.
        :param str model_file_name: Name of the model file.
        :param str universe_file_name: Name of the universe file.
        :param kwargs: Additional keyword arguments to pass to the hf download function.
        """
        model_file_path = hf_hub_download(model_path, model_file_name, **kwargs)
        universe_path = hf_hub_download(model_path, universe_file_name, **kwargs)
        config_path = hf_hub_download(model_path, config_file_name, **kwargs)

        self._load_local_model(model_file_path, universe_path, config_path)

    @classmethod
    def from_pretrained(
        cls,
        path_to_files: str,
        model_file_name: str = MODEL_FILE_NAME,
        universe_file_name: str = UNIVERSE_FILE_NAME,
        config_file_name: str = CONFIG_FILE_NAME,
    ) -> "ScEmbed":
        """
        Load the model from a set of files that were exported using the export function.

        :param str path_to_files: Path to the directory containing the files.
        :param str model_file_name: Name of the model file.
        :param str universe_file_name: Name of the universe file.
        :param str config_file_name: Name of the config file.

        :return: The loaded model.
        """
        model_file_path = os.path.join(path_to_files, model_file_name)
        universe_file_path = os.path.join(path_to_files, universe_file_name)
        config_file_path = os.path.join(path_to_files, config_file_name)

        instance = cls()
        instance._load_local_model(model_file_path, universe_file_path, config_file_path)
        instance.trained = True

        return instance

    def train(
        self,
        data: Union[str, List[str]],
        window_size: int = DEFAULT_WINDOW_SIZE,
        epochs: int = DEFAULT_EPOCHS,
        min_count: int = DEFAULT_MIN_COUNT,
        num_cpus: int = 1,
        seed: int = 42,
        save_checkpoint_path: str = None,
        gensim_params: dict = {},
        load_from_checkpoint: str = None,
    ) -> np.ndarray:
        """
        Train the model.

        :param Union[str, List[str]] data: Data to train on. This is either a list of paths to gtoks files or a path to a folder containing gtok files.
        :param int window_size: Window size for the model.
        :param int epochs: Number of epochs to train for.
        :param int min_count: Minimum count for a region to be included in the vocabulary.
        :param int num_cpus: Number of cpus to use for training.
        :param int seed: Seed to use for training.
        :param str save_checkpoint_path: Path to save the model checkpoints to.
        :param dict gensim_params: Additional parameters to pass to the gensim model.
        :param str load_from_checkpoint: Path to a checkpoint to load from.

        :return np.ndarray: Loss values for each epoch.
        """
        # we only need gensim if we are training
        from gensim.models import Word2Vec as GensimWord2Vec

        # validate a model exists
        if self._model is None:
            raise RuntimeError(
                "Cannot train a model that has not been initialized. Please initialize the model first using a tokenizer or from a huggingface model."
            )

        # create gensim model that will be used to train
        if load_from_checkpoint is not None:
            _LOGGER.info(f"Loading model from checkpoint: {load_from_checkpoint}")
            gensim_model = GensimWord2Vec.load(load_from_checkpoint)
        else:
            _LOGGER.info("Creating new gensim model.")
            gensim_model = GensimWord2Vec(
                vector_size=self._model.embedding_dim,
                window=window_size,
                min_count=min_count,
                workers=num_cpus,
                seed=seed,
                **gensim_params,
            )
            _LOGGER.info("Building vocabulary.")
            vocab = [
                str(i)
                for i in track(
                    range(len(self.tokenizer)),
                    total=len(self.tokenizer),
                    description="Building vocabulary.",
                )
            ]
            gensim_model.build_vocab(vocab)

        # create the dataset
        dataset = Region2VecDataset(data, shuffle=True, convert_to_str=True)

        # create our own learning rate scheduler
        lr_scheduler = LearningRateScheduler(
            n_epochs=epochs,
        )

        # train the model
        losses = []

        for epoch in track(range(epochs), description="Training model", total=epochs):
            # shuffle the data
            _LOGGER.info(f"Starting epoch {epoch+1}.")
            gensim_model.train(
                tqdm(dataset, desc=f"Epoch {epoch+1}", total=len(dataset)),
                epochs=1,  # train for 1 epoch at a time, shuffle data each time
                compute_loss=True,
                total_words=gensim_model.corpus_total_words,
            )

            # log out and store loss
            _LOGGER.info(f"Loss: {gensim_model.get_latest_training_loss()}")
            losses.append(gensim_model.get_latest_training_loss())

            # update the learning rate
            lr_scheduler.update()

            # if we have a checkpoint path, save the model
            if save_checkpoint_path is not None:
                gensim_model.save(save_checkpoint_path)

        _LOGGER.info("Training complete. Moving weights to pytorch model.")

        # once done training, set the weights of the pytorch model in self._model
        for id in track(
            gensim_model.wv.key_to_index,
            total=len(gensim_model.wv.key_to_index),
            description="Setting weights.",
        ):
            self._model.projection.weight.data[int(id)] = torch.tensor(gensim_model.wv[id])

        # set the model as trained
        self.trained = True

        return np.array(losses)

    def export(
        self,
        path: str,
        checkpoint_file: str = MODEL_FILE_NAME,
        universe_file: str = UNIVERSE_FILE_NAME,
        config_file: str = CONFIG_FILE_NAME,
    ):
        """
        Function to facilitate exporting the model in a way that can
        be directly uploaded to huggingface. This exports the model
        weights and the vocabulary.

        :param str path: Path to export the model to.
        """
        # make sure the model is trained
        if not self.trained:
            raise RuntimeError("Cannot export an untrained model.")

        export_region2vec_model(
            self._model,
            self.tokenizer,
            path,
            checkpoint_file=checkpoint_file,
            universe_file=universe_file,
            config_file=config_file,
        )

    def encode(self, regions: Union[sc.AnnData, str], pooling: POOLING_TYPES = None) -> np.ndarray:
        """
        Get the vector for a region.

        :param Region region: Region to get the vector for.
        :param str pooling: Pooling type to use.

        :return np.ndarray: Vector for the region.
        """
        # allow the user to override the pooling method
        pooling = pooling or self.pooling_method

        # data validation
        if not (isinstance(regions, sc.AnnData) or isinstance(regions, str)):
            raise TypeError(
                f"Regions must be of type AnnData or str, not {type(regions).__name__}"
            )
        if isinstance(regions, str):
            regions = sc.read_h5ad(regions)

        if pooling not in ["mean", "max"]:
            raise ValueError(f"pooling must be one of {POOLING_TYPES}")

        # tokenize the region
        tokens = self.tokenizer.tokenize(regions)
        tokens = [[t.id for t in sublist] for sublist in tokens]

        # get the vector
        embeddings = []
        for token_set in track(tokens, total=len(tokens), description="Getting embeddings"):
            region_embeddings = self._model.projection(torch.tensor(token_set))
            if pooling == "mean":
                region_embeddings = torch.mean(region_embeddings, axis=0).detach().numpy()
            elif pooling == "max":
                region_embeddings = torch.max(region_embeddings, axis=0).values.detach().numpy()
            else:
                # this should be unreachable
                raise ValueError(f"pooling must be one of {POOLING_TYPES}")
            embeddings.append(region_embeddings)

        return np.vstack(embeddings)
