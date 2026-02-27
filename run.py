#!/usr/bin/env python3
"""Entry point for the ADAM GUI application."""

import sys


def main():
    from adam_gui.app import AdamApplication

    app = AdamApplication(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
