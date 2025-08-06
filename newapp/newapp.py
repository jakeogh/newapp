#!/usr/bin/env python3
# -*- coding: utf8 -*-

# pylint: disable=useless-suppression             # [I0021]
# pylint: disable=missing-docstring               # [C0111] docstrings are always outdated and wrong
# pylint: disable=missing-param-doc               # [W9015]
# pylint: disable=missing-module-docstring        # [C0114]
# pylint: disable=fixme                           # [W0511] todo encouraged
# pylint: disable=line-too-long                   # [C0301]
# pylint: disable=too-many-instance-attributes    # [R0902]
# pylint: disable=too-many-lines                  # [C0302] too many lines in module
# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive(!)
# pylint: disable=too-many-return-statements      # [R0911]
# pylint: disable=too-many-branches               # [R0912]
# pylint: disable=too-many-statements             # [R0915]
# pylint: disable=too-many-arguments              # [R0913]
# pylint: disable=too-many-nested-blocks          # [R1702]
# pylint: disable=too-many-locals                 # [R0914]
# pylint: disable=too-many-public-methods         # [R0904]
# pylint: disable=too-few-public-methods          # [R0903]
# pylint: disable=no-member                       # [E1101] no member for base
# pylint: disable=attribute-defined-outside-init  # [W0201]
# pylint: disable=too-many-boolean-expressions    # [R0916] in if statement
from __future__ import annotations

import errno
import logging
import os
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import click
import sh
from asserttool import am_root
from asserttool import ic
from asserttool import icp
from asserttool import not_root
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tvicgvd
from configtool import click_read_config
from edittool import parse_edit_config
from eprint import eprint
from filetool import ensure_line_in_config_file as _ensure_line_in_config_file
from getdents import files
from getdents import files_pathlib
from getdents import paths
from globalverbose import gvd
from licenseguesser import build_license_list
from mptool import output
from portagetool import portage_categories
from portagetool import resolve_package_name
from replace_text import replace_text_in_file
from retry_on_exception import retry_on_exception
from timestamptool import get_timestamp
from with_chdir import chdir
from with_user import User

from .templates import autogenerate_readme
from .templates import bash_app
from .templates import cee_app
from .templates import depend_python
from .templates import description_md
from .templates import ebuild
from .templates import echo_url
from .templates import edit_config
from .templates import gitignore
from .templates import init
from .templates import install_md
from .templates import pyproject_toml
from .templates import python_app
from .templates import setup_py
from .templates import src_install_dobin
from .templates import zig_app

sh.mv = None
logging.basicConfig(level=logging.INFO)

CFG, CONFIG_MTIME = click_read_config(
    click_instance=click,
    app_name="newapp",
)


# https://github.com/mitsuhiko/click/issues/441
CONTEXT_SETTINGS = dict(default_map=CFG)
# dict(help_option_names=['--help'],
#     terminal_width=shutil.get_terminal_size((80, 20)).columns)


# ic(CFG)


@User("user")
def mkdir_user(path):
    os.makedirs(path, exist_ok=True)


@retry_on_exception(
    exception=PermissionError,
    # errno=errno.EPERM,
)
@retry_on_exception(
    exception=OSError,
    errno=errno.ENOSPC,
)
def ensure_line_in_config_file(path: Path, line: str):
    _ensure_line_in_config_file(
        path=path,
        line=line,
        comment_marker="#",
        ignore_leading_whitespace=False,
    )


def create_package_env_records(*, group: str, app_name: str, app_path: Path):
    icp(group, app_name, app_path)
    assert os.geteuid() == 0
    os.system(f"mkdir /etc/portage/env/{group}")
    os.system(f"mkdir /etc/portage/package.env/{group}")
    # os.system(f"chown user:user /etc/portage/env/{group}")  # ugly

    try:
        ensure_line_in_config_file(
            path=Path(f"/etc/portage/env/{group}/{app_name}-9999"),
            line=f"EGIT_REPO_URI='{app_path}'\n",
        )
    except PermissionError as e:
        icp(e)
        raise
    # os.system(f"sudo chown root:root /etc/portage/env/{group}")

    # os.system(f"sudo chown user:user /etc/portage/package.env/{group}")  # ugly
    try:
        ensure_line_in_config_file(
            path=Path(f"/etc/portage/package.env/{group}/{app_name}"),
            line=f"{group}/{app_name} {group}/{app_name}-9999\n",
        )
    except PermissionError as e:
        icp(e)
        raise
    # os.system(f"sudo chown root:root /etc/portage/package.env/{group}")  # ugly


@User("user")
def write_edit_config(
    *,
    app_path: Path,
    package_name: str,
    package_group: str,
    local: bool,
):
    ic(package_name, package_group, local)
    with chdir(app_path):
        os.system("ls -alh")
        with open(".edit_config", "x", encoding="utf8") as fh:
            fh.write(
                generate_edit_config(
                    package_name=package_name,
                    package_group=package_group,
                    local=local,
                )
            )


# def accept_keywords_path(group: str, app_name: str) -> Path:
#    accept_keywords = (
#        Path("/etc/portage/package.accept_keywords") / Path(group) / Path(app_name)
#    )
#    accept_keywords.parent.mkdir(exist_ok=True)
#    return accept_keywords


def get_extension(language: str) -> str:
    if language == "python":
        ext = ".py"
    elif language == "bash":
        ext = ".sh"
    elif language == "zig":
        ext = ".zig"
        # assert group == "dev-zig"  # sys-fs/ncdu
    elif language == "c":
        ext = ".c"
    elif language == "go":
        ext = ".go"
    else:
        raise ValueError("unsupported language: " + language)
    return ext


def replace_text(
    path: Path,
    str_to_match: str,
    replacement: str,
) -> None:
    ic(str_to_match, replacement)

    replace_text_in_file(
        path=path,
        match_bytes=str_to_match.encode("utf8"),
        replacement_bytes=replacement.encode("utf8"),
        output_fh=None,
        read_mode="rb",
        write_mode="wb",
        remove_match=False,
    )


def replace_match_pairs_in_file(
    *,
    path: Path,
    match_pairs: tuple,
) -> None:
    assert isinstance(match_pairs, tuple)
    for old_match, new_match in match_pairs:
        if old_match == new_match:
            continue
        ic(path, old_match, new_match)
        replace_text(
            path=path,
            str_to_match=old_match,
            replacement=new_match,
        )


@User("user")
def get_url_for_overlay(
    overlay: str,
) -> str:
    command = sh.eselect("repository", "list")
    command_output = command.stdout.split("\n")
    ic(type(command_output), command_output)

    for line in command_output[1:]:
        ic(line)
        try:
            index, repo_name, repo_url = [item for item in line.split() if item]
        except ValueError:
            pass

        repo_url = repo_url.split("(")[-1].split(")")[0]
        if repo_name == overlay:
            ic(repo_url)
            return repo_url

    raise ValueError(f"unknown repo {overlay}")


@User("user")
def valid_branch(ctx, param, value):
    ic(value)
    branch_check_cmd = "git check-ref-format --branch " + value
    if os.system(branch_check_cmd):
        raise click.BadParameter(f'fatal: "{value}" is not a valid branch name')
    return value


def find_edit_configs(
    *,
    apps_folder: Path,
):
    edit_configs = []
    for path in files_pathlib(
        apps_folder,
        max_depth=1,
    ):
        if path.name == ".edit_config":
            edit_configs.append(path)

    edit_configs = sorted(edit_configs)
    return edit_configs


# @User("user")
def generate_edit_config(
    *,
    package_name: str,
    package_group: str,
    local: bool,
):
    if local:
        remote = "#"
    else:
        remote = ""
    remote += f'''remote="https://github.com/jakeogh/{package_name}.git"'''

    optional_blank_remote = ""
    if local:
        optional_blank_remote = '''remote=""'''
    return edit_config.format(
        package_name=package_name,
        package_group=package_group,
        optional_blank_remote=optional_blank_remote,
        remote=remote,
    )


# @User("user")
def generate_setup_py(
    *,
    url: str,
    package_name: str,
    command: str,
    license: str,
    owner: str,
    owner_email: str,
    description: str,
    dependencies: tuple[str, ...],
) -> str:
    ic(
        url,
        package_name,
        command,
        license,
        owner,
        owner_email,
        description,
    )

    return setup_py.format(
        package_name=package_name,
        command=command,
        url=url,
        license=license,
        owner=owner,
        owner_email=owner_email,
        description=description,
    )


# @User("user")
def generate_src_install_dobin_template(app_name):
    return src_install_dobin.format(app_name=app_name)


# @User("user")
def generate_autogenerate_readme():
    return autogenerate_readme


# @User("user")
def generate_ebuild_template(
    *,
    description: str,
    enable_python: bool,
    enable_go: bool,
    enable_dobin: bool,
    homepage: str,
    app_path: Path,
    app_name: str,
    dependencies: tuple[str, ...],
) -> str:
    ic(enable_python)
    inherit_python = ""
    rdepend_python = ""
    if enable_python:
        inherit_python = "inherit distutils-r1"
        rdepend_python = depend_python

    inherit_go = ""
    rdepend_go = ""
    if enable_go:
        inherit_go = "inherit go-module golang-vcs golang-build"
        # rdepend_go = depend_go

    result = ebuild.format(
        description=description,
        inherit_python=inherit_python,
        inherit_go=inherit_go,
        depend_python=rdepend_python,
        homepage=homepage,
        app_path=app_path,
        year=str(date.today().year),
    )

    if enable_dobin:
        result += generate_src_install_dobin_template(app_name)
    return result


def generate_gitignore_template(*, ebuild_name):
    return gitignore.format(ebuild_name=ebuild_name)


def generate_app_template(
    package_name: str,
    *,
    language: str,
    append_files: tuple[Path, ...],
) -> str:
    result = None
    if language == "python":
        result = python_app.format(
            package_name=package_name, newline="\\n", null="\\x00"
        )
    if language == "bash":
        result = bash_app.format(package_name=package_name, newline="\\n", null="\\x00")
    if language == "zig":
        result = zig_app.format(package_name=package_name, newline="\\n", null="\\x00")
    if language == "c":
        # result = cee_app.format(package_name=package_name, newline="\\n", null="\\x00")
        result = cee_app

    if result:
        for file in append_files:
            with open(file, "r", encoding="utf8") as fh:
                result += fh.read()
        return result

    raise ValueError(language)


def generate_url_template(url):
    return echo_url.format(url=url)


def generate_init_template(package_name):
    return init.format(package_name=package_name)


def generate_description_md_template(*, package_name, repo_url):
    return description_md.format(package_name=package_name, repo_url=repo_url)


def generate_install_md_template(*, package_name):
    return install_md.format(package_name=package_name)


# bug, this renames module names from _ to - which is not valid py
def rename_repo_at_app_path(
    *,
    app_path: Path,
    app_user: str,
    old_name: str,
    new_name: str,
    app_group: str,
    hg: bool,
    local: bool,
):
    ic(old_name, new_name)
    old_module_name = old_name.replace("-", "_")
    new_module_name = old_name.replace("-", "_")

    with chdir(
        app_path,
    ):
        if Path(old_name).exists():  # not all apps have a dir here
            sh.git.mv(old_name, new_name)
        if Path(old_name.replace("-", "_")).exists():  # not all apps have a dir here
            sh.git.mv(old_name.replace("-", "_"), new_name)

        with open(".edit_config", "x", encoding="utf8") as fh:
            fh.write(
                generate_edit_config(
                    package_name=new_name,
                    package_group=app_group,
                    local=local,
                )
            )

        # enable_github.sh needs to be created if this is a remote template
        remote_add_origin(
            hg=hg,
            app_path=app_path,
            local=local,
            app_name=new_name,
            app_user=app_user,
        )

        all_paths = list(
            paths(
                app_path,
            )
        )
        exclude_path = app_path / Path(".git")
        for dent in all_paths:
            path = dent.pathlib
            if path.name.startswith("."):
                continue
            if path.parent.name.startswith("."):
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

            if old_name.replace("-", "_") in path.name:
                if path.name == new_name:
                    continue
                ic(old_name.replace("-", "_"), path.name)
                new_path_name = path.name.replace(old_name.replace("-", "_"), new_name)
                ic(new_path_name)
                new_path = path.parent / Path(new_path_name)
                sh.git.mv(path, new_path)

        all_files = list(
            files(
                app_path,
            )
        )
        exclude_path = app_path / Path(".git")
        for dent in all_files:
            ic(dent)
            path = dent.pathlib
            if path.name.startswith("."):
                continue
            if path.parent.name.startswith("."):
                continue
            if path.as_posix().startswith(exclude_path.as_posix()):
                continue

            replace_match_pairs_in_file(
                path=path,
                match_pairs=(
                    (old_name, new_name),
                    (old_module_name, new_module_name),
                ),
            )
        sh.git.add("-u")
        sh.git.commit("-m rename")


@User("user")
def clone_repo(
    *,
    branch: str,
    repo_url: str,
    apps_folder: Path,
    template_repo_url: str,
    app_path: Path,
    app_group: str,
    hg: bool,
    local: bool,
):
    icp(
        repo_url,
        branch,
        apps_folder,
        template_repo_url,
        app_path,
        app_group,
        hg,
        local,
    )
    app_name, app_user, _, _ = parse_url(
        repo_url,
        apps_folder=apps_folder,
    )
    rename_cloned_repo = False
    if template_repo_url:
        template_app_name, template_app_user, _, _ = parse_url(
            template_repo_url,
            apps_folder=apps_folder,
        )
        repo_to_clone_url = template_repo_url
        if template_app_name != app_name:
            rename_cloned_repo = True
    else:
        repo_to_clone_url = repo_url

    if hg:
        sh.hg(
            "clone", repo_to_clone_url, str(app_path), _out=sys.stdout, _err=sys.stderr
        )
    else:
        sh.git.clone(
            repo_to_clone_url,
            "--recurse-submodules",
            "--recursive",
            str(app_path),
            _out=sys.stdout,
            _err=sys.stderr,
        )

    if branch != "master":
        branch_cmd = "git checkout -b " + '"' + branch + '"'
        icp(branch_cmd)
        os.system(branch_cmd)

    if (
        not rename_cloned_repo
    ):  # when renaming a template repo, dont want to fork if its one of my repos
        git_fork_cmd = "hub fork"
        icp(git_fork_cmd)
        os.system(git_fork_cmd)
    else:
        rename_repo_at_app_path(
            app_path=app_path,
            app_user=app_user,
            app_group=app_group,
            local=local,
            hg=hg,
            old_name=template_app_name,
            new_name=app_name,
        )


@User("user")
def create_repo(
    *,
    app_path: Path,
    app_module_name: str,
    hg: bool,
):
    icp(app_path, app_module_name, hg)
    if hg:
        raise NotImplementedError("hg")
    os.makedirs(app_path, exist_ok=False)
    with chdir(
        app_path,
    ):
        os.makedirs(app_module_name, exist_ok=False)
        os.system("git init")


def remote_add_origin(
    *,
    app_path: Path,
    local: bool,
    app_name: str,
    app_user: str,
    hg: bool,
):
    if hg:
        raise NotImplementedError("hg")

    repo_config_command = sh.Command("git")
    repo_config_command = repo_config_command.bake(
        "remote", "add", "origin", f"git@github.com:jakeogh/{app_name}.git"
    )

    # repo_config_command = f"git remote add origin git@github.com:jakeogh/{app_name}.git"
    ic(repo_config_command)
    if not local:
        with chdir(
            app_path,
        ):
            # os.system(repo_config_command)
            repo_config_command()
    else:
        ic("local == True, skipping:", repo_config_command)

    enable_github = [
        "#!/bin/sh",
        f"hub create {app_user}/{app_name}",
        str(repo_config_command),
        "git push --set-upstream origin master",
        "touch .push",
        "\n",
    ]
    enable_github = "\n".join(enable_github)
    output_file = app_path / Path("enable_github.sh")
    with open(output_file, "x", encoding="utf8") as fh:
        fh.write(enable_github)


def parse_url(
    repo_url: str,
    *,
    apps_folder: Path,
    keep_underscore: bool = False,  # for rename
):
    ic(repo_url)

    if repo_url.startswith("git:github.com:"):
        app_name = repo_url.split(":")[-1].split(".git")[0]
        app_user = repo_url.split(":")[-1].split("/")[0]
    else:
        url_parsed = urlparse(repo_url)
        ic(url_parsed)

        repo_url_path = Path(url_parsed.path)
        app_name = repo_url_path.parts[-1]
        app_user = repo_url_path.parts[-2]

    app_name = app_name.lower()
    if not keep_underscore:
        app_name = app_name.replace("_", "-")
    app_name = app_name.split(".git")[0]
    app_module_name = app_name.replace("-", "_")
    app_module_name = app_module_name.split(".git")[0]
    ic(app_module_name)
    app_path = apps_folder / Path(app_name)
    ic(app_path)
    return app_name, app_user, app_module_name, app_path


@User("user")
def write_url_sh(repo_url):
    url_template = generate_url_template(url=repo_url)
    with open("url.sh", "x", encoding="utf8") as fh:
        fh.write(url_template)
    sh.chmod("+x", "url.sh")


@User("user")
def write_autogenerate_readme_sh():
    autogenerate_readme_template = generate_autogenerate_readme()
    with open(".autogenerate_readme.sh", "x", encoding="utf8") as fh:
        fh.write(autogenerate_readme_template)
    sh.git.add(".autogenerate_readme.sh")
    # sh.chmod("+x", ".autogenerate_readme.sh")


@User("user")
def write_setup_py(
    *,
    use_existing_repo: bool,
    app_module_name: str,
    app_name: str,
    owner: str,
    owner_email: str,
    description: str,
    dependencies: tuple[str, ...],
    license: str,
    repo_url: str,
):

    os.system("pwd")
    os.system("ls -al")
    if use_existing_repo:
        if Path("setup.py").exists():
            return

    with open("setup.py", "x", encoding="utf8") as fh:
        fh.write(
            generate_setup_py(
                package_name=app_module_name,
                command=app_name,
                owner=owner,
                owner_email=owner_email,
                description=description,
                dependencies=dependencies,
                license=license,
                url=repo_url,
            )
        )


@User("user")
def write_pyproject_toml():
    with open("pyproject.toml", "x", encoding="utf8") as fh:
        fh.write(pyproject_toml)


@click.group(context_settings=CONTEXT_SETTINGS, no_args_is_help=True)
@click_add_options(click_global_options)
@click.pass_context
def cli(
    ctx,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )


@cli.command()
@click.argument("overlay_name", type=str, nargs=1)
@click_add_options(click_global_options)
@click.pass_context
def get_overlay_url(
    ctx,
    overlay_name,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    url = get_url_for_overlay(
        overlay_name,
    )
    print(url)


@cli.command()
@click.argument("app", type=str)
@click_add_options(click_global_options)
@click.pass_context
def nineify(
    ctx,
    app,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )
    # not_root()
    assert "/" in app
    group, name = app.split("/")
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
@click_add_options(click_global_options)
@click.pass_context
def template_pylint(
    ctx,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )
    app_template = generate_app_template(
        "TEMP",
        language="python",
        append_files=(),
    )
    for line in app_template.splitlines():
        if line.startswith("# flake8: "):
            print(line)
        if line.startswith("# pylint: "):
            print(line)


@cli.command()
@click.argument("package-name", type=str, default="TESTPACKAGE")
@click_add_options(click_global_options)
@click.pass_context
def template_python(
    ctx,
    package_name: str,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )
    app_template = generate_app_template(
        package_name,
        language="python",
        append_files=(),
    )
    output(
        app_template,
        reason=None,
        dict_output=dict_output,
        tty=tty,
    )


@cli.command()
@click.argument("package-name", type=str, default="TESTPACKAGE")
@click_add_options(click_global_options)
@click.pass_context
def template_bash(
    ctx,
    package_name: str,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )
    app_template = generate_app_template(
        package_name,
        language="bash",
        append_files=(),
    )
    print(app_template)


@cli.command()
@click.argument("package-name", type=str, default="TESTPACKAGE")
@click_add_options(click_global_options)
@click.pass_context
def template_zig(
    ctx,
    package_name: str,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )
    app_template = generate_app_template(
        package_name,
        language="zig",
        append_files=(),
    )
    print(app_template)


@cli.command("rename")
@click.argument("old_repo_url", type=str, nargs=1)
@click.argument("new_repo_url", type=str, nargs=1)
@click.argument("group", type=str, nargs=1)
@click.option("--apps-folder", type=str, required=True)
@click.option("--gentoo-overlay-repo", type=str, required=True)
@click.option("--github-user", type=str, required=True)
@click.option("--local", is_flag=True)
@click.option("--hg", is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def _rename(
    ctx,
    old_repo_url,
    new_repo_url,
    group,
    apps_folder,
    gentoo_overlay_repo,
    github_user,
    local,
    verbose_inf: bool,
    dict_output: bool,
    hg: bool,
    verbose: bool = False,
):
    am_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    old_app_name, old_app_user, old_app_module_name, old_app_path = parse_url(
        old_repo_url,
        apps_folder=apps_folder,
        keep_underscore=True,
    )
    new_app_name, new_app_user, new_app_module_name, new_app_path = parse_url(
        new_repo_url,
        apps_folder=apps_folder,
    )
    assert old_app_user == new_app_user

    ic(old_app_name, new_app_name)
    ic(old_app_path, new_app_path)

    assert group in portage_categories()

    with chdir(
        old_app_path,
    ):
        old_setup_py = old_app_path / Path("setup.py")
        replace_match_pairs_in_file(
            path=old_setup_py,
            match_pairs=(
                (old_app_name, new_app_name),
                (old_app_module_name, new_app_module_name),
            ),
        )
        sh.git.add(old_setup_py)
        del old_setup_py

        old_readme_md = old_app_path / Path("README.md")
        try:
            replace_match_pairs_in_file(
                path=old_readme_md,
                match_pairs=(
                    (old_app_name, new_app_name),
                    (old_app_module_name, new_app_module_name),
                ),
            )
        except FileNotFoundError as e:
            ic(e)
            sh.touch("README.md")
        sh.git.add(old_readme_md)
        del old_readme_md

        old_url_sh = old_app_path / Path("url.sh")
        try:
            replace_text(
                path=old_url_sh,
                str_to_match=old_app_name,
                replacement=new_app_name,
            )
        except Exception as e:
            write_url_sh(
                new_repo_url,
            )
        sh.git.add(old_url_sh)
        del old_url_sh

        old_edit_config = old_app_path / Path(".edit_config")
        replace_text(
            path=old_edit_config,
            str_to_match=old_app_name,
            replacement=new_app_name,
        )
        # sh.git.add(old_edit_config)
        del old_edit_config

        enable_github_sh = old_app_path / Path("enable_github.sh")
        if enable_github_sh.exists():
            replace_text(
                path=enable_github_sh,
                str_to_match=old_app_name,
                replacement=new_app_name,
            )
            # sh.git.add(enable_github_sh)
        del enable_github_sh

        old_app_py = (
            old_app_path / old_app_module_name / Path(old_app_module_name + ".py")
        )
        replace_match_pairs_in_file(
            path=old_app_py,
            match_pairs=(
                (old_app_name, new_app_name),
                (old_app_module_name, new_app_module_name),
            ),
        )
        sh.git.add(old_app_py)
        # del old_app_py

        old_app_init_py = old_app_path / old_app_module_name / Path("__init__.py")
        replace_text(
            path=old_app_init_py,
            str_to_match=old_app_module_name,
            replacement=new_app_module_name,
        )
        sh.git.add(old_app_init_py)
        del old_app_init_py

        # in old_app_path
        new_app_py = (
            old_app_path / old_app_module_name / Path(new_app_module_name + ".py")
        )
        if new_app_py.as_posix() != old_app_py.as_posix():
            sh.git.mv(old_app_py, new_app_py)
        del old_app_py
        del new_app_py

        if new_app_module_name != old_app_module_name:
            sh.git.mv(old_app_module_name, new_app_module_name)

        # print(sh.ls())
        sh.git.add(Path(new_app_module_name) / Path("__init__.py"))
        sh.git.add(Path(new_app_module_name) / Path("py.typed"))
        sh.git.add(Path(new_app_module_name) / Path(new_app_module_name + ".py"))
        old_ebuild_symlink = old_app_path / Path(old_app_name + "-9999.ebuild")
        if not old_ebuild_symlink.exists():
            old_ebuild_folder = (
                Path(gentoo_overlay_repo) / Path(group) / Path(old_app_name)
            )
            sh.ln(
                "-s",
                old_ebuild_folder / old_ebuild_symlink.name,
                old_ebuild_symlink.name,
                _ok_code=[0, 1],
            )
            del old_ebuild_folder

    old_ebuild_dir = old_ebuild_symlink.resolve().parent
    if old_ebuild_symlink.exists():
        with chdir(
            old_ebuild_dir,
        ):
            # in ebuild folder
            old_ebuild_path = Path(old_app_name + "-9999.ebuild").resolve()
            replace_text(
                path=old_ebuild_path,
                str_to_match=old_app_module_name,
                replacement=new_app_module_name,
            )
            sh.git.add(old_ebuild_path)
            new_ebuild_name = Path(new_app_name + "-9999.ebuild")
            sh.git.mv(
                "-v",
                old_ebuild_path,
                new_ebuild_name,
                _out=sys.stdout,
                _err=sys.stderr,
            )
            sh.git.add(new_ebuild_name)
            sh.git.commit("-m", "rename")
            del old_ebuild_path

        with chdir(
            old_ebuild_dir.parent,
        ):
            # in ebuild parent folder
            sh.busybox.mv(
                "-v",
                old_app_name,
                new_app_name,
                _out=sys.stdout,
                _err=sys.stderr,
            )
            new_ebuild_path = Path(new_app_name / new_ebuild_name).resolve()
            sh.git.add("*")
            sh.git.commit(
                "-m",
                "rename",
                _ok_code=[0, 1],
                _out=sys.stdout,
                _err=sys.stderr,
            )
            sh.git.push()

        with chdir(
            old_app_path,
        ):
            print(sh.ls())
            sh.rm(old_ebuild_symlink.name)
            del old_ebuild_symlink

            new_ebuild_symlink_name = new_ebuild_name
            sh.ln("-s", new_ebuild_path, new_ebuild_symlink_name)
            del new_ebuild_symlink_name
            del new_ebuild_name
            sh.git.commit("-m", "rename")
            sh.git.remote.rm("origin", _ok_code=[0, 2])
            sh.git.push(_ok_code=[0, 128])

    with chdir(
        apps_folder,
    ):
        sh.busybox.mv(
            "-v",
            old_app_path,
            new_app_path,
            _out=sys.stdout,
            _err=sys.stderr,
        )

    # old_accept_keywords = accept_keywords_path(group=group, app_name=old_app_name)
    # new_accept_keywords = accept_keywords_path(group=group, app_name=new_app_name)
    # sh.busybox(
    #    "mv",
    #    "-v",
    #    "-i",
    #    old_accept_keywords.as_posix(),
    #    new_accept_keywords.as_posix(),
    #    _out=sys.stdout,
    #    _err=sys.stderr,
    #    # _close_stderr=True,
    # )

    # replace_text(
    #    path=new_accept_keywords,
    #    str_to_match="/" + old_app_module_name + "-",
    #    replacement="/" + new_app_module_name + "-",
    # )


@cli.command("list")
@click.option(
    "--apps-folder",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        allow_dash=False,
        path_type=Path,
    ),
    required=True,
)
@click.option("--ls-remote", is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def list_all(
    ctx,
    apps_folder: Path,
    ls_remote: bool,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    edit_configs = find_edit_configs(
        apps_folder=apps_folder,
    )
    for config in edit_configs:
        ic(config)
        if ls_remote:
            project_dir = config.parent
            return_code = None
            ic(project_dir)
            with chdir(
                project_dir,
            ):
                try:
                    sh.git("ls-remote")
                    return_code = 0
                except sh.ErrorReturnCode_128:
                    return_code = 128

            output(
                (return_code, config.parent.name),
                reason=None,
                dict_output=dict_output,
                tty=tty,
            )
        else:
            output(
                config.parent.name,
                reason=None,
                dict_output=dict_output,
                tty=tty,
            )


@cli.command("list-paths")
@click.option(
    "--apps-folder",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        allow_dash=False,
        path_type=Path,
    ),
    required=True,
)
@click_add_options(click_global_options)
@click.pass_context
def list_all_paths(
    ctx,
    apps_folder: Path,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    edit_configs = find_edit_configs(
        apps_folder=apps_folder,
    )
    for config in edit_configs:
        ic(config)
        output(
            os.fsencode(config.parent.as_posix()),
            reason=None,
            dict_output=dict_output,
            tty=tty,
        )


@cli.command("list-ebuilds")
@click.option(
    "--apps-folder",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        allow_dash=False,
        path_type=Path,
    ),
    required=True,
)
@click.option("--github-user", type=str, required=True)
@click_add_options(click_global_options)
@click.pass_context
def list_all_ebuilds(
    ctx,
    apps_folder: Path,
    github_user: str,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    edit_configs = find_edit_configs(
        apps_folder=apps_folder,
    )
    for edit_config_path in edit_configs:
        icp(edit_config_path)
        with chdir(
            edit_config_path.parent,
        ):
            remote = str(sh.git.remote("get-url", "origin")).strip()
            app_name, app_user, app_module_name, app_path = parse_url(
                remote,
                apps_folder=apps_folder,
            )
            icp(app_name, app_user, app_module_name, app_path, remote)
            if app_name == "gevent":
                continue  # bug
            ebuild_name = app_name + "-9999.ebuild"
            (
                _edit_config,
                short_package,
                group,
                remote,
                test_command_arg,
                dont_reformat,
                install_command,
                skip_test,
            ) = parse_edit_config(
                path=Path(edit_config),
            )
            ebuild_path = (
                Path("/home/user/_myapps/jakeogh")
                / Path(group)
                / Path(app_name)
                / Path(ebuild_name)
            )
            icp(ebuild_path)
            assert ebuild_path.exists()
            _symlink_name = Path(Path(app_path) / Path(ebuild_name))
            if not _symlink_name.exists():
                sh.ln(
                    "-s",
                    ebuild_path.as_posix(),
                    _symlink_name.as_posix(),
                    _ok_code=[0, 1],
                )
            with open(ebuild_path, "r") as fh:
                ebuild_lines = fh.readlines()

            for line in ebuild_lines:
                if line.startswith("EGIT_REPO_URI="):
                    repo_line = line.strip()
                    break

            icp(repo_line)
            if "myapps" not in repo_line:
                if not repo_line.startswith('EGIT_REPO_URI="https://github.com/'):
                    assert repo_line.startswith('EGIT_REPO_URI="https://gitlab.com/')
                assert repo_line.endswith('.git"')
                _path = Path(f"/home/sysskel/etc/portage/env/{group}/{app_name}-9999")
                icp(_path)
                if not Path(_path).exists():
                    icp(f"missing: {_path.as_posix()}")
                    create_package_env_records(
                        group=group,
                        app_name=app_name,
                        app_path=app_path,
                    )

                _path = Path(f"/home/sysskel/etc/portage/env/{group}/{app_name}-9999")
                icp(_path)
                assert Path(_path).exists()

                _path = Path(
                    f"/home/sysskel/etc/portage/package.env/{group}/{app_name}"
                )
                icp(_path)
                assert Path(_path).exists()
            else:
                repo_line_items = repo_line.split('EGIT_REPO_URI="')[1]
                icp(repo_line_items)
                repo_line_items = repo_line_items.split('"')[0]
                icp(repo_line_items)
                repo_line_items = repo_line_items.split(" ")
                icp(repo_line_items)
                for _ in repo_line_items:
                    if "myapps" in _:
                        continue
                    github_url = _
                    icp(github_url)
                    if not "github.com" in github_url:
                        assert "gitlab.com" in github_url

                new_egit_repo_uri_line = f'EGIT_REPO_URI="{github_url}"'
                icp(new_egit_repo_uri_line)
                replace_text_in_file(
                    path=ebuild_path,
                    match_bytes=repo_line.encode("utf8"),
                    replacement_bytes=new_egit_repo_uri_line.encode("utf8"),
                    output_fh=None,
                    read_mode="rb",
                    write_mode="wb",
                    remove_match=False,
                )
                # assert False
            # if not remote.startswith("git@github.com:"):
            #    if app_user == github_user:
            #        icp(
            #            "remote is to",
            #            github_user,
            #            "but does not startwith git@github.com:",
            #            remote,
            #        )
            #        raise ValueError(edit_config_path, remote)
            # if not app_name == edit_config_path.parent.name:
            #    icp(app_name, "is not", edit_config_path.parent.name)
            #    raise ValueError(edit_config_path, remote)

        del app_name, app_user, app_module_name, app_path
        try:
            del github_url, repo_line_items
        except UnboundLocalError:
            pass

        # output(
        #    os.fsencode(config.parent.as_posix()),
        #    reason=None,
        #    dict_output=dict_output,
        #    tty=tty,
        # )


@cli.command()
@click.option(
    "--apps-folder",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        allow_dash=False,
        path_type=Path,
    ),
    required=True,
)
@click.option("--gentoo-overlay-repo", type=str, required=True)
@click.option("--local", is_flag=True)
@click.option("--github-user", type=str, required=True)
@click_add_options(click_global_options)
@click.pass_context
def check_all(
    ctx,
    apps_folder: Path,
    gentoo_overlay_repo: str,
    github_user: str,
    verbose_inf: bool,
    dict_output: bool,
    local: bool,
    verbose: bool = False,
):
    not_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    ic(apps_folder)

    edit_configs = find_edit_configs(
        apps_folder=apps_folder,
    )

    for edit_config_path in edit_configs:
        ic(edit_config_path)
        with chdir(
            edit_config_path.parent,
        ):
            remote = str(sh.git.remote("get-url", "origin")).strip()
            app_name, app_user, app_module_name, app_path = parse_url(
                remote,
                apps_folder=apps_folder,
            )
            if not remote.startswith("git@github.com:"):
                if app_user == github_user:
                    ic(
                        "remote is to",
                        github_user,
                        "but does not startwith git@github.com:",
                        remote,
                    )
                    raise ValueError(edit_config_path, remote)
            if not app_name == edit_config_path.parent.name:
                ic(app_name, "is not", edit_config_path.parent.name)
                raise ValueError(edit_config_path, remote)

        del app_name, app_user, app_module_name, app_path


@User("user", env_vars={"HOME": "/home/user"})
def commit_changes():
    os.system("whoami")
    print(sh.whoami())
    sh.git.add("--all")
    sh.git.commit("-m", "initial auto-commit")


@User("user")
def write_app_template(*, app_module_name: str, language: str, ext: str, templates):
    app_template = generate_app_template(
        package_name=app_module_name,
        language=language,
        append_files=templates,
    )
    with open(app_module_name + ext, "x") as fh:
        fh.write(app_template)

    if language == "python":
        init_template = generate_init_template(package_name=app_module_name)
        with open("__init__.py", "x", encoding="utf8") as fh:
            fh.write(init_template)
        sh.touch("py.typed")


@cli.command()
@click.argument(
    "language", type=click.Choice(["python", "bash", "sh", "zig", "c", "go"]), nargs=1
)
@click.argument("repo_url", type=str, nargs=1)
@click.argument("group", type=str, nargs=1)
@click.option("--branch", type=str, callback=valid_branch, default="master")
@click.option(
    "--template",
    "templates",
    type=click.Path(
        exists=True,
        dir_okay=False,
        file_okay=True,
        allow_dash=False,
        path_type=Path,
    ),
    required=False,
    multiple=True,
)
@click.option(
    "--depend",
    "dependencies",
    type=str,
    required=False,
    multiple=True,
)
@click.option("--apps-folder", type=str, required=True)
@click.option("--gentoo-overlay-repo", type=str, required=True)
@click.option("--github-user", type=str, required=True)
@click.option(
    "--license",
    type=click.Choice(build_license_list()),
    default="ISC",
)
@click.option("--owner", type=str, required=True)
@click.option("--owner-email", type=str, required=True)
@click.option("--description", type=str, required=True)
@click.option("--local", is_flag=True)
@click.option("--rename", type=str)
@click.option("--hg", is_flag=True)
@click.option("--use-existing-repo", is_flag=True)
@click_add_options(click_global_options)
@click.pass_context
def new(
    ctx,
    language: str,
    repo_url: str,
    group: str,
    branch: str,
    rename: None | str,
    templates: tuple[Path, ...],
    dependencies: tuple[str, ...],
    apps_folder: str,
    gentoo_overlay_repo: str,
    github_user: str,
    license: str,
    owner: str,
    owner_email: str,
    description: str,
    local: bool,
    use_existing_repo: bool,
    verbose_inf: bool,
    dict_output: bool,
    hg: bool,
    verbose: bool = False,
):
    am_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    if templates:
        templates = [t.resolve() for t in templates]

    if dependencies:
        dependencies = [
            resolve_package_name(
                dependency,
            )
            for dependency in dependencies
        ]

    original_repo_url = repo_url

    if repo_url.startswith("https://github.com/"):
        if repo_url.endswith(".git"):
            repo_url = repo_url[:-4]

    assert "/" not in group
    assert ":" not in group
    assert group in portage_categories()
    assert repo_url.startswith("https://")

    template_repo_url: None | str = None
    if not repo_url.startswith(f"https://github.com/{github_user}/"):
        template_repo_url = repo_url
        _app_name, _app_user, _app_module_name, _app_path = parse_url(
            repo_url,
            apps_folder=apps_folder,
        )
        if rename:
            _app_name = rename
        repo_url = f"https://github.com/{github_user}/{_app_name}"
        del _app_name, _app_user, _app_module_name, _app_path
    else:
        template_repo_url = None

    app_name, app_user, app_module_name, app_path = parse_url(
        repo_url,
        apps_folder=apps_folder,
    )
    ic(app_name)
    ic(app_user)
    assert app_user == github_user
    assert "_" not in app_path.name

    if language == "sh":
        language = "bash"

    ext = get_extension(language)

    @User("user")
    def pull_overlay():
        with chdir("/home/sysskel/myapps/jakeogh"):
            sh.git("pull")

    try:
        pull_overlay()
    # fixme with_user should pass this exception through
    except sh.ErrorReturnCode_1 as e:
        icp(e)

    icp(template_repo_url)
    if template_repo_url:
        clone_repo(
            repo_url=repo_url,
            template_repo_url=template_repo_url,
            apps_folder=apps_folder,
            hg=hg,
            branch=branch,
            app_path=app_path,
            app_group=group,
            local=local,
        )

    icp(app_path.exists(), use_existing_repo)
    if app_path.exists():
        eprint(f"Not creating new app, {app_path} already exists.")
    elif use_existing_repo:
        eprint(f"Adding existing repo to {app_path}")
    else:
        if not use_existing_repo:
            create_repo(
                hg=hg,
                app_path=app_path,
                app_module_name=app_module_name,
            )
        else:
            assert app_path.is_dir()
            assert Path(app_path / Path(".git")).exists()
            with chdir(
                app_path,
            ):
                mkdir_user(app_module_name)
                # os.makedirs(app_module_name, exist_ok=True)

        ic(template_repo_url)
        if not template_repo_url:
            with chdir(
                app_path,
            ):
                if language == "python":
                    write_setup_py(
                        use_existing_repo=use_existing_repo,
                        app_module_name=app_module_name,
                        app_name=app_name,
                        owner=owner,
                        owner_email=owner_email,
                        description=description,
                        dependencies=dependencies,
                        license=license,
                        repo_url=repo_url,
                    )

                if not Path("url.sh").exists():
                    write_url_sh(
                        repo_url,
                    )

                if not Path(".autogenerate_readme.sh").exists():
                    write_autogenerate_readme_sh()

                if language == "python":
                    os.system("fastep")

            with chdir(
                app_path / app_module_name,
            ):

                write_app_template(
                    app_module_name=app_module_name,
                    language=language,
                    templates=templates,
                    ext=ext,
                )

            with chdir(
                app_path,
            ):

                commit_changes()

        with chdir(
            app_path,
        ):
            remote_add_origin(
                hg=hg,
                app_path=app_path,
                local=local,
                app_name=app_name,
                app_user=app_user,
            )

            @User("user")
            def write_description_and_install():
                _description_md = generate_description_md_template(
                    package_name=app_name, repo_url=repo_url
                )
                with open(".description.md", "x", encoding="utf8") as fh:
                    fh.write(_description_md)
                sh.git.add(".description.md")

                _install_md = generate_install_md_template(package_name=app_name)
                with open(".install.md", "x", encoding="utf8") as fh:
                    fh.write(_install_md)
                sh.git.add(".install.md")

            write_description_and_install()

    write_edit_config(
        app_path=app_path,
        package_name=app_name,
        package_group=group,
        local=local,
    )

    ebuild_path = Path(gentoo_overlay_repo) / Path(group) / Path(app_name)
    ebuild_name = app_name + "-9999.ebuild"
    if not ebuild_path.exists():
        enable_go = False
        if language == "go":
            enable_go = True
        enable_python = False
        if Path(app_path / Path("setup.py")).exists():
            enable_python = True
        if Path(app_path / Path("setup.cfg")).exists():
            enable_python = True

        os.makedirs(ebuild_path, exist_ok=False)

        enable_dobin = False
        if language in {"bash", "go"}:
            enable_dobin = True
        with chdir(
            ebuild_path,
        ):
            with open(ebuild_name, "w", encoding="utf8") as fh:
                fh.write(
                    generate_ebuild_template(
                        app_name=app_name,
                        description=description,
                        enable_python=enable_python,
                        enable_go=enable_go,
                        enable_dobin=enable_dobin,
                        homepage=original_repo_url,
                        dependencies=dependencies,
                        app_path=app_path,
                    )
                )
            # do this first, so we have the current remote HEAD ref before trying to push
            # still a race conditon obviously
            os.system("emaint sync -A")
            sh.git.add(ebuild_name)
            sh.ebuild(ebuild_name, "manifest")
            sh.git.add("*")
            sh.git.add(
                "-u"
            )  # add any unstaged changes (like some other ebuild was deleted)
            os.system(f"git commit -m 'newapp {app_name}'")
            os.system("git push")
            os.system("emaint sync -A")
            # accept_keyword = f"={group}/{app_name}-9999 **\n"
            # accept_keywords = accept_keywords_path(group=group, app_name=app_name)
            ## needs sudo
            # try:
            #    ensure_line_in_config_file(
            #        path=accept_keywords,
            #        line=accept_keyword,
            #    )
            # except PermissionError as e:
            #    icp(e)
            #    raise e
            sh.ln("-s", ebuild_path / ebuild_name, app_path / ebuild_name)
            os.system(f"sudo git config --system --add safe.directory {app_path}/.git")

            create_package_env_records(
                group=group,
                app_name=app_name,
                app_path=app_path,
            )

            sh.git.diff("--exit-code")
            # need to commit any pending ebuild changes here, but that's the wront git message, and it fails if it's unhanged

        with chdir(
            app_path,
        ):
            gitignore_template = generate_gitignore_template(ebuild_name=ebuild_name)
            if use_existing_repo:
                with open(".gitignore", "a", encoding="utf8") as fh:
                    fh.write(gitignore_template)
            else:  # could be a cloned repo, not a new one...
                try:
                    with open(".gitignore", "x", encoding="utf8") as fh:
                        fh.write(gitignore_template)
                except FileExistsError as e:
                    ic(e)
                    with open(".gitignore", "a", encoding="utf8") as fh:
                        fh.write(gitignore_template)

            # sh.git.add(".gitignore")

            sh.git.commit("-m", "initial commit", _ok_code=[0, 1])
    else:
        eprint(f"Not creating new ebuild, {ebuild_path} already exists.")

    ic(app_path)
    ic(app_module_name)

    main_py_path = app_path / Path(app_module_name) / Path(app_module_name + ext)
    ic(main_py_path)

    @User(
        "user",
        env_vars={
            "HOME": "/home/user",
            "EDITOR": "/home/sysskel/etc/skel/bin/editor_lock",
        },
    )
    def run_edittool(path: Path):
        os.system(
            "edittool edit --skip-isort --skip-black --skip-pylint --skip-text-replace "
            + main_py_path.as_posix()
        )

    run_edittool(main_py_path)


@cli.command()
@click.argument("repo_url", type=str, nargs=1)
@click.argument("group", type=str, nargs=1)
@click.option("--apps-folder", type=str, required=True)
@click.option("--gentoo-overlay-repo", type=str, required=True)
@click.option("--github-user", type=str, required=True)
@click_add_options(click_global_options)
@click.pass_context
def delete(
    ctx,
    repo_url: str,
    group: str,
    apps_folder: str,
    gentoo_overlay_repo: str,
    github_user: str,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
):
    # not_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    ic(apps_folder)

    app_name, app_user, app_module_name, app_path = parse_url(
        repo_url,
        apps_folder=apps_folder,
    )
    ic(app_name, app_user, app_module_name, app_path)
    assert app_user == github_user
    assert "_" not in app_path.name
    assert app_path.is_dir()

    with chdir("/home/sysskel/myapps/jakeogh"):
        sh.git("pull")

    ebuild_path = Path(gentoo_overlay_repo) / Path(group) / Path(app_name)
    ic(ebuild_path)
    recycle_bin = Path("/delme") / Path("deleted_apps") / Path(get_timestamp())
    recycle_bin.mkdir(parents=True, exist_ok=False)
    icp(recycle_bin)
    with chdir(
        recycle_bin,
    ):
        group_path = Path(group)
        group_path.mkdir(exist_ok=False)
        # sh.busybox.mv(ebuild_path, group_path, _close_stderr=True)
        # sh.busybox.mv(app_path, ".", _close_stderr=True)
        sh.busybox.mv(ebuild_path, group_path)
        sh.busybox.mv(app_path, ".")
    with chdir(
        ebuild_path.parent,
    ):
        sh.git.add("-u")
        sh.git.commit("-m", "auto-commit")
        sh.git.push()
        os.system("sudo emaint sync -A")


##http://liw.fi/cmdtest/
##http://liw.fi/cliapp/
#
# def debug(func):
#    msg = func.__qualname__
#    @wraps(func)
#    #http://www.dabeaz.com/py3meta/Py3Meta.pdf
#    def wrapper(*args, **kwargs):
#        print(msg)
#        return func(*args, **kwargs)
#    return wrapper
#
#
# def formatExceptionInfo(maxTBlevel=5):
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
# def unique(seq):
#    seen = set()
#    for item in seq:
#        if item not in seen:
#            seen.add(item)
#            yield item
#
#
# def reverse_sort_list(domains):
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
# def print_hex(text):
#    print(':'.join(hex(ord(x))[2:] for x in text))
#
#
# def dprint(*args, **kwargs):
#    if click_debug:
#        caller = sys._getframe(1).f_code.co_name
#        print(str("%.5f" % time.time()), os.getpid(), '{0: <15}'.format(caller+'()'), *args, file=sys.stderr, **kwargs)
#
# print(pydoc.render_doc(logger))
#
# log_level=log_levels['DEBUG']
# log_level=log_levels['INFO:']
#
#
# def print_traceback():
#    ex_type, ex, tb = sys.exc_info()
#    traceback.print_tb(tb)
#    del tb
