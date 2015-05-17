import threading

from golib.model import Move, StateError
from golib.config.golib_conf import gsize, B, W, E


__author__ = 'Arnaud Peloquin'


class RuleUnsafe:
    """ Hold the current and historical states of a game. Accept/reject new moves.

    Ensure that each stone that is played (put) respects the rules of Go.
    Compute the captured stones.
    Hold the history of moves, as well as the history of killed stones, to allow rewind/forward.

    The current implementation of this class is based on "buffers" that are reset before each new change (either put
    or remove stone). The main line of play is updated only when confirm(). A kind of in-house transaction mechanism.

    This class is not thread safe. Plus, its consistency is highly dependent on the good usage of self.confirm()

    Attributes:
        listener:
            Is informed when stones have changed.
        stones: list(list)
            The stones that have been confirmed so far.
        deleted: list
            The history of the stones that have been killed so far. Used to put them back on rewind.
        history: list
            The sequence of moves that brought to the current state. Needed by in-sequence modification
            algorithm, to check conflicts with subsequent moves.
        stones_buff, deleted_buff, history_buff:
            Copies of above data structures, where incoming changes are first applied. Those changes may be persisted
            to the official structures using confirm().
    """

    def __init__(self, listener=None):
        self.listener = listener
        self.stones = [[E for _ in range(gsize)] for _ in range(gsize)]
        self.stones_buff = None

        self.deleted = []
        self.deleted_buff = None

        self.history = []
        self.history_buff = None

        self.reset()  # initialize buffers

    def copystones(self):
        return [list(self[row]) for row in range(gsize)]

    def confirm(self):
        """ Persist the state of the last modification (either put() or remove()).
        """
        if self.stones_buff is not None:
            self.stones = self.stones_buff
            self.deleted = self.deleted_buff
            self.history = self.history_buff
            if self.listener is not None:
                self.listener.stones_changed(self.stones)
        else:
            self.raisese("Confirmation Denied")

    def clear(self):
        self.__init__(listener=self.listener)

    def copy(self):
        copy = RuleUnsafe(listener=self.listener)
        copy.stones = self.copystones()
        copy.deleted = list(self.deleted)
        copy.history = list(self.history)
        copy.reset()
        return copy

    def reset(self):
        """ Rollback to the last confirmed state.
        """
        self.stones_buff = self.copystones()
        self.deleted_buff = list(self.deleted)
        self.history_buff = list(self.history)

    def put(self, move, reset=True):
        """ Try to put the provided move on the Goban, and raise exception if Go rules do not allow it.

        If the move number is before the last move saved, try to insert by rewinding, applying the new move,
        and replaying the history on top of it. This may also raise an exception.

        Note that the persistent state of this rule object will not be updated after the call, meaning that from its
        perspective the move has not happened. To persist, please confirm().

        Args:
            move: Move
                The move to put. Its number must already have been set, and its color must be in (B, W).
            reset: bool
                Whether to reset the buffers before applying this move.

        """
        assert 0 < move.number, "Cannot put a null or negative move number."
        if reset:
            self.reset()

        if move.number == len(self.history_buff):
            self._append(move)
            self.history_buff.append(move.copy())
        else:
            self._rewind_to(move)
            self.history_buff.insert(move.number-1, move.copy())
            for i in range(move.number, len(self.history_buff)):
                self.history_buff[i].number += 1
            self._forward_from(move)

    def remove(self, move, reset=True):
        """ Try to remove the provided move from the Goban. Raise an exception if there's nothing to remove.

        If the move number is before the last move saved, try to remove it by rewinding, removing the provided move,
        and replaying the history on top of it. This may also raise an exception.

        Note that the persistent state of this rule object will not be updated after the call, meaning that from its
        perspective the move has not happened. To persist, please confirm().

        Args:
            move: Move
                The move to remove. Its number must already have been set, and its color must be in (B, W).
        """
        assert 0 < move.number, "Cannot remove a null or negative move number."
        assert move.color is not E,  "A move is either B or W."
        if reset:
            self.reset()

        if move.number == len(self.history_buff):
            self._pop(move)
            self.history_buff.pop()
        else:
            self._rewind_to(move)
            self.history_buff.pop(move.number-1)
            for i in range(move.number-1, len(self.history_buff)):
                self.history_buff[i].number -= 1
            self._forward_from(move)

    def _forward_from(self, start_move):
        """ Apply moves from the history buffer, starting at the provided move and up to the last.
        """
        for i in range(start_move.number - 1, len(self.history_buff)):
            self._append(self.history_buff[i])

    def _rewind_to(self, move):
        """ Revert the Goban to the provided move number.
        """
        i = -1
        while move.number <= len(self.deleted_buff):
            self._pop(self.history_buff[i])
            i -= 1

    def _append(self, move):
        """ Check if the provided move can be played on the Goban, and update buffers accordingly.

        Raise exception if: Ko, Suicide play, Playing on an already occupied position.
        """
        if move.get_coord("sgf") != ('-', '-'):
            assert move.color in (B, W), "Cannot append empty move."
            if self.stones_buff[move.x][move.y] == E:
                enem_color = enemy_of(move.color)
                self.stones_buff[move.x][move.y] = move.color
                # check if kill (attack advantage)
                deleted = []
                self.deleted_buff.append(deleted)
                safe = False
                for row, col in touch(move.x, move.y):
                    neighcolor = self.stones_buff[row][col]
                    if neighcolor == enem_color:
                        group, nblibs = self._data(row, col)
                        if nblibs == 0:
                            for k, l in group:
                                deleted.append(Move("tk", (enem_color, k, l)))
                                self.stones_buff[k][l] = E
                            safe = True  # killed at least one enemy

                # check for ko rule
                if 3 < len(self.deleted_buff):
                    if len(self.deleted_buff[-1]) == 1:
                        prevdel = self.deleted_buff[-2]
                        if (len(prevdel) == 1) and (move == prevdel[0]):
                            self.raisese("Ko")

                # check for suicide play if not already safe
                if not safe:
                    _, nblibs = self._data(move.x, move.y)
                    if not nblibs:
                        self.raisese("Suicide")
            else:
                self.raisese("Occupied")
        else:
            # no check needed if move is "pass"
            self.deleted_buff.append([])

    def _pop(self, move):
        """ Check if the provided move can be removed from the Goban, and update buffers accordingly.

        Raise exception if the move to pop does not match what's been saved in this rules object.
        """
        if move.get_coord("sgf") != ('-', '-'):
            if self.stones_buff[move.x][move.y] == move.color:
                self.stones_buff[move.x][move.y] = E
                captured = self.deleted_buff.pop()
                for mv in captured:
                    self.stones_buff[mv.x][mv.y] = mv.color
            else:
                self.raisese("Empty" if self.stones_buff[move.x][move.y] == E else "Wrong Color.")
        else:
            self.deleted_buff.pop()

    def _data(self, x, y, _group=None, _libs=None):
        """ Compute the list of stones and the number of liberties of the group at (x, y).

        Args:
            x, y: int, int:
                The coordinates of one stone of the group.
            _group, _libs:
                Internal variables used in the recursion, no need to set them from outside.

        Return group, nb_libs: list, int
            The stones and the number of liberties of the group.
        """
        color = self.stones_buff[x][y]
        if _group is None:
            assert color != E
            _group = []
            _libs = []
        if (x, y) not in _group:
            _group.append((x, y))
            for x, y in touch(x, y):
                neighcolor = self.stones_buff[x][y]
                if neighcolor == E:
                    if (x, y) not in _libs:
                        _libs.append((x, y))
                elif neighcolor == color:
                    self._data(x, y, _group, _libs)
        return _group, len(_libs)

    def grids_repr(self):
        """ Display both confirmed and buffered grids side by side. Looks nicer with monospaced fonts.
        """
        string = "Confirmed".ljust(44)
        string += "Buffer\n"
        for x in range(gsize):
            for y in range(gsize):
                char = self[y][x]
                string += char if char != E else '~'
                string += ' '
            string += "  ||  "
            for y in range(gsize):
                char = self.stones_buff[y][x]
                string += char if char != E else '~'
                string += ' '
            string += "\n"
        return string

    def raisese(self, message):
        self.reset()
        raise StateError(message)

    def __getitem__(self, item):
        return self.stones.__getitem__(item)

    def __repr__(self):
        """ For debugging purposes, can be modified at will. """
        return self.grids_repr()


class Rule(RuleUnsafe):
    """ Place put(), remove() and confirm() under the same re-entrant lock,to force their sequential execution.
    """

    def __init__(self, listener=None):
        super().__init__(listener=listener)
        self.rlock = threading.RLock()

    def put(self, move, reset=True):
        with self.rlock:
            return super().put(move, reset)

    def remove(self, move, reset=True):
        with self.rlock:
            return super().remove(move, reset)

    def confirm(self):
        """ See RuleUnsafe.confirm().

        The caller should wrap the operations (e.g. put or remove) associated with this confirmation in a global lock.
        Otherwise another thread may perform an operation, that would reset this thread's operation(s) before it can
        grab the lock on confirm().
        """
        with self.rlock:
            return super().confirm()

    def copystones(self):
        if hasattr(self, "rlock"):
            with self.rlock:
                return super().copystones()
        else:
            return super().copystones()


def touch(x, y):
    """ Yield the (up to) 4 positions directly connected to (x, y).

    >>> [pos for pos in touch(0, 0)]
    [(1, 0), (0, 1)]
    >>> [pos for pos in touch(0, 5)]
    [(1, 5), (0, 6), (0, 4)]
    >>> [pos for pos in touch(5, 5)]
    [(4, 5), (6, 5), (5, 6), (5, 4)]
    >>> len([pos for pos in touch(gsize-1, gsize-1)])
    2
    >>> len([pos for pos in touch(gsize, gsize)])
    0

    """
    for (i, j) in ((-1, 0), (1, 0), (0, 1), (0, -1)):
        row = x + i
        if 0 <= row < gsize:
            col = y + j
            if 0 <= col < gsize:
                yield row, col


def enemy_of(color):
    if color == B:
        return W
    elif color == W:
        return B
    else:
        raise ValueError("No enemy for '{0}'".format(color))