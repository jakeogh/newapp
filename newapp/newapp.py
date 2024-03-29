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
# pylint: disable=C0305  # Trailing newlines


import os
import shutil
import sys
from datetime import date
from math import inf
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import click
import sh
from asserttool import eprint
from asserttool import ic
from asserttool import not_root
from asserttool import tv
from clicktool import click_add_options
from clicktool import click_global_options
from configtool import click_read_config
from getdents import files
from getdents import files_pathlib
from getdents import paths
from licenseguesser import license_list
from pathtool import write_line_to_file
from portagetool import portage_categories
from replace_text import replace_text_in_file
from run_command import run_command
from with_chdir import chdir

from .templates import bash_app
from .templates import depend_python
from .templates import ebuild
from .templates import echo_url
from .templates import edit_config
from .templates import gitignore
from .templates import init
from .templates import python_app
from .templates import setup_py
from .templates import src_install_dobin
from .templates import zig_app

sh.mv = None

CFG, CONFIG_MTIME = click_read_config(click_instance=click,
                                      app_name='newapp',
                                      verbose=False,
                                      )


# https://github.com/mitsuhiko/click/issues/441
CONTEXT_SETTINGS = dict(default_map=CFG)
    #dict(help_option_names=['--help'],
    #     terminal_width=shutil.get_terminal_size((80, 20)).columns)


#ic(CFG)


def replace_text(path: Path,
                 match: str,
                 replacement: str,
                 verbose: int,
                 ) -> None:

    if verbose:
        ic(match, replacement)

    replace_text_in_file(path=path,
                         match=match.encode('utf8'),
                         replacement=replacement.encode('utf8'),
                         output_fh=None,
                         read_mode='rb',
                         write_mode='wb',
                         stdout=False,
                         remove_match=False,
                         verbose=verbose,
                         )


def replace_match_pairs_in_file(*,
                                path: Path,
                                match_pairs: tuple,
                                verbose: int,
                                ) -> None:
    assert isinstance(match_pairs, tuple)
    for old_match, new_match in match_pairs:
        if old_match == new_match:
            continue
        ic(path, old_match, new_match)
        replace_text(path=path,
                     match=old_match,
                     replacement=new_match,
                     verbose=verbose,
                     )


def get_url_for_overlay(overlay: str,
                        verbose: int,
                        ) -> str:
    command = ["eselect", "repository", "list"]
    command_output = run_command(command, str_output=True, verbose=verbose,)
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

    raise ValueError(f'unknown repo {overlay}')


def valid_branch(ctx, param, value):
    ic(value)
    branch_check_cmd = "git check-ref-format --branch " + value
    if os.system(branch_check_cmd):
        raise click.BadParameter(f'fatal: "{value}" is not a valid branch name')
    return value


def find_edit_configs(*,
                      apps_folder: Path,
                      verbose: int,
                      ):

    edit_configs = []
    for path in files_pathlib(apps_folder, verbose=verbose,):
        if path.name == '.edit_config':
            edit_configs.append(path)

    edit_configs = sorted(edit_configs)
    return edit_configs


def generate_edit_config(*,
                         package_name: str,
                         package_group: str,
                         local: bool,
                         ):

    if local:
        remote = "#"
    else:
        remote = ''
    remote += f'''remote="https://github.com/jakeogh/{package_name}.git"'''

    optional_blank_remote = ''
    if local:
        optional_blank_remote = '''remote=""'''
    return edit_config.format(package_name=package_name,
                              package_group=package_group,
                              optional_blank_remote=optional_blank_remote,
                              remote=remote,
                              )


def generate_setup_py(*,
                      url: str,
                      package_name: str,
                      command: str,
                      license: str,
                      owner: str,
                      owner_email: str,
                      description: str,
                      ):

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
                           description=description,)


def generate_src_install_dobin_template(app_name):
    return src_install_dobin.format(app_name=app_name)


def generate_ebuild_template(*,
                             description: str,
                             enable_python: bool,
                             enable_dobin: bool,
                             homepage: str,
                             app_path: Path,
                             app_name: str,
                             ):
    ic(enable_python)
    inherit_python = ''
    rdepend_python = ''
    if enable_python:
        inherit_python = 'inherit distutils-r1'
        rdepend_python = depend_python
    result = ebuild.format(description=description,
                           inherit_python=inherit_python,
                           depend_python=rdepend_python,
                           homepage=homepage,
                           app_path=app_path,
                           year=str(date.today().year),
                           )

    if enable_dobin:
        result += generate_src_install_dobin_template(app_name)
    return result


def generate_gitignore_template():
    return gitignore.format()


def generate_app_template(package_name: str, *,
                          language: str,
                          append_files: Optional[tuple[Path]],
                          verbose: int,
                          ) -> str:

    result = None
    if language == 'python':
        result = python_app.format(package_name=package_name, newline="\\n", null="\\x00")
    if language == 'bash':
        result = bash_app.format(package_name=package_name, newline="\\n", null="\\x00")
    if language == 'zig':
        result = zig_app.format(package_name=package_name, newline="\\n", null="\\x00")

    if append_files is None:
        append_files = ()

    if result:
        for file in append_files:
            with open(file, 'r', encoding='utf8') as fh:
                result += fh.read()
        return result

    raise ValueError(language)


def generate_url_template(url):
    return echo_url.format(url=url)


def generate_init_template(package_name):
    return init.format(package_name=package_name)


def rename_repo_at_app_path(*,
                            app_path: Path,
                            old_name: str,
                            new_name: str,
                            app_group: str,
                            hg: bool,
                            local: bool,
                            verbose: int,
                            ):
    ic(old_name, new_name)
    old_module_name = old_name.replace('-', '_')
    new_module_name = old_name.replace('-', '_')

    with chdir(app_path):
        if Path(old_name).exists():  # not all apps have a dir here
            sh.git.mv(old_name, new_name)
        if Path(old_name.replace('-', '_')).exists():  # not all apps have a dir here
            sh.git.mv(old_name.replace('-', '_'), new_name)

        with open(".edit_config", 'x', encoding='utf8') as fh:
            fh.write(generate_edit_config(package_name=new_name,
                                          package_group=app_group,
                                          local=local,))

        # enable_github.sh needs to be created if this is a remote template
        remote_add_origin(hg=hg,
                          app_path=app_path,
                          local=local,
                          app_name=new_name,
                          verbose=verbose,
                          )

        all_paths = list(paths(app_path,
                               verbose=verbose,
                               ))
        exclude_path = app_path / Path('.git')
        for dent in all_paths:
            path = dent.pathlib
            if path.name.startswith('.'):
                continue
            if path.parent.name.startswith('.'):
                continue
            if path.as_posix().startswith(exclude_path.as_posix()):
                continue

            if old_name in path.name:
                if path.name == new_name:
                    continue
                ic(old_name, path.name)
                new_path_name = path.name.replace(old_name, new_name)
                ic(new_path_name)
                new_path = path.parent / Path(new_path_name)
                sh.git.mv(path, new_path)

            if old_name.replace('-', '_') in path.name:
                if path.name == new_name:
                    continue
                ic(old_name.replace('-', '_'), path.name)
                new_path_name = path.name.replace(old_name.replace('-', '_'), new_name)
                ic(new_path_name)
                new_path = path.parent / Path(new_path_name)
                sh.git.mv(path, new_path)

        all_files = list(files(app_path,
                               verbose=verbose,
                               ))
        exclude_path = app_path / Path('.git')
        for dent in all_files:
            ic(dent)
            path = dent.pathlib
            if path.name.startswith('.'):
                continue
            if path.parent.name.startswith('.'):
                continue
            if path.as_posix().startswith(exclude_path.as_posix()):
                continue

            replace_match_pairs_in_file(path=path,
                                        match_pairs=((old_name, new_name), (old_module_name, new_module_name),),
                                        verbose=verbose,
                                        )
        sh.git.add('-u')
        sh.git.commit('-m rename')


def clone_repo(*,
               branch: str,
               repo_url: str,
               apps_folder: Path,
               template_repo_url: str,
               app_path: Path,
               app_group: str,
               hg: bool,
               local: bool,
               verbose: int,
               ):

    app_name, app_user, _, _ = parse_url(repo_url, apps_folder=apps_folder, verbose=verbose,)
    rename_cloned_repo = False
    if template_repo_url:
        template_app_name, template_app_user, _, _ = parse_url(template_repo_url, apps_folder=apps_folder, verbose=verbose,)
        repo_to_clone_url = template_repo_url
        if template_app_name != app_name:
            rename_cloned_repo = True
    else:
        repo_to_clone_url = repo_url

    if hg:
        sh.hg('clone', repo_to_clone_url, str(app_path))
    else:
        sh.git.clone(repo_to_clone_url, str(app_path))

    if branch != "master":
        branch_cmd = "git checkout -b " + '"' + branch + '"'
        ic(branch_cmd)
        os.system(branch_cmd)

    if not rename_cloned_repo:  # when renaming a template repo, dont want to fork if its one of my repos
        git_fork_cmd = "hub fork"
        os.system(git_fork_cmd)
    else:
        rename_repo_at_app_path(app_path=app_path,
                                app_group=app_group,
                                local=local,
                                hg=hg,
                                old_name=template_app_name,
                                new_name=app_name,
                                verbose=verbose,
                                )


def create_repo(*,
                app_path: Path,
                app_module_name: str,
                hg: bool,
                verbose: int,
                ):

    if hg:
        raise NotImplementedError('hg')
    os.makedirs(app_path, exist_ok=False)
    with chdir(app_path):
        os.makedirs(app_module_name, exist_ok=False)
        os.system("git init")


def remote_add_origin(*,
                      app_path: Path,
                      local: bool,
                      app_name: str,
                      hg: bool,
                      verbose: int,
                      ):

    if hg:
        raise NotImplementedError('hg')

    repo_config_command = f"git remote add origin git@github.com:jakeogh/{app_name}.git"
    ic(repo_config_command)
    if not local:
        with chdir(app_path):
            os.system(repo_config_command)
    else:
        ic('local == True, skipping:', repo_config_command)

    enable_github = [
        "#!/bin/sh",
        'hub create {}'.format('jakeogh/' + app_name),
        repo_config_command,
        'git push --set-upstream origin master',
        'touch .push_enabled',
        "\n"]
    enable_github = "\n".join(enable_github)
    output_file = app_path / Path('enable_github.sh')
    with open(output_file, 'x', encoding='utf8') as fh:
        fh.write(enable_github)


def parse_url(repo_url: str,
              *,
              apps_folder: Path,
              verbose: int,
              keep_underscore: bool = False,    # for rename
              ):

    if verbose:
        ic(repo_url)

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

    app_name = app_name.lower()
    if not keep_underscore:
        app_name = app_name.replace('_', '-')
    app_module_name = app_name.replace('-', '_')
    ic(app_module_name)
    app_path = apps_folder / Path(app_name)
    ic(app_path)
    return app_name, app_user, app_module_name, app_path


def write_url_sh(repo_url,
                 *,
                 verbose: int,
                 ):
    url_template = generate_url_template(url=repo_url)
    with open("url.sh", 'x', encoding='utf8') as fh:
        fh.write(url_template)
    sh.chmod('+x', 'url.sh')


def write_setup_py(*,
                   use_existing_repo: bool,
                   app_module_name: str,
                   app_name: str,
                   owner: str,
                   owner_email: str,
                   description: str,
                   license: str,
                   repo_url: str,
                   ):

    if use_existing_repo:
        if Path('setup.py').exists():
            return

    with open("setup.py", 'x') as fh:
        fh.write(generate_setup_py(package_name=app_module_name,
                                   command=app_name,
                                   owner=owner,
                                   owner_email=owner_email,
                                   description=description,
                                   license=license,
                                   url=repo_url,))


@click.group(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click_add_options(click_global_options)
@click.pass_context
def cli(ctx,
        verbose: int,
        verbose_inf: bool,
        ):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose


@cli.command()
@click.pass_context
def template_pylint(ctx):
    app_template = generate_app_template('TEMP',
                                         language='python',
                                         append_files=None,
                                         verbose=ctx.obj['verbose'],
                                         )
    for line in app_template.splitlines():
        if line.startswith('# flake8: '):
            print(line)
        if line.startswith('# pylint: '):
            print(line)


@cli.command()
@click.argument('overlay_name', type=str, nargs=1)
@click.pass_context
def get_overlay_url(ctx,
                    overlay_name,
                    ):
    url = get_url_for_overlay(overlay_name,
                              verbose=ctx.obj['verbose'],
                              )
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
def template_python(ctx,
                    package_name: str,
                    ):
    app_template = generate_app_template(package_name,
                                         language='python',
                                         append_files=None,
                                         verbose=ctx.obj['verbose'],
                                         )
    print(app_template)


@cli.command()
@click.argument("package-name", type=str, default="TESTPACKAGE")
@click.pass_context
def template_bash(ctx,
                  package_name: str,
                  ):

    app_template = generate_app_template(package_name,
                                         language='bash',
                                         append_files=None,
                                         verbose=ctx.obj['verbose'],
                                         )
    print(app_template)


@cli.command()
@click.argument("package-name", type=str, default="TESTPACKAGE")
@click.pass_context
def template_zig(ctx,
                 package_name: str,
                 ):

    app_template = generate_app_template(package_name,
                                         language='zig',
                                         append_files=None,
                                         verbose=ctx.obj['verbose'],
                                         )
    print(app_template)


@cli.command()
@click.argument('old_repo_url', type=str, nargs=1)
@click.argument('new_repo_url', type=str, nargs=1)
@click.argument('group', type=str, nargs=1)
@click.option('--apps-folder', type=str, required=True)
@click.option('--gentoo-overlay-repo', type=str, required=True)
@click.option('--github-user', type=str, required=True)
@click.option('--local', is_flag=True)
@click.option('--hg', is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def rename(ctx,
           old_repo_url,
           new_repo_url,
           group,
           apps_folder,
           gentoo_overlay_repo,
           github_user,
           local,
           verbose: int,
           verbose_inf: bool,
           hg: bool,
           ):

    not_root()
    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    old_app_name, old_app_user, old_app_module_name, old_app_path = \
        parse_url(old_repo_url,
                  apps_folder=apps_folder,
                  keep_underscore=True,
                  verbose=verbose,
                  )
    new_app_name, new_app_user, new_app_module_name, new_app_path = \
        parse_url(new_repo_url,
                  apps_folder=apps_folder,
                  verbose=verbose,
                  )
    assert old_app_user == new_app_user

    ic(old_app_name, new_app_name)
    ic(old_app_path, new_app_path)

    assert group in portage_categories()

    with chdir(old_app_path):
        old_setup_py = old_app_path / Path('setup.py')
        replace_match_pairs_in_file(path=old_setup_py,
                                    match_pairs=((old_app_name, new_app_name), (old_app_module_name, new_app_module_name),),
                                    verbose=verbose,
                                    )
        sh.git.add(old_setup_py)
        del old_setup_py

        old_readme_md = old_app_path / Path('README.md')
        try:
            replace_match_pairs_in_file(path=old_readme_md,
                                        match_pairs=((old_app_name, new_app_name), (old_app_module_name, new_app_module_name),),
                                        verbose=verbose,
                                        )
        except FileNotFoundError as e:
            ic(e)
            sh.touch('README.md')
        sh.git.add(old_readme_md)
        del old_readme_md

        old_url_sh = old_app_path / Path('url.sh')
        try:
            replace_text(path=old_url_sh,
                         match=old_app_name,
                         replacement=new_app_name,
                         verbose=verbose,
                         )
        except Exception as e:
            write_url_sh(new_repo_url, verbose=verbose,)
        sh.git.add(old_url_sh)
        del old_url_sh

        old_edit_config = old_app_path / Path('.edit_config')
        replace_text(path=old_edit_config,
                     match=old_app_name,
                     replacement=new_app_name,
                     verbose=verbose,
                     )
        #sh.git.add(old_edit_config)
        del old_edit_config

        enable_github_sh = old_app_path / Path('enable_github.sh')
        replace_text(path=enable_github_sh,
                     match=old_app_name,
                     replacement=new_app_name,
                     verbose=verbose,
                     )
        #sh.git.add(enable_github_sh)
        del enable_github_sh

        old_app_py = old_app_path / old_app_module_name / Path(old_app_module_name + '.py')
        replace_match_pairs_in_file(path=old_app_py,
                                    match_pairs=((old_app_name, new_app_name), (old_app_module_name, new_app_module_name),),
                                    verbose=verbose,
                                    )
        sh.git.add(old_app_py)
        #del old_app_py

        old_app_init_py = old_app_path / old_app_module_name / Path('__init__.py')
        replace_text(path=old_app_init_py,
                     match=old_app_module_name,
                     replacement=new_app_module_name,
                     verbose=verbose,
                     )
        sh.git.add(old_app_init_py)
        del old_app_init_py

        # in old_app_path
        new_app_py = old_app_path / old_app_module_name / Path(new_app_module_name + '.py')
        if new_app_py.as_posix() != old_app_py.as_posix():
            sh.git.mv(old_app_py, new_app_py)
        del old_app_py
        del new_app_py

        if new_app_module_name != old_app_module_name:
            sh.git.mv(old_app_module_name, new_app_module_name)

        #print(sh.ls())
        sh.git.add(Path(new_app_module_name) / Path('__init__.py'))
        sh.git.add(Path(new_app_module_name) / Path('py.typed'))
        sh.git.add(Path(new_app_module_name) / Path(new_app_module_name + '.py'))
        old_ebuild_symlink = old_app_path / Path(old_app_name + '-9999.ebuild')
        if not old_ebuild_symlink.exists():
            old_ebuild_folder = Path(gentoo_overlay_repo) / Path(group) / Path(old_app_name)
            sh.ln('-s', old_ebuild_folder / old_ebuild_symlink.name, old_ebuild_symlink.name, _ok_code=[0, 1])
            del old_ebuild_folder


    old_ebuild_dir = old_ebuild_symlink.resolve().parent
    if old_ebuild_symlink.exists():
        with chdir(old_ebuild_dir):
            # in ebuild folder
            old_ebuild_path = Path(old_app_name + '-9999.ebuild').resolve()
            replace_text(path=old_ebuild_path,
                         match=old_app_module_name,
                         replacement=new_app_module_name,
                         verbose=verbose,
                         )
            sh.git.add(old_ebuild_path)
            new_ebuild_name = Path(new_app_name + '-9999.ebuild')
            sh.git.mv('-v', old_ebuild_path, new_ebuild_name, _out=sys.stdout, _err=sys.stderr,)
            sh.git.add(new_ebuild_name)
            sh.git.commit('-m', 'rename')
            del old_ebuild_path

        with chdir(old_ebuild_dir.parent):
            # in ebuild parent folder
            sh.busybox.mv('-v', old_app_name, new_app_name, _out=sys.stdout, _err=sys.stderr,)
            new_ebuild_path = Path(new_app_name / new_ebuild_name).resolve()
            sh.git.commit('-m', 'rename', _ok_code=[0, 1], _out=sys.stdout, _err=sys.stderr,)
            sh.git.push()

        with chdir(old_app_path):
            print(sh.ls())
            sh.rm(old_ebuild_symlink.name)
            del old_ebuild_symlink

            new_ebuild_symlink_name = new_ebuild_name
            sh.ln('-s', new_ebuild_path, new_ebuild_symlink_name)
            del new_ebuild_symlink_name
            del new_ebuild_name
            sh.git.commit('-m', 'rename')
            sh.git.remote.rm('origin', _ok_code=[0, 2])
            sh.git.push(_ok_code=[0, 128])

    with chdir(apps_folder):
        sh.busybox.mv('-v', old_app_path, new_app_path, _out=sys.stdout, _err=sys.stderr,)

    replace_text(path=Path('/etc/portage/package.accept_keywords'),
                 match='/' + old_app_module_name + '-',
                 replacement='/' + new_app_module_name + '-',
                 verbose=verbose,
                 )


@cli.command('list')
@click.option('--apps-folder',
              type=click.Path(exists=True,
                              dir_okay=True,
                              file_okay=False,
                              allow_dash=False,
                              path_type=Path,),
              required=True,)
@click.option('--ls-remote', is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def list_all(ctx,
             apps_folder: Path,
             ls_remote: bool,
             verbose: int,
             verbose_inf: bool,
             ):

    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    edit_configs = find_edit_configs(apps_folder=apps_folder,
                                     verbose=verbose,
                                     )
    for config in edit_configs:
        if verbose:
            ic(config)
        if ls_remote:
            project_dir = config.parent
            return_code = None
            if verbose:
                ic(project_dir)
            with chdir(project_dir):
                try:
                    sh.git('ls-remote')
                    return_code = 0
                except sh.ErrorReturnCode_128:
                    return_code = 128

            print(return_code, config.parent.name)
        else:
            print(config.parent.name)


@cli.command()
@click.option('--apps-folder',
              type=click.Path(exists=True,
                              dir_okay=True,
                              file_okay=False,
                              allow_dash=False,
                              path_type=Path,),
              required=True,)
@click.option('--gentoo-overlay-repo', type=str, required=True)
@click.option('--local', is_flag=True)
@click.option('--github-user', type=str, required=True)
@click_add_options(click_global_options)
@click.pass_context
def check_all(ctx,
              apps_folder: Path,
              gentoo_overlay_repo: str,
              github_user: str,
              verbose: int,
              verbose_inf: bool,
              local: bool,
              ):

    not_root()
    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    ic(apps_folder)

    edit_configs = find_edit_configs(apps_folder=apps_folder,
                                     verbose=verbose,
                                     )

    for edit_config_path in edit_configs:
        ic(edit_config_path)
        with chdir(edit_config_path.parent):
            remote = str(sh.git.remote('get-url', 'origin')).strip()
            app_name, app_user, app_module_name, app_path = parse_url(remote,
                                                                      apps_folder=apps_folder,
                                                                      verbose=verbose,
                                                                      )
            if not remote.startswith('git@github.com:'):
                if app_user == github_user:
                    ic('remote is to', github_user, 'but does not startwith git@github.com:', remote)
                    raise ValueError(edit_config_path, remote)
            if not app_name == edit_config_path.parent.name:
                ic(app_name, 'is not', edit_config_path.parent.name)
                raise ValueError(edit_config_path, remote)

        del app_name, app_user, app_module_name, app_path


@cli.command()
@click.argument('language', type=click.Choice(['python', 'bash', 'sh', 'zig', 'c']), nargs=1)
@click.argument('repo_url', type=str, nargs=1)
@click.argument('group', type=str, nargs=1)
@click.option('--branch', type=str, callback=valid_branch, default="master")
@click.option("--template", 'templates',
              type=click.Path(exists=True,
                              dir_okay=False,
                              file_okay=True,
                              allow_dash=False,
                              path_type=Path,),
              required=False,
              multiple=True,)
@click.option('--apps-folder', type=str, required=True)
@click.option('--gentoo-overlay-repo', type=str, required=True)
@click.option('--github-user', type=str, required=True)
@click.option('--license', type=click.Choice(license_list(verbose=False,)), default="ISC")
@click.option('--owner', type=str, required=True)
@click.option('--owner-email', type=str, required=True)
@click.option('--description', type=str, required=True)
@click.option('--local', is_flag=True)
@click.option('--rename', type=str)
@click.option('--hg', is_flag=True)
@click.option('--use-existing-repo', is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def new(ctx,
        language: str,
        repo_url: str,
        group: str,
        branch: str,
        rename: Optional[str],
        templates: Optional[tuple[Path]],
        apps_folder: str,
        gentoo_overlay_repo: str,
        github_user: str,
        license: str,
        owner: str,
        owner_email: str,
        description: str,
        local: bool,
        use_existing_repo: bool,
        verbose: int,
        verbose_inf: bool,
        hg: bool,
        ):

    not_root()
    tty, verbose = tv(ctx=ctx,
                      verbose=verbose,
                      verbose_inf=verbose_inf,
                      )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    if templates:
        templates = [t.resolve() for t in templates]

    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]

    assert '/' not in group
    assert ':' not in group
    assert group in portage_categories()
    assert repo_url.startswith('https://')

    template_repo_url: Optional[str] = None
    if not repo_url.startswith('https://github.com/{}/'.format(github_user)):
        template_repo_url = repo_url
        _app_name, _app_user, _app_module_name, _app_path = parse_url(repo_url,
                                                                      apps_folder=apps_folder,
                                                                      verbose=verbose,
                                                                      )
        if rename:
            _app_name = rename
        repo_url = 'https://github.com/{github_user}/{app_name}'.format(github_user=github_user, app_name=_app_name)
        del _app_name, _app_user, _app_module_name, _app_path
    else:
        template_repo_url = None

    app_name, app_user, app_module_name, app_path = parse_url(repo_url,
                                                              apps_folder=apps_folder,
                                                              verbose=verbose,
                                                              )
    ic(app_name)
    ic(app_user)
    assert app_user == github_user
    assert '_' not in app_path.name

    if language == 'sh':
        language = 'bash'

    if language == 'python':
        ext = '.py'
    elif language == 'bash':
        ext = '.sh'
    elif language == 'zig':
        ext = '.zig'
        assert group == 'dev-zig'
    elif language == 'c':
        ext = '.c'
    else:
        raise ValueError('unsupported language: ' + language)

    if template_repo_url:
        clone_repo(repo_url=repo_url,
                   template_repo_url=template_repo_url,
                   apps_folder=apps_folder,
                   hg=hg,
                   branch=branch,
                   app_path=app_path,
                   app_group=group,
                   local=local,
                   verbose=verbose,
                   )

    if ((not app_path.exists()) or use_existing_repo):
        if not use_existing_repo:
            create_repo(hg=hg,
                        app_path=app_path,
                        app_module_name=app_module_name,
                        verbose=verbose,
                        )
        else:
            assert app_path.is_dir()
            assert Path(app_path / Path('.git')).exists()
            with chdir(app_path):
                os.makedirs(app_module_name, exist_ok=True)

        if not template_repo_url:
            with chdir(app_path):
                if language == 'python':
                    write_setup_py(use_existing_repo=use_existing_repo,
                                   app_module_name=app_module_name,
                                   app_name=app_name,
                                   owner=owner,
                                   owner_email=owner_email,
                                   description=description,
                                   license=license,
                                   repo_url=repo_url,)

                gitignore_template = generate_gitignore_template()
                if use_existing_repo:
                    with open('.gitignore', 'a') as fh:
                        fh.write(gitignore_template)
                else:
                    with open('.gitignore', 'x') as fh:
                        fh.write(gitignore_template)

                if not Path('url.sh').exists():
                    write_url_sh(repo_url, verbose=verbose,)

                if language == 'python':
                    os.system("fastep")

            with chdir(app_path / app_module_name):
                app_template = generate_app_template(package_name=app_module_name,
                                                     language=language,
                                                     append_files=templates,
                                                     verbose=ctx.obj['verbose'],
                                                     )
                with open(app_module_name + ext, 'x') as fh:
                    fh.write(app_template)

                if language == 'python':
                    init_template = generate_init_template(package_name=app_module_name)
                    with open("__init__.py", 'x') as fh:
                        fh.write(init_template)
                    sh.touch('py.typed')

            with chdir(app_path):
                sh.git.add('--all')
                sh.git.commit('-m', 'autocomit')

        with chdir(app_path):
            with open(".edit_config", 'x') as fh:
                fh.write(generate_edit_config(package_name=app_name,
                                              package_group=group,
                                              local=local))

            remote_add_origin(hg=hg,
                              app_path=app_path,
                              local=local,
                              app_name=app_name,
                              verbose=verbose,
                              )
    else:
        eprint("Not creating new app, {} already exists.".format(app_path))


    ebuild_path = Path(gentoo_overlay_repo) / Path(group) / Path(app_name)
    if not ebuild_path.exists():
        enable_python = False
        if Path(app_path / Path('setup.py')).exists():
            enable_python = True

        os.makedirs(ebuild_path, exist_ok=False)
        ebuild_name = app_name + "-9999.ebuild"

        enable_dobin = False
        if language in ['bash']:
            enable_dobin = True
        with chdir(ebuild_path):
            with open(ebuild_name, 'w') as fh:
                fh.write(generate_ebuild_template(app_name=app_name,
                                                  description=description,
                                                  enable_python=enable_python,
                                                  enable_dobin=enable_dobin,
                                                  homepage=repo_url,
                                                  app_path=app_path,))
            sh.git.add(ebuild_name)
            sh.ebuild(ebuild_name,  'manifest')
            sh.git.add('*')
            os.system("git commit -m 'newapp {}'".format(app_name))
            os.system("git push")
            os.system("sudo emaint sync -A")
            accept_keyword = "={}/{}-9999 **\n".format(group, app_name)
            accept_keywords = Path("/etc/portage/package.accept_keywords") / Path(group) / Path(app_name)
            accept_keywords.parent.mkdir(exist_ok=True)
            write_line_to_file(path=accept_keywords,
                               line=accept_keyword,
                               unique=True,
                               make_new_if_necessary=True,
                               verbose=verbose,
                               )
            sh.ln('-s', ebuild_path / ebuild_name, app_path / ebuild_name)
            sh.git.diff('--exit-code')
            # need to commit any pending ebuild changes here, but that's the wront git message, and it fails if it's unhanged
            sh.git.commit('-m', 'initial commit', _ok_code=[0, 1])
    else:
        eprint('Not creating new ebuild, {} already exists.'.format(ebuild_path))

    ic(app_path)
    ic(app_module_name)

    main_py_path = app_path / Path(app_module_name) / Path(app_module_name + ext)
    ic(main_py_path)
    os.system("edittool edit " + main_py_path.as_posix())


##http://liw.fi/cmdtest/
##http://liw.fi/cliapp/
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
#def print_hex(text):
#    print(':'.join(hex(ord(x))[2:] for x in text))
#
#
#def dprint(*args, **kwargs):
#    if click_debug:
#        caller = sys._getframe(1).f_code.co_name
#        print(str("%.5f" % time.time()), os.getpid(), '{0: <15}'.format(caller+'()'), *args, file=sys.stderr, **kwargs)
#
#print(pydoc.render_doc(logger))
#
#log_level=log_levels['DEBUG']
#log_level=log_levels['INFO:']
#
#
#def print_traceback():
#    ex_type, ex, tb = sys.exc_info()
#    traceback.print_tb(tb)
#    del tb

