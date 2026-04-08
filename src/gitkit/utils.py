import os
from pathlib import Path
import shutil
import sys
from typing import Optional
import uuid
from git import Repo


_app_repo: Optional[Repo] = None


def set_app_repo(repo: Repo):
    global _app_repo
    _app_repo = repo


def get_app_repo() -> Repo:
    global _app_repo

    if _app_repo is None:
        _app_repo = Repo(".")
    return _app_repo


def gitkit_bail(error_msg: str, *, okay: bool = False):
    """Print the error_msg and exit. Otherwise, do nothing"""
    sys.stderr.write("\nGitkit found it necessary to bail out:\n")
    sys.stderr.write(error_msg + "\n")
    sys.exit(0 if okay else 1)


class RepoTester:
    @classmethod
    def setup_class(cls):
        cls.dir = Path(f"/tmp/{uuid.uuid4()}")
        cls.repo = Repo.init(cls.dir)
        cls.repo.git.commit(allow_empty=True, m="init")
        os.chdir(cls.dir)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.dir)
