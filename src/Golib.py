from Tkinter import Tk
from go.kifu import Kifu
from gui.controller import Controller
from gui.ui import UI

__author__ = 'Kohistan'

"""
Application entry point.

"""

if __name__ == '__main__':
    root = Tk()
    #kifu = Kifu.parse("/Users/Kohistan/Documents/go/Perso Games/MrYamamoto-Kohistan.sgf")
    kifu = Kifu.new()

    app = UI(root)
    control = Controller(kifu, app, app)
    root.mainloop()