from golib_conf import gsize
from go.sgf import Collection, GameTree, Node, Parser
from go.sgfwarning import SgfWarning

__author__ = 'Kohistan'


class Kifu:
    """
    Utility class simplifying common interactions with the SGF structure.

    For now it only supports one main line of play: no variations are allowed.
    This means that an entire game is one single list of nodes.

    self.game -- the GameTree object backing the recording of this kifu.

    """

    def __init__(self, game, sgffile=None):
        self.game = game
        self.sgffile = sgffile

    def append(self, move):
        node = self._prepare(move)
        self.game.nodes.append(node)

    def insert(self, move, number):
        node = self._prepare(move)
        node.number(number)

        idx = None
        # update subsequent moves number
        for i in range(len(self.game.nodes)):
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

    def pop(self):
        self.game.nodes.pop()

    def last_move(self):
        """
        Note: this is a naive implementation based on the assumption that the game has no children.
        In other words, that there are not variations at all.

        """
        return self.game.nodes[-1].getmove()

    def next_color(self):
        current = self.last_move()
        if current is not None:
            return 'B' if current.color == 'W' else 'W'
        else:
            return 'B'

    def relocate(self, origin, dest):
        node = self.getmove_at(origin.x, origin.y)
        a, b = dest.getab()
        node.properties[origin.color] = [a + b]

    def getmove_at(self, x, y):
        """
        Note: this is a naive implementation based on the assumption that the game has no children.
        In other words, that there are not variations at all.

        """
        for node in self.game.nodes:
            mv = node.getmove()
            if mv and mv.x == x and mv.y == y:
                return node

    def delete(self, move):
        """
        Note: this is a naive implementation based on the assumption that the game has no children.
        In other words, that there are not variations at all.

        """
        decr = False
        torem = None
        for node in self.game.nodes:
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
        node = Node(self.game, self.game.nodes[-1])
        r, c = move.getab()
        node.properties[move.color] = [r + c]  # sgf properties are in a list
        node.number()
        return node

    def __repr__(self):
        return repr(self.game)

    @staticmethod
    def new():
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

        return Kifu(game)

    @staticmethod
    def parse(filepath):
        """
        Create a Kifu reflecting the given file.

        """
        try:
            with file(filepath) as f:
                parser = Parser()
                sgf_string = f.read()
                f.close()
                collection = Collection(parser)
                parser.parse(sgf_string)
                return Kifu(collection[0])
        except IOError as ioe:
            print ioe
            return Kifu.new()


if __name__ == '__main__':
    colors = ['B', 'W']
    kifu = Kifu.new()
    previous = kifu.game.nodes[-1]
    for i in range(gsize):
        nod = Node(kifu.game, previous)
        nod.properties[colors[i % 2]] = [chr(i + 97) + chr(i + 97)]
        kifu.game.nodes.append(nod)
        previous = nod

    f_out = file("/Users/Kohistan/Documents/go/Perso Games/updated.sgf", 'w')
    kifu.game.parent.output(f_out)

















