#!/usr/bin/env python3
# -*- coding: utf8 -*-

import os
from pathlib import Path
import click
from urllib.parse import urlparse
from kcl.dirops import dir_exists
from kcl.dirops import create_dir
from kcl.printops import eprint

APPS = Path("/home/cfg/_myapps")

@click.group()
def cli():
    pass


def valid_branch(ctx, param, value):
    branch_check_cmd = "git check-ref-format --branch " + value
    if not os.system(branch_check_cmd):
        raise click.BadParameter('Invalid branch name.')
    return True


@cli.command()
#@click.option('--new-apppath', type=click.Path(exists=False, file_okay=False, dir_okay=False, writable=False, readable=True, resolve_path=True, allow_dash=False, path_type=None))
@click.argument('git_repo', type=str, nargs=1)
@click.argument('branch', type=str, callback=valid_branch, nargs=1)
@click.option('--verbose', is_flag=True)
@click.pass_context
def new(ctx, git_repo, branch, verbose):

    #if not (new_apppath or git_repo):
    #    click.echo(ctx.get_help(), color=ctx.color)

    #if git_repo:
    #    assert new_branch

    #if new_apppath:
    #    apppath = os.path.realpath(os.path.expanduser(new_apppath))
    #    app_collection_folder, appname = os.path.split(apppath)
    #    #app_collection_folder = os.path.dirname(apppath)
    #    newapp_template_folder = app_collection_folder + '/newapp'
    #    eprint("newapp_template_folder:", newapp_template_folder)
    #    assert dir_exists(newapp_template_folder)
    #    eprint("creating app:", appname)
    #    eprint("in:", app_collection_folder)
    #    assert not dir_exists(apppath)
    #    create_dir(apppath)
    #    #create_dir(apppath + '/' + appname)

    #    cp_command = "cp -avr " + newapp_template_folder + '/*' + ' ' + apppath + '/'
    #    eprint("cp_command:", cp_command)
    #    os.system(cp_command)

    #    cp_edit_cfg_command = "cp -av " + newapp_template_folder + '/.edit_config' + ' ' + apppath + '/'
    #    eprint("cp_edit_cfg_command:", cp_edit_cfg_command)
    #    os.system(cp_edit_cfg_command)

    #    mv_command = "mv " + apppath + '/newapp' + ' ' + apppath + '/' + appname
    #    eprint("mv_command:", mv_command)
    #    os.system(mv_command)

    #    mv_app_command = "mv " + apppath + '/' + appname + '/newapp.py' + ' ' + apppath + '/' + appname + '/' + appname + '.py'
    #    eprint("mv_app_command:", mv_app_command)
    #    os.system(mv_app_command)

    #    replace_text_command = "replace-text --recursive " + "newapp" + ' ' + appname + ' ' + apppath
    #    eprint("replace_text_command:", replace_text_command)
    #    os.system(replace_text_command)

    #    os.chdir(apppath)
    #    os.system("git init")

    #elif git_repo:
    if git_repo:
        assert git_repo.startswith('https://github.com/jakeogh/')
        git_repo_parsed = urlparse(git_repo)
        #print(git_repo)
        #print(dir(git_repo))
        git_repo_path = git_repo_parsed.path
        if "." in git_repo_path:
            if git_repo_path.endswith('.git'):
                git_repo_path = git_repo_path[:-4]
            else:
                assert False

        git_repo_path = Path(git_repo_path)
        app_name = git_repo_path.parts[-1]
        app_path = APPS / app_name
        eprint("app_path:", app_path)
        git_clone_cmd = " ".join(["git clone", git_repo, str(app_path)])
        print(git_clone_cmd)
        os.system(git_clone_cmd)
        os.chdir(app_path)
        repo_config_cmd = "git remote set-url origin git@github.com:jakeogh/" + app_name + '.git'
        print(repo_config_cmd)
        os.system(repo_config_cmd)
        branch_cmd = "git checkout -b " + '"' + branch + '"'
        print(branch_cmd)
        os.system(branch_cmd)


if __name__ == '__main__':
    cli()


#import os
#import sys
#
## drop into shell anywhere with:
## import IPython; IPython.embed()
## import pdb; pdb.set_trace()
## from pudb import set_trace; set_trace(paused=False)
## https://news.ycombinator.com/item?id=16611827 3.7
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
##https://github.com/Lukasa/utils/blob/master/two_digit_numbers.py
#
#def main(path):
#    print(path)
#    with open(path, 'rb') as fh:
#        data = fh.read()
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
#
#
##standard example:
#def main(dsn):
#    "Do something"
#    print("ok")
#
#if __name__ == '__main__':
#    import sys
#    n = len(sys.argv[1:])
#    if n == 0:
#        sys.exit('usage: python %s dsn' % sys.argv[0])
#    elif n == 1:
#        main(sys.argv[1])
#    else:
#        sys.exit('Unrecognized arguments: %s' % ' '.join(sys.argv[2:]))
#
#
##argparse example:
#def main(dsn):
#    "Do something"
#    print(dsn)
#
#if __name__ == '__main__':
#    import argparse
#    p = argparse.ArgumentParser()
#    p.add_argument('dsn')
#    arg = p.parse_args()
#    main(arg.dsn)
#
#
##plac example (uses argparse): -h and --help work
#def main(dsn):
#    "Do something"
#    print(dsn)
#
#if __name__ == '__main__':
#    import plac
#    plac.call(main)
#
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
#
#
##formatting strings
#
#
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
#def exec_command(command):
#    tar_cmd_proc = subprocess.Popen(tar_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
#    cprint("executing tar_command:", tar_command)
#    tar_cmd_proc_output_stdout, tar_cmd_proc_output_stderr = tar_cmd_proc.communicate(gpg_cmd_proc_output_stdout)
#    cprint("tar_cmd_proc_output_stdout:")
#    tar_cmd_proc_output_stdout_decoded = tar_cmd_proc_output_stdout.decode('utf-8')
#    for line in tar_cmd_proc_output_stdout_decoded.split('\n'):
#        cprint("STDOUT:", line)
#
#    cprint("tar_cmd_proc_output_stderr:")
#    tar_cmd_proc_output_stderr_decoded = tar_cmd_proc_output_stderr.decode('utf-8')
#    for line in tar_cmd_proc_output_stderr_decoded.split('\n'):
#        cprint("STDERR:", line)
#
#    cprint("tar_cmd_proc.returncode:", tar_cmd_proc.returncode)
#
#    if tar_cmd_proc.returncode != 0:
#        cprint("tar did not return 0")
#        return False
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
