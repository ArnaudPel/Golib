from golib.model import sgf
# little hack to force Tauber's sgf extensibility.
sgf.createtree = lambda parent, parser=None: GameTreeGl(parent, parser=parser)
sgf.createnode = lambda parent, previous, parser=None: NodeGl(parent, previous, parser=parser)
# end of little hack :)

import golib.model
from golib.config.golib_conf import B, W


__author__ = 'Arnaud Peloquin'

"""
Extensions of Tauber's SGF, in order not to mix codes. This mostly consists in adds, plus a few overrides.

"""

Parser = sgf.Parser  # redirect, so that go.sgf imports are exclusively made from the current file.


class CollectionGl(sgf.Collection):

    def __getitem__(self, item):
        return self.children.__getitem__(item)

    def __repr__(self):
        return "{0} [{1} children]".format(self.__class__.__name__, len(self.children))


class GameTreeGl(sgf.GameTree):
    def __getitem__(self, item):
        """
        Provide direct getitem access to self.children.
        To access nodes, use self.nodes[]

        """
        return self.children.__getitem__(item)

    def __setitem__(self, key, value):
        return self.children.__setitem__(key, value)

    def __len__(self):
        return self.children.__len__()

    def __repr__(self):
        return "{0} [{1} nodes] [{2} children]".format(self.__class__.__name__, len(self.nodes), len(self.children))


class NodeGl(sgf.Node):
    def my_end_property(self):
        if self.current_property == 'MN':
            value = [int(self.current_prop_value[0])]
        else:
            value = self.current_prop_value
        self.properties[self.current_property] = value

    def my_end_node(self):
        self.number()
        self.parent.setup()

    def output(self, f):
        f.write(";")
        for prop in self.properties.keys():
            f.write(prop)
            for value in self.properties[prop]:
                if type(value) is not int:
                    if "\\" in value:
                        value = "\\\\".join(value.split("\\"))
                    if "]" in value:
                        value = "\]".join(value.split("]"))
                f.write("[%s]" % value)
            f.write("\n")

    def number(self, nb=-1):
        """
        A.P.
        Set the move number property (MN) if not already there.

        """
        # if number provided, force update
        if 0 <= nb:
            self.properties["MN"] = [nb]

        # else create number only if it is missing
        elif "MN" not in self.properties.keys():
            number = 0
            try:
                number = self.previous.properties["MN"][0]
            except AttributeError:  # no previous, start numbering
                pass
            try:
                if self.getmove() is not None:
                    number += 1
            except golib.model.SgfWarning:  # previous is not a move, don't increment
                pass
            self.properties["MN"] = [number]

    def getmove(self):
        """
        A.P.
        Returns a Move object, or null if this node has no move property.

        """
        number = -1
        try:
            number = self.properties["MN"][0]
        except KeyError:
            pass

        color = B
        pos = None
        try:
            pos = self.properties[color][0]
        except KeyError:
            try:
                color = W
                pos = self.properties[color][0]
            except KeyError:
                keys = self.properties.keys()
                if 'AW' in keys or 'BW' in keys or 'EW' in keys:
                    raise golib.model.SgfWarning("Setup properties detected (not currently supported). "
                                     "The game may not be rendered correctly. Move:" + str(number))
        if pos is not None:
            if len(pos) == 0:
                pos = '--'  # the player has passed
            return golib.model.Move("sgf", (color, pos[0], pos[1]), number=number)
        return None

    def __repr__(self):
        """
        A.P.
        For debug purposes really.

        """
        #return "{0} prev:{1} next:{2} keys={3}".\
        #    format(self.__class__.__name__,
        #           self.previous.getmove() if self.previous is not None else None,
        #           self.next.getmove() if self.next is not None else None,
        #           [key for key in self.properties.keys()])
        return self.getmove().__repr__() + str(self.properties["MN"])
