#! /usr/bin/env python3

import argparse
import configparser
import logging.config
import os
import subprocess
import sys
from argparse import RawTextHelpFormatter
from collections import namedtuple
from pprint import pformat
from typing import Dict

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)


def sbatch(cmd, J="fortytwo", log="fortywo.log", mem=65536):
    """Submit to sbatch queue."""
    if len(cmd) == 0:
        print("Error, command can not be empy")
        sys.exit()
    sbatch_cmd = (
        "sbatch -J " + J + " -o " + log + " --mem " + str(mem) + ' --wrap="' + cmd + '"'
    )
    subprocess.call(sbatch_cmd, shell=True)
    return


Range = namedtuple("Range", "start end")

MAX_DW_SIZE = "60Gb"
PREFIX = "SRR"
PREFETCH = "~/programs/sratoolkit.2.8.1-3-centos_linux64/bin/prefetch"
FQDUMP = "~/programs/sratoolkit.2.8.1-3-centos_linux64/bin/fastq-dump"

ROLLO = """Download fastq files from SRR codes (get them from SRA).

Reads the input file supplied by the user and downloads the SRR records 
specified. The complete input file contains the following 


[Config] 
ranges= True/False
prefix= SRR
prefetch_path=path_to_prefetch
fqdump_path=path_to_fqdump


[SRR_code]
name=SRR_number


If you set the option "ranges" in [Config] to true, the program expects to 
set of number for each SRR_code name, which are the range of number associated
with a given name (i.e. common if the experiment has replicates).

If the [Config] section is not present, ranges defaults to false and 
the program will use default values for the rest. Run with -v to see the 
values used in that case.

Use the -dw setting to download the files, and after that you can rename
them according to you input file with the -rename option. 

"""
WHOWHEN = "Guillem Portella, rev. Jan 2019"


def do_download_sra(*, to_dw):
    """Download the values in the dictionary."""

    my_prefetch = to_dw["prefetch_exe"]
    my_fqdump = to_dw["fqdump_exe"]
    max_dw_size = to_dw["max_dw_size"]

    if "sra_dict" in to_dw:
        for _, run_id in to_dw["sra_dict"].items():
            cmd = " ".join([my_prefetch, "-v", run_id, f"-X {max_dw_size} && "])
            cmd += " ".join([my_fqdump, "--outdir fastq --gzip --split-files"])
            cmd += " ~/ncbi/public/sra/" + run_id + ".sra && "
            cmd += "rm -fr  ~/ncbi/public/sra/" + run_id + ".sra "
            sbatch(cmd, J=run_id, log=run_id + ".log")
    else:
        logging.error("Could not find SRR ids to submit.")
        sys.exit()


def do_rename_sra(*, to_dw):
    """Rename."""
    for name, run_id in to_dw.items():
        file = "fastq/" + run_id + "_1.fastq.gz"
        target_name = "fastq/" + name + ".fastq.gz"
        try:
            os.rename(file, target_name)
        except FileNotFoundError:
            print(f"Could not find {file}.")
            print(f"Did you run the script with -dw first?")
            print(f"If so, make sure it's not still downloading.")
            sys.exit()


def parse_input_file(inp_f: str, verbose: bool) -> Dict[str, Dict[str, str]]:
    """Read in input file.

    Reads the input file supplied by the user and returns a dict
    with the name of run as a key, and the SRR code as value.

    First ist searches for a Config section, and sets the option to use ranges
    rather than single values for a key, or changes the default prefix
    for the codes. If not found, it understands the values as single values
    (i.e. not ranges), and uses the default prefix.

    At the moment has limited input validation... fingers crossed.
    """
    config = configparser.ConfigParser()
    config.read(inp_f)

    b_ranges = False

    # check if we have things defined in Config section, otherwise use defaults
    if config.has_option("Config", "ranges"):
        if config.get("Config", "ranges") == "True":
            logging.debug("Setting it to ranges")
            b_ranges = True

    if config.has_option("Config", "prefix"):
        logging.debug("Setting a non-default prefix")
        my_prefix = config.get("Config", "prefix")
    else:
        my_prefix = PREFIX

    if config.has_option("Config", "prefetch_path"):
        my_prefetch = config.get("Config", "prefetch_path")
    else:
        my_prefetch = PREFETCH

    if config.has_option("Config", "prefetch_path"):
        my_fqdump = config.get("Config", "prefetch_path")
    else:
        my_fqdump = FQDUMP

    if config.has_option("Config", "max_dw_size"):
        my_max_dw_size = config.get("Config", "max_dw_size")
    else:
        my_max_dw_size = MAX_DW_SIZE

    my_config = {
        "prefetch_exe": my_prefetch,
        "fqdump_exe": my_fqdump,
        "max_dw_size": my_max_dw_size,
    }

    if not config.has_section("SRR_code") or len(config.options("SRR_code")) < 1:
        msg = "We could not find SRR_code section, or it was empty.\n\n"
        msg += "Add a [SRR_code] section in your ini file, specifying the\n"
        msg += "SRR number (without the SRR prefix to the code).\n"
        msg += "If your SRR code does not start with SRR, define the prefix\n"
        msg += "In the [Config] section, under the key 'prefix'\n"
        logging.error(msg)
        sys.exit()

    sra_dict = {}
    if b_ranges:
        for item, values in config.items("SRR_code"):
            # logging.info(item, values)
            ranges = [int(x) for x in values.split(",")]
            if len(ranges) != 2 and b_ranges:
                msg = "Input range needs to have two integer numbers, "
                msg += f"but I found {len(ranges)} for key {item}\n"
                msg += f"Make sure to separate the ranges with comas."
                logging.error(msg)
                sys.exit()
            else:
                rr = Range(*ranges)
                for i, vv in enumerate(range(rr.start, rr.end + 1)):
                    sra_dict[item + "_" + str(i)] = my_prefix + str(vv)
    else:
        for item, value in config.items("SRR_code"):
            sra_dict[item] = my_prefix + str(value)

    my_config["sra_dict"] = sra_dict

    if verbose:
        logging.info(pformat(my_config))

    return my_config


def parse_arguments():
    """Parse the arguments.

    rtype: arguments dictionary
    """
    parser = argparse.ArgumentParser(
        description=ROLLO, epilog=WHOWHEN, formatter_class=RawTextHelpFormatter
    )
    parser.add_argument(
        "-inp",
        metavar="input_file",
        nargs="+",
        required=True,
        help="Input file with the names and the SRR codes.",
    )
    parser.add_argument("-rename", default=False, action="store_true", help="Rename")
    parser.add_argument(
        "-dw", default=False, action="store_true", help="Download from GEO"
    )
    parser.add_argument(
        "-v",
        default=False,
        action="store_true",
        help="Print out all configuration details.",
    )
    args = vars(parser.parse_args())
    return args


if __name__ == "__main__":
    arguments = parse_arguments()
    if not arguments["rename"] and not arguments["dw"]:
        print("You should either ask to download or to rename ")
        sys.exit()

    if arguments["rename"] and arguments["dw"]:
        print("You should either ask to download or to rename ")
        sys.exit()

    dict_runs = parse_input_file(arguments["inp"], verbose=arguments["v"])

    if arguments["dw"]:
        do_download_sra(to_dw=dict_runs)
    else:
        do_rename_sra(to_dw=dict_runs)
