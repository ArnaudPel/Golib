from Tkconstants import BOTH, LEFT, TOP, N
from tkFileDialog import asksaveasfilename, askopenfilename
from Tkinter import Misc, StringVar, Label
from traceback import print_exc
from ttk import Frame, Button

from gui.goban import Goban


__author__ = 'Kohistan'

"""
The main user interface.

"""


class UI(Frame):
    def __init__(self, master, origin=(0, 0)):
        Frame.__init__(self, master)
        self.origin = origin
        self.goban = Goban(self)
        self.buttons = Frame(self)
        self.msg = StringVar(value="Hello")
        self.init_components()
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
        roff = self.origin[0]
        coff = self.origin[1]
        self.goban.grid(row=roff, column=coff)
        self.goban.focus_set()
        self.goban.bind("<q>", self.close)  # dev utility mostly, will probably have to be removed
        self.buttons.grid(row=roff, column=coff+1, sticky=N, pady=10)

        b_delete = Button(self.buttons, text="Delete", command=lambda: self.execute("delete"))
        b_open = Button(self.buttons, text="Open", command=lambda: self.execute("open"))
        b_save = Button(self.buttons, text="Save", command=lambda: self.execute("save"))
        msglabel = Label(self, textvariable=self.msg)

        b_delete.grid(row=0, column=0)
        b_open.grid(row=1, column=0)
        b_save.grid(row=2, column=0)
        msglabel.grid(row=1, column=0)

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
    def message(self, msg):
        self.msg.set(msg)

    def promptopen(self):
        return askopenfilename(filetypes=[("Smart Game Format", "sgf")])

    def promptsave(self):
        return asksaveasfilename(defaultextension="sgf")









