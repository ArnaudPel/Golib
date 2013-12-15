from Tkconstants import BOTH, LEFT, TOP
from tkFileDialog import asksaveasfilename, askopenfilename
from Tkinter import Misc
from traceback import print_exc
from ttk import Frame, Button

from gui.goban import Goban


__author__ = 'Kohistan'

"""
The main user interface.

"""


class UI(Frame):
    def __init__(self, master):
        Frame.__init__(self, master)
        self.goban = Goban(self)
        self.init_components()
        self.goban.focus_set()
        self.goban.bind("<q>", self.close)  # dev utility mostly, will probably have to be removed
        self.closed = False

        # user input part of the gui, delegated to goban ATM. may become lists later
        self.mousein = self.goban
        self.keyin = self.goban

        # these are expected to be set from outside, in an attempt to inject dependency via setter
        self.commands = {}

        # delegate some work to goban
        # todo make that a bit more generic, using registration or something
        self.display = self.goban.display
        self.highlight = self.goban.highlight
        self.select = self.goban.select
        self.erase = self.goban.erase
        self.clear = self.goban.clear
        self.relocate = self.goban.relocate

    def init_components(self):
        self.pack(fill=BOTH, expand=1)
        self.goban.pack(side=LEFT)

        b_delete = Button(self, text="Delete", command=lambda: self.execute("delete"))
        b_open = Button(self, text="Open", command=lambda: self.execute("open"))
        b_save = Button(self, text="Save", command=lambda: self.execute("save"))

        b_delete.pack(side=TOP)
        b_open.pack(side=TOP)
        b_save.pack(side=TOP)

    def close(self, _):
        self.closed = True
        self.goban.closed = True
        Misc.quit(self)

    def execute(self, command):
        try:
            self.commands[command]()
        except KeyError:
            print "No \"{0}\" command set, ignoring.".format(command)
        except Exception:
            # keep going
            print_exc()
        self.goban.focus_set()

    # DISPLAY METHODS

    def promptopen(self):
        return askopenfilename(filetypes=[("Smart Game Format", "sgf")])

    def promptsave(self):
        return asksaveasfilename(defaultextension="sgf")









