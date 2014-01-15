### SGF.PY

#    Copyright (C) 2002 James Tauber
#    Modifications 2013 Arnaud Peloquin
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# module for representing, parsing and writing out SGF files
#
# TO PARSE
# given a file_name
#     parser = sgf.Parser()
#     f = file(file_name)
#     sgf_string = f.read()
#     f.close()
#     collection = sgf.Collection(parser)
#     parser.parse(sgf_string)
# collection now represents the SGF collection
#
# TO SAVE
# given a file_name
#     f = file(file_name, "w")
#     collection.output(f)
#     f.close()
#
# THE OBJECTS
# Collection has children[] each of which is a GameTree
# GameTree has nodes[] each of which is a Node
#          and children[] each of which is a GameTree
# Node has properties[] dictionary with string keys and values
#      and previous - previous node in SGF
#          next - next node in SGF
#          previous_variation - previous variation (if first node in a variation)
#          next_variation - next variation (if first node in a variation)
#          first - boolean indicating when first node in a variation
#          variations[] - list of variations immediately from this node


### IMPORTS
from string import join
from go.sgfwarning import SgfWarning


### SGF OBJECTS
from golib_conf import gsize


class Collection:
    def __init__(self, parser=None):
        self.parser = parser
        if parser:
            self.setup()
        self.children = []

    def setup(self):
        self.parser.start_gametree = self.my_start_gametree

    def my_start_gametree(self):
        self.children.append(GameTree(self, self.parser))

    def output(self, f):
        for child in self.children:
            child.output(f)

    def __getitem__(self, item):
        return self.children.__getitem__(item)

    def __repr__(self):
        return "{0} [{1} children]".format(self.__class__.__name__, len(self.children))


class GameTree:
    def __init__(self, parent, parser=None):
        self.parent = parent
        self.parser = parser
        if parser:
            self.setup()
        self.nodes = []
        self.children = []

    def setup(self):
        self.parser.start_gametree = self.my_start_gametree
        self.parser.end_gametree = self.my_end_gametree
        self.parser.start_node = self.my_start_node

    def my_start_node(self):
        if len(self.nodes) > 0:
            previous = self.nodes[-1]
        elif self.parent.__class__ == GameTree:
            previous = self.parent.nodes[-1]
        else:
            previous = None
        node = Node(self, previous, self.parser)
        if len(self.nodes) == 0:
            #node.first = 1
            if self.parent.__class__ == GameTree:
                if len(previous.variations) > 0:
                    previous.variations[-1].next_variation = node
                    node.previous_variation = previous.variations[-1]
                previous.variations.append(node)
            else:
                if len(self.parent.children) > 1:
                    node.previous_variation = self.parent.children[-2].nodes[0]
                    self.parent.children[-2].nodes[0].next_variation = node

        self.nodes.append(node)

    def my_start_gametree(self):
        self.children.append(GameTree(self, self.parser))

    def my_end_gametree(self):
        self.parent.setup()

    def output(self, f):
        f.write("(")
        for node in self.nodes:
            node.output(f)
        for child in self.children:
            child.output(f)
        f.write(")")

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


class Node:
    def __init__(self, parent, previous, parser=None):
        self.parent = parent
        self.previous = previous
        self.parser = parser
        if parser:
            self.setup()
        self.properties = {}
        self.next = None
        self.previous_variation = None
        self.next_variation = None
        #self.first = 0
        self.variations = []
        if previous and not previous.next:
            previous.next = self

    def setup(self):
        self.parser.start_property = self.my_start_property
        self.parser.add_prop_value = self.my_add_prop_value
        self.parser.end_property = self.my_end_property
        self.parser.end_node = self.my_end_node

    def my_start_property(self, identifier):
        # @@@ check for duplicates
        self.current_property = identifier
        self.current_prop_value = []

    def my_add_prop_value(self, value):
        self.current_prop_value.append(value)

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
                        value = join(value.split("\\"), "\\\\")
                    if "]" in value:
                        value = join(value.split("]"), "\]")
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
            except SgfWarning:  # previous is not a move, don't increment
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

        color = 'B'
        pos = None
        try:
            pos = self.properties[color][0]
        except KeyError:
            try:
                color = 'W'
                pos = self.properties[color][0]
            except KeyError:
                keys = self.properties.keys()
                if 'AW' in keys or 'BW' in keys or 'EW' in keys:
                    raise SgfWarning("Setup properties detected (not currently supported). "
                                     "The game may not be rendered correctly. Move:" + str(number))
        if pos is not None:
            if len(pos) == 0:
                pos = '--'  # the player has passed
            return Move("sgf", (color, pos[0], pos[1]), number=number)
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


class Move(object):
    """
    A.P.
    Class to regroup "move" representations. Such representations can take several forms:
        - openCV coordinate frame ()
        - kgs coordinate frame (with the I column removed)
        - sgf format

    """

    def __init__(self, ctype, ctuple=None, string=None, number=-1):
        self.number = number
        self.color = None
        self.x = self.y = None
        # tuple argument trumps string argument
        if ctuple is None:
            ctuple = self.split_str(ctype, string)

        if ctuple is not None:
            self.interpret(ctype, *ctuple)
        else:
            raise TypeError("Please provide \"ctuple\" or \"string\" keyword argument")

    def interpret(self, ctype, color, a, b):
        self.color = color
        if ctype == "tk":
            self.x = a
            self.y = b
        elif ctype == "sgf":
            self.x = ord(a) - 97
            self.y = ord(b) - 97
        elif ctype == "cv":
            self.x = b
            self.y = a
        elif ctype == "kgs":
            self.x = ord(a) - (65 if ord(a) < 73 else 66)
            self.y = gsize - int(b)
        else:
            raise TypeError("Unrecognized coordinate type: \"%s\"" % ctype)

    # @staticmethod
    def split_str(self, ctype, s):
        if s is None:
            return None
        elif ctype == "sgf":
            return s[0], s[2], s[3]
        elif ctype == "kgs":
            return s[0], s[2], (s[3] if len(s) == 5 else s[3:5])
        else:
            raise NotImplementedError("No string parser for coordinate type \"%s\"" % str(ctype))

    def get_coord(self, ctype="sgf"):
        """
        Return coordinates of this move in the provided coordinate frame (ctype), as a tuple.
        Basically invert the conversion operated in __init__().

        """
        if ctype == "tk":
            return self.x, self.y
        elif ctype == "sgf":
            return chr(self.x + 97), chr(self.y + 97)
        elif ctype == "cv":
            return self.y, self.x
        elif ctype == "kgs":
            return chr(self.x + (65 if self.x < 8 else 66)), gsize - self.y

    def copy(self):
        return Move("tk", (self.color, self.x, self.y), number=self.number)

    def repr(self, ctype):
        return "{0}[{1}{2}]".format(self.color, *self.get_coord(ctype=ctype))

    def __eq__(self, o):
        return self.color == o.color and self.x == o.x and self.y == o.y

    def __hash__(self):
        """
        Implementation based on the assumption that x, y are in [0, gsize[
        Let gszise * gsize be g2.
        Black positions hashes are in [0, g2[
        White positions hashes are in [g2, 2*g2[
        Pass moves are in [2*g2, 2*g2 + 1]

        """
        if 0 <= self.x and 0 <= self.y:
            color = 0 if self.color == 'B' else gsize * gsize
            return self.x + gsize * self.y + color
        else:
            return 2 * gsize * gsize + (1 if self.color == 'W' else 0)

    def __repr__(self):
        # temporary changing type below during dev/debug can be useful

        # coord_type = "sgf"
        # coord_type = "cv"
        # coord_type = "kgs"
        coord_type = "tk"
        return self.repr(coord_type)


### SGF PARSER

class ParseException(Exception):
    pass


class Parser:
    #noinspection PyUnresolvedReferences,PyUnboundLocalVariable
    def parse(self, sgf_string):

        def whitespace(char):
            return char in " \t\r\n"

        def ucletter(char):
            return 65 <= ord(char) <= 90

        def lcletter(char):
            return 97 <= ord(char) <= 122

        state = 0

        for ch in sgf_string:
            if state == 0:
                if whitespace(ch):
                    state = 0
                elif ch == '(':
                    self.start_gametree()
                    state = 1
                else:
                    state = 0  # ignore everything up to first (
                    # raise ParseException, (ch, state)
            elif state == 1:
                if whitespace(ch):
                    state = 1
                elif ch == ";":
                    self.start_node()
                    state = 2
                else:
                    raise ParseException(ch, state)
            elif state == 2:
                if whitespace(ch):
                    state = 2
                elif ucletter(ch):
                    prop_ident = ch
                    state = 3
                elif ch == ";":
                    self.end_node()
                    self.start_node()
                    state = 2
                elif ch == "(":
                    self.end_node()
                    self.start_gametree()
                    state = 1
                elif ch == ")":
                    self.end_node()
                    self.end_gametree()
                    state = 4
                else:
                    raise ParseException(ch, state)
            elif state == 3:
                if ucletter(ch):
                    prop_ident = prop_ident + ch
                    state = 3
                elif lcletter(ch):  # @@@ currently ignoring lowercase
                    state = 3
                elif ch == "[":
                    self.start_property(prop_ident)
                    prop_value = ""
                    state = 5
                else:
                    raise ParseException(ch, state)
            elif state == 4:
                if ch == ")":
                    self.end_gametree()
                    state = 4
                elif whitespace(ch):
                    state = 4
                elif ch == "(":
                    self.start_gametree()
                    state = 1
                else:
                    raise ParseException(ch, state)
            elif state == 5:
                if ch == "\\":
                    state = 6
                elif ch == "]":
                    self.add_prop_value(prop_value)
                    state = 7
                else:
                    prop_value = prop_value + ch
            elif state == 6:
                prop_value = prop_value + ch
                state = 5
            elif state == 7:
                if whitespace(ch):
                    state = 7
                elif ch == "[":
                    prop_value = ""
                    state = 5
                elif ch == ";":
                    self.end_property()
                    self.end_node()
                    self.start_node()
                    state = 2
                elif ucletter(ch):
                    self.end_property()
                    prop_ident = ch
                    state = 3
                elif ch == ")":
                    self.end_property()
                    self.end_node()
                    self.end_gametree()
                    state = 4
                elif ch == "(":
                    self.end_property()
                    self.end_node()
                    self.start_gametree()
                    state = 1
                else:
                    raise ParseException(ch, state)
            else:
                raise ParseException(ch, state)
                pass

        if state != 4:
            raise ParseException(state)
