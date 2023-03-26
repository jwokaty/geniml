""" Constants for scembed """

__author__ = ["Nathan LeRoy", "Jason Smith", "Erfaneh Gharavi"]
__email__ = "nleroy@virginia.edu"

LOGGING_LEVEL = "INFO"
PKG_NAME = "scembed"

DEFAULT_EPOCHS = 100
DEFAULT_GENSIM_EPOCHS = 1
DEAFULT_N_SHUFFLES = 10
DEFAULT_WINDOW_SIZE = 5
DEFAULT_EMBEDDING_SIZE = 100
DEFAULT_EPOCHS = 10
DEFAULT_INIT_LR = (
    0.1  # https://github.com/databio/gitk/issues/6#issuecomment-1476273162
)
DEFAULT_MIN_LR = 0.0001  # gensim default
DEFAULT_DECAY_RATE = 0.95
