from golib.config.golib_conf import gsize, W, B

__author__ = 'Arnaud Peloquin'


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
            self._interpret(ctype, *ctuple)
        else:
            raise TypeError("Please provide \"ctuple\" or \"string\" keyword argument")

    def _interpret(self, ctype, color, a, b):
        """
        Set the coordinates of the move, by interpreting (a, b) based on ctype.
        a, b -- the coordinates. their value depends on ctype.
        ctype -- the coordinate type.

        """
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

        ctype -- the coordinate type.

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
        """
        Express this move in the provided coordinate type.

        """
        if 0 <= self.x:
            mvstr = "{0}{1}".format(*self.get_coord(ctype=ctype))
        else:
            mvstr = "pass"
        return "%s[%s]" % (self.color, mvstr)

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
            color = 0 if self.color == B else gsize * gsize
            return self.x + gsize * self.y + color
        else:
            return 2 * gsize * gsize + (1 if self.color == W else 0)

    def __repr__(self):
        # temporary changing type below during dev/debug can be useful

        # coord_type = "sgf"
        # coord_type = "cv"
        coord_type = "kgs"
        # coord_type = "tk"
        return self.repr(coord_type)


