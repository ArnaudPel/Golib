import sys

from golib.config.golib_conf import appname, gsize, B, W
from golib.model import CollectionGl, GameTreeGl, NodeGl, Parser, SgfWarning, SGF_TYPE


class Kifu:
    """ Provide common interactions with the SGF structure.

    Only one line of play is supported: no variations are allowed.
    This means that an entire game is one single list of nodes.

    Attributes:
        game: GameTree
            The object backing the recording of this kifu.
        sgffile: str
            The file where to load/save the game.
        modified: bool
            Indicates whether this game has been modified since load/save.
    """

    def __init__(self, sgffile=None, log=None, err=None):
        self.game = None
        self.sgffile = None
        self._parse(sgffile, log=log, err=err)
        self.modified = False

    def copy(self):
        copy = Kifu(log=lambda _: None)
        copy.game.nodes.clear()
        copy.sgffile = self.sgffile
        copy.modified = self.modified
        previous = None
        for node in self:
            ng = NodeGl(copy.game, previous)
            ng.properties = {}
            for k, v in node.properties.items():
                if type(v) is list:
                    ng.properties[k] = list(v)
                else:
                    ng.properties[k] = v
            assert type(node.first) is int
            ng.first = node.first
            # no variations allowed yet, but that may have to be copied someday
            # ng.previous_variation = node.previous_variation
            # ng.variations = list(node.variations)
            copy.game.nodes.append(ng)
            if previous is not None:
                previous.next = ng
            previous = ng
        return copy

    def append(self, move):
        """ Append the move at the end of the game.
        """
        node = self._prepare(move)
        self.game.nodes.append(node)
        self.modified = True

    def insert(self, move, position: int):
        """ Insert the move at the provided position. Increment subsequent moves number by one.
        If position points to the end of the game, append instead.
        """
        new_node = self._prepare(move)
        new_node.number(position)

        idx = None
        # update subsequent moves number
        for i in range(len(self)):
            nod = self.game.nodes[i]
            try:
                nb = nod.properties["MN"][0]
                if position <= nb:
                    nod.properties["MN"][0] += 1
                if nb == position:
                    idx = i
            except KeyError:
                pass  # not a move

        if idx is not None:
            self.game.nodes.insert(idx, new_node)
        elif i == position - 1:
            self.game.nodes.append(new_node)
        self.modified = True

    def relocate(self, origin, dest):
        """ Locate the move matching "origin" and change its coordinates to those of "dest".
        The move number is not changed.
        """
        node = self.locate(origin.x, origin.y)
        a, b = dest.get_coord(SGF_TYPE)
        node.properties[origin.color] = [a + b]
        self.modified = True

    def delete(self, move):
        """ Delete the provided move if found, and decrement subsequent move numbers by one.
        """
        decr = False
        torem = None
        for node in self:
            if decr:
                node.properties["MN"][0] -= 1
            else:
                try:
                    if node.getmove().number == move.number:
                        decr = True
                        torem = node
                        # keep looping to decrement subsequent moves
                except AttributeError:
                    pass  # not a move
        if torem is not None:
            self.game.nodes.remove(torem)
            self.modified = True

    def update_mv(self, move, node=None):
        """ Update the node with the provided move. If the node is not provided, look for it in the game.
        """
        if node is None:
            node = self.locate(move.x, move.y)
        for color in (B, W):
            # delete previous move position
            try:
                del node.properties[color]
            except KeyError:
                pass
        self._prepare(move, node=node)
        self.modified = True

    def get_move_seq(self, first=1, last=1000):
        """ Return the sub-sequence of moves. Non-move nodes (like startup node) are skipped.

        Args:
            first: int
                Node sequence start index, inclusive. NOT interpreted as a move number.
            last: int
                Node sequence end index, inclusive. NOT interpreted as a move number.
        """
        seq = []
        for i in range(first, len(self)):
            mv = self[i].getmove()
            if mv and (first <= mv.number <= last):
                seq.append(mv)
                if mv.number == last:
                    break
        return seq

    def getmove_at(self, number: int):
        """ Return the move corresponding to number.
        """
        for i in range(number, len(self)):
            mv = self[i].getmove()
            if mv is not None and mv.number == number:
                return mv

    def locate(self, x: int, y: int, upbound=None):
        """ Return the node describing the provided intersection.

        Search from most recent to least recent, in order to get the stone currently on that location.
        """
        start = upbound if upbound else len(self) - 1
        for i in range(start, -1, -1):
            mv = self[i].getmove()
            if mv and mv.x == x and mv.y == y:
                return self[i]

    def contains_pos(self, x: int, y: int, start: int=0):
        """ Return the index of the first node containing a move at the provided coordinates.

        Args:
            start: int
                The index where to start search (inclusive).
        """
        for i in range(start, len(self)):
            mv = self[i].getmove()
            if (mv is not None) and (mv.x == x) and (mv.y == y):
                return i
        return False

    def lastmove(self):
        """ Return the last move on the main line of play.
        """
        for i in range(-1, -len(self), -1):
            mv = self[i].getmove()
            if mv is not None:
                return mv

    def next_color(self):
        """ Return the color of the next move to append, based on a black-white alternation assumption.
        """
        current = self.lastmove()
        if current is not None:
            return B if current.color == W else W
        else:
            return B  # probably the beginning of the game

    def save(self):
        """ Save the whole game to file.
        """
        if self.sgffile is not None:
            with open(self.sgffile, 'w') as f:
                self.game.output(f)
                self.modified = False
                print("Game saved to: " + self.sgffile)
        else:
            raise SgfWarning("No file defined, can't save.")

    def _prepare(self, move, node=None):
        """ Create or update a node according to the provided move.
        """
        if node is None:
            node = NodeGl(self.game, self[-1])
        r, c = move.get_coord(SGF_TYPE)
        node.properties[move.color] = [r + c]  # sgf properties are in a list
        node.number(nb=move.number)
        return node

    def __iter__(self):
        """ Iterate over the nodes of the main line of play.
        """
        return self.game.nodes.__iter__()

    def __getitem__(self, item):
        """ Return a node of the main line of play.
        """
        return self.game.nodes.__getitem__(item)

    def __len__(self):
        """ Return the number of nodes on the main line of play.
        """
        return self.game.nodes.__len__()

    def __repr__(self):
        return repr(self.game)

    def _new(self):
        """ Use a new (empty) GameTree object in this Kifu.
        """
        # initialize game
        collection = CollectionGl()
        game = GameTreeGl(collection)
        collection.children.append(game)

        # add context node
        context = NodeGl(game, None)
        context.properties["SZ"] = [gsize]
        context.properties['C'] = ["Recorded with {}.".format(appname)]
        context.number()
        game.nodes.append(context)
        self.game = game

    def _parse(self, filepath, log=None, err=None):
        """ Use a GameTree object loaded from the provided file.
        """
        if log is None:
            log = lambda msg: sys.stdout.write(str(msg) + "\n")
        if filepath is not None:
            try:
                with open(filepath) as f:
                    parser = Parser()
                    sgf_string = f.read()
                    f.close()
                    collection = CollectionGl(parser)
                    parser.parse(sgf_string)
                    log("Opened '{0}'".format(filepath))
                    self.game = collection[0]
                    self.sgffile = filepath
            except IOError as ioe:
                self._new()
                if err is not None:
                    err(ioe)
                    err("Opened new game")
        else:
            self._new()
            log("Opened new game")