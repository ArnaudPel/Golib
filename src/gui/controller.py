from threading import RLock
from golib_conf import rwidth, gsize

from go.rules import Rule
from go.sgf import Move
from go.kifu import Kifu


__author__ = 'Kohistan'


class ControllerBase(object):
    """
    Provide Go-related controls only (no GUI).

    """

    def __init__(self, kifu):
        self.kifu = kifu
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
            print data

    def _remove(self, move, method=None):
        allowed, data = self.rules.remove(move)
        if allowed:
            if method is not None:
                method(move)
            self.rules.confirm()
            self._stone_removed(move, data)
        else:
            print data

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
            raise NotImplementedError("Cannot create variations for a game yet. Sorry.")

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

    def __init__(self, kifu, user_input, display):
        super(ControllerUnsafe, self).__init__(kifu)
        self.display = display
        self.input = user_input
        self.clickloc = None
        self.selected = None

        self._bind()

    def _bind(self):

        """
        Bind the action listeners.
        """
        self.input.mousein.bind("<Button-1>", self._click)
        self.input.mousein.bind("<B1-Motion>", self._drag)
        self.input.mousein.bind("<ButtonRelease-1>", self._mouse_release)
        self.input.mousein.bind("<Button-2>", self._backward)

        self.input.keyin.bind("<Right>", self._forward)
        self.input.keyin.bind("<Up>", self._forward)
        self.input.keyin.bind("<Left>", self._backward)
        self.input.keyin.bind("<Down>", self._backward)
        self.input.keyin.bind("<p>", self.printself)
        self.input.keyin.bind("<Escape>", lambda _: self.display.select(None))
        self.input.keyin.bind("<Delete>", self._delete)

        # dependency injection attempt
        try:
            self.input.commands["open"] = self._open
            self.input.commands["save"] = self._save
            self.input.commands["delete"] = self._delete
        except AttributeError:
            print "Some commands could not be bound to User Interface."

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
            self._put(move, method=self._append)

    def _forward(self, event):
        """
        Internal function to display the next kifu stone on the goban.
        """
        lastmove = self.kifu.game.lastmove()
        if lastmove and (self.current_mn < lastmove.number):
            move = self.kifu.game.getmove(self.current_mn + 1).getmove()
            self._put(move, method=self._incr_move_number)

    def _backward(self, event):

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

    def _delete(self, event=None):
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
            self.display.clear()
            super(ControllerUnsafe, self).__init__(Kifu.parse(sfile))
        else:
            print "Opening cancelled."

    def _save(self):
        if self.kifu.sgffile is not None:
            self.kifu.save()
        else:
            sfile = self.display.promptsave()
            if len(sfile):
                self.kifu.sgffile = sfile
                self.kifu.save()
            else:
                print "Saving cancelled."

    def _incr_move_number(self, _):
        self.current_mn += 1

    def printself(self, event):
        print self.rules


class Controller(ControllerUnsafe):
    """
    Place put() and remove() under the same lock. Both need to executed "atomically",
    but it also seems sensible to force them to be executed sequentially, hence the same lock.

    """

    def __init__(self, kifu, user_input, display):
        super(Controller, self).__init__(kifu, user_input, display)
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
    return max(0, min(x, gsize-1)), max(0, min(y, gsize-1))