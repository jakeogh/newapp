#!/usr/bin/env python3
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


import os
import shutil
from pathlib import Path
from urllib.parse import urlparse
import click
from kcl.printops import eprint
from kcl.fileops import write_line_to_file
from kcl.configops import click_read_config
from kcl.commandops import run_command
from icecream import ic
from .templates import app
from .templates import ebuild
from .templates import gitignore
from .templates import edit_config
from .templates import setup_py
from .templates import echo_url
ic.configureOutput(includeContext=True)
from shutil import get_terminal_size
ic.lineWrapWidth, _ = get_terminal_size((80, 20))

CFG, CONFIG_MTIME = click_read_config(click_instance=click, app_name='newapp', verbose=False)

# https://github.com/mitsuhiko/click/issues/441
CONTEXT_SETTINGS = dict(default_map=CFG)
    #dict(help_option_names=['--help'],
    #     terminal_width=shutil.get_terminal_size((80, 20)).columns)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('--verbose', is_flag=True)
@click.pass_context
def cli(ctx, verbose):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose


def get_url_for_overlay(overlay, verbose=False):
    command = ["eselect", "repository", "list"]
    command_output = run_command(command, str_output=True)
    command_output = command_output.split('\n')
    if verbose:
        ic(type(command_output))
        ic(command_output)

    for line in command_output[1:]:
        if verbose:
            ic(line)
        try:
            index, repo_name, repo_url = [item for item in line.split() if item]
        except ValueError:
            pass

        repo_url = repo_url.split("(")[-1].split(")")[0]
        if repo_name == overlay:
            return repo_url


def valid_branch(ctx, param, value):
    eprint("value:", value)
    branch_check_cmd = "git check-ref-format --branch " + value
    if os.system(branch_check_cmd):
        raise click.BadParameter('fatal: "{0}" is not a valid branch name'.format(value))
    return value


def generate_edit_config(package_name, package_group, local):
    if local:
        remote = "#"
    else:
        remote = ''
    remote += '''remote="https://github.com/jakeogh/{}.git"'''.format(package_name)

    optional_blank_remote = ''
    if local:
        optional_blank_remote = '''remote=""'''
    return edit_config.format(package_name=package_name,
                              package_group=package_group,
                              optional_blank_remote=optional_blank_remote,
                              remote=remote)


def generate_setup_py(url, package_name, command, license, owner, owner_email, description):
    return setup_py.format(package_name=package_name,
                           command=command,
                           url=url,
                           license=license,
                           owner=owner,
                           owner_email=owner_email,
                           description=description)


def generate_ebuild_template(description, homepage, app_path):
    return ebuild.format(description=description,
                         homepage=homepage,
                         app_path=app_path)


def generate_gitignore_template():
    return gitignore.format()


def generate_app_template(package_name):
    return app.format(package_name=package_name, newline="\\n", null="\\x00")


def generate_echo_url_template(url):
    return echo_url.format(url=url)


@cli.command()
@click.pass_context
def get_pylint_config(ctx):
    app_template = generate_app_template('TEMP')
    for line in app_template.splitlines():
        if line.startswith('# pylint: '):
            print(line)


@cli.command()
@click.argument('overlay_name', type=str, nargs=1)
@click.pass_context
def get_overlay_url(ctx, overlay_name):
    url = get_url_for_overlay(overlay_name, verbose=ctx.obj['verbose'])
    print(url)


@cli.command()
@click.argument("app", type=str)
@click.pass_context
def nineify(ctx, app):
    assert '/' in app
    group, name = app.split('/')
    ic(group)
    ic(name)
    relative_destination = Path(group) / Path(name)
    template_path = Path("/var/db/repos/gentoo") / relative_destination
    ic(template_path)
    local_overlay = Path("/home/cfg/_myapps/jakeogh")
    destination = local_overlay / relative_destination
    ic(template_path, destination)
    try:
        shutil.copytree(template_path, destination)
    except FileExistsError as e:
        ic(e)


@cli.command()
@click.argument("package-name", type=str)
@click.pass_context
def get_app_template(ctx, package_name):
    app_template = generate_app_template(package_name)
    print(app_template)


@cli.command()
@click.argument('git_repo_url', type=str, nargs=1)
@click.argument('group', type=str, nargs=1)
@click.argument('branch', type=str, callback=valid_branch, nargs=1, default="master")
@click.option('--apps-folder', type=str, required=True)
@click.option('--gentoo-overlay-repo', type=str, required=True)
@click.option('--github-user', type=str, required=True)
@click.option('--license', type=click.Choice(["ISC"]), default="ISC")
@click.option('--owner', type=str, required=True)
@click.option('--owner-email', type=str, required=True)
@click.option('--description', type=str, default="Short explination of what it does _here_")
@click.option('--local', is_flag=True)
@click.option('--template', is_flag=True)
@click.option('--hg', is_flag=True)
@click.option('--rename', type=str)
@click.pass_context
def new(ctx,
        git_repo_url,
        group, branch,
        apps_folder,
        gentoo_overlay_repo,
        github_user,
        license,
        owner,
        owner_email,
        description,
        local,
        template,
        hg,
        rename):

    verbose = ctx.obj['verbose']
    ic(apps_folder)

    if not template:
        assert git_repo_url.startswith('https://github.com/{}/'.format(github_user))

    if rename:
        assert template

    if git_repo_url.endswith('.git'):
        git_repo_url = git_repo_url[:-4]

    assert '/' not in group
    assert ':' not in group

    git_repo_url_parsed = urlparse(git_repo_url)
    git_repo_url_path = Path(git_repo_url_parsed.path)
    app_name = git_repo_url_path.parts[-1]
    app_module_name = app_name.replace('-', '_')

    if rename:
        app_name = rename
    app_path = Path(apps_folder) / Path(app_module_name)
    ic(app_path)
    ic(app_name)
    if not app_path.exists():
        if template:
            if hg:
                clone_cmd = " ".join(["hg clone", git_repo_url, str(app_path)])
            else:
                clone_cmd = " ".join(["git clone", git_repo_url, str(app_path)])
            ic(clone_cmd)
            os.system(clone_cmd)
            os.chdir(app_path)
            #if template.startswith('https://github.com/'):
            if not hg:
                git_fork_cmd = "hub fork"
                os.system(git_fork_cmd)
            #else:
            #    raise NotImplementedError
        else:
            if hg:
                assert False
            os.makedirs(app_path, exist_ok=False)
            os.chdir(app_path)
            os.makedirs(app_module_name, exist_ok=False)
            os.system("git init")

        #repo_config_command = "git remote set-url origin git@github.com:jakeogh/" + app_name + '.git'
        if not hg:
            repo_config_command = "git remote add origin git@github.com:jakeogh/" + app_name + '.git'
            ic(repo_config_command)
        if not local:
            if not hg:
                os.system(repo_config_command)
        else:
            enable_github = [
                "#!/bin/sh",
                repo_config_command,
                "\n"]
            enable_github = "\n".join(enable_github)
            with open("enable_github.sh", 'x') as fh:
                fh.write(enable_github)

        if branch != "master":
            branch_cmd = "git checkout -b " + '"' + branch + '"'
            ic(branch_cmd)
            os.system(branch_cmd)

        with open(".edit_config", 'x') as fh:
            fh.write(generate_edit_config(package_name=app_name,
                                          package_group=group,
                                          local=local))

        if not template:
            with open("setup.py", 'x') as fh:
                fh.write(generate_setup_py(package_name=app_module_name,
                                           command=app_name,
                                           owner=owner,
                                           owner_email=owner_email,
                                           description=description,
                                           license=license,
                                           url=git_repo_url))

            template = generate_gitignore_template()
            with open('.gitignore', 'x') as fh:
                fh.write(template)

            os.system("fastep")

            os.chdir(app_module_name)
            app_template = generate_app_template(package_name=app_module_name)
            with open(app_module_name + '.py', 'x') as fh:
                fh.write(app_template)

            echo_url_template = generate_echo_url_template(url=git_repo_url)
            with open("echo_url.sh", 'x') as fh:
                fh.write(echo_url_template)

            os.system("touch __init__.py")

            os.chdir(app_path)
            os.system("git add --all")
    else:
        eprint("Not creating new app, {} already exists.".format(app_path))

    ebuild_path = Path(gentoo_overlay_repo) / Path(group) / Path(app_name)
    if not ebuild_path.exists():
        os.makedirs(ebuild_path, exist_ok=False)
        os.chdir(ebuild_path)
        ebuild_name = app_name + "-9999.ebuild"

        with open(ebuild_name, 'w') as fh:
            fh.write(generate_ebuild_template(description=description,
                                              homepage=git_repo_url,
                                              app_path=app_path))
        os.system("git add " + ebuild_name)
        os.system("ebuild {} manifest".format(ebuild_name))
        os.system("git add *")
        os.system("git commit -m 'newapp {}'".format(app_name))
        os.system("git push")
        os.system("sudo emaint sync -A")
        accept_keyword = "={}/{}-9999 **\n".format(group, app_name)
        accept_keywords = Path("/etc/portage/package.accept_keywords")
        write_line_to_file(file_to_write=accept_keywords,
                           line=accept_keyword,
                           unique=True,
                           make_new=False)
    else:
        eprint("Not creating new ebuild, {} already exists.".format(ebuild_path))

    ic(app_path)
    ic(app_module_name)

    main_py_path = app_path / Path(app_module_name) / Path(app_module_name + ".py")
    ic(main_py_path)
    os.system("edit " + main_py_path.as_posix())


#
##from pudb.remote import set_trace
##set_trace(term_size=(80, 24))
#
#
##def log_uncaught_exceptions(ex_cls, ex, tb):
##   cprint(''.join(traceback.format_tb(tb)))
##   cprint('{0}: {1}'.format(ex_cls, ex))
##
##sys.excepthook = log_uncaught_exceptions
#
#
## handle stdin or a filename as input
#if __name__ == '__main__':
#    import sys
#    if len(sys.argv[:]) < 2:
#        path = '/dev/stdin'
#        main(path)
#    else:
#        for path in sys.argv[1:]:
#            if path.startswith(b'file://'):
#                main(path)
#            else:
#                main(path)
#
#import os
#home = os.path.expanduser("~")
#os.path.sep = b'/'
#os.path.altsep = b'/'
#program_folder = os.path.dirname(os.path.realpath(__file__))
#
#if len(sys.argv[]) < 2:
#        path = '/dev/stdin'
#else:
#        path = sys.argv[1]
#
#input_fh = open(path, 'rb')
#try:
#    input = sys.argv[1]
#except:
#    input = open('/dev/stdin', 'r').read()
#
#
#try:
#    filedir = os.path.expanduser(sys.argv[1])
#except IndexError:
#    print 'Script must be called with one argument.'
#    sys.exit(1)
#
#if (not filedir[-1] == '/'):
#    filedir += '/'
#files = os.listdir(filedir)
#
#def debug(func):
#    msg = func.__qualname__
#    @wraps(func)
#    #http://www.dabeaz.com/py3meta/Py3Meta.pdf
#    def wrapper(*args, **kwargs):
#        print(msg)
#        return func(*args, **kwargs)
#    return wrapper
#
#
##http://liw.fi/cmdtest/
##http://liw.fi/cliapp/
#
#"""
#SYNOPSIS
#
#    TODO helloworld [-h] [-v,--verbose] [--version]
#
#DESCRIPTION
#
#    TODO This describes how to use this script.
#    This docstring will be printed by the script if there is an error or
#    if the user requests help (-h or --help).
#
#EXAMPLES
#
#    TODO: Show some examples of how to use this script.
#
#EXIT STATUS
#
#    TODO: List exit codes
#
#AUTHOR
#
#    TODO: Name <name@example.org>
#
#LICENSE
#
#    TODO: This script is not licensed yet.
#
#VERSION
#
#"""
#
##import urllib
##import urlparse
##import serial
##import numpy
##import scipy
#
#import sys
#import os
#import traceback
#import optparse
#import time
##from pexpect import run, spawn
#from os.path import exists
#from sys import exit
#
## Uncomment the following section if you want readline history support.
##import readline, atexit
##histfile = os.path.join(os.environ['HOME'], '.TODO_history')
##try:
##    readline.read_history_file(histfile)
##except IOError:
##    pass
##atexit.register(readline.write_history_file, histfile)
#
#def main ():
#
#    global options, args
#
#        try:
#        print "options=",options
#        print "args=",args
#
#        except IndexError:
#                sys.stderr.write(helpstring)
#
#
#if __name__ == '__main__':
#    try:
#            start_time = time.time()
#            parser = optparse.OptionParser(formatter=optparse.TitledHelpFormatter(), usage=globals()['__doc__'], version='0.1')
#            parser.add_option('-v', '--verbose', action='store_true', default=False, help='verbose output')
#            parser.add_option('-q', '--quick', action='store_true', default=False, help='quick compare, not 100%')
#            (options, args) = parser.parse_args()
#            if len(args) < 1:
#                parser.error('missing argument')
#            if options.verbose: print time.asctime()
#
#            exit_code = main()
#
#            if exit_code is None:
#                    exit_code = 0
#            if options.verbose: print time.asctime()
#            if options.verbose: print 'TOTAL TIME IN MINUTES:',
#            if options.verbose: print (time.time() - start_time) / 60.0
#        print " "
#            sys.exit(exit_code)
#        except KeyboardInterrupt, e: # Ctrl-C
#            raise e
#        except SystemExit, e: # sys.exit()
#            raise e
#        except Exception, e:
#            print 'ERROR, UNEXPECTED EXCEPTION'
#            print str(e)
#            traceback.print_exc()
#            os._exit(1)
#
#
#def formatExceptionInfo(maxTBlevel=5):
#    cla, exc, trbk = sys.exc_info()
#    excName = cla.__name__
#    try:
#        excArgs = exc.__dict__["args"]
#    except KeyError:
#        excArgs = "<no args>"
#
#    excArgsString = ''
#    for item in excArgs:
#        excArgsString = excArgsString + ' ' + str(item)
#
#    excTb = traceback.format_tb(trbk, maxTBlevel)
#    excTbString = ''
#    for item in excTb:
#        excTbString = excTbString + " " + str(item)
#
#    report = "%s %s %s"%(excName, excArgsString, excTbString)
#    return(report)
#
##http://stackoverflow.com/questions/1549509/remove-duplicates-in-a-list-while-keeping-its-order-python
#def unique(seq):
#    seen = set()
#    for item in seq:
#        if item not in seen:
#            seen.add(item)
#            yield item
#
#
#
#def reverse_sort_list(domains):
#    data = []
#    for x in domains:
#        d = x.strip()[::-1]
##        print("d:", d)
#        data.append(d)
#    data.sort() #sorting a list of strings by tld
#    for y in data:
##        print("y:", y)
#        y = y[::-1]
#        print(y)
#
#
#def domain_set_to_sorted_list_grouped_by_tld(domains):
#    data = []
#    for x in domains:
#       d = x.strip().split('.')
#       d.reverse()
#       data.append(d)
#    data.sort()
#    for y in data:
#       y.reverse()
#       print('.'.join(y))
#
#
#
#def print_hex(text):
#    print(':'.join(hex(ord(x))[2:] for x in text))
#
#
#
#def dprint(*args, **kwargs):
#    if click_debug:
#        caller = sys._getframe(1).f_code.co_name
#        print(str("%.5f" % time.time()), os.getpid(), '{0: <15}'.format(caller+'()'), *args, file=sys.stderr, **kwargs)
#
#def eprint(*args, **kwargs):
#    print(*args, file=sys.stderr, **kwargs)
#
#print(pydoc.render_doc(logger))
#
#log_level=log_levels['DEBUG']
#log_level=log_levels['INFO:']
#
## pylint: disable=invalid-name
## pylint: enable=invalid-name
#
#
#def print_traceback():
#    ex_type, ex, tb = sys.exc_info()
#    traceback.print_tb(tb)
#    del tb
#
#
