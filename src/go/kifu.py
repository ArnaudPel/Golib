from sys import stdout
from golib_conf import gsize
from go.sgfck import CollectionGl, GameTreeGl, NodeGl, Parser
from go.sgfwarning import SgfWarning

__author__ = 'Kohistan'


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

    def __init__(self, sgffile=None, log=None):
        self.game = None
        self.sgffile = None
        self._parse(sgffile, log=log)
        self.modified = False

    def append(self, move):
        node = self._prepare(move)
        self.game.nodes.append(node)
        self.modified = True

    def insert(self, move, number):
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

    def contains_move(self, move, start=0):
        for i in range(start, len(self)):
            mv = self[i].getmove()
            if mv == move:
                return True
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
            return 'B' if current.color == 'W' else 'W'
        else:
            return 'B'  # probably the beginning of the game

    def save(self):
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

    def _parse(self, filepath, log=None):
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
                log(ioe)
                self._new()
                log("Opened new game")
        else:
            self._new()
            log("Opened new game")


if __name__ == '__main__':
    colors = ['B', 'W']
    kifu = Kifu()
    previous = kifu.game.nodes[-1]
    for i in range(gsize):
        nod = NodeGl(kifu.game, previous)
        nod.properties[colors[i % 2]] = [chr(i + 97) + chr(i + 97)]
        kifu.game.nodes.append(nod)
        previous = nod

    f_out = file("/Users/Kohistan/Documents/go/Perso Games/updated.sgf", 'w')
    kifu.game.parent.output(f_out)

















