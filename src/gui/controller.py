from sys import stdout
from ntpath import basename, dirname
from threading import RLock
from go.move import Move
from go.stateerror import StateError
from golib_conf import rwidth, gsize, appname

from go.rules import Rule, RuleUnsafe
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

    def _append(self, move):
        """
        Append the move to self.kifu if the controller is pointing at the last move.
        Raise an exception otherwise, as branching (creating a variation inside the game) is not supported yet.

        """
        if self.at_last_move():
            self.kifu.append(move)
            self.rules.confirm()
            self._incr_move_number()
        else:
            raise NotImplementedError("Variations not allowed yet. Hold 'b' or 'w' key + click to insert a move")

    def _insert(self, move):
        if 0 < self.current_mn:
            self.kifu.insert(move, self.current_mn)
            self.rules.confirm()
            self._incr_move_number()
        else:
            self._append(move)

    def _incr_move_number(self, step=1):
        self.current_mn += step
        self.log_mn()

    def at_last_move(self):
        last_move = self.kifu.lastmove()
        return not last_move or (self.current_mn == last_move.number)

    def log_mn(self):
        mv = self.kifu.getmove_at(self.current_mn)
        if mv and (mv.get_coord("sgf") == ('-', '-')):
            self.log("{0} pass".format(mv.color))
        else:
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
        self.rules = Rule(listener=display)
        self.display = display
        self.input = user_input
        self.clickloc = None
        self.dragging = False
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
            color = "Black" if self.keydown == 'b' else "White"
            self.log("Insert {0} stone as move {1}".format(color, self.current_mn + 1))

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
        self._select(Move("tk", ("Dummy", x, y)))

    def _mouse_release(self, event):
        """
        Internal function to add a move to the kifu and display it. The move
        is expressed via a mouse click.
        """
        x, y = getxy(event)
        if not self.dragging:
            move = Move("tk", (self.kifu.next_color(), x, y), number=self.current_mn + 1)
            try:
                if self.keydown in ('b', 'w'):
                    move.color = self.keydown.upper()
                    # check for potential conflict:
                    # forwarding can be blocked if we occupy a position already used later in game
                    if self._checkinsert(move):
                        self.rules.put(move)
                        self._insert(move)
                        self.rules.confirm()
                else:
                    self.rules.put(move)
                    self._append(move)
            except (StateError, NotImplementedError) as err:
                self.log(err)
        else:
            self.dragging = False

    def _drag(self, event):
        x_ = event.x / rwidth
        y_ = event.y / rwidth
        x_loc = self.clickloc[0]
        y_loc = self.clickloc[1]
        if (x_loc, y_loc) != (x_, y_):
            self.dragging = True
            color = self.rules.stones[x_loc][y_loc]
            if color in ('B', 'W'):
                origin = self.kifu.locate(x_loc, y_loc).getmove()
                dest = Move("tk", (color, x_, y_), number=origin.number)
                if self._checkinsert(dest):
                    try:
                        self.rules.remove(origin)
                        self.rules.put(dest, reset=False)
                        self.rules.confirm()
                        self.kifu.relocate(origin, dest)
                        self.display.highlight(self.kifu.getmove_at(self.current_mn))
                        self.clickloc = x_, y_
                    except StateError as se:
                        self.log(se)

    def _forward(self, event=None):
        """
        Internal function to display the next kifu stone on the goban.

        check -- allow for bound checking to have happened outside.
        """
        if not self.at_last_move():
            move = self.kifu.getmove_at(self.current_mn + 1)
            self.rules.put(move)
            self.rules.confirm()
            self._incr_move_number()

    def _backward(self, event=None):

        """
        Internal function to undo the last move made on the goban.
        """
        if 0 < self.current_mn:
            try:
                move = self.kifu.getmove_at(self.current_mn)
                self.rules.remove(move)
                self.rules.confirm()
                self._incr_move_number(step=-1)
            except StateError as se:
                self.log(se)

    def _delete(self, _):
        if self.selected is not None:
            try:
                move = self.kifu.locate(*self.selected, upbound=self.current_mn).getmove()
                self.rules.remove(move)
                self.rules.confirm()
                self.kifu.delete(move)
                self._incr_move_number(step=-1)

                # point to next stone to delete, only if we are at the head
                lastmv = self.kifu.lastmove()
                if lastmv and move.number - 1 == lastmv.number:
                    self._select(lastmv)
                else:
                    self._select()

            except StateError as se:
                self.log(se)

    def _checkinsert(self, move):
        """
        Check that "move" can be inserted at self.current_mn.
        Forward check from the insertion move number, to ensure that no conflict will occur in the sequence:
        if a stone is inserted while another is recorded to be played later at the same location, it can
        create severe problems (as of current implementation, forward navigation cannot go past the conflict).

        """
        if self.kifu.contains_pos(move.x, move.y, start=self.current_mn):
            # checking move presence in self.kifu is not enough,
            # as the current stone may be captured before any conflict appears
            rule = RuleUnsafe()  # no need for thread safety here

            # initialize rule object up to insert position
            for nr in range(1, self.current_mn + 1):
                tempmv = self.kifu.getmove_at(nr)
                rule.put(tempmv, reset=False)
            rule.put(move, reset=False)

            # perform check
            for nr in range(self.current_mn + 1, self.kifu.lastmove().number + 1):
                tempmv = self.kifu.getmove_at(nr)
                try:
                    rule.put(tempmv, reset=False)
                except StateError as se:
                    self.log("Cannot insert move at %d: %s at move %d" % (self.current_mn, se, nr))
                    return False
        return True

    def _incr_move_number(self, step=1, _=None):
        super(ControllerUnsafe, self)._incr_move_number(step=step)
        self.display.highlight(self.kifu.getmove_at(self.current_mn))

    def _append(self, move):
        super(ControllerUnsafe, self)._append(move)
        self._select(move)

    def _opensgf(self):
        sfile = self.display.promptopen(filetypes=[("Smart Game Format", "sgf")])
        if len(sfile):
            self.loadkifu(sfile)
        else:
            self.log("Opening sgf cancelled")

    def _new(self):
        if not self.kifu.modified or self.display.promptdiscard(title="Open new game"):
            self.loadkifu()
            self.log("New game")

    def loadkifu(self, sfile=None):
        self.kifu = Kifu(sgffile=sfile, log=self.log)
        if self.kifu.sgffile is None:
            sfile = "New game"
            if sfile is None:  # if sfile is not None here, there's been a file reading error
                self.log("New game")
        self.display.title("{0} - {1}".format(appname, basename(sfile)))
        self.display.clear()
        self.rules.clear()
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
        # implementation note: this method was first based on the existing _forward() and _backward()
        # with the current implementation of Rule/Display though, the successive confirm() made it too slow
        if move_nr is not None:
            lastmove = self.kifu.lastmove()
            if lastmove is not None:
                bound = max(0, min(move_nr, lastmove.number))
                self.rules.reset()  # need to do it manually, because it is not done below
                while self.current_mn < bound:
                    move = self.kifu.getmove_at(self.current_mn + 1)
                    self.rules.put(move, reset=False)
                    self.current_mn += 1
                while bound < self.current_mn:
                    move = self.kifu.getmove_at(self.current_mn)
                    self.rules.remove(move, reset=False)
                    self.current_mn -= 1
                self.rules.confirm()
                self.display.highlight(self.kifu.getmove_at(self.current_mn))
                self.log_mn()

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

        # todo lock methods used by vision


def getxy(click):
    """
    Convert the click location into goban coordinates.
    Return -- the goban's row and column indexes.

    """
    x = click.x / rwidth
    y = click.y / rwidth
    return max(0, min(x, gsize - 1)), max(0, min(y, gsize - 1))