from tkinter import Tk
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
    # Apparently a common hack to get the window size. Temporarily hide the
    # window to avoid update_idletasks() drawing the window in the wrong position.
    root.withdraw()
    root.update_idletasks()  # Update "requested size" from geometry manager
    x = (root.winfo_screenwidth() - root.winfo_reqwidth()) / 2
    y = (root.winfo_screenheight() - root.winfo_reqheight()) / 2
    root.geometry("+%d+%d" % (x, y))
    root.deiconify()

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
