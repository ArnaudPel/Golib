from sys import stdout
from ntpath import basename
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

    def __init__(self, kifufile=None):
        # temporary log implementation that will changed for a more decent pattern
        self.log = lambda msg: stdout.write(str(msg) + "\n")
        self.kifu = Kifu.parse(kifufile, log=self.log)
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
        last_move = self.kifu.game.lastmove()
        if not last_move or (self.current_mn == last_move.number):
            self.kifu.append(move)
            self.current_mn += 1
        else:
            raise NotImplementedError("Variations are not allowed yet.")

    def _insert(self, move):
        self.current_mn += 1
        self.kifu.insert(move, self.current_mn)

    def _incr_move_number(self, _):
        self.current_mn += 1
        self.log("Move {0}".format(self.current_mn))

    def printself(self, _):
        print self.rules

    def _stone_put(self, move, captured):
        """ Called after a stone has been put to Rule(). Use to update listeners (e.g. GUI). """
        pass

    def _stone_removed(self, move, freed):
        """ Called after a stone has been removed from Rule(). Use to update listeners (e.g. GUI). """
        pass


class ControllerUnsafe(ControllerBase):
    """
    Class arbitrating the interactions between input and display.
    Input management is not thread-safe.

    """

    def __init__(self, user_input, display, kifufile=None):
        super(ControllerUnsafe, self).__init__(None)  # use our own kifu loading
        self.display = display
        self.input = user_input
        self.clickloc = None
        self.selected = None

        # temporary log implementation that will changed for a more decent pattern
        self.log = self.display.message

        self._bind()
        self.keydown = None

        self.loadkifu(kifufile)

    def _bind(self):

        """
        Bind the action listeners.
        """
        self.input.mousein.bind("<Button-1>", self._click)
        self.input.mousein.bind("<B1-Motion>", self._drag)
        self.input.mousein.bind("<ButtonRelease-1>", self._mouse_release)
        self.input.mousein.bind("<Button-2>", self._backward)

        self.input.keyin.bind("<Key>", self._keypress)
        self.input.keyin.bind("<KeyRelease>", self._keyrelease)
        self.input.keyin.bind("<Right>", self._forward)
        self.input.keyin.bind("<Up>", self._forward)
        self.input.keyin.bind("<Left>", self._backward)
        self.input.keyin.bind("<Down>", self._backward)
        self.input.keyin.bind("<p>", self.printself)
        self.input.keyin.bind("<g>", self.prompt_goto)
        self.input.keyin.bind("<Escape>", lambda _: self.display.select(None))
        self.input.keyin.bind("<Delete>", self._delete)

        # dependency injection attempt
        try:
            self.input.commands["open"] = self._open
            self.input.commands["save"] = self._save
            self.input.commands["delete"] = self._delete
            self.input.commands["back"] = self._backward
            self.input.commands["forward"] = self._forward
            self.input.commands["beginning"] = lambda: self._goto(0)
            self.input.commands["end"] = lambda: self._goto(500)
        except AttributeError:
            print "Some commands could not be bound to User Interface."

    def _keypress(self, event):
        self.keydown = event.char
        if self.keydown in ('b', 'w'):
            color = "black" if self.keydown == 'b' else "white"
            self.log("Ready to insert {0} stone as move {1}".format(color, self.current_mn))

    def _keyrelease(self, _):
        if self.keydown in ('b', 'w'):
            self.log("Move {0}".format(self.current_mn))
        self.keydown = None

    def _click(self, event):

        """
        Internal function to add a move to the kifu and display it. The move
        is expressed via a mouse click.
        """
        x, y = getxy(event)
        self.clickloc = (x, y)
        self.selected = (x, y)
        self.display.select(Move("Dummy", x, y))

    def _mouse_release(self, event):
        x, y = getxy(event)
        if (x, y) == self.clickloc:
            move = Move(self.kifu.next_color(), x, y)
            if self.keydown in ('b', 'w'):
                move.color = self.keydown.upper()
                self._put(move, method=self._insert)
            else:
                try:
                    self._put(move, method=self._append)
                except NotImplementedError as nie:
                    print nie
                    self.log("Please hold 'b' or 'w' and click to insert a move")

    def _forward(self, event=None, checked=None):
        """
        Internal function to display the next kifu stone on the goban.

        check -- allow for bound checking to have happened outside.
        """
        if checked is None:
            lastmove = self.kifu.game.lastmove()
            checked = lastmove and (self.current_mn < lastmove.number)
        if checked:
            move = self.kifu.game.getmove(self.current_mn + 1).getmove()
            self._put(move, method=self._incr_move_number)

    def _backward(self, event=None):

        """
        Internal function to undo the last move made on the goban.
        """
        if 0 < self.current_mn:
            move = self.kifu.game.getmove(self.current_mn).getmove()

            def _prev_highlight(_):
                self.current_mn -= 1
                if 0 < self.current_mn:
                    prev_move = self.kifu.game.getmove(self.current_mn).getmove()
                    self.display.highlight(prev_move)
                else:
                    self.display.highlight(None)
                self.log("Move {0}".format(self.current_mn))

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
        mv = self.kifu.getmove_at(*self.selected).getmove()

        def delimpl(move):
            self.kifu.delete(move)
            self.current_mn -= 1
            self.selected = None

        self._remove(mv, delimpl)

    def _stone_put(self, move, captured, highlight=True):
        self.display.display(move)
        if highlight:
            self.display.highlight(move)
        self.display.erase(captured)

    def _stone_removed(self, move, freed):
        self.display.erase(move)
        self.display.display(freed)  # put previously dead stones back

    def _open(self):
        sfile = self.display.promptopen()
        if len(sfile):
            self.loadkifu(sfile)
            self.display.clear()
            self.rules = Rule()
            self.current_mn = 0
        else:
            self.log("Opening cancelled")

    def loadkifu(self, sfile):
        self.kifu = Kifu.parse(sfile, log=self.log)
        if sfile is None:
            sfile = "New game"
        self.display.title("{0} - {1}".format(appname, basename(sfile)))

    def _save(self):
        if self.kifu.sgffile is not None:
            self.kifu.save()
        else:
            sfile = self.display.promptsave()
            if len(sfile):
                self.kifu.sgffile = sfile
                self.kifu.save()
                self.display.title("{0} - {1}".format(appname, basename(sfile)))
            else:
                self.log("Saving cancelled")

    def _goto(self, move_nr):
        """
        Update display and state to reach the specified move number.

        """
        lastmove = self.kifu.game.lastmove()
        if lastmove is not None:
            bound = max(0, min(move_nr, lastmove.number))
            while self.current_mn < bound:
                self._forward(checked=True)
            while bound < self.current_mn:
                self._backward(None)

    def prompt_goto(self, _):
        number = int(self.display.promptgoto())
        self._goto(number)


class Controller(ControllerUnsafe):
    """
    Place put() and remove() under the same lock. Both need to executed "atomically",
    but it also seems sensible to force them to be executed sequentially, hence the same lock.

    """

    def __init__(self, user_input, display, kifufile=None):
        super(Controller, self).__init__(user_input, display, kifufile)
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