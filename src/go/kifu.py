from sys import stdout
from golib_conf import gsize, B, W
from go.sgf_ck import CollectionGl, GameTreeGl, NodeGl, Parser
from go.exceptions import SgfWarning

__author__ = 'Arnaud Peloquin'


class Kifu:
    """
    Utility class simplifying common interactions with the SGF structure.

    For now Kifu only supports one line of play: no variations are allowed.
    This means that an entire game is one single list of nodes.
    In order to make future changes as seamless as possible, some python "magic methods"
    have been used where possible. Hopefully they will help keep this "branch" concept
    inside Kifu.
    Methods currently relying on that naive implementation have a @naive doctag

    self.game -- the GameTree object backing the recording of this kifu.

    """

    def __init__(self, sgffile=None, log=None, err=None):
        self.game = None
        self.sgffile = None
        self._parse(sgffile, log=log, err=err)
        self.modified = False

    def append(self, move):
        """
        Append the move at the end of the game.

        """
        node = self._prepare(move)
        self.game.nodes.append(node)
        self.modified = True

    def insert(self, move, number):
        """
        Insert the move at the provided move number. Subsequent moves have their number incremented by one.

        """
        node = self._prepare(move)
        node.number(number)

        idx = None
        # update subsequent moves number
        for i in range(len(self)):
            nd = self.game.nodes[i]
            try:
                nb = nd.properties["MN"][0]
                if number <= nb:
                    nd.properties["MN"][0] += 1
                if nb == number:
                    idx = i
            except KeyError:
                pass  # not a move

        if idx is not None:
            self.game.nodes.insert(idx, node)

        # this insertion is actually an append
        elif i == number - 1:
            self.game.nodes.append(node)
        self.modified = True

    def relocate(self, origin, dest):
        """
        Change the coordinates of "origin" to those of "dest". The move number is not changed.

        """
        node = self.locate(origin.x, origin.y)
        a, b = dest.get_coord("sgf")
        node.properties[origin.color] = [a + b]
        self.modified = True

    def delete(self, move):
        """
        @naive

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
                    pass
        if torem is not None:
            self.game.nodes.remove(torem)
            self.modified = True

    def get_move_seq(self, first=1, last=1000):
        """
        Return the sub-sequence of moves of the main line of play, in a fresh list.
        Non-move nodes (like startup node) are ignored.
        @naive

        first, last -- move number delimiting the sequence (both inclusive)

        """
        seq = []
        for i in range(first, len(self)):
            mv = self[i].getmove()
            if mv and (first <= mv.number <= last):
                seq.append(mv)
                if mv.number == last:
                    break
        return seq

    def getmove_at(self, number):
        """
        Return the move having the given number if found.
        @naive

        """
        for i in range(number, len(self)):
            mv = self[i].getmove()
            if mv is not None and mv.number == number:
                return mv

    def locate(self, x, y, upbound=None):
        """
        Return the node describing the given goban intersection, or None if the intersection is empty.
        @naive

        """
        start = upbound if upbound else len(self) - 1
        for i in range(start, -1, -1):  # go backwards to match move on screen
            mv = self[i].getmove()
            if mv and mv.x == x and mv.y == y:
                return self[i]

    def contains_pos(self, x, y, start=0):
        """
        Return the index of the first node containing a move placed at the provided coordinates.
        start -- the index where to start search (inclusive)

        """
        for i in range(start, len(self)):
            mv = self[i].getmove()
            if (mv.x == x) and (mv.y == y):
                return i
        return False

    def lastmove(self):
        """
        Return the last move on the main line of play, if any.
        @naive

        """
        for i in range(-1, -len(self), -1):
            mv = self[i].getmove()
            if mv is not None:
                return mv

    def next_color(self):
        """
        Return the (guessed) color of the next move to append, based on a black-white alternation assumption.

        """
        current = self.lastmove()
        if current is not None:
            return B if current.color == W else W
        else:
            return B  # probably the beginning of the game

    def save(self):
        """
        Save to file.

        """
        if self.sgffile is not None:
            with open(self.sgffile, 'w') as f:
                self.game.output(f)
                self.modified = False
                print "Game saved to: " + self.sgffile
        else:
            raise SgfWarning("No file defined, can't save.")

    def _prepare(self, move):
        """
        Create a new node for the given move.

        """
        node = NodeGl(self.game, self[-1])
        r, c = move.get_coord("sgf")
        node.properties[move.color] = [r + c]  # sgf properties are in a list
        node.number(nb=move.number)
        return node

    def __iter__(self):
        """
         Iterate over the nodes of the main line of play.
         @naive

         """
        return self.game.nodes.__iter__()

    def __getitem__(self, item):
        """
         Return a node of the main line of play.
         @naive

         """
        return self.game.nodes.__getitem__(item)

    def __len__(self):
        """
         The number of nodes on the main line of play.
         @naive

         """
        return self.game.nodes.__len__()

    def __repr__(self):
        return repr(self.game)

    def _new(self):
        """
        Create an empty Kifu.

        """
        # initialize game
        collection = CollectionGl()
        game = GameTreeGl(collection)
        collection.children.append(game)

        # add context node
        context = NodeGl(game, None)
        context.properties["SZ"] = [gsize]
        context.properties['C'] = ["Recorded with Camkifu."]
        context.number()
        game.nodes.append(context)

        self.game = game

    def _parse(self, filepath, log=None, err=None):
        """
        Create a Kifu reflecting the given file.

        """
        if log is None:
            log = lambda msg: stdout.write(str(msg) + "\n")
        if filepath is not None:
            try:
                with file(filepath) as f:
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