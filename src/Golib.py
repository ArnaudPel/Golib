from Tkinter import Tk
import argparse
import os
import platform

from golib.gui.controller import Controller
from golib.gui.ui import UI


__author__ = 'Arnaud Peloquin'

"""
Application entry point.

"""


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sgf", help="SGF file to load at startup.")
    return parser


def center(win):
    """
    From stackoverflow, used to center app on screen

    """
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() / 2) - (width / 2)
    y = (win.winfo_screenheight() / 2) - (height / 2)
    win.geometry('{0}x{1}+{2}+{3}'.format(width, height, x, y))


if __name__ == '__main__':
    root = Tk()
    app = UI(root)
    app.pack()

    args = get_argparser().parse_args()
    control = Controller(app, app, sgffile=args.sgf)

    # mac OS special, to bring app to front at startup
    if "Darwin" in platform.system():
        os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')

    center(root)
    root.mainloop()
