from sys import stdout
from golib_conf import gsize
from go.sgf import Collection, GameTree, Node, Parser
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

    def append(self, move):
        node = self._prepare(move)
        self.game.nodes.append(node)

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

    def get_main_seq(self):
        """
        Return the sequence of moves of the main line of play.
        @naive

        """
        seq = []
        for node in self.game.nodes:
            mv = node.getmove()
            if mv:
                seq.append(mv)
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

    def relocate(self, origin, dest):
        node = self.locate(origin.x, origin.y)
        a, b = dest.getab()
        node.properties[origin.color] = [a + b]

    def locate(self, x, y):
        """
        Return the node describing the given goban intersection, or None if the intersection is empty.
        @naive

        """
        for node in self.game.nodes:
            mv = node.getmove()
            if mv and mv.x == x and mv.y == y:
                return node

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
                except AttributeError:
                    pass
        if torem is not None:
            self.game.nodes.remove(torem)

    def save(self):
        if self.sgffile is not None:
            with open(self.sgffile, 'w') as f:
                self.game.output(f)
                print "Game saved to: " + self.sgffile
        else:
            raise SgfWarning("No file defined, can't save.")

    def _prepare(self, move):
        """
        Create a new node for the given move.

        """
        node = Node(self.game, self[-1])
        r, c = move.getab()
        node.properties[move.color] = [r + c]  # sgf properties are in a list
        node.number()
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
        collection = Collection()
        game = GameTree(collection)
        collection.children.append(game)

        # add context node
        context = Node(game, None)
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
                    collection = Collection(parser)
                    parser.parse(sgf_string)
                    log("Opened '{0}'".format(filepath))
                    self.game = collection[0]
                    self.sgffile = filepath
            except IOError as ioe:
                log(ioe)
                self._new()
        else:
            self._new()


if __name__ == '__main__':
    colors = ['B', 'W']
    kifu = Kifu()
    previous = kifu.game.nodes[-1]
    for i in range(gsize):
        nod = Node(kifu.game, previous)
        nod.properties[colors[i % 2]] = [chr(i + 97) + chr(i + 97)]
        kifu.game.nodes.append(nod)
        previous = nod

    f_out = file("/Users/Kohistan/Documents/go/Perso Games/updated.sgf", 'w')
    kifu.game.parent.output(f_out)

















