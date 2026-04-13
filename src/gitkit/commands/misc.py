import fileinput
import os
from pathlib import Path
import sys
import textwrap
from typing import Dict, List, Optional
from gitkit.utils import gitkit_bail, get_app_repo
import typer
from pynput import keyboard


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


@verify_app.command(help="Check your hunks for any silliness")
def check_changes():
    from gitkit.logic.parts import part_stats

    repo = get_app_repo()
    stats = part_stats()

    class Hunk(List):
        pass

    def parse_hunks(diff: str) -> List[Hunk]:
        res = []
        current_hunk = Hunk()
        in_hunk = False

        for line in diff.split("\n"):
            if line.isspace() or line.startswith("++") or line.startswith("--"):
                continue

            if line.startswith("+") or line.startswith("-"):
                in_hunk = True
                current_hunk.append(line)
            elif in_hunk:
                res.append(current_hunk)
                current_hunk = Hunk()
                in_hunk = False

        return res

    hunks_by_file: Dict[str, List[Hunk]] = {}
    for file in stats.files_changed:
        diff: str = repo.git.diff("origin/master", "--", file)
        hunks_by_file[str(file)] = parse_hunks(diff)

    def hunk_display_lines(hunk: Hunk) -> List[str]:
        # move + or - to end for dedentation
        hunk_text = "\n".join([line[1:] + line[0] for line in hunk])
        hunk_text = textwrap.dedent(hunk_text)

        lines = []
        for line in hunk_text.split("\n"):
            if line.endswith("+"):
                lines.append(f"\x1b[32;49m{line.removesuffix('+')}\x1b[0m")
            else:
                lines.append(f"\x1b[31;49m{line.removesuffix('-')}\x1b[0m")

        return lines

    hunks_to_view = [
        (file_name, hunk)
        for file_name, hunks in hunks_by_file.items()
        for hunk in hunks
    ]
    i = 0
    force_exit = False

    def on_press(key: Optional[keyboard.Key | keyboard.KeyCode]):
        if type(key) is keyboard.Key:
            if key == keyboard.Key.esc:
                nonlocal force_exit
                force_exit = True
                return False

        if type(key) is keyboard.KeyCode:
            nonlocal i
            if key.char == "n":
                i += 1
                return False
            elif key.char == "N":
                if i > 0:
                    i -= 1
                return False

    while i < len(hunks_to_view) and not force_exit:
        file_name, hunk = hunks_to_view[i]

        with keyboard.Listener(on_press=on_press) as listener:
            print("\x1bc")

            print(f"({i + 1}/ {len(hunks_to_view)})")
            print(f"** {file_name} **")
            for line in hunk_display_lines(hunk):
                print(line)

            print("ESC to exit")
            listener.join()
