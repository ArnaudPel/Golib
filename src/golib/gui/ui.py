import tkinter.constants
import platform
import traceback

import tkinter as tk
from tkinter.ttk import Frame, Button
from tkinter.filedialog import asksaveasfilename, askopenfilename
from tkinter.simpledialog import askinteger
from tkinter.messagebox import askokcancel

import golib.gui
from golib.config.golib_conf import appname, B, W
from golib.model import SGF_TYPE

"""
The main user interface.

"""

if "Darwin" in platform.system():
    mod1 = "Command"
else:
    mod1 = "Control"


class UI(Frame):
    """
    The top level GUI.

    """

    def __init__(self, master, origin=(0, 0)):
        Frame.__init__(self, master)
        self.origin = origin
        self.goban = golib.gui.Goban(self)
        self.buttons = Frame(self)
        self.ctx_event = None  # save the event that has originated the context menu
        self.msg = tk.StringVar(value="Hello")
        self.err = tk.StringVar(value="-")
        self.create_menubar()
        self.init_components()

        self.closed = False

        # user input part of the gui, delegated to goban ATM. may become lists later
        self.mousein = self.goban
        self.keyin = self.goban

        # these commands are expected to be set from outside, in an attempt to inject dependency via setter.
        # See 'controller' classes who instantiate some of these commands.
        self.commands = {}
        self.master.protocol("WM_DELETE_WINDOW", lambda: self.execute("close"))
        self.commands["close"] = lambda: self.master.quit()  # this command needs a default value

        # delegate some work to goban
        self.stones_changed = self.goban.stones_changed
        self.highlight = self.goban.highlight
        self.select = self.goban.select
        self.clear = self.goban.clear

    def init_components(self):
        """
        Called during __init__(). Can be extended, don't forget super() call.
        Note on layout managers: pack() and grid() don't mix well (at all) in the same container,
        or a global freeze is likely to happen.
        This is why no layout manager is called on self, and is left to creator to decide.

        """
        self.title(appname)
        roff = self.origin[0]
        coff = self.origin[1]
        self.goban.grid(row=roff, column=coff)
        self.buttons.grid(row=roff, column=coff+1, sticky=tkinter.constants.N, pady=10)

        b_delete = Button(self.buttons, text="Delete", command=lambda: self.execute("delselect"))
        # b_open = Button(self.buttons, text="Open", command=lambda: self.execute("open"))
        # b_save = Button(self.buttons, text="Save", command=lambda: self.execute("save"))

        b_back = Button(self.buttons, text="<", command=lambda: self.execute("back"))
        b_forward = Button(self.buttons, text=">", command=lambda: self.execute("forward"))
        b_beqinning = Button(self.buttons, text="<<", command=lambda: self.execute("beginning"))
        b_end = Button(self.buttons, text=">>", command=lambda: self.execute("end"))

        msglabel = tk.Label(self, textvariable=self.msg)
        errlabel = tk.Label(self, textvariable=self.err, fg="red")

        # position buttons on the buttons grid
        b_delete.grid(row=0, column=0, columnspan=2)
        # b_open.grid(row=1, column=0)
        # b_save.grid(row=1, column=1)

        b_back.grid(row=2, column=0)
        b_forward.grid(row=2, column=1)
        b_beqinning.grid(row=3, column=0)
        b_end.grid(row=3, column=1)

        # position things on the main GUI grid
        msglabel.grid(row=1, column=0)
        errlabel.grid(row=2, column=0)

        self.goban.focus_set()

    def create_menubar(self):
        self.menubar = tk.Menu(self._root())

        m_file = tk.Menu(self.menubar)
        m_file.add_command(label="New Game", command=lambda: self.execute("new"), accelerator=mod1+"N")
        self.bind_all("<{0}-n>".format(mod1), lambda _: self.execute("new"))

        m_file.add_command(label="Open...", command=lambda: self.execute("open"), accelerator=mod1+"O")
        self.bind_all("<{0}-o>".format(mod1), lambda _: self.execute("open"))

        m_file.add_command(label="Save...", command=lambda: self.execute("save"), accelerator=mod1+"+S")
        self.bind_all("<{0}-s>".format(mod1), lambda _: self.execute("save"))

        self.menubar.add_cascade(label="File", menu=m_file)

        # mac OS goody  todo what does it do on Linux or Windows ?
        m_help = tk.Menu(self.menubar, name='help')
        self.menubar.add_cascade(label="Help", menu=m_help)

        # display the menu
        self._root().config(menu=self.menubar)

    def get_ctx_menu(self, event, occupied):
        """
        Create a contextual menu for the goban.

        """
        self.ctx_event = event
        menu = tk.Menu(self.master)
        if occupied:
            menu.add_command(label="Swap color", command=self.swap_color)
        else:
            menu.add_command(label="Insert B", command=lambda: self.insert(B))
            menu.add_command(label="Insert W", command=lambda: self.insert(W))
        return menu

    def execute(self, command, *args):
        if command in self.commands:
            try:
                self.commands[command](*args)
            except Exception:
                # keep going
                traceback.print_exc()
            self.goban.focus_set()
        else:
            print("No \"{0}\" command set, ignoring.".format(command))

    # DISPLAY METHODS
    def message(self, msg):
        self.msg.set(msg)

    def error(self, msg):
        self.err.set(msg)

    def promptopen(self, filetypes=None, title="Open"):
        if filetypes:
            return askopenfilename(title=title, filetypes=filetypes)
        else:
            return askopenfilename(title=title)

    def promptdiscard(self, title="Unsaved changes"):
        msg = "Discard unsaved changes in current game ?"
        return askokcancel(title=title, message=msg, icon="warning")

    def promptsave(self, initdir=None, initfile=None):
        return asksaveasfilename(defaultextension=SGF_TYPE, initialdir=initdir, initialfile=initfile)

    def promptgoto(self):
        number = askinteger("Jump", "Go to move")
        self.goban.focus_set()
        return number

    def context_menu(self, event, occupied):
        x = event.x + self.winfo_rootx()
        y = event.y + self.winfo_rooty()
        self.get_ctx_menu(event, occupied).post(x, y)

    def insert(self, color):
        self.execute("insert", self.ctx_event, color)

    def swap_color(self):
        self.execute("color", self.ctx_event)

    def title(self, title):
        self._root().title(title)