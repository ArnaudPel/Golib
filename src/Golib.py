from Tkinter import Tk
import argparse
from sys import argv
from gui.controller import Controller
from gui.ui import UI

__author__ = 'Kohistan'

"""
Application entry point.

"""


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sgf", help="SGF file to load at startup.")
    return parser

if __name__ == '__main__':
    root = Tk()
    app = UI(root)
    app.pack()

    args = get_argparser().parse_args()
    control = Controller(app, app, kifufile=args.sgf)
    root.mainloop()
