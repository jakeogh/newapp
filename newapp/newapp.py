#!/usr/bin/env python3
# -*- coding: utf8 -*-

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import click
import sh
from getdents import files
from getdents import paths
from icecream import ic
from kcl.configops import click_read_config
from kcl.fileops import write_line_to_file
from kcl.printops import eprint
from kcl.userops import not_root
from replace_text import replace_text
from run_command import run_command
from with_chdir import chdir

from .templates import app
from .templates import ebuild
from .templates import echo_url
from .templates import edit_config
from .templates import gitignore
from .templates import init
from .templates import setup_py

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
# pylint: disable=C0305  # Trailing newlines


CFG, CONFIG_MTIME = click_read_config(click_instance=click,
                                      app_name='newapp',
                                      verbose=False,
                                      debug=False,)

#ic(CFG)

# https://github.com/mitsuhiko/click/issues/441
CONTEXT_SETTINGS = dict(default_map=CFG)
    #dict(help_option_names=['--help'],
    #     terminal_width=shutil.get_terminal_size((80, 20)).columns)


@click.group(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click.option('--verbose', is_flag=True)
@click.option('--debug', is_flag=True)
@click.pass_context
def cli(ctx, verbose, debug):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['debug'] = debug


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
    ic(value)
    branch_check_cmd = "git check-ref-format --branch " + value
    if os.system(branch_check_cmd):
        raise click.BadParameter('fatal: "{0}" is not a valid branch name'.format(value))
    return value


def generate_edit_config(*,
                         package_name,
                         package_group,
                         local,):

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


def generate_setup_py(*,
                      url,
                      package_name,
                      command,
                      license,
                      owner,
                      owner_email,
                      description,):

    ic(url,
       package_name,
       command,
       license,
       owner,
       owner_email,
       description,)

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


def generate_url_template(url):
    return echo_url.format(url=url)


def generate_init_template(package_name):
    return init.format(package_name=package_name)


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
    not_root()
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
@click.argument("package-name", type=str, default="TESTPACKAGE")
@click.pass_context
def get_app_template(ctx, package_name):
    app_template = generate_app_template(package_name)
    print(app_template)


def rename_repo(*,
                app_path: Path,
                old_name: str,
                new_name: str,
                verbose: bool,
                debug: bool,):
    os.chdir(app_path)
    sh.git.mv(old_name, new_name)
    all_paths = list(paths(app_path, verbose=verbose, debug=debug,))
    exclude_path = app_path / Path('.git')
    for dent in all_paths:
        path = dent.pathlib
        if path.name.startswith('.'):
            continue
        if path.as_posix().startswith(exclude_path.as_posix()):
            continue

        if old_name in path.name:
            new_path_name = path.name.replace(old_name, new_name)
            new_path = path.parent / Path(new_path_name)
            sh.git.mv(path, new_path)

    all_files = list(files(app_path, verbose=verbose, debug=debug,))
    exclude_path = app_path / Path('.git')
    for dent in all_files:
        path = dent.pathlib
        if path.name.startswith('.'):
            continue
        if path.as_posix().startswith(exclude_path.as_posix()):
            continue

        assert old_name not in path.name
        replace_text(file_to_modify=path,
                     match=old_name,
                     replacement=new_name,
                     verbose=verbose,
                     debug=debug,)


def clone_repo(*,
               branch: str,
               repo_url: str,
               apps_folder: Path,
               template_repo_url: str,
               app_path: Path,
               hg: bool,
               verbose: bool,
               debug: bool,):

    app_name, app_user, _, _ = parse_url(repo_url, apps_folder=apps_folder, verbose=verbose, debug=debug,)
    rename_cloned_repo = False
    if template_repo_url:
        template_app_name, template_app_user, _, _ = parse_url(template_repo_url, apps_folder=apps_folder, verbose=verbose, debug=debug,)
        repo_to_clone_url = template_repo_url
        if template_app_name != app_name:
            rename_cloned_repo = True
    else:
        repo_to_clone_url = repo_url

    if hg:
        clone_cmd = "hg clone"
    else:
        clone_cmd = "git clone"

    clone_cmd = " ".join([clone_cmd, repo_to_clone_url, str(app_path)])
    ic(clone_cmd)
    os.system(clone_cmd)

    if branch != "master":
        branch_cmd = "git checkout -b " + '"' + branch + '"'
        ic(branch_cmd)
        os.system(branch_cmd)

    if not rename_cloned_repo:  # when renaming a template repo, dont want to fork if its one of my repos
        git_fork_cmd = "hub fork"
        os.system(git_fork_cmd)
    else:
        rename_repo(app_path=app_path,
                    old_name=template_app_name,
                    new_name=app_name,
                    verbose=verbose,
                    debug=debug,)


def create_repo(*,
                app_path: Path,
                app_module_name: str,
                hg: bool,
                verbose: bool,
                debug: bool,):

    if hg:
        raise NotImplementedError('hg')
    os.makedirs(app_path, exist_ok=False)
    os.chdir(app_path)
    os.makedirs(app_module_name, exist_ok=False)
    os.system("git init")


#def rename_project(ctx, *,
#                   old_name: str,
#                   new_name: str,
#                   verbose: bool,
#                   debug: bool,):


def remote_add_origin(*,
                      app_path: Path,
                      local: bool,
                      app_name: str,
                      hg: bool,
                      verbose: bool,
                      debug: bool,):

    if hg:
        raise NotImplementedError('hg')

    repo_config_command = "git remote add origin git@github.com:jakeogh/{}.git".format(app_name)
    ic(repo_config_command)
    if not local:
        os.chdir(app_path)
        os.system(repo_config_command)
    else:
        ic('local == True, skipping:', repo_config_command)

    enable_github = [
        "#!/bin/sh",
        'hub create {}'.format('jakeogh/' + app_name),
        repo_config_command,
        'git push --set-upstream origin master',
        "\n"]
    enable_github = "\n".join(enable_github)
    output_file = app_path / Path('enable_github.sh')
    with open(output_file, 'x') as fh:
        fh.write(enable_github)


def parse_url(repo_url: str, *,
              apps_folder: Path,
              verbose: bool,
              debug: bool,):
    if repo_url.startswith('git:github.com:'):
        app_name = repo_url.split(':')[-1].split('.git')[0]
        app_user = repo_url.split(':')[-1].split('/')[0]
    else:
        url_parsed = urlparse(repo_url)
        if verbose:
            ic(url_parsed)

        repo_url_path = Path(url_parsed.path)
        app_name = repo_url_path.parts[-1]
        app_user = repo_url_path.parts[-2]

    app_module_name = app_name.replace('-', '_')
    ic(app_module_name)
    app_path = apps_folder / Path(app_name)
    ic(app_path)
    return app_name, app_user, app_module_name, app_path


def replace_text_in_file(*,
                         path: Path,
                         match_pairs: tuple,
                         verbose: bool,
                         debug: bool,):
    assert isinstance(match_pairs, tuple)
    for old_match, new_match in match_pairs:
        ic(path, old_match, new_match)
        replace_text(file_to_modify=path,
                     match=old_match,
                     replacement=new_match,
                     verbose=verbose,
                     debug=debug,)


def write_url_sh(repo_url, *,
                 verbose: bool,
                 debug: bool,):
    url_template = generate_url_template(url=repo_url)
    with open("url.sh", 'x') as fh:
        fh.write(url_template)
    sh.chmod('+x', 'url.sh')


@cli.command()
@click.argument('old_repo_url', type=str, nargs=1)
@click.argument('new_repo_url', type=str, nargs=1)
@click.argument('group', type=str, nargs=1)
@click.option('--apps-folder', type=str, required=True)
@click.option('--gentoo-overlay-repo', type=str, required=True)
@click.option('--github-user', type=str, required=True)
@click.option('--local', is_flag=True)
@click.option('--hg', is_flag=True)
@click.pass_context
def rename(ctx,
           old_repo_url,
           new_repo_url,
           group,
           apps_folder,
           gentoo_overlay_repo,
           github_user,
           local,
           hg,):

    not_root()
    verbose = ctx.obj['verbose']
    debug = ctx.obj['debug']
    apps_folder = Path(apps_folder)
    ic(apps_folder)

    old_app_name, old_app_user, old_app_module_name, old_app_path = \
        parse_url(old_repo_url,
                  apps_folder=apps_folder,
                  verbose=verbose,
                  debug=debug,)
    new_app_name, new_app_user, new_app_module_name, new_app_path = \
        parse_url(new_repo_url,
                  apps_folder=apps_folder,
                  verbose=verbose,
                  debug=debug,)
    assert old_app_user == new_app_user

    ic(old_app_name, new_app_name)
    ic(old_app_path, new_app_path)

    os.chdir(old_app_path)
    old_setup_py = old_app_path / Path('setup.py')
    replace_text_in_file(path=old_setup_py,
                         match_pairs=((old_app_name, new_app_name), (old_app_module_name, new_app_module_name),),
                         verbose=verbose,
                         debug=debug,)
    sh.git.add(old_setup_py)
    del(old_setup_py)

    old_readme_md = old_app_path / Path('README.md')
    try:
        replace_text_in_file(path=old_readme_md,
                             match_pairs=((old_app_name, new_app_name), (old_app_module_name, new_app_module_name),),
                             verbose=verbose,
                             debug=debug,)
    except FileNotFoundError as e:
        ic(e)
        sh.touch('README.md')
    sh.git.add(old_readme_md)
    del(old_readme_md)

    old_url_sh = old_app_path / Path('url.sh')
    try:
        replace_text(file_to_modify=old_url_sh,
                     match=old_app_name,
                     replacement=new_app_name,
                     verbose=verbose,
                    debug=debug,)
    except Exception as e:
        write_url_sh(new_repo_url, verbose=verbose, debug=debug,)
    sh.git.add(old_url_sh)
    del(old_url_sh)

    old_edit_config = old_app_path / Path('.edit_config')
    replace_text(file_to_modify=old_edit_config,
                 match=old_app_name,
                 replacement=new_app_name,
                 verbose=verbose,
                 debug=debug,)
    #sh.git.add(old_edit_config)
    del(old_edit_config)

    enable_github_sh = old_app_path / Path('enable_github.sh')
    replace_text(file_to_modify=enable_github_sh,
                 match=old_app_name,
                 replacement=new_app_name,
                 verbose=verbose,
                 debug=debug,)
    #sh.git.add(enable_github_sh)
    del(enable_github_sh)

    old_app_py = old_app_path / old_app_module_name / Path(old_app_module_name + '.py')
    replace_text_in_file(path=old_app_py,
                         match_pairs=((old_app_name, new_app_name), (old_app_module_name, new_app_module_name),),
                         verbose=verbose,
                         debug=debug,)
    sh.git.add(old_app_py)
    #del(old_app_py)

    old_app_init_py = old_app_path / old_app_module_name / Path('__init__.py')
    replace_text(file_to_modify=old_app_init_py,
                 match=old_app_module_name,
                 replacement=new_app_module_name,
                 verbose=verbose,
                 debug=debug,)
    sh.git.add(old_app_init_py)
    del old_app_init_py

    os.chdir(old_app_path)

    # in old_app_path
    new_app_py = old_app_path / old_app_module_name / Path(new_app_module_name + '.py')
    sh.git.mv(old_app_py, new_app_py)
    del old_app_py
    del new_app_py
    sh.git.mv(old_app_module_name, new_app_module_name)
    #print(sh.ls())
    sh.git.add(Path(new_app_module_name) / Path('__init__.py'))
    sh.git.add(Path(new_app_module_name) / Path('py.typed'))
    sh.git.add(Path(new_app_module_name) / Path(new_app_module_name + '.py'))
    old_ebuild_symlink = old_app_path / Path(old_app_name + '-9999.ebuild')
    if not old_ebuild_symlink.exists():
        old_ebuild_folder = Path(gentoo_overlay_repo) / Path(group) / Path(old_app_name)
        sh.ln('-s', old_ebuild_folder / old_ebuild_symlink.name, old_ebuild_symlink.name)
        del old_ebuild_folder

    assert old_ebuild_symlink.exists()
    os.chdir(old_ebuild_symlink.resolve().parent)

    # in ebuild folder
    old_ebuild_path = Path(old_app_name + '-9999.ebuild').resolve()
    replace_text(file_to_modify=old_ebuild_path,
                 match=old_app_module_name,
                 replacement=new_app_module_name,
                 verbose=verbose,
                 debug=debug,)
    sh.git.add(old_ebuild_path)
    new_ebuild_name = Path(new_app_name + '-9999.ebuild')
    sh.git.mv(old_ebuild_path, new_ebuild_name)
    del old_ebuild_path
    os.chdir('..')

    # in ebuild parent folder
    sh.mv(old_app_name, new_app_name, '-v')
    new_ebuild_path = Path(new_app_name / new_ebuild_name).resolve()
    sh.git.commit('-m', 'rename', _ok_code=[0, 1])
    sh.git.push()
    os.chdir(old_app_path)

    # in old_app_folder
    print(sh.ls())
    sh.rm(old_ebuild_symlink.name)
    del old_ebuild_symlink

    new_ebuild_symlink_name = new_ebuild_name
    sh.ln('-s', new_ebuild_path, new_ebuild_symlink_name)
    del new_ebuild_symlink_name
    del new_ebuild_name
    sh.git.commit('-m', 'rename')
    sh.git.remote.rm('origin')
    sh.git.push()

    # in apps_folder
    os.chdir(apps_folder)
    sh.mv(old_app_path, new_app_path, '-v')


@cli.command()
@click.option('--apps-folder', type=str, required=True)
@click.option('--gentoo-overlay-repo', type=str, required=True)
@click.option('--local', is_flag=True)
@click.option('--github-user', type=str, required=True)
@click.pass_context
def check_all(ctx,
              apps_folder,
              gentoo_overlay_repo,
              github_user,
              local,):

    not_root()
    verbose = ctx.obj['verbose']
    debug = ctx.obj['debug']
    apps_folder = Path(apps_folder)
    ic(apps_folder)

    edit_configs = []
    for file in files(apps_folder, verbose=verbose, debug=debug,):
        if file.name == b'.edit_config':
            file = Path(file)
            if verbose:
                ic(file)
            edit_configs.append(file)

    edit_configs = sorted(edit_configs)
    for edit_config_path in edit_configs:
        ic(edit_config_path)
        with chdir(edit_config_path.parent):
            remote = sh.git.remote('get-url', 'origin')
            app_name, app_user, app_module_name, app_path = parse_url(remote,
                                                                      apps_folder=apps_folder,
                                                                      verbose=verbose,
                                                                      debug=debug,)
            if not remote.startswith('git@github.com:'):
                if app_user == github_user:
                    ic('remote is to', github_user, 'but does not startwith git@github.com:', remote)
                    raise ValueError(edit_config_path, remote)
            if not app_name == edit_config_path.parent.name:
                ic(app_name, 'is not', edit_config_path.parent.name)
                raise ValueError(edit_config_path, remote)

        del app_name, app_user, app_module_name, app_path


@cli.command()
@click.argument('repo_url', type=str, nargs=1)
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
@click.option('--template', 'template_repo_url', type=str)
@click.option('--hg', is_flag=True)
@click.pass_context
def new(ctx,
        repo_url,
        group,
        branch,
        apps_folder,
        gentoo_overlay_repo,
        github_user,
        license,
        owner,
        owner_email,
        description,
        local,
        template_repo_url,
        hg,):

    not_root()
    verbose = ctx.obj['verbose']
    debug = ctx.obj['debug']
    apps_folder = Path(apps_folder)
    ic(apps_folder)

    assert repo_url.startswith('https://github.com/{}/'.format(github_user))

    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]

    assert '/' not in group
    assert ':' not in group

    app_name, app_user, app_module_name, app_path = parse_url(repo_url,
                                                              apps_folder=apps_folder,
                                                              verbose=verbose,
                                                              debug=debug,)
    ic(app_name)
    ic(app_user)
    assert app_user == github_user
    assert '_' not in app_path.name

    if template_repo_url:
        clone_repo(repo_url=repo_url,
                   template_repo_url=template_repo_url,
                   apps_folder=apps_folder,
                   hg=hg,
                   branch=branch,
                   app_path=app_path,
                   verbose=verbose,
                   debug=debug,)

    if not app_path.exists():
        create_repo(hg=hg,
                    app_path=app_path,
                    app_module_name=app_module_name,
                    verbose=verbose,
                    debug=debug,)

        os.chdir(app_path)

        if not template_repo_url:
            with open("setup.py", 'x') as fh:
                fh.write(generate_setup_py(package_name=app_module_name,
                                           command=app_name,
                                           owner=owner,
                                           owner_email=owner_email,
                                           description=description,
                                           license=license,
                                           url=repo_url))

            template = generate_gitignore_template()
            with open('.gitignore', 'x') as fh:
                fh.write(template)

            write_url_sh(repo_url, verbose=verbose, debug=debug,)

            os.system("fastep")

            os.chdir(app_module_name)
            app_template = generate_app_template(package_name=app_module_name)
            with open(app_module_name + '.py', 'x') as fh:
                fh.write(app_template)

            init_template = generate_init_template(package_name=app_module_name)
            with open("__init__.py", 'x') as fh:
                fh.write(init_template)
            sh.touch('py.typed')

            os.chdir(app_path)
            sh.git.add('--all')
    else:
        eprint("Not creating new app, {} already exists.".format(app_path))

    os.chdir(app_path)
    with open(".edit_config", 'x') as fh:
        fh.write(generate_edit_config(package_name=app_name,
                                      package_group=group,
                                      local=local))

    remote_add_origin(hg=hg,
                      app_path=app_path,
                      local=local,
                      app_name=app_name,
                      verbose=verbose,
                      debug=debug,)

    ebuild_path = Path(gentoo_overlay_repo) / Path(group) / Path(app_name)
    if not ebuild_path.exists():
        os.makedirs(ebuild_path, exist_ok=False)
        os.chdir(ebuild_path)
        ebuild_name = app_name + "-9999.ebuild"

        with open(ebuild_name, 'w') as fh:
            fh.write(generate_ebuild_template(description=description,
                                              homepage=repo_url,
                                              app_path=app_path,))
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
                           make_new=False,
                           verbose=verbose,
                           debug=debug,)
        sh.ln('-s', ebuild_path / ebuild_name, app_path / ebuild_name)
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
##http://liw.fi/cmdtest/
##http://liw.fi/cliapp/
#
#
#
#import os
#home = os.path.expanduser("~")
#os.path.sep = b'/'
#os.path.altsep = b'/'
#program_folder = os.path.dirname(os.path.realpath(__file__))
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
##http://stackoverflow.com/questions/1549509/remove-duplicates-in-a-list-while-keeping-its-order-python
#def unique(seq):
#    seen = set()
#    for item in seq:
#        if item not in seen:
#            seen.add(item)
#            yield item
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
#def print_hex(text):
#    print(':'.join(hex(ord(x))[2:] for x in text))
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

