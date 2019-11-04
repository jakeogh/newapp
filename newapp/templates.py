#!/usr/bin/env python3


edit_config='''#!/bin/sh
short_package="{package_name}"
group="{package_group}"
package="${{group}}/${{short_package}}"
{remote}
{optional_blank_remote}
test_command_arg=""
pre_lint_command=""
dont_unmerge=""
'''


app = '''#!/usr/bin/env python3

import os
import sys
import click

from icecream import ic
ic.configureOutput(includeContext=True)
from shutil import get_terminal_size
ic.lineWrapWidth, _ = get_terminal_size((80, 20))
#ic.disable()


# DONT CHANGE FUNC NAME
@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli()


# import IPython; IPython.embed()
# import pdb; pdb.set_trace()
# from pudb import set_trace; set_trace(paused=False)'''


ebuild = '''# Copyright 1999-2019 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=7
PYTHON_COMPAT=( python{{3_6,3_7}} )

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
