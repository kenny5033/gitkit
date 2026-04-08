import fileinput
from pathlib import Path
import sys
from gitkit.utils import gitkit_bail, get_app_repo
import typer


app = typer.Typer()
hooks_app = typer.Typer()
app.add_typer(hooks_app, name="hooks", rich_help_panel="Utilities")
verify_app = typer.Typer()
app.add_typer(verify_app, name="verify", rich_help_panel="Utilities")


@hooks_app.command(help="Install the gitkit prepush script")
def install_pre_push():
    repo = get_app_repo()

    git_hooks_dir = repo.git.config("core.hooksPath").strip()
    pre_push_path = Path(git_hooks_dir) / "pre-push"
    pre_push_path.chmod(0o755)

    install_tag = "# (gitkit pre-push)"
    remove_next_line = False
    for line in fileinput.input(pre_push_path, inplace=True):
        if remove_next_line:
            remove_next_line = False
            continue

        if line.strip() == install_tag:
            remove_next_line = True
            continue

        sys.stdout.write(line)

    with open(pre_push_path, "a") as f:
        f.write(install_tag + "\n")
        f.write(f"uv run gitkit --repo-path {repo.git_dir} verify pre-push\n")


@verify_app.command(name="pre-push", help="Run prepush verification checks")
def verify_pre_push():
    from gitkit.logic.parts import get_current_part
    from gitkit.logic.series import interpret_part_type, PartType

    part_type = interpret_part_type()
    if part_type == PartType.OTHER:
        sys.exit(0)

    if part_type == PartType.CONTEXT:
        gitkit_bail("You cannot push a context")

    if part_type == PartType.PART:
        if get_current_part() is not None:
            gitkit_bail("This part has yet to be rebased")
