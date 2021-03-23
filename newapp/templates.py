#!/usr/bin/env python3


from icecream import ic

init='''#from .{package_name} import {package_name}'''


echo_url='''#!/bin/sh
echo "{url}"'''


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
# -*- coding: utf8 -*-

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


# TODO:
#   https://github.com/kvesteri/validators
import os
import sys
import click
from pathlib import Path
from with_sshfs import sshfs
from with_chdir import chdir
from retry_on_exception import retry_on_exception
from enumerate_input import enumerate_input
#from collections import defaultdict
#from prettyprinter import cpprint, install_extras
#install_extras(['attrs'])
from kcl.configops import click_read_config
from kcl.configops import click_write_config_entry
from kcl.userops import not_root
#from kcl.pathops import path_is_block_special
#from getdents import files
from typing import List
from typing import Sequence
from typing import Generator
from typing import Iterable
from typing import ByteString
from typing import Optional

# click-command-tree
#from click_plugins import with_plugins
#from pkg_resources import iter_entry_points

def eprint(*args, **kwargs):
    if 'file' in kwargs.keys():
        kwargs.pop('file')
    print(*args, file=sys.stderr, **kwargs)


try:
    from icecream import ic  # https://github.com/gruns/icecream
except ImportError:
    ic = eprint



# import pdb; pdb.set_trace()
# #set_trace(term_size=(80, 24))
# from pudb import set_trace; set_trace(paused=False)

##def log_uncaught_exceptions(ex_cls, ex, tb):
##   eprint(''.join(traceback.format_tb(tb)))
##   eprint('{{0}}: {{1}}'.format(ex_cls, ex))
##
##sys.excepthook = log_uncaught_exceptions

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
                                allow_dash=False,),
                nargs=1,
                required=True,)
@click.option('--add', is_flag=True)
@click.option('--verbose', is_flag=True)
@click.option('--debug', is_flag=True)
@click.option('--simulate', is_flag=True)
@click.option('--ipython', is_flag=True)
@click.option('--count', is_flag=True)
@click.option('--skip', type=int, default=False)
@click.option('--head', type=int, default=False)
@click.option('--tail', type=int, default=False)
@click.option("--printn", is_flag=True)
@click.option("--progress", is_flag=True)
#@with_plugins(iter_entry_points('click_command_tree'))
#@click.group()
@click.pass_context
def cli(ctx,
        paths,
        sysskel,
        add,
        verbose: bool,
        debug: bool,
        simulate: bool,
        ipython: bool,
        count: bool,
        skip: int,
        head: int,
        tail: int,
        progress: bool,
        printn: bool,
        ):

    null = not printn
    end = '{newline}'
    if null:
        end = '{null}'
    if sys.stdout.isatty():
        end = '{newline}'
        assert not ipython

    #progress = False
    if (verbose or debug):
        progress = False

    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['debug'] = debug
    ctx.obj['end'] = end
    ctx.obj['null'] = null
    ctx.obj['progress'] = progress
    ctx.obj['count'] = count
    ctx.obj['skip'] = skip
    ctx.obj['head'] = head
    ctx.obj['tail'] = tail

    global APP_NAME
    config, config_mtime = click_read_config(click_instance=click,
                                             app_name=APP_NAME,
                                             verbose=verbose,
                                             debug=debug,)
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
                                                        verbose=verbose,
                                                        debug=debug,)
        if verbose:
            ic(config)

    iterator = paths

    for index, path in enumerate_input(iterator=iterator,
                                       null=null,
                                       progress=progress,
                                       skip=skip,
                                       head=head,
                                       tail=tail,
                                       debug=debug,
                                       verbose=verbose,):
        path = Path(path)

        if verbose or simulate:
            ic(index, path)
        #if count:
        #    if count > (index + 1):
        #        ic(count)
        #        sys.exit(0)

        if simulate:
            continue

        with open(path, 'rb') as fh:
            path_bytes_data = fh.read()

        if not count:
            print(path, end=end)

    if count:
        print(index + 1, end=end)

#        if ipython:
#            import IPython; IPython.embed()

#@cli.command()
#@click.argument("urls", type=str, nargs=-1)
#@click.option('--verbose', is_flag=True)
#@click.option('--debug', is_flag=True)
#@click.pass_context
#def some_command(ctx,
#                 urls,
#                 verbose: bool,
#                 debug: bool,
#                 ):
#    pass
#    verbose = verbose or ctx.obj['verbose']
#    debug = debug or ctx.obj['debug']
#
#    iterator = urls
#    for index, url in enumerate_input(iterator=iterator,
#                                      null=ctx.obj['null'],
#                                      progress=ctx.obj['progress'],
#                                      skip=ctx.obj['skip'],
#                                      head=ctx.obj['head'],
#                                      tail=ctx.obj['tail'],
#                                      debug=ctx.obj['debug'],
#                                      verbose=ctx.obj['verbose'],):
#
#        if ctx.obj['verbose']:
#            ic(index, url)


'''

depend_python = '''
RDEPEND="
	dev-python/click[${PYTHON_USEDEP}]
	dev-python/icecream[${PYTHON_USEDEP}]
	dev-python/colorama[${PYTHON_USEDEP}]
"
	#dev-python/click-command-tree[${PYTHON_USEDEP}]

DEPEND="${RDEPEND}"
'''

ebuild = '''# Copyright 1999-2021 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=7
PYTHON_COMPAT=( python3_{{8..9}} )

inherit git-r3
{inherit_python}

DESCRIPTION="{description}"
HOMEPAGE="{homepage}"
EGIT_REPO_URI="{app_path} {homepage}.git"

LICENSE="BSD"
SLOT="0"
KEYWORDS=""
#IUSE="test"

{depend_python}

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

dependencies = ["icecream", "click", "colorama", "click-command-tree"]

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
    "package_data": {{"{package_name}": ['py.typed']}},
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

