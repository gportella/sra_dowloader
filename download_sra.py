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

    if config.has_option("Config", "fqdump_path"):
        my_fqdump = config.get("Config", "fqdump_path")
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
