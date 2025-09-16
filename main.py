#!/usr/bin/env python3
"""Run Sugar-AI Activity locally (GTK4)."""

import sys
import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

# Provide minimal SUGAR bundle environment for local runs
os.environ.setdefault("SUGAR_BUNDLE_ID", "org.sugarlabs.SugarAI")
os.environ.setdefault("SUGAR_BUNDLE_NAME", "Sugar-AI")
os.environ.setdefault("SUGAR_BUNDLE_PATH", os.getcwd())
os.environ.setdefault(
    "SUGAR_ACTIVITY_ROOT",
    os.path.join(os.path.expanduser("~"), ".sugar", "default", "org.sugarlabs.SugarAI"),
)

from sugar4.activity.activityhandle import ActivityHandle

import activity as sugar_ai_activity


def main(argv=None):
    argv = argv or sys.argv

    app = Gtk.Application(application_id="org.sugarlabs.SugarAI")

    def on_activate(app):
        handle = ActivityHandle("sugar-ai-local")
        win = sugar_ai_activity.SugarAIActivity(handle, application=app)
        # Prefer set_application on GTK4 Window-like Activity
        try:
            win.set_application(app)
        except Exception:
            # Fallback: add to application
            try:
                app.add_window(win)
            except Exception:
                pass
        win.present()

    app.connect("activate", on_activate)
    return app.run(argv)


if __name__ == "__main__":
    sys.exit(main())
