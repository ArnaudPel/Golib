from Tkinter import Tk
from sys import argv
from gui.controller import Controller
from gui.ui import UI

__author__ = 'Kohistan'

"""
Application entry point.

"""

if __name__ == '__main__':
    root = Tk()
    app = UI(root)
    app.pack()
    sgf = argv[1] if 1 < len(argv) else None
    control = Controller(app, app, kifufile=sgf)
    root.mainloop()