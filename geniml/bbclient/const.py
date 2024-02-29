import os

MODULE_NAME = "bbclient"

DEFAULT_BEDBASE_API = "https://api.bedbase.org"
DEFAULT_BEDSET_SUBFOLDER = "bedsets"
DEFAULT_BEDFILE_SUBFOLDER = "bedfiles"
DEFAULT_BEDSET_EXT = ".txt"
DEFAULT_BEDFILE_EXT = ".bed.gz"

BEDSET_URL_PATTERN = "{bedbase_api}/bedset/{bedset_id}/bedfiles"
BEDFILE_URL_PATTERN = "{bedbase_api}/objects/bed.{bed_id}.bedfile/access/http/bytes"

BBCLIENT_CACHE_ENV = "BBCLIENT_CACHE"

HOME_PATH = os.getenv("HOME")
if not HOME_PATH:
    HOME_PATH = os.path.expanduser("~")
DEFAULT_CACHE_FOLDER = os.getenv(BBCLIENT_CACHE_ENV) or os.path.join(HOME_PATH, ".bbcache/")
