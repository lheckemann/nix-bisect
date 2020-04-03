"""Determine the status of a nix build as lazily as possible in a
bisect-friendly format"""

import sys
import argparse
from pathlib import Path

from nix_bisect import nix, exceptions, git_bisect
from nix_bisect.derivation import Derivation


def drvish_to_drv(drvish, nix_file):
    """No-op on drv files, otherwise evaluate in the context of nix_file"""
    path = Path(drvish)
    if path.exists() and path.name.endswith(".drv"):
        return str(path)
    else:
        return nix.instantiate(drvish, nix_file)


def build_status(
    drvish, nix_file, failure_line=None, max_rebuilds=None,
):
    """Determine the status of `drvish` and return the result as indicated"""
    drv = drvish_to_drv(drvish, nix_file)
    print(f"Querying status of {drv}.")

    try:
        drv = Derivation(drv, max_rebuilds=max_rebuilds)

        if not drv.can_build_deps():
            failed = drv.sample_dependency_failure()
            print(f"Dependency {failed} failed to build.")
            return f"dependency_failure"

        if drv.can_build():
            return "success"
        else:
            if failure_line is None or drv.log_contains(failure_line):
                return "failure"
            else:
                return "failure_without_line"
    except exceptions.ResourceConstraintException:
        return "resource_limit"


def _main():
    actions = {
        "good": git_bisect.quit_good,
        "bad": git_bisect.quit_bad,
        "skip": git_bisect.quit_skip,
        "abort": git_bisect.abort,
    }
    action_choices = actions.keys()

    parser = argparse.ArgumentParser(
        description="Build a package with nix, suitable for git-bisect."
    )
    parser.add_argument(
        "drvish",
        type=str,
        help="Derivation or an attribute/expression that can be resolved to a derivation in the context of the nix file",
    )
    parser.add_argument(
        "--file",
        "-f",
        help="Nix file that contains the attribute",
        type=str,
        default=".",
    )
    parser.add_argument(
        "--max-rebuilds", type=int, help="Number of builds to allow.", default=None,
    )
    parser.add_argument(
        "--failure-line",
        help="Line required in the build logs to count as a failure.",
        default=None,
    )
    parser.add_argument(
        "--on-success",
        default="good",
        choices=action_choices,
        help="Bisect action if the expression can be successfully built",
    )
    parser.add_argument(
        "--on-failure",
        default="bad",
        choices=action_choices,
        help="Bisect action if the expression can be successfully built",
    )
    parser.add_argument(
        "--on-dependency-failure",
        default="skip",
        choices=action_choices,
        help="Bisect action if the expression can be successfully built",
    )
    parser.add_argument(
        "--on-failure-without-line",
        default="skip",
        choices=action_choices,
        help="Bisect action if the expression can be successfully built",
    )
    parser.add_argument(
        "--on-resource-limit",
        default="skip",
        choices=action_choices,
        help="Bisect action if a resource limit like rebuild count is exceeded",
    )

    try:
        args = parser.parse_args()
    except SystemExit:
        git_bisect.abort()

    status = build_status(
        args.drvish,
        args.file,
        failure_line=args.failure_line,
        max_rebuilds=args.max_rebuilds,
    )
    action_on_status = {
        "success": args.on_success,
        "failure": args.on_failure,
        "dependency_failure": args.on_dependency_failure,
        "failure_without_line": args.on_failure_without_line,
        "resource_limit": args.on_resource_limit,
    }
    actions[action_on_status[status]]()


if __name__ == "__main__":
    sys.exit(_main())