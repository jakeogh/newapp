#!/usr/bin/env python3


echo_url='''#!/bin/sh
echo "{url}"
'''


edit_config='''#!/bin/sh
short_package="{package_name}"
group="{package_group}"
package="${{group}}/${{short_package}}"
{remote}
{optional_blank_remote}
test_command_arg="--help"
pre_lint_command=""
dont_unmerge=""
'''


app = '''#!/usr/bin/env python3

# pylint: disable=C0111  # docstrings are always outdated and wrong
# pylint: disable=W0511  # todo is encouraged
# pylint: disable=C0301  # line too long
# pylint: disable=R0902  # too many instance attributes
# pylint: disable=C0302  # too many lines in module
# pylint: disable=C0103  # single letter var names, func name too descriptive
# pylint: disable=R0911  # too many return statements
# pylint: disable=R0912  # too many branches
# pylint: disable=R0915  # too many statements
# pylint: disable=R0913  # too many arguments
# pylint: disable=R1702  # too many nested blocks
# pylint: disable=R0914  # too many local variables
# pylint: disable=R0903  # too few public methods
# pylint: disable=E1101  # no member for base
# pylint: disable=W0201  # attribute defined outside __init__
# pylint: disable=R0916  # Too many boolean expressions in if statement
## pylint: disable=W0703  # catching too general exception


# TODO:
#   https://github.com/kvesteri/validators
import os
import sys
import click
from pathlib import Path
from collections import defaultdict
from icecream import ic
from kcl.configops import click_read_config
from kcl.configops import click_write_config_entry
from enumerate_input import enumerate_input
#from getdents import files

ic.configureOutput(includeContext=True)
# import IPython; IPython.embed()
# import pdb; pdb.set_trace()
# from pudb import set_trace; set_trace(paused=False)

global APP_NAME
APP_NAME = '{package_name}'


# DONT CHANGE FUNC NAME
@click.command()
@click.argument("paths", type=str, nargs=-1)
@click.argument("sysskel",
                type=click.Path(exists=False,
                                dir_okay=True,
                                file_okay=False,
                                path_type=str,
                                allow_dash=False),
                nargs=1,
                required=True)
@click.option('--add', is_flag=True)
@click.option('--verbose', is_flag=True)
@click.option('--debug', is_flag=True)
@click.option('--simulate', is_flag=True)
@click.option('--count', type=str)
@click.option("--printn", is_flag=True)
#@click.group()
def cli(paths,
        sysskel,
        add,
        verbose,
        debug,
        simulate,
        count,
        printn,):

    null = not printn

    if verbose:
        ic(sys.stdout.isatty())

    global APP_NAME
    config, config_mtime = click_read_config(click_instance=click,
                                             app_name=APP_NAME,
                                             verbose=verbose)
    if verbose:
        ic(config, config_mtime)

    if add:
        section = "test_section"
        key = "test_key"
        value = "test_value"
        config, config_mtime = click_write_config_entry(click_instance=click,
                                                        app_name=APP_NAME,
                                                        section=section,
                                                        key=key,
                                                        value=value,
                                                        verbose=verbose)
        if verbose:
            ic(config)

    for index, path in enumerate_input(iterator=paths,
                                       null=null,
                                       debug=debug,
                                       verbose=verbose):
        path = Path(path)

        if verbose or simulate:
            ic(index, path)
        if count:
            if count > (index + 1):
                ic(count)
                sys.exit(0)

        if simulate:
            continue

        with open(path, 'rb') as fh:
            path_bytes_data = fh.read()

#        if ipython:
#            import IPython; IPython.embed()


'''

ebuild = '''# Copyright 1999-2020 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=7
PYTHON_COMPAT=( python3_{{8..9}} )

inherit distutils-r1 git-r3

DESCRIPTION="{description}"
HOMEPAGE="{homepage}"
EGIT_REPO_URI="{app_path} {homepage}.git"

LICENSE="BSD"
SLOT="0"
KEYWORDS=""
#IUSE="test"

RDEPEND="
	dev-python/click[${{PYTHON_USEDEP}}]
	dev-python/icecream[${{PYTHON_USEDEP}}]
	dev-python/colorama[${{PYTHON_USEDEP}}]
"

DEPEND="${{RDEPEND}}"

'''

gitignore = '''.git
.edit_config
enable_github.sh
'''

setup_py='''# -*- coding: utf-8 -*-

import sys
import fastentrypoints
from setuptools import find_packages, setup
if not sys.version_info[0] == 3:
    sys.exit("Python 3 is required. Use: \\'python3 setup.py install\\'")

dependencies = ["icecream", "click", "colorama"]

config = {{
    "version": "0.1",
    "name": "{package_name}",
    "url": "{url}",
    "license": "{license}",
    "author": "{owner}",
    "author_email": "{owner_email}",
    "description": "{description}",
    "long_description": __doc__,
    "packages": find_packages(exclude=['tests']),
    "include_package_data": True,
    "zip_safe": False,
    "platforms": "any",
    "install_requires": dependencies,
    "entry_points": {{
        "console_scripts": [
            "{command}={package_name}.{package_name}:cli",
        ],
    }},
}}

setup(**config)'''

