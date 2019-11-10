#!/usr/bin/env python3
# -*- coding: utf8 -*-

import os
from pathlib import Path
from urllib.parse import urlparse
import click
from kcl.printops import eprint
from kcl.fileops import write_unique_line_to_file
from kcl.configops import click_read_config
from icecream import ic
from .templates import app
from .templates import ebuild
from .templates import gitignore
from .templates import edit_config
from .templates import setup_py

CFG = click_read_config(click_instance=click, app_name='newapp', verbose=True)

# https://github.com/mitsuhiko/click/issues/441
CONTEXT_SETTINGS = dict(default_map=CFG)
    #dict(help_option_names=['--help'],
    #     terminal_width=shutil.get_terminal_size((80, 20)).columns)


def valid_branch(ctx, param, value):
    eprint("value:", value)
    branch_check_cmd = "git check-ref-format --branch " + value
    if os.system(branch_check_cmd):
        raise click.BadParameter('fatal: "{0}" is not a valid branch name'.format(value))
    return value


def generate_edit_config(package_name, package_group, local):
    if local:
        remote = "#"
    remote += '''remote="https://github.com/jakeogh/{}.git"'''.format(package_name)

    optional_blank_remote = ''
    if local:
        optional_blank_remote = '''remote=""'''
    return edit_config.format(package_name=package_name, package_group=package_group, optional_blank_remote=optional_blank_remote, remote=remote)


def generate_setup_py(url, package_name, license, owner, owner_email, description):
    return setup_py.format(package_name=package_name, url=url, license=license, owner=owner, owner_email=owner_email, description=description)


def generate_ebuild_template(description, homepage, app_path):
    return ebuild.format(description=description, homepage=homepage, app_path=app_path)


def generate_gitignore_template():
    return gitignore.format()


def generate_app_template():
    return app


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('git_repo', type=str, nargs=1)
@click.argument('group', type=str, nargs=1)
@click.argument('branch', type=str, callback=valid_branch, nargs=1, default="master")
@click.option('--apps-folder', type=str, required=True)
@click.option('--gentoo-overlay-repo', type=str, required=True)
@click.option('--github-user', type=str, required=True)
@click.option('--verbose', is_flag=True)
@click.option('--license', type=click.Choice(["ISC"]), default="ISC")
@click.option('--owner', type=str, required=True)
@click.option('--owner-email', type=str, required=True)
@click.option('--description', type=str, default="Short explination of what it does _here_")
@click.option('--local', is_flag=True)
@click.option('--template', is_flag=True)
@click.pass_context
def cli(ctx, git_repo, group, branch, apps_folder, gentoo_overlay_repo, github_user, verbose, license, owner, owner_email, description, local, template):
    ic(apps_folder)

    if not git_repo.startswith('https://github.com/{}/'.format(github_user)):
        assert template
    if git_repo.endswith('.git'):
        git_repo = git_repo[:-4]

    git_repo_parsed = urlparse(git_repo)
    git_repo_path = Path(git_repo_parsed.path)
    app_name = git_repo_path.parts[-1]
    app_path = Path(apps_folder) / Path(app_name)
    ic(app_path)
    if not app_path.exists():
        if template:
            git_clone_cmd = " ".join(["git clone", git_repo, str(app_path)])
            print(git_clone_cmd)
            os.system(git_clone_cmd)
            os.chdir(app_path)
            #os.makedirs(app_name, exist_ok=False)  # hm
        else:
            os.makedirs(app_path, exist_ok=False)
            os.chdir(app_path)
            os.makedirs(app_name, exist_ok=False)
            os.system("git init")

        repo_config_command = "git remote set-url origin git@github.com:jakeogh/" + app_name + '.git'
        print(repo_config_command)
        if not local:
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
            print(branch_cmd)
            os.system(branch_cmd)

        with open(".edit_config", 'x') as fh:
            fh.write(generate_edit_config(package_name=app_name, package_group=group, local=local))

        if not template:
            with open("setup.py", 'x') as fh:
                fh.write(generate_setup_py(package_name=app_name,
                                           owner=owner,
                                           owner_email=owner_email,
                                           description=description,
                                           license=license,
                                           url=git_repo))

            template = generate_gitignore_template()
            with open('.gitignore', 'x') as fh:
                fh.write(template)

            os.system("fastep")

            os.chdir(app_name)
            app_template = generate_app_template()
            with open(app_name + '.py', 'x') as fh:
                fh.write(app_template)

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
            fh.write(generate_ebuild_template(description=description, homepage=git_repo, app_path=app_path))
        os.system("git add " + ebuild_name)
        accept_keyword = "={}/{}-9999 **\n".format(group, app_name)
        accept_keywords = Path("/etc/portage/package.accept_keywords")
        write_unique_line_to_file(file_to_write=accept_keywords, line=accept_keyword, make_new=False)
    else:
        eprint("Not creating new ebuild, {} already exists.".format(ebuild_path))

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
