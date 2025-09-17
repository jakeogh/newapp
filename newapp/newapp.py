#!/usr/bin/env python3
# -*- coding: utf8 -*-

from __future__ import annotations

# Keep only essential top-level imports that are needed for decorators/global setup
import os
from pathlib import Path

import click
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
from globalverbose import gvd
from licenseguesser import build_license_list
from mptool import output
from portagetool import portage_categories
from portagetool import resolve_package_name
from timestamptool import get_timestamp
from with_user import User
from with_user import UserContextError

# Template imports moved inside functions to avoid relative import issues

CFG, CONFIG_MTIME = click_read_config(
    click_instance=click,
    app_name="newapp",
)

# https://github.com/mitsuhiko/click/issues/441
CONTEXT_SETTINGS = dict(default_map=CFG)


@User("user", env_vars={"HOME": "/home/user"})
def mkdir_user(path: Path):
    import os

    os.makedirs(path, exist_ok=True)


@User("user", env_vars={"HOME": "/home/user"})
def git_add(thing: str):
    import subprocess

    subprocess.run(
        ["git", "add", thing],
        check=True,
    )


@User("user")
def git_mv(*, old_path: Path, new_path: Path):
    import subprocess

    subprocess.run(
        ["git", "mv", old_path.as_posix(), new_path.as_posix()],
        check=True,
    )


def ensure_line_in_config_file(path: Path, line: str):
    import errno

    from filetool import \
        ensure_line_in_config_file as _ensure_line_in_config_file
    from retry_on_exception import retry_on_exception

    @retry_on_exception(
        exception=PermissionError,
        # errno=errno.EPERM,
    )
    @retry_on_exception(
        exception=OSError,
        errno=errno.ENOSPC,
    )
    def _wrapped():
        _ensure_line_in_config_file(
            path=path,
            line=line,
            comment_marker="#",
            ignore_leading_whitespace=False,
        )

    return _wrapped()


def create_package_env_records(
    *,
    group: str,
    app_name: str,
    app_path: Path,
):
    import os
    from pathlib import Path

    icp(
        group,
        app_name,
        app_path,
    )
    assert os.geteuid() == 0
    os.system(f"mkdir /etc/portage/env/{group}")
    os.system(f"mkdir /etc/portage/package.env/{group}")

    try:
        ensure_line_in_config_file(
            path=Path(f"/etc/portage/env/{group}/{app_name}-9999"),
            line=f"EGIT_REPO_URI='{app_path}'\n",
        )
    except PermissionError as e:
        icp(e)
        raise
    try:
        ensure_line_in_config_file(
            path=Path(f"/etc/portage/package.env/{group}/{app_name}"),
            line=f"{group}/{app_name} {group}/{app_name}-9999\n",
        )
    except PermissionError as e:
        icp(e)
        raise


@User("user")
def write_edit_config(
    *,
    app_path: Path,
    package_name: str,
    package_group: str,
    local: bool,
    edit_config_str: str,
):
    import os

    from with_chdir import chdir

    eprint(
        f"{package_name=}",
        f"{package_group}",
        f"{local}",
    )
    with chdir(app_path):
        os.system("ls -alh")
        with open(
            ".edit_config",
            "x",
            encoding="utf8",
        ) as fh:
            fh.write(edit_config_str)


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


# @User("user")
def replace_text(
    path: Path,
    str_to_match: str,
    replacement: str,
) -> None:
    from replace_text import replace_text_in_file

    # ic(str_to_match, replacement)

    replace_text_in_file(
        path=path,
        match_bytes=str_to_match.encode("utf8"),
        replacement_bytes=replacement.encode("utf8"),
        output_fh=None,
        read_mode="rb",
        write_mode="wb",
        remove_match=False,
    )


@User("user")
def replace_match_pairs_in_file(
    *,
    path: Path,
    match_pairs: tuple,
) -> None:
    assert isinstance(match_pairs, tuple)
    icp(path, match_pairs)
    for old_match, new_match in match_pairs:
        if old_match == new_match:
            continue
        replace_text(
            path=path,
            str_to_match=old_match,
            replacement=new_match,
        )


def replace_match_pairs_in_file_root(
    *,
    path: Path,
    match_pairs: tuple,
) -> None:
    from replace_text import replace_text_in_file

    assert isinstance(match_pairs, tuple)
    icp(path, match_pairs)
    for old_match, new_match in match_pairs:
        if old_match == new_match:
            continue
        replace_text_in_file(
            path=path,
            match_bytes=old_match.encode("utf8"),
            replacement_bytes=new_match.encode("utf8"),
            output_fh=None,
            read_mode="rb",
            write_mode="wb",
            remove_match=False,
        )


@User("user")
def get_url_for_overlay(
    overlay: str,
) -> str:
    import sh

    command = sh.eselect("repository", "list")
    command_output = command.stdout.split("\n")
    # ic(type(command_output), command_output)

    for line in command_output[1:]:
        # ic(line)
        try:
            index, repo_name, repo_url = [item for item in line.split() if item]
        except ValueError:
            pass

        repo_url = repo_url.split("(")[-1].split(")")[0]
        if repo_name == overlay:
            return repo_url

    raise ValueError(f"unknown repo {overlay}")


# @User("user")
# def valid_branch(
#    ctx,
#    param,
#    value,
# ):
#    # ic(value)
#    branch_check_cmd = "git check-ref-format --branch " + value
#    if os.system(branch_check_cmd):
#        raise click.BadParameter(f'fatal: "{value}" is not a valid branch name')
#    return value


def find_edit_configs(
    *,
    apps_folder: Path,
):
    from getdents import files_pathlib

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
    from .templates import edit_config

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
def generate_src_install_dobin_template(app_name):
    from .templates import src_install_dobin

    return src_install_dobin.format(app_name=app_name)


def generate_gitignore_template(*, ebuild_name):
    from .templates import gitignore

    return gitignore.format(ebuild_name=ebuild_name)


def generate_init_template(package_name):
    from .templates import init

    return init.format(package_name=package_name)


def generate_description_md_template(*, package_name, repo_url):
    from .templates import description_md

    return description_md.format(package_name=package_name, repo_url=repo_url)


def generate_install_md_template(*, package_name):
    from .templates import install_md

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
    import sh
    from getdents import files
    from getdents import paths
    from with_chdir import chdir

    # ic(old_name, new_name)
    old_module_name = old_name.replace("-", "_")
    new_module_name = old_name.replace("-", "_")

    with chdir(
        app_path,
    ):
        if Path(old_name).exists():  # not all apps have a dir here
            git_mv(old_path=old_name, new_path=new_name)
        if Path(old_name.replace("-", "_")).exists():  # not all apps have a dir here
            git_mv(old_path=old_name.replace("-", "_"), new_path=new_name)

        with open(
            ".edit_config",
            "x",
            encoding="utf8",
        ) as fh:
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
                # ic(old_name, path.name)
                new_path_name = path.name.replace(old_name, new_name)
                # ic(new_path_name)
                new_path = path.parent / Path(new_path_name)
                git_mv(old_path=path, new_path=new_path)

            if old_name.replace("-", "_") in path.name:
                if path.name == new_name:
                    continue
                # ic(old_name.replace("-", "_"), path.name)
                new_path_name = path.name.replace(old_name.replace("-", "_"), new_name)
                # ic(new_path_name)
                new_path = path.parent / Path(new_path_name)
                git_mv(old_path=path, new_path=new_path)

        all_files = list(
            files(
                app_path,
            )
        )
        exclude_path = app_path / Path(".git")
        for dent in all_files:
            # ic(dent)
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
    import os
    import sys

    import sh

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
            "clone",
            repo_to_clone_url,
            str(app_path),
            _out=sys.stdout,
            _err=sys.stderr,
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
    import os
    from pathlib import Path

    from with_chdir import chdir

    # icp(
    #    app_path,
    #    app_module_name,
    #    hg,
    # )
    if hg:
        raise NotImplementedError("hg")
    os.makedirs(app_path, exist_ok=False)
    with chdir(
        app_path,
    ):
        os.makedirs(app_module_name, exist_ok=False)
        os.system("git init")


def _write_enable_github(*, output_file: Path, enable_github: str):
    with open(
        output_file,
        "x",
        encoding="utf8",
    ) as fh:
        fh.write(enable_github)


def remote_add_origin(
    *,
    app_path: Path,
    local: bool,
    app_name: str,
    app_user: str,
    hg: bool,
):
    import sh
    from with_chdir import chdir

    if hg:
        raise NotImplementedError("hg")

    repo_config_command = sh.Command("git")
    repo_config_command = repo_config_command.bake(
        "remote",
        "add",
        "origin",
        f"git@github.com:jakeogh/{app_name}.git",
    )

    # repo_config_command = f"git remote add origin git@github.com:jakeogh/{app_name}.git"
    # ic(repo_config_command)
    if not local:
        with chdir(
            app_path,
        ):
            # os.system(repo_config_command)
            repo_config_command()
    else:
        # ic("local == True, skipping:", repo_config_command)
        pass

    enable_github = [
        "#!/bin/sh",
        f"hub create {app_user}/{app_name}",
        str(repo_config_command),
        "git push --set-upstream origin master",
        "touch .push",
        "\n",
    ]
    _enable_github = "\n".join(enable_github)
    output_file = app_path / Path("enable_github.sh")
    _write_enable_github(output_file=output_file, enable_github=_enable_github)


def parse_url(
    repo_url: str,
    *,
    apps_folder: Path,
    keep_underscore: bool = False,  # for rename
):
    from urllib.parse import urlparse

    # ic(repo_url)

    if repo_url.startswith("git:github.com:"):
        app_name = repo_url.split(":")[-1].split(".git")[0]
        app_user = repo_url.split(":")[-1].split("/")[0]
    else:
        url_parsed = urlparse(repo_url)
        # ic(url_parsed)

        repo_url_path = Path(url_parsed.path)
        app_name = repo_url_path.parts[-1]
        app_user = repo_url_path.parts[-2]

    app_name = app_name.lower()
    if not keep_underscore:
        app_name = app_name.replace("_", "-")
    app_name = app_name.split(".git")[0]
    app_module_name = app_name.replace("-", "_")
    app_module_name = app_module_name.split(".git")[0]
    # ic(app_module_name)
    app_path = apps_folder / Path(app_name)
    # ic(app_path)
    return app_name, app_user, app_module_name, app_path


@User("user")
def _write_url_sh(url_template_str: str):
    with open(
        "url.sh",
        "x",
        encoding="utf8",
    ) as fh:
        fh.write(url_template_str)


def write_url_sh(repo_url):
    import sh

    from .templates import echo_url

    def generate_url_template(url):
        return echo_url.format(url=url)

    url_template_str = generate_url_template(url=repo_url)
    _write_url_sh(url_template_str=url_template_str)
    sh.chmod("+x", "url.sh")


@User("user", env_vars={"HOME": "/home/user"})
def _write_autogenerate_readme(autogenerate_readme: str):
    import subprocess

    with open(
        ".autogenerate_readme.sh",
        "x",
        encoding="utf8",
    ) as fh:
        fh.write(autogenerate_readme)
    subprocess.run(["git", "add", ".autogenerate_readme.sh"], check=True)


def write_autogenerate_readme_sh():
    import subprocess

    import sh

    from .templates import autogenerate_readme

    _write_autogenerate_readme(autogenerate_readme)

    # sh.git.add(".autogenerate_readme.sh")
    # sh.chmod("+x", ".autogenerate_readme.sh")


@User("user")
def _write_setup_py(setup_py_str: str):
    with open(
        "setup.py",
        "x",
        encoding="utf8",
    ) as fh:
        fh.write(setup_py_str)


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
    import os

    from .templates import setup_py

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

        return setup_py.format(
            package_name=package_name,
            command=command,
            url=url,
            license=license,
            owner=owner,
            owner_email=owner_email,
            description=description,
        )

    os.system("pwd")
    os.system("ls -al")
    if use_existing_repo:
        if Path("setup.py").exists():
            return

    setup_py_str = generate_setup_py(
        package_name=app_module_name,
        command=app_name,
        owner=owner,
        owner_email=owner_email,
        description=description,
        dependencies=dependencies,
        license=license,
        url=repo_url,
    )
    _write_setup_py(setup_py_str)


@User("user")
def write_pyproject_toml():
    from .templates import pyproject_toml

    with open(
        "pyproject.toml",
        "x",
        encoding="utf8",
    ) as fh:
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
@click.argument(
    "overlay_name",
    type=str,
    nargs=1,
)
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
    import shutil

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
    # ic(group)
    # ic(name)
    relative_destination = Path(group) / Path(name)
    template_path = Path("/var/db/repos/gentoo") / relative_destination
    # ic(template_path)
    local_overlay = Path("/home/cfg/_myapps/jakeogh")
    destination = local_overlay / relative_destination
    # ic(template_path, destination)
    try:
        shutil.copytree(template_path, destination)
    except FileExistsError as e:
        # ic(e)
        pass


# @cli.command()
# @click_add_options(click_global_options)
# @click.pass_context
# def template_pylint(
#    ctx,
#    verbose_inf: bool,
#    dict_output: bool,
#    verbose: bool = False,
# ):
#    tty, verbose = tvicgvd(
#        ctx=ctx,
#        verbose=verbose,
#        verbose_inf=verbose_inf,
#        ic=ic,
#        gvd=gvd,
#    )
#    app_template = generate_app_template(
#        "TEMP",
#        language="python",
#        append_files=(),
#    )
#    for line in app_template.splitlines():
#        if line.startswith("# fl ake8: "):
#            print(line)
#        if line.startswith("# py lint: "):
#            print(line)


# @cli.command()
# @click.argument(
#    "package-name",
#    type=str,
#    default="TESTPACKAGE",
# )
# @click_add_options(click_global_options)
# @click.pass_context
# def template_python(
#    ctx,
#    package_name: str,
#    verbose_inf: bool,
#    dict_output: bool,
#    verbose: bool = False,
# ):
#    tty, verbose = tvicgvd(
#        ctx=ctx,
#        verbose=verbose,
#        verbose_inf=verbose_inf,
#        ic=ic,
#        gvd=gvd,
#    )
#    app_template = generate_app_template(
#        package_name,
#        language="python",
#        append_files=(),
#    )
#    output(
#        app_template,
#        reason=None,
#        dict_output=dict_output,
#        tty=tty,
#    )
#
#
# @cli.command()
# @click.argument(
#    "package-name",
#    type=str,
#    default="TESTPACKAGE",
# )
# @click_add_options(click_global_options)
# @click.pass_context
# def template_bash(
#    ctx,
#    package_name: str,
#    verbose_inf: bool,
#    dict_output: bool,
#    verbose: bool = False,
# ):
#    tty, verbose = tvicgvd(
#        ctx=ctx,
#        verbose=verbose,
#        verbose_inf=verbose_inf,
#        ic=ic,
#        gvd=gvd,
#    )
#    app_template = generate_app_template(
#        package_name,
#        language="bash",
#        append_files=(),
#    )
#    print(app_template)
#
#
# @cli.command()
# @click.argument(
#    "package-name",
#    type=str,
#    default="TESTPACKAGE",
# )
# @click_add_options(click_global_options)
# @click.pass_context
# def template_zig(
#    ctx,
#    package_name: str,
#    verbose_inf: bool,
#    dict_output: bool,
#    verbose: bool = False,
# ):
#    tty, verbose = tvicgvd(
#        ctx=ctx,
#        verbose=verbose,
#        verbose_inf=verbose_inf,
#        ic=ic,
#        gvd=gvd,
#    )
#    app_template = generate_app_template(
#        package_name,
#        language="zig",
#        append_files=(),
#    )
#    print(app_template)


@User("user")
def find_and_move(
    *,
    dir: Path,
    match: str,
    replacement: str,
    git: bool = False,
) -> None:
    import os
    import subprocess

    if not isinstance(dir, Path):
        raise TypeError("dir must be a pathlib.Path")
    if not isinstance(match, str) or not isinstance(replacement, str):
        raise TypeError("match and replacement must be str")
    if not isinstance(git, bool):
        raise TypeError("git must be a bool")
    icp(
        dir,
        match,
        replacement,
        git,
    )

    for root, _, files in os.walk(dir):
        for fname in files:
            if match in fname:
                old_path = Path(root) / fname
                new_name = fname.replace(
                    match,
                    replacement,
                    1,
                )
                new_path = Path(root) / new_name

                if git:
                    subprocess.run(
                        ["git", "mv", str(old_path), str(new_path)],
                        check=True,
                    )
                else:
                    old_path.rename(new_path)


@cli.command("rename")
@click.argument(
    "old_repo_url",
    type=str,
    nargs=1,
)
@click.argument(
    "new_repo_url",
    type=str,
    nargs=1,
)
@click.argument(
    "group",
    type=str,
    nargs=1,
)
@click.option(
    "--apps-folder",
    type=str,
    required=True,
)
@click.option(
    "--gentoo-overlay-repo",
    type=str,
    required=True,
)
@click.option(
    "--github-user",
    type=str,
    required=True,
)
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
    import sys

    import sh
    from with_chdir import chdir

    am_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    # ic(apps_folder)

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

    icp(old_app_name, new_app_name)
    icp(old_app_path, new_app_path)

    assert group in portage_categories()
    sh.emerge(["--unmerge", f"{group}/{old_app_name}"])

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

    assert not Path(apps_folder / old_app_path).exists()

    with chdir(
        new_app_path,
    ):
        sh.busybox.mv(
            "-v",
            old_app_module_name,
            new_app_module_name,
            _out=sys.stdout,
            _err=sys.stderr,
        )

    # first rename files and replace text within them
    # then rename parent dir
    with chdir(
        new_app_path,
    ):

        old_py_files = []
        old_py_files.append(new_app_path / Path("setup.py"))
        old_py_files.append(new_app_path / Path("url.sh"))
        old_py_files.append(new_app_path / Path("README.md"))
        old_py_files.append(
            new_app_path / old_app_module_name / Path(new_app_module_name + ".py")
        )
        old_py_files.append(new_app_path / new_app_module_name / Path("__init__.py"))
        old_py_files.append(new_app_path / new_app_module_name / Path("cli.py"))
        old_py_files.append(new_app_path / Path("enable_github.sh"))
        old_py_files.append(new_app_path / Path(".edit_config"))
        for _ in old_py_files:
            if not _.exists():
                continue
            replace_match_pairs_in_file(
                path=_,
                match_pairs=(
                    (old_app_name, new_app_name),
                    (old_app_module_name, new_app_module_name),
                ),
            )
            try:
                git_add(_)
            except UserContextError as e:
                icp(e)
                # icp(e.args)
                icp(e.args[0])
                if (
                    not "The following paths are ignored by one of your .gitignore files"
                    in e.args
                ):
                    raise

        find_and_move(
            dir=Path("."),
            match=old_app_module_name,
            replacement=new_app_module_name,
            git=True,
        )

        old_ebuild_symlink = new_app_path / Path(new_app_name + "-9999.ebuild")
        old_ebuild_symlink.unlink()

    # rename ebuild folder
    with chdir(Path(gentoo_overlay_repo) / Path(group)):
        sh.busybox.mv(
            "-v",
            old_app_name,
            new_app_name,
            _out=sys.stdout,
            _err=sys.stderr,
        )

    # recreate ebuild symlink
    with chdir(new_app_path):
        new_ebuild_folder = Path(gentoo_overlay_repo) / Path(group) / Path(new_app_name)
        sh.ln(
            "-s",
            new_ebuild_folder / Path(new_app_name + ".ebuild"),
            Path(new_app_name + ".ebuild"),
            _ok_code=[0, 1],
        )


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
    import sh
    from with_chdir import chdir

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    # ic(apps_folder)

    edit_configs = find_edit_configs(
        apps_folder=apps_folder,
    )
    for config in edit_configs:
        # ic(config)
        if ls_remote:
            project_dir = config.parent
            return_code = None
            # ic(project_dir)
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
    import os

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    # ic(apps_folder)

    edit_configs = find_edit_configs(
        apps_folder=apps_folder,
    )
    for config in edit_configs:
        # ic(config)
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
@click.option(
    "--github-user",
    type=str,
    required=True,
)
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
    import sh
    from replace_text import replace_text_in_file
    from with_chdir import chdir

    from .templates import edit_config

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    # ic(apps_folder)

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
            icp(
                app_name,
                app_user,
                app_module_name,
                app_path,
                remote,
            )
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
            # icp(ebuild_path)
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
@click.option(
    "--gentoo-overlay-repo",
    type=str,
    required=True,
)
@click.option("--local", is_flag=True)
@click.option(
    "--github-user",
    type=str,
    required=True,
)
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
    import sh
    from with_chdir import chdir

    not_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    # ic(apps_folder)

    edit_configs = find_edit_configs(
        apps_folder=apps_folder,
    )

    for edit_config_path in edit_configs:
        # ic(edit_config_path)
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
                    # ic(
                    #    "remote is to",
                    #    github_user,
                    #    "but does not startwith git@github.com:",
                    #    remote,
                    # )
                    raise ValueError(edit_config_path, remote)
            if not app_name == edit_config_path.parent.name:
                # ic(app_name, "is not", edit_config_path.parent.name)
                raise ValueError(edit_config_path, remote)

        del app_name, app_user, app_module_name, app_path


@User("user", env_vars={"HOME": "/home/user"})
def commit_changes():
    import subprocess

    subprocess.run(
        ["git", "add", "--all"],
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial auto-commit"],
        check=True,
    )


@User("user")
def _write_app_template(
    *,
    app_template: str,
    app_module_name: str,
    ext: str,
    app_path: Path,
):
    from with_chdir import chdir

    with chdir(
        app_path / app_module_name,
    ):
        with open(app_module_name + ext, "x") as fh:
            fh.write(app_template)


@User("user")
def _write_python_init(python_init: str):
    with open(
        "__init__.py",
        "x",
        encoding="utf8",
    ) as fh:
        fh.write(python_init)


def write_app_template(
    *,
    app_module_name: str,
    language: str,
    ext: str,
    templates,
    app_path: Path,
):
    import sh

    def generate_app_template(
        package_name: str,
        *,
        language: str,
        append_files: tuple[Path, ...],
    ) -> str:
        from .templates import bash_app
        from .templates import cee_app
        from .templates import python_app
        from .templates import zig_app

        result = None
        if language == "python":
            result = python_app.format(
                package_name=package_name,
                newline="\\n",
                null="\\x00",
            )
        if language == "bash":
            result = bash_app.format(
                package_name=package_name,
                newline="\\n",
                null="\\x00",
            )
        if language == "zig":
            result = zig_app.format(
                package_name=package_name,
                newline="\\n",
                null="\\x00",
            )
        if language == "c":
            # result = cee_app.format(package_name=package_name, newline="\\n", null="\\x00")
            result = cee_app

        if result:
            for file in append_files:
                with open(
                    file,
                    "r",
                    encoding="utf8",
                ) as fh:
                    result += fh.read()
            return result

        raise ValueError(language)

    app_template = generate_app_template(
        package_name=app_module_name,
        language=language,
        append_files=templates,
    )
    _write_app_template(
        app_module_name=app_module_name,
        ext=ext,
        app_template=app_template,
        app_path=app_path,
    )

    if language == "python":
        init_template = generate_init_template(package_name=app_module_name)
        _write_python_init(init_template)
        Path("py.typed").touch()


@User("user", env_vars={"HOME": "/home/user"})
def _write_ebuild_template(
    *,
    ebuild_name: str,
    ebuild_path: Path,
    ebuild_template_str: str,
):
    from with_chdir import chdir

    with chdir(
        ebuild_path,
    ):
        with open(
            ebuild_name,
            "w",
            encoding="utf8",
        ) as fh:
            fh.write(ebuild_template_str)

        # do this first, so we have the current remote HEAD ref before trying to push
        # still a race conditon obviously


def write_ebuild_template(
    *,
    ebuild_path: Path,
    ebuild_name: str,
    app_name: str,
    description: str,
    enable_python: bool,
    enable_go: bool,
    enable_dobin: bool,
    homepage: str,
    dependencies: tuple[str, ...],
    app_path: Path,
    original_repo_url: str,
):
    import os
    from datetime import date

    import sh

    from .templates import depend_python
    from .templates import ebuild

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

        # ic(enable_python)
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

    ebuild_template_str = generate_ebuild_template(
        app_name=app_name,
        description=description,
        enable_python=enable_python,
        enable_go=enable_go,
        enable_dobin=enable_dobin,
        homepage=original_repo_url,
        dependencies=dependencies,
        app_path=app_path,
    )

    os.makedirs(ebuild_path, exist_ok=False)
    _write_ebuild_template(
        ebuild_name=ebuild_name,
        ebuild_path=ebuild_path,
        ebuild_template_str=ebuild_template_str,
    )


@User("user", env_vars={"HOME": "/home/user"})
def git_ops(
    ebuild_name: str,
    app_name: str,
    ebuild_path: Path,
    app_path: Path,
):
    import os
    import subprocess

    import sh

    git_add(ebuild_name)
    subprocess.run(["ebuild", ebuild_name, "manifest"], check=True)
    git_add("*")
    # add any unstaged changes (like some other ebuild was deleted)
    git_add("-u")
    os.system(f"git commit -m 'newapp {app_name}'")
    os.system("git push")
    subprocess.run(
        ["ln", "-s", str(ebuild_path / ebuild_name), str(app_path / ebuild_name)],
        check=True,
    )


@User("user", env_vars={"HOME": "/home/user"})
def write_description_and_install(description_md: str, install_md: str):
    import sh

    with open(
        ".description.md",
        "x",
        encoding="utf8",
    ) as fh:
        fh.write(description_md)
    git_add(".description.md")

    with open(
        ".install.md",
        "x",
        encoding="utf8",
    ) as fh:
        fh.write(install_md)
    git_add(".install.md")


@cli.command()
@click.argument(
    "language",
    type=click.Choice(["python", "bash", "sh", "zig", "c", "go"]),
    nargs=1,
)
@click.argument(
    "repo_url",
    type=str,
    nargs=1,
)
@click.argument(
    "group",
    type=str,
    nargs=1,
)
# @click.option(
#    "--branch",
#    type=str,
#    callback=valid_branch,
#    default="master",
# )
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
@click.option(
    "--apps-folder",
    type=str,
    required=True,
)
@click.option(
    "--gentoo-overlay-repo",
    type=str,
    required=True,
)
@click.option(
    "--github-user",
    type=str,
    required=True,
)
@click.option(
    "--license",
    type=click.Choice(build_license_list()),
    default="ISC",
)
@click.option(
    "--owner",
    type=str,
    required=True,
)
@click.option(
    "--owner-email",
    type=str,
    required=True,
)
@click.option(
    "--description",
    type=str,
    required=True,
)
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
    import os
    import sys
    from datetime import date

    import sh
    from with_chdir import chdir

    branch = "master"
    am_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    # ic(apps_folder)

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
    # ic(app_name)
    # ic(app_user)
    assert app_user == github_user
    assert "_" not in app_path.name

    if language == "sh":
        language = "bash"

    ext = get_extension(language)

    @User("user")
    def pull_overlay():
        import sh
        from with_chdir import chdir

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
                    app_path=app_path,
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
            description_md = generate_description_md_template(
                package_name=app_name, repo_url=repo_url
            )
            install_md = generate_install_md_template(package_name=app_name)

            write_description_and_install(
                description_md=description_md, install_md=install_md
            )

    edit_config_str = generate_edit_config(
        package_name=app_path,
        package_group=group,
        local=local,
    )
    write_edit_config(
        app_path=app_path,
        package_name=app_name,
        package_group=group,
        local=local,
        edit_config_str=edit_config_str,
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

        enable_dobin = False
        if language in {"bash", "go"}:
            enable_dobin = True

        write_ebuild_template(
            ebuild_path=ebuild_path,
            ebuild_name=ebuild_name,
            app_name=app_name,
            description=description,
            enable_python=enable_python,
            enable_go=enable_go,
            enable_dobin=enable_dobin,
            homepage=original_repo_url,
            dependencies=dependencies,
            app_path=app_path,
            original_repo_url=original_repo_url,
        )

        os.system("emaint sync -A")

        with chdir(
            ebuild_path,
        ):

            git_ops(
                ebuild_name=ebuild_name,
                app_name=app_name,
                ebuild_path=ebuild_path,
                app_path=app_path,
            )
            os.system("emaint sync -A")
            os.system(f"git config --system --add safe.directory {app_path}/.git")

            create_package_env_records(
                group=group,
                app_name=app_name,
                app_path=app_path,
            )

            @User("user", env_vars={"HOME": "/home/user"})
            def git_diff():
                import sh

                sh.git.diff("--exit-code")

            git_diff()
            # need to commit any pending ebuild changes here, but that's the wront git message, and it fails if it's unhanged

        with chdir(
            app_path,
        ):

            @User("user", env_vars={"HOME": "/home/user"})
            def write_gitignore_template():
                import sh

                gitignore_template = generate_gitignore_template(
                    ebuild_name=ebuild_name
                )
                if use_existing_repo:
                    with open(
                        ".gitignore",
                        "a",
                        encoding="utf8",
                    ) as fh:
                        fh.write(gitignore_template)
                else:  # could be a cloned repo, not a new one...
                    try:
                        with open(
                            ".gitignore",
                            "x",
                            encoding="utf8",
                        ) as fh:
                            fh.write(gitignore_template)
                    except FileExistsError as e:
                        # ic(e)
                        with open(
                            ".gitignore",
                            "a",
                            encoding="utf8",
                        ) as fh:
                            fh.write(gitignore_template)

                # sh.git.add(".gitignore")

                sh.git.commit(
                    "-m",
                    "initial commit",
                    _ok_code=[0, 1],
                )

            write_gitignore_template()
    else:
        eprint(f"Not creating new ebuild, {ebuild_path} already exists.")

    # ic(app_path)
    # ic(app_module_name)

    main_py_path = app_path / Path(app_module_name) / Path(app_module_name + ext)
    # ic(main_py_path)

    run_edittool(main_py_path)


@User(
    "user",
    env_vars={
        "HOME": "/home/user",
        "EDITOR": "/home/sysskel/etc/skel/bin/editor_lock",
    },
)
def run_edittool(path: Path):
    import os

    os.system(
        "edittool edit --skip-isort --skip-black --skip-pylint --skip-text-replace "
        + path.as_posix()
    )


@cli.command()
@click.argument(
    "repo_url",
    type=str,
    nargs=1,
)
@click.argument(
    "group",
    type=str,
    nargs=1,
)
@click.option(
    "--apps-folder",
    type=str,
    required=True,
)
@click.option(
    "--gentoo-overlay-repo",
    type=str,
    required=True,
)
@click.option(
    "--github-user",
    type=str,
    required=True,
)
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
    import sh
    from with_chdir import chdir

    # not_root()
    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    apps_folder = Path(apps_folder)
    # ic(apps_folder)

    app_name, app_user, app_module_name, app_path = parse_url(
        repo_url,
        apps_folder=apps_folder,
    )
    # ic(
    #    app_name,
    #    app_user,
    #    app_module_name,
    #    app_path,
    # )
    assert app_user == github_user
    assert "_" not in app_path.name
    assert app_path.is_dir()

    with chdir("/home/sysskel/myapps/jakeogh"):
        sh.git("pull")

    ebuild_path = Path(gentoo_overlay_repo) / Path(group) / Path(app_name)
    # ic(ebuild_path)
    recycle_bin = Path("/delme") / Path("deleted_apps") / Path(get_timestamp())
    recycle_bin.mkdir(parents=True, exist_ok=False)
    # icp(recycle_bin)
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
        import os

        sh.git.add("-u")
        sh.git.commit("-m", "auto-commit")
        sh.git.push()
        os.system("sudo emaint sync -A")
