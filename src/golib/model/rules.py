from threading import RLock

from golib.model.exceptions import StateError
from golib.model.move import Move
from golib.config.golib_conf import gsize, B, W, E


__author__ = 'Arnaud Peloquin'

"""
Hold the state of a game, and ensure logical consistency of changes made to that state.

"""


class RuleUnsafe(object):
    """
    Class responsible for holding the state of a game (stones currently on the goban, liberties count)
    This class is not thread safe.
    Its consistency is highly dependent on the good usage of self.confirm()

    """

    def __init__(self, listener=None):
        self.listener = listener
        self.stones = [[E for _ in range(gsize)] for _ in range(gsize)]
        self.stones_buff = None

        self.deleted = []
        self.deleted_buff = None

        # the sequence of moves that brought to the current state.
        # needed by in-sequence modification algorithm, to replay subsequent moves.
        self.history = []
        self.history_buff = None

        self.reset()  # initialize buffers

    def copystones(self):
        return [list(self[row]) for row in range(gsize)]

    def confirm(self):
        """
        Persist the state of the last check, either put() or remove()

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

    def reset(self):
        """ Rollback to the last confirmed state. """
        self.stones_buff = self.copystones()
        self.deleted_buff = list(self.deleted)
        self.history_buff = list(self.history)

    def put(self, move, reset=True):
        """
        Check if the move passed as argument can be performed.

        Note that the state of this rule object will not be updated after this call,
        meaning that from its point of vue the move has not happened.
        To update the state, please confirm()

        move -- the move to check for execution.

        """
        assert 0 < move.number, "Cannot put a null or negative move number."
        if reset:
            self.reset()

        if move.number == len(self.history_buff):
            self._append(move)
            self.history_buff.insert(move.number-1, move.copy())
        else:
            self._rewind(move)
            self.history_buff.insert(move.number-1, move.copy())
            for i in range(move.number, len(self.history_buff)):
                self.history_buff[i].number += 1
            self._forward(move)

    def remove(self, move, reset=True):
        """
        Check if the move passed as argument can be undone. There is no notion of sequence.

        Note that the state of this rule object will not be updated after this call,
        meaning that from its point of vue the move has not happened.
        To update the state, please confirm()

        move -- the move to check for undo.

        """
        assert 0 < move.number, "Cannot remove a null or negative move number."
        assert move.color is not E,  "A move is either B or W."
        if reset:
            self.reset()

        if move.number == len(self.history_buff):
            self._pop(move)
            self.history_buff.pop()
        else:
            self._rewind(move)
            self.history_buff.pop(move.number-1)
            for i in range(move.number-1, len(self.history_buff)):
                self.history_buff[i].number -= 1
            self._forward(move)

    def _forward(self, move):
        for i in range(move.number - 1, len(self.history_buff)):
            self._append(self.history_buff[i])

    def _rewind(self, move):
        i = -1
        while move.number <= len(self.deleted_buff):
            self._pop(self.history_buff[i])
            i -= 1

    def _append(self, move):
        """
        Append the provided move. Can only be B or W. To mark a position empty, remove().
        Update stones_buff, store potential captured stones, and check for suicide play.

        """
        if move.get_coord("sgf") != ('-', '-'):
            assert move.color in (B, W)
            if self.stones_buff[move.x][move.y] == E:
                enem_color = enemy(move.color)
                self.stones_buff[move.x][move.y] = move.color
                # check if kill (attack advantage)
                deleted = []
                self.deleted_buff.append(deleted)
                safe = False
                for row, col in connected(move.x, move.y):
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
        """
        Pop the provided move. Update stones_buff, put back previously captured stones.

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
        """
        Returns the list of stones and the number of liberties of the group at (a, b).

        a, b -- the coordinates of any stone of the group.
        _group, _libs -- internal variables used in the recursion, no need to set them from outside.

        """
        color = self.stones_buff[x][y]
        if _group is None:
            assert color != E
            _group = []
            _libs = []
        if (x, y) not in _group:
            _group.append((x, y))
            for x, y in connected(x, y):
                neighcolor = self.stones_buff[x][y]
                if neighcolor == E:
                    if (x, y) not in _libs:
                        _libs.append((x, y))
                elif neighcolor == color:
                    self._data(x, y, _group, _libs)
        return _group, len(_libs)

    def grids_repr(self):
        """
        Display both confirmed and buffered grid side by side.
        Will look nicer with monospaced fonts.

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
        """ Reset buffers and raise a StateError. """
        self.reset()
        raise StateError(message)

    def __getitem__(self, item):
        return self.stones.__getitem__(item)

    def __repr__(self):
        """ For debugging purposes, can be modified at will. """
        return self.grids_repr()


class Rule(RuleUnsafe):
    """
    Place put(), remove() and confirm() under the same lock,to force their sequential execution.

    """

    def __init__(self, listener=None):
        super().__init__(listener=listener)
        self.rlock = RLock()

    def put(self, move, reset=True):
        with self.rlock:
            return super(Rule, self).put(move, reset)

    def remove(self, move, reset=True):
        with self.rlock:
            return super().remove(move, reset)

    def confirm(self):
        """
        See RuleUnsafe.confirm().

        The caller should wrap the operations (e.g. put or remove) associated with this confirmation in a global lock.
        Otherwise another thread may perform an operation, that would reset this thread's operation(s) before it can
        confirm().

        """
        with self.rlock:
            return super().confirm()

    def copystones(self):
        if hasattr(self, "rlock"):
            with self.rlock:
                return super().copystones()
        else:
            return super().copystones()

def connected(x, y):
    """
    Yields the (up to) 4 positions connected to (a, b).

    >>> [pos for pos in connected(0, 0)]
    [(1, 0), (0, 1)]
    >>> [pos for pos in connected(0, 5)]
    [(1, 5), (0, 6), (0, 4)]
    >>> [pos for pos in connected(5, 5)]
    [(4, 5), (6, 5), (5, 6), (5, 4)]
    >>> len([pos for pos in connected(gsize-1, gsize-1)])
    2
    >>> len([pos for pos in connected(gsize, gsize)])
    0

    """
    for (i, j) in ((-1, 0), (1, 0), (0, 1), (0, -1)):
        row = x + i
        if 0 <= row < gsize:
            col = y + j
            if 0 <= col < gsize:
                yield row, col


def enemy(color):
    if color == B:
        return W
    elif color == W:
        return B
    else:
        raise ValueError("No enemy for '{0}'".format(color))