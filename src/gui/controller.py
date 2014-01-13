from sys import stdout
from ntpath import basename, dirname
from threading import RLock
from golib_conf import rwidth, gsize, appname

from go.rules import Rule
from go.sgf import Move
from go.kifu import Kifu


__author__ = 'Kohistan'


class ControllerBase(object):
    """
    Provide Go-related controls only (no GUI).

    """

    def __init__(self, sgffile=None):
        # temporary log implementation that will hopefully be changed for a more decent framework
        self.log = lambda msg: stdout.write(str(msg) + "\n")
        self.kifu = Kifu(sgffile=sgffile, log=self.log)
        self.rules = Rule()
        self.current_mn = 0
        self.api = {
            "append": lambda c, x, y: self._put(Move(c, x, y), method=self._append)
        }

    def _put(self, move, method=None):
        allowed, data = self.rules.put(move)
        if allowed:
            if method is not None:
                method(move)
            self.rules.confirm()
            self._stone_put(move, data)
        else:
            self.log(data)

    def _remove(self, move, method=None):
        allowed, data = self.rules.remove(move)
        if allowed:
            self.rules.confirm()
            self._stone_removed(move, data)
            if method is not None:
                method(move)
        else:
            self.log(data)

    def _append(self, move):
        """
        Append the move to self.kifu if the controller is pointing at the last move.
        Raise an exception otherwise, as branching (creating a variation inside the game) is not supported yet.

        """
        if self.at_last_move():
            self.kifu.append(move)
            self._incr_move_number()
        else:
            raise NotImplementedError("Variations are not allowed yet.")

    def _insert(self, move):
        self._incr_move_number()
        self.kifu.insert(move, self.current_mn)

    def _incr_move_number(self, _=None):
        self.current_mn += 1
        self.log_mn()

    def at_last_move(self):
        last_move = self.kifu.lastmove()
        return not last_move or (self.current_mn == last_move.number)

    def _stone_put(self, move, captured):
        """ Called after a stone has been put to Rule(). Use to update listeners (e.g. GUI). """
        pass

    def _stone_removed(self, move, freed):
        """ Called after a stone has been removed from Rule(). Use to update listeners (e.g. GUI). """
        pass

    def log_mn(self):
        self.log("Move {0} / {1}".format(self.current_mn, self.kifu.lastmove().number))

    def printself(self, _):
        print self.rules


class ControllerUnsafe(ControllerBase):
    """
    Class arbitrating the interactions between input and display.
    Input management is not thread-safe.

    """

    def __init__(self, user_input, display, sgffile=None):
        super(ControllerUnsafe, self).__init__(None)  # use our own kifu loading
        self.display = display
        self.input = user_input
        self.clickloc = None
        self.selected = None

        # temporary log implementation that will changed for a more decent pattern
        self.log = self.display.message

        self._bind()
        self.keydown = None

        self.loadkifu(sgffile)

    def _bind(self):

        """
        Bind the action listeners.
        """
        try:
            self.input.mousein.bind("<Button-1>", self._click)
            self.input.mousein.bind("<B1-Motion>", self._drag)
            self.input.mousein.bind("<ButtonRelease-1>", self._mouse_release)
            self.input.mousein.bind("<Button-2>", self._backward)
        except AttributeError as ae:
            self.log("Some mouse actions could not be bound to User Interface.")
            self.log(ae)

        try:
            self.input.keyin.bind("<Key>", self._keypress)
            self.input.keyin.bind("<KeyRelease>", self._keyrelease)
            self.input.keyin.bind("<Right>", self._forward)
            self.input.keyin.bind("<Up>", self._forward)
            self.input.keyin.bind("<Left>", self._backward)
            self.input.keyin.bind("<Down>", self._backward)
            self.input.keyin.bind("<p>", self.printself)
            self.input.keyin.bind("<g>", lambda _: self._goto(self.display.promptgoto()))
            self.input.keyin.bind("<Escape>", lambda _: self._select())
            self.input.keyin.bind("<Delete>", self._delete)
        except AttributeError as ae:
            self.log("Some keys could not be bound to User Interface.")
            self.log(ae)

        # dependency injection attempt
        try:
            self.input.commands["new"] = self._new
            self.input.commands["open"] = self._opensgf
            self.input.commands["save"] = self._save
            self.input.commands["delete"] = self._delete
            self.input.commands["back"] = self._backward
            self.input.commands["forward"] = self._forward
            self.input.commands["beginning"] = lambda: self._goto(0)
            self.input.commands["end"] = lambda: self._goto(722)  # big overkill for any sane game
            self.input.commands["close"] = self._onclose
        except AttributeError as ae:
            self.log("Some commands could not be bound to User Interface.")
            self.log(ae)

    def _keypress(self, event):
        self.keydown = event.char
        if self.keydown in ('b', 'w'):
            color = "black" if self.keydown == 'b' else "white"
            self.log("Ready to insert {0} stone as move {1}".format(color, self.current_mn))

    def _keyrelease(self, _):
        if self.keydown in ('b', 'w'):
            self.log_mn()
        self.keydown = None

    def _click(self, event):
        """
        Internal function to select a move on click. Move adding is performed on mouse release.

        """
        x, y = getxy(event)
        self.clickloc = (x, y)
        self._select(Move("Dummy", x, y))

    def _mouse_release(self, event):
        """
        Internal function to add a move to the kifu and display it. The move
        is expressed via a mouse click.
        """
        x, y = getxy(event)
        if (x, y) == self.clickloc:
            move = Move(self.kifu.next_color(), x, y)
            if self.keydown in ('b', 'w'):
                move.color = self.keydown.upper()
                self._put(move, method=self._insert)
                self._select(move)
            else:
                try:
                    self._put(move, method=self._append)
                    self._select(move)
                    self.log_mn()
                except NotImplementedError as nie:
                    print nie
                    self.log("Please hold 'b' or 'w' key and click to insert a move")

    def _forward(self, event=None, checked=None):
        """
        Internal function to display the next kifu stone on the goban.

        check -- allow for bound checking to have happened outside.
        """
        if checked is None:
            checked = not self.at_last_move()
        if checked:
            move = self.kifu.getmove_at(self.current_mn + 1)
            if move.getab() == ('-', '-'):
                self.log("{0} pass".format(move.color))
                self.current_mn += 1
            else:
                self._put(move, method=self._incr_move_number)

    def _backward(self, event=None):

        """
        Internal function to undo the last move made on the goban.
        """
        if 0 < self.current_mn:
            def _prev_highlight(_=None):
                self.current_mn -= 1
                if 0 < self.current_mn:
                    prev_move = self.kifu.getmove_at(self.current_mn)
                    if prev_move.getab() == ('-', '-'):
                        self.display.highlight(None)
                    else:
                        self.display.highlight(prev_move)
                else:
                    self.display.highlight(None)
                self.log_mn()

            move = self.kifu.getmove_at(self.current_mn)
            if move.getab() == ('-', '-'):
                _prev_highlight()
            else:
                self._remove(move, method=_prev_highlight)

    def _drag(self, event):
        x_ = event.x / rwidth
        y_ = event.y / rwidth
        if self.clickloc != (x_, y_):
            color = self.rules.stones[self.clickloc[0]][self.clickloc[1]]
            if color in ('B', 'W'):
                origin = Move(color, *self.clickloc)
                dest = Move(color, x_, y_)
                rem_allowed, freed = self.rules.remove(origin)
                if rem_allowed:
                    put_allowed, captured = self.rules.put(dest, reset=False)
                    if put_allowed:
                        self.rules.confirm()
                        self.kifu.relocate(origin, dest)
                        self.display.relocate(origin, dest)
                        self.display.display(freed)
                        self.display.erase(captured)
                        self.clickloc = x_, y_

    def _delete(self, _):
        if self.selected is not None:
            mv = (self.kifu.locate(*self.selected)).getmove()

            def delimpl(move):
                self.kifu.delete(move)
                self.current_mn -= 1
                lastmv = self.kifu.lastmove()
                if lastmv and move.number-1 == lastmv.number:
                    self._select(lastmv)
                else:
                    self._select()

            self._remove(mv, delimpl)

    def _stone_put(self, move, captured, highlight=True):
        self.display.display(move)
        if highlight:
            self.display.highlight(move)
        self.display.erase(captured)

    def _stone_removed(self, move, freed):
        self.display.erase(move)
        self.display.display(freed)  # put previously dead stones back

    def _opensgf(self):
        sfile = self.display.promptopen(filetypes=[("Smart Game Format", "sgf")])
        if len(sfile):
            self.loadkifu(sfile)
        else:
            self.log("Opening sgf cancelled")

    def _new(self):
        if not self.kifu.modified or self.display.promptdiscard(title="Open new game"):
            self.loadkifu()

    def loadkifu(self, sfile=None):
        self.kifu = Kifu(sgffile=sfile, log=self.log)
        if self.kifu.sgffile is None:
            sfile = "New game"
            if sfile is None:  # if sfile is not None here, there's been a file reading error
                self.log("New game")
        self.display.title("{0} - {1}".format(appname, basename(sfile)))
        self.display.clear()
        self.rules = Rule()
        self.current_mn = 0

    def _save(self):
        sf = self.kifu.sgffile
        if sf:
            sfile = self.display.promptsave(initdir=dirname(sf), initfile=basename(sf))
        else:
            sfile = self.display.promptsave()
        if len(sfile):
            self.kifu.sgffile = sfile
            self.kifu.save()
            self.display.title("{0} - {1}".format(appname, basename(sfile)))
        else:
            self.log("Saving cancelled")

    def _select(self, move=None):
        if move:
            self.selected = move.x, move.y
            self.display.select(move)
        else:
            self.selected = None
            self.display.select(None)

    def _goto(self, move_nr):
        """
        Update display and state to reach the specified move number.
        move_nr -- the move number to jump to.

        """
        if move_nr is not None:
            lastmove = self.kifu.lastmove()
            if lastmove is not None:
                bound = max(0, min(move_nr, lastmove.number))
                while self.current_mn < bound:
                    self._forward(checked=True)
                while bound < self.current_mn:
                    self._backward(None)

    def _onclose(self):
        if not self.kifu.modified or self.display.promptdiscard(title="Closing {0}".format(appname)):
            raise SystemExit(0)


class Controller(ControllerUnsafe):
    """
    Place put() and remove() under the same lock. Both need to executed "atomically",
    but it also seems sensible to force them to be executed sequentially, hence the same lock.

    """

    def __init__(self, user_input, display, sgffile=None):
        super(Controller, self).__init__(user_input, display, sgffile)
        self.rlock = RLock()

    def _put(self, move, method=None):
        """
        Lock the entire _put method so that another thread cannot cancel changes before they've been confirmed.

        """
        with self.rlock:
            super(Controller, self)._put(move, method)

    def _remove(self, move, method=None):
        with self.rlock:
            super(Controller, self)._remove(move, method)


def getxy(click):
    """
    Convert the click location into goban coordinates.
    Return -- the goban's row and column indexes.

    """
    x = click.x / rwidth
    y = click.y / rwidth
    return max(0, min(x, gsize - 1)), max(0, min(y, gsize - 1))