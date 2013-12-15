from Tkinter import Tk
from sys import argv
from go.kifu import Kifu
from gui.controller import Controller
from gui.ui import UI

__author__ = 'Kohistan'

"""
Application entry point.

"""

if __name__ == '__main__':
    root = Tk()

    if 1 < len(argv):
        kifu = Kifu.parse(argv[1])
    else:
        kifu = Kifu.new()

    app = UI(root)
    app.pack()
    control = Controller(kifu, app, app)
    root.mainloop()