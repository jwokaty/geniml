def build_subparser_gdst(parser):
    """
    Builds argument parser.

    :return argparse.ArgumentParser
    """

    parser.add_argument(
        "--model-path",
        required=True,
        type=str,
        help="path to a Region2Vec model or a Base model",
    )
    parser.add_argument(
        "--embed-type", required=True, type=str, help="region2vec or base"
    )
    parser.add_argument(
        "--num-samples",
        default=10000,
        type=int,
        help="number of samples used in calculation",
    )

    return parser


def build_subparser_npt(parser):
    """
    Builds argument parser.

    :return argparse.ArgumentParser
    """
    parser.add_argument(
        "--model-path",
        required=True,
        type=str,
        help="path to a region2vec model or a Base model",
    )
    parser.add_argument(
        "--embed-type", required=True, type=str, help="region2vec or base"
    )
    parser.add_argument(
        "--K", required=True, type=int, help="number of nearest regions"
    )
    parser.add_argument(
        "--num-samples",
        default=1000,
        type=int,
        help="number of samples used in calculation",
    )

    return parser


def build_subparser_cct_tss(parser):
    """
    Builds argument parser.

    :return argparse.ArgumentParser
    """
    parser.add_argument(
        "--model-path",
        required=True,
        type=str,
        help="path to a region2vec model or a Base model",
    )
    parser.add_argument(
        "--embed-type", required=True, type=str, help="region2vec or base"
    )
    parser.add_argument(
        "--save-folder",
        required=True,
        type=str,
        help="path to the folder that saves intermediate results",
    )
    parser.add_argument(
        "--Rscript-path", required=True, type=str, help="path to Rscript"
    )
    parser.add_argument("--assembly", required=True, type=str, help="hg19 or hg38")
    parser.add_argument(
        "--threshold",
        default=0.0001,
        type=float,
        help="threshold that determines a significant cluster",
    )
    parser.add_argument(
        "--num-samples",
        default=1000,
        type=int,
        help="number of samples used in calculation",
    )

    return parser


def build_subparser(parser):
    sp = parser.add_subparsers(dest="subcommand")
    msg_by_cmd = {
        "gdst": "Genome distance scaling test",
        "npt": "Neighorhood preserving test",
        "cct-tss": "Contrastive clusters test on transcription start sites",
    }
    subparsers = {}
    for k, v in msg_by_cmd.items():
        subparsers[k] = sp.add_parser(k, description=v, help=v)
    subparsers["gdst"] = build_subparser_gdst(subparsers["gdst"])
    subparsers["npt"] = build_subparser_npt(subparsers["npt"])
    subparsers["cct-tss"] = build_subparser_cct_tss(subparsers["cct-tss"])

    return parser
