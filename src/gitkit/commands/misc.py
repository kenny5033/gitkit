import fileinput
from pathlib import Path
import sys
import textwrap
from typing import Dict, List
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


@verify_app.command(help="Check your added lines for any silliness")
def check_changes():
    from gitkit.logic.parts import part_stats

    repo = get_app_repo()
    stats = part_stats()

    hunks_by_file: Dict[str, List[List[str]]] = {}
    for file in stats.files_changed:
        hunks_by_file[str(file)] = []

        diff: str = repo.git.diff("origin/master", file)
        in_hunk = False
        current_hunk = []
        for line in diff.split("\n"):
            if not in_hunk:
                current_hunk = []

            if line.startswith("+ ") or line.startswith("- "):
                in_hunk = True
                current_hunk.append(line)
            elif in_hunk:
                in_hunk = False
                hunks_by_file[str(file)].append(current_hunk)

    for file_name, hunks in hunks_by_file.items():
        lines = ["*" * 10, f"** {file_name}", "*" * 10]
        for i, hunk in enumerate(hunks):
            lines.append(f"({i})")

            # move + or - to end for dedentation
            hunk_text = "\n".join([line[1:] + line[0] for line in hunk])
            hunk_text = textwrap.dedent(hunk_text)
            processed_hunk_lines = []
            for line in hunk_text.split("\n"):
                new_line = ""
                if line.endswith("+"):
                    new_line = f"\x1b[32;49m{line.removesuffix('+')}"
                else:
                    new_line = f"\x1b[31;49m{line.removesuffix('-')}"

                processed_hunk_lines.append(f"{new_line}\x1b[39;49m")

            lines.extend(processed_hunk_lines)
            lines.append("")

        print("\n".join(lines))
