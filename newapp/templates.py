#!/usr/bin/env python3


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

# pylint: disable=C0111     # docstrings are always outdated and wrong
# pylint: disable=W0511     # todo is encouraged
# pylint: disable=R0902     # too many instance attributes
# pylint: disable=C0302     # too many lines in module
# pylint: disable=C0103     # single letter var names
# pylint: disable=R0911     # too many return statements
# pylint: disable=R0912     # too many branches
# pylint: disable=R0915     # too many statements
# pylint: disable=R0913     # too many arguments
# pylint: disable=R1702     # too many nested blocks
# pylint: disable=R0914     # too many local variables
# pylint: disable=R0903     # too few public methods
# pylint: disable=E1101     # no member for base
# pylint: disable=W0201     # attribute defined outside __init__
## pylint: disable=W0703     # catching too general exception

import os
import sys
import click
from pathlib import Path
from shutil import get_terminal_size
from icecream import ic
from kcl.configops import click_read_config
from kcl.configops import click_write_config_entry


ic.configureOutput(includeContext=True)
ic.lineWrapWidth, _ = get_terminal_size((80, 20))
# import IPython; IPython.embed()
# import pdb; pdb.set_trace()
# from pudb import set_trace; set_trace(paused=False)

APP_NAME = '{package_name}'


# DONT CHANGE FUNC NAME
#@click.command()
@click.argument("urls", type=str, nargs=-1)
@click.argument("sysskel",
                type=click.Path(exists=False,
                                dir_okay=True,
                                file_okay=False,
                                path_type=str,
                                allow_dash=False), nargs=1, required=True)
@click.option('--add', is_flag=True)
@click.option('--verbose', is_flag=True)
@click.group()
def cli(sysskel, add, verbose):
    config = click_read_config(click, APP_NAME, verbose)
    if verbose:
        ic(config)
    if add:
        section = "test_section"
        key = "test_key"
        value = "test_value"
        click_write_config_entry(click, APP_NAME, section, key, value)
        config = click_read_config(click, APP_NAME, verbose)
        if verbose:
            ic(config)


#if __name__ == "__main__":
#    cli()

'''

ebuild = '''# Copyright 1999-2020 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=7
PYTHON_COMPAT=( python3_{{7,8}} )

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
#	test? ( dev-python/nose[${{PYTHON_USEDEP}}]
#		>=dev-python/toolz-0.8[${{PYTHON_USEDEP}}] )"

#python_compile() {{
#	python_is_python3 || local -x CFLAGS="${{CFLAGS}} -fno-strict-aliasing"
#	distutils-r1_python_compile
#}}

#python_test() {{
#	pushd "${{BUILD_DIR}}"/lib/ > /dev/null || die
#	PYTHONPATH=.:${{PN}} nosetests --with-doctest ${{PN}} || die "tests failed under ${{EPYTHON}}"
#	popd > /dev/null || die
#}}
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
            "{package_name}={package_name}.{package_name}:cli",
        ],
    }},
}}

setup(**config)'''

