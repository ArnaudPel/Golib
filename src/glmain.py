import os
import platform
import argparse
import tkinter

from golib.config import golib_conf
import golib.gui


"""
Application entry point.

"""


def get_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(conflict_handler='resolve')
    parser.add_argument("--sgf", help="SGF file to load at startup.")
    return parser


def center(win):
    """
    From stackoverflow, used to center app on screen

    """
    # Apparently a common hack to get the window size. Temporarily hide the
    # window to avoid update_idletasks() drawing the window in the wrong position.
    win.withdraw()
    win.update_idletasks()  # Update "requested size" from geometry manager
    x = (win.winfo_screenwidth() - win.winfo_reqwidth()) / 2
    y = (win.winfo_screenheight() - win.winfo_reqheight()) / 2
    win.geometry("+%d+%d" % (x, y))
    win.deiconify()


def place(win):
    if golib_conf.glocation is None:
        center(win)
    else:
        win.geometry("+%d+%d" % golib_conf.glocation)


def configure(win):
    """
    Configure general GUI parameters based on the screen width

    """
    from golib.config import golib_conf as gc
    gc.screenh = win.winfo_screenheight()
    gc.screenw = win.winfo_screenwidth()
    goban_height = gc.screenh - 150  # leave some space for messages display at the bottom
    goban_width = gc.screenw - 150   # leave some space for buttons on the left
    size = golib_conf.gsize
    gc.rwidth = min(40, int(goban_height / size), int(goban_width / size))


def bring_to_front():
    """
    Mac OS special, to bring app to front at startup

    """
    if "Darwin" in platform.system():
        os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')


if __name__ == '__main__':
    root = tkinter.Tk()
    configure(root)
    app = golib.gui.UI(root)
    app.pack()

    args = get_argparser().parse_args()
    control = golib.gui.Controller(app, app, sgffile=args.sgf)

    place(root)
    bring_to_front()
    root.mainloop()
