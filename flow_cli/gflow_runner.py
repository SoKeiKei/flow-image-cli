"""Run gflow-cli after installing this project's compatibility layer."""

from __future__ import annotations

from .new_flow_video import install_patches


def main() -> None:
    install_patches()
    from gflow_cli.cli import main as upstream_main

    upstream_main()


if __name__ == "__main__":
    main()
