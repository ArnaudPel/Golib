from threading import RLock
from go.move import Move
from golib_conf import gsize
from go.stateerror import StateError


__author__ = 'Kohistan'

"""
Hold the current state of a game, and ensure logical consistency of changes
made to that state.

"""


class RuleUnsafe(object):
    """
    Class responsible for holding the state of a game (stones currently on the goban, liberties count)
    This class is not thread safe.
    Its consistency is highly dependent on the good usage of self.confirm()

    """

    def __init__(self):
        self.stones = [['E' for _ in range(gsize)] for _ in range(gsize)]
        self.stones_buff = None

        self.deleted = []
        self.deleted_buff = None

        self.reset()  # initialize buffers

    def copystones(self):
        return [list(self.stones[row]) for row in range(gsize)]

    def confirm(self):
        """
        Persist the state of the last check, either put() or remove()

        """
        if self.stones_buff is not None:
            self.stones = self.stones_buff
            self.deleted = self.deleted_buff
        else:
            raise StateError("Confirmation Denied")

    def reset(self):
        """ Clear any unconfirmed data. """
        self.stones_buff = self.copystones()
        self.deleted_buff = list(self.deleted)

    def put(self, move, reset=True):
        """
        Check if the move passed as argument can be performed.

        Note that the state of this rule object will not be updated after this call,
        meaning that from its point of vue the move has not happened.
        To update the state, please confirm()

        move -- the move to check for execution.

        """
        if reset:
            self.reset()

        # check for ko rule
        if len(self.deleted_buff):
            lastdel = self.deleted_buff[-1]
            if (len(lastdel) == 1) and (move == iter(lastdel).next()):
                return False, "Ko"

        x_ = move.x
        y_ = move.y
        color = move.color
        enem_color = enemy(color)

        if self.stones_buff[x_][y_] == 'E':
            self.stones_buff[x_][y_] = color

            # check if kill (attack advantage)
            enemies = []
            deleted = set()
            safe = False
            assert 0 < move.number, "Cannot put a null or negative move number."
            self.deleted_buff.insert(move.number-1, deleted)
            for row, col in connected(x_, y_):
                neighcolor = self.stones_buff[row][col]
                if neighcolor == enem_color:
                    enemies.append((row, col))
            for x, y in enemies:
                group, nblibs = self._data(x, y)
                if nblibs == 0:
                    safe = True  # killed at least one enemy
                    for k, l in group:
                        deleted.add(Move("tk", (enem_color, k, l)))
                        self.stones_buff[k][l] = 'E'
                        try:
                            enemies.remove((k, l))
                        except ValueError:
                            pass

            # check for suicide play if not already safe
            retval = True, deleted
            if not safe:
                _, nblibs = self._data(x_, y_)
                if not nblibs:
                    retval = False, "Suicide"
        else:
            retval = False, "Occupied"

        return retval

    def remove(self, move, reset=True):
        """
        Check if the move passed as argument can be undone. There is no notion of sequence.

        Note that the state of this rule object will not be updated after this call,
        meaning that from its point of vue the move has not happened.
        To update the state, please confirm()

        move -- the move to check for undo.

        """
        if reset:
            self.reset()
        x_ = move.x
        y_ = move.y

        allowed = self.stones_buff[x_][y_] == move.color
        if allowed:
            self.stones_buff[x_][y_] = 'E'
            assert 0 < move.number, "Cannot remove a null or negative move number."
            data = self.deleted_buff.pop(move.number-1)
            for mv in data:
                self.stones_buff[mv.x][mv.y] = mv.color
        else:
            data = "Empty" if self.stones_buff[x_][y_] == 'E' else "Wrong Color."
        return allowed, data

    def _data(self, x, y, _group=None, _libs=None):
        """
        Returns the list of stones and the number of liberties of the group at (a, b).

        a, b -- the coordinates of any stone of the group.
        _group, _libs -- internal variables used in the recursion, no need to set them from outside.

        """
        color = self.stones_buff[x][y]
        if _group is None:
            assert color != 'E'
            _group = []
            _libs = []
        if (x, y) not in _group:
            _group.append((x, y))
            for x, y in connected(x, y):
                neighcolor = self.stones_buff[x][y]
                if neighcolor == 'E':
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
                char = self.stones[y][x]
                string += char if char != 'E' else '~'
                string += ' '
            string += "  ||  "
            for y in range(gsize):
                char = self.stones_buff[y][x]
                string += char if char != 'E' else '~'
                string += ' '
            string += "\n"
        return string

    def __getitem__(self, item):
        return self.stones.__getitem__(item)

    def __repr__(self):
        """
        For debugging purposes, can be modified at will.

        """
        return self.grids_repr()


class Rule(RuleUnsafe):
    """
    Place put(), remove() and confirm() under the same lock,to force their sequential execution.

    """

    def __init__(self):
        super(Rule, self).__init__()
        self.rlock = RLock()

    def put(self, move, reset=True):
        with self.rlock:
            return super(Rule, self).put(move, reset)

    def remove(self, move, reset=True):
        with self.rlock:
            return super(Rule, self).remove(move, reset)

    def confirm(self):
        """
        Top level needs must also acquire a lock to wrap operation (e.g. put or remove) and confirmation.
        Otherwise another thread can perform an operation, and reset the first operation.

        """
        with self.rlock:
            return super(Rule, self).confirm()


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
    if color == 'B':
        return 'W'
    elif color == 'W':
        return 'B'
    else:
        raise ValueError("No enemy for '{0}'".format(color))











