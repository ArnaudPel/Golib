from sys import stdout, stderr
from ntpath import basename, dirname
from threading import RLock
from time import sleep

from golib.model.exceptions import StateError
from golib.model.move import Move
from golib.config import golib_conf  # needed to dynamically read rwidth value
from golib.config.golib_conf import gsize, appname, B, W, E
from golib.model.rules import Rule, RuleUnsafe, enemy
from golib.model.kifu import Kifu


__author__ = 'Arnaud Peloquin'


class ControllerBase(object):
    """
    Provide Go-related controls only (no GUI).

    """

    def __init__(self, sgffile=None):
        # temporary log implementation that will hopefully be changed for a more decent framework
        self.log = lambda msg: stdout.write(str(msg) + "\n")
        self.err = lambda msg: stderr.write(str(msg) + "\n")
        self.kifu = Kifu(sgffile=sgffile, log=self.log, err=self.err)
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

    def _bulk_update(self, moves):
        """
        Bulk update of the goban with multiple moves, allowing for better performance (up to 2 global updates only of
        structures for the whole bulk). The update can consist of deletions and/or appends.

        moves -- the list of moves to apply. those may be of color 'E', then meaning the removal of the
        stone already present (an exception will most likely be raised if no stone is present when trying to delete).

        """
        order = {E: 0, B: 1, W: 1}  # keep B/W order, but removals must be performed and confirmed before appending
        moves = sorted(moves, key=lambda m: order[m.color])
        if self.at_last_move():
            rule_save = self.rules.copy()  # to rollback if something goes wrong
            kifu_save = self.kifu.copy()   # to rollback if something goes wrong
            number_save = self.current_mn
            self.rules.reset()
            try:
                i = 0
                mv = moves[i]
                while mv.color is E:
                    torem = self.kifu.locate(mv.x, mv.y).getmove()
                    self.rules.remove(torem, reset=False)
                    self.kifu.delete(torem)
                    self.current_mn -= 1
                    i += 1
                    if i < len(moves):
                        mv = moves[i]
                    else:
                        break
                if i:
                    self.rules.confirm()  # save deletion changes
                while i < len(moves):
                    assert mv.color in (B, W)
                    mv.number = self.current_mn + 1
                    self.rules.put(mv, reset=False)
                    self.kifu.append(mv)
                    self.current_mn += 1
                    i += 1
                    if i < len(moves):
                        mv = moves[i]
                    else:
                        break
                self.rules.confirm()  # save addition changes
                self.log_mn()
            except StateError as se:
                self.rules = rule_save
                self.kifu = kifu_save
                self.current_mn = number_save
                print("Bulk update failed: {}".format(se))
        else:
            raise NotImplementedError("Variations not allowed yet. Please navigate to end of game.")

    def _delete(self, x, y):
        """
        Delete the selected move from the game. It will no longer appear in the sequence and will be erased from
        sgf file if saved.

        """
        move = self.kifu.locate(x, y, upbound=self.current_mn).getmove()
        self.rules.remove(move)
        self.rules.confirm()
        self.kifu.delete(move)
        self._incr_move_number(step=-1)
        return move  # to be used by extending code

    def locate(self, x, y):
        """
        Look for a Move object having (x, y) location in the kifu.

        x, y -- interpreted in the opencv (=tk) coordinates frame.

        """
        node = self.kifu.locate(x, y)
        if node is not None:
            return node.getmove()

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
            kifu_lastmove = self.kifu.lastmove()
            total_moves = 0
            if kifu_lastmove is not None:
                total_moves = kifu_lastmove.number
            self.log("Move {0} / {1}".format(self.current_mn, total_moves))

    def is_empty_blocking(self, x, y, seconds=0.1):
        """
        Return True if the position is empty, false otherwise.

        @warning This method makes the thread sleep as long as current move is not the last move. This limitation
        is based on the fact that variations are not allowed, and the rules object is modified by browsing moves.
        The caveat is that calling this method from the GUI thread while not being at the last move would most likely
        freeze the GUI.

        x, y -- interpreted in the tk coordinates frame (=opencv coordinates frame).
        seconds -- the duration of one sleep iteration.

        """
        while not self.at_last_move():
            sleep(seconds)
        return self.rules[x][y] is E

    def printself(self, _):
        print(self.rules)


class ControllerUnsafe(ControllerBase):
    """
    Class arbitrating the interactions between input and display.
    Input management is not thread-safe.

    """

    def __init__(self, user_input, display, sgffile=None):
        super().__init__(None)  # use our own kifu loading
        self.rules = Rule(listener=display)
        self.display = display
        self.input = user_input
        self.clickloc = None
        self.dragging = False
        self.selected = None

        # temporary log implementation that should be changed for a more decent pattern
        self.log = self.display.message
        self.err = self.display.error

        self._bind()
        self.keydown = None

        self.loadkifu(sgffile)

    def _bind(self):

        """
        Bind the action listeners.
        """
        try:
            self.input.mousein.bind("<Button-1>", self._lclick)
            self.input.mousein.bind("<B1-Motion>", self._drag)
            self.input.mousein.bind("<ButtonRelease-1>", self._mouse_release)
            self.input.mousein.bind("<Button-2>", self._rclick)
        except AttributeError as ae:
            self.err("Some mouse actions could not be found.")
            self.err(ae)

        try:
            self.input.keyin.bind("<Right>", self._forward)
            self.input.keyin.bind("<Up>", self._forward)
            self.input.keyin.bind("<Left>", self._backward)
            self.input.keyin.bind("<Down>", self._backward)
            self.input.keyin.bind("<p>", self.printself)
            self.input.keyin.bind("<g>", lambda _: self._goto(self.display.promptgoto()))
            self.input.keyin.bind("<Escape>", lambda _: self._select())
            self.input.keyin.bind("<Delete>", self._del_selected)
            self.input.keyin.bind("<BackSpace>", self._del_selected)
        except AttributeError as ae:
            self.err("Some keys could not be found.")
            self.err(ae)

        # dependency injection attempt
        try:
            self.input.commands["new"] = self._newsgf
            self.input.commands["open"] = self._opensgf
            self.input.commands["save"] = self._save
            self.input.commands["delselect"] = self._del_selected
            self.input.commands["back"] = self._backward
            self.input.commands["forward"] = self._forward
            self.input.commands["beginning"] = lambda: self._goto(0)
            self.input.commands["end"] = lambda: self._goto(722)  # big overkill for any sane game
            self.input.commands["close"] = self._onclose
            self.input.commands["insert"] = self._insert
            self.input.commands["color"] = self.swap_color
        except AttributeError as ae:
            self.err("Some commands could not be found.")
            self.err(ae)

    def _lclick(self, event):
        """
        Internal function to select a move on click. Move adding is performed on mouse release.

        """
        x, y = get_intersection(event)
        self.clickloc = (x, y)
        self._select(Move("tk", ("Dummy", x, y)))

    def _rclick(self, event):
        x, y = get_intersection(event)
        self.input.context_menu(event, self.rules[x][y] is not E)

    def _mouse_release(self, event):
        """
        Append a move if the mouse has been released at the same location it has been pressed.
        Do nothing otherwise (the relocation is handled in _drag()).

        """
        x, y = get_intersection(event)
        if not self.dragging:
            move = Move("tk", (self.kifu.next_color(), x, y), number=self.current_mn + 1)
            try:
                self.rules.put(move)
                self._append(move)
                return move  # to be used by extending code
            except (StateError, NotImplementedError) as err:
                self.err(err)
        else:
            self.dragging = False

    def _drag(self, event):
        """
        Handle a stone dragged by the user, and update self.kifu accordingly.

        """
        x_, y_ = get_intersection(event)
        x_loc = int(self.clickloc[0])
        y_loc = int(self.clickloc[1])
        if (x_loc, y_loc) != (x_, y_):
            self.dragging = True
            color = self.rules.stones[x_loc][y_loc]
            if color in (B, W):
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
                        return origin, dest  # to be used by extending code
                    except StateError as se:
                        print(se)
                        self.err(se)

    def _insert(self, event, color):
        """
        Insert a new move in the line of play, right after the move number currently being displayed on the goban.
        This insert may fail if it breaks the consistency of later moves (see Controller._checkinsert()).

        """
        x, y = get_intersection(event)
        move = Move('tk', (color, x, y), number=self.current_mn + 1)
        # check for potential conflict: browsing could be blocked if we occupy a position already used later in game
        if self._checkinsert(move):
            self.rules.put(move)
            self.kifu.insert(move, self.current_mn + 1)
            self.rules.confirm()
            self._incr_move_number()
            self.rules.confirm()

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
        Point the rule structure to the previous move. The current move will still be in the game, and can be accessed
        again by _forward().
        """
        if 0 < self.current_mn:
            try:
                move = self.kifu.getmove_at(self.current_mn)
                self.rules.remove(move)
                self.rules.confirm()
                self._incr_move_number(step=-1)
            except StateError as se:
                self.err(se)

    def _del_selected(self, _):
        try:
            if self.selected is not None:
                move = self._delete(*self.selected)
                # point to next stone to delete, only if we are at the head
                lastmv = self.kifu.lastmove()
                if lastmv and move.number - 1 == lastmv.number:
                    self._select(lastmv)
                else:
                    self._select()
        except StateError as se:
            self.err(se)

    def _checkinsert(self, move):
        """
        Check that "move" can be inserted at self.current_mn.
        Forward check from the insertion move number, to ensure that no conflict will occur in the sequence:
        if a stone is inserted while another is recorded to be played later at the same location, it can
        create severe problems (as of current implementation, forward navigation cannot go past the conflict).

        """
        # checking move presence in self.kifu is not enough,
        # as the current stone may be captured before any conflict appears
        rule = RuleUnsafe()  # no need for thread safety here

        nr = 0
        # initialize rule object up to insert position (excluded)
        for nr in range(1, self.current_mn + 1):
            rule.put(self.kifu.getmove_at(nr), reset=False)

        # perform check
        try:
            rule.put(move, reset=False)  # new move insertion
            for nr in range(self.current_mn + 1, self.kifu.lastmove().number + 1):
                rule.put(self.kifu.getmove_at(nr), reset=False)
        except StateError as se:
            self.err("Cannot insert %s at %d: %s at move %d" % (move.color, self.current_mn, se, nr))
            return False
        return True

    def _incr_move_number(self, step=1, _=None):
        super()._incr_move_number(step=step)
        self.display.highlight(self.kifu.getmove_at(self.current_mn))

    def _append(self, move):
        super()._append(move)
        self._select(move)

    def _opensgf(self):
        if not self.kifu.modified or self.display.promptdiscard(title="Discard current sgf"):
            dialog_title = "Open sgf (Cancel to open a blank SGF)"
            sfile = self.display.promptopen(title=dialog_title, filetypes=[("Smart Game Format", "sgf")])
            if len(sfile):
                self.loadkifu(sfile)
                return True
            else:
                self.log("Opening sgf cancelled")
                return False

    def _newsgf(self):
        """
        Discard the current kifu and open a new one (with the agreement of the user).

        """
        if not self.kifu.modified or self.display.promptdiscard(title="Open new game"):
            self.loadkifu()
            self.log("New game")

    def loadkifu(self, sfile=None):
        self.kifu = Kifu(sgffile=sfile, log=self.log, err=self.err)
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
        """
        Call with an argument to display the move as selected.
        Call without argument to reset selection.

        """
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
        # this second implementation is more efficient though, as it can refresh display only at the end.
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

    def swap_color(self, event=None):
        """
        Get the stone corresponding to the click 'event' if any, and swap its color if possible.

        """
        x, y = get_intersection(event)
        node = self.kifu.locate(x, y, upbound=self.current_mn)
        if node is not None:
            move = node.getmove()
            move.color = enemy(move.color)
            # now check that the insertion of that stone with the opposite color is not going to break anything
            if self._check_update(move, message="Cannot swap color"):
                self.rules.remove(node.getmove())
                self.rules.put(move, reset=False)
                self.rules.confirm()
                self.kifu.update_mv(move, node)

    def _check_update(self, move: Move, message: str="Cannot update move"):
        """
        Check the consistency of the whole game, after having taken into account the provided move update.

        For example changing the color of a stone in the middle of the line play may cancel the killing of a group.
        If stones had then been played in the "hole" created by that kill, tampering with it breaks the whole game
        (basically, browsing can't go past the first conflicting location).

        Return True if no problem is anticipated, False if the update should be refused. Note: no real action is taken.

        """
        rule = RuleUnsafe()
        moves = self.kifu.get_move_seq()
        try:
            previous = moves[move.number - 1]  # move indexing is 1-based
            assert previous.number == move.number
            # assert (previous.x, previous.y) == (move.x, move.y)
            moves[move.number - 1] = move
        except AssertionError:
            print("Unexpected kifu moves list in Controller.check_color_swap()")
            return False
        i = 0
        try:
            for i, mv in enumerate(moves):
                rule.put(mv, reset=False)
        except StateError as se:
            self.err("{} {}: leads to {} at move {}".format(message, move.number, se, i))
            return False
        return True


class Controller(ControllerUnsafe):
    """
    Place put() and remove() under the same lock. Both need to executed "atomically",
    but it also seems sensible to force them to be executed sequentially, hence the same lock.

    """

    def __init__(self, user_input, display, sgffile=None):
        super().__init__(user_input, display, sgffile)
        self.rlock = RLock()

    def _append(self, move):
        with self.rlock:
            super()._append(move)

    def _bulk_update(self, moves):
        with self.rlock:
            return super()._bulk_update(moves)

    def _delete(self, x, y):
        with self.rlock:
            return super()._delete(x, y)

    def locate(self, x, y):
        with self.rlock:
            return super().locate(x, y)

    def is_empty_blocking(self, x, y, seconds=0.1):
        with self.rlock:
            return super().is_empty_blocking(x, y, seconds)


def get_intersection(click_event) -> (int, int):
    """
    Return the closest goban intersection from the click location.
    Return -- the goban's row and column indexes.

    """
    x = int(click_event.x / golib_conf.rwidth)
    y = int(click_event.y / golib_conf.rwidth)
    return max(0, min(x, gsize - 1)), max(0, min(y, gsize - 1))