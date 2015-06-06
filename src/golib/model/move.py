from golib.config.golib_conf import gsize, W, B


# Move coordinates types
TK_TYPE = "tk"    # TkInter (and incidentally, Opencv)
SGF_TYPE = "sgf"  # Smart Game Format
NP_TYPE = "np"    # Numpy
KGS_TYPE = "kgs"  # KGS Go Server


class Move:
    """ Handle the representation of a move on the Goban.

    Attributes:
        number: int
            The move number as understood by the players (black plays first move, etc..)
        color: B, W or E
            The color of the player that has played this Move. E for empty.
        x: int
            The first coordinate of the intersection where this Move has been played,  in an internal coordinate type.
        y: int
            The second coordinate of the intersection where this Move has been played, in an internal coordinate type.
    """

    def __init__(self, ctype: str, ctuple=None, string=None, number: int=-1):
        """ Provide constructor arguments either through "ctuple" or "string".

        Args:
            ctype:
                The coordinates type that should be used to interpret ctuple (see *_TYPE above).
            ctuple: tuple(color, x, y)
                x and y are interpreted depending on the 'ctype' argument.
            string: str
                If 'ctuple' is not provided, provide data as a string, interpreted depending on 'ctype'.
            number: int
                The move number to set.
        """
        self.number = number
        self.color = None
        self.x = None
        self.y = None
        # tuple argument trumps string argument
        if ctuple is None:
            ctuple = self.split_str(ctype, string)
        if ctuple is not None:
            self._interpret(ctype, *ctuple)
        else:
            raise TypeError("Please provide one of the two keyword argument: ctuple= or string=")

    def _interpret(self, ctype, color, a, b):
        """ Set the coordinates of the move, by interpreting (a, b) according to ctype.

        Args:
            a, b: depends on ctype
                The coordinates of the intersection where this Move has been played.
        ctype:
            The coordinate type.
        """
        self.color = color
        if ctype == TK_TYPE:
            self.x = int(a)
            self.y = int(b)
        elif ctype == SGF_TYPE:
            self.x = ord(a) - 97
            self.y = ord(b) - 97
        elif ctype == NP_TYPE:
            self.x = b
            self.y = a
        elif ctype == KGS_TYPE:  # kgs GUI: ranging from A1 to T19  (careful : the 'I' letter is omitted)
            self.x = ord(a) - (65 if ord(a) < 73 else 66)
            self.y = gsize - int(b)
        else:
            raise TypeError("Unrecognized coordinate type: \"%s\"" % ctype)

    def split_str(self, ctype, raw: str) -> tuple:
        """ Extract Move color and coordinates from the raw string.

        Args:
            ctype:
                The format according to which interpret "raw".
            raw: str
                The Move data to interpret.
        Returns:
            color, x, y
        """
        if raw is None:
            return None
        elif ctype == SGF_TYPE:
            return raw[0], raw[2], raw[3]
        elif ctype == KGS_TYPE:
            return raw[0], raw[2], (raw[3] if len(raw) == 5 else raw[3:5])
        else:
            raise NotImplementedError("No string parser for coordinate type \"%s\"" % str(ctype))

    def get_coord(self, ctype=SGF_TYPE) -> tuple:
        """ Return the coordinates of this move in the provided coordinate frame "ctype".

        Returns:
            x, y
        """
        if ctype == TK_TYPE:
            return self.x, self.y
        elif ctype == SGF_TYPE:
            return chr(self.x + 97), chr(self.y + 97)
        elif ctype == NP_TYPE:
            return self.y, self.x
        elif ctype == KGS_TYPE:
            return chr(self.x + (65 if self.x < 8 else 66)), gsize - self.y

    def copy(self):
        return Move(TK_TYPE, (self.color, self.x, self.y), number=self.number)

    def repr(self, ctype) -> str:
        """ Represent this move in the provided coordinate type.
        """
        if 0 <= self.x:
            mvstr = "{0}{1}".format(*self.get_coord(ctype=ctype))
        else:
            mvstr = "pass"
        return "%s[%s]" % (self.color, mvstr)

    def __eq__(self, o):
        return self.color == o.color and self.x == o.x and self.y == o.y

    def __hash__(self):
        """ Implementation based on the assumption that x, y are in [0, gsize[

        Let gszise * gsize be g2.
        Black positions hashes are in [0, g2[
        White positions hashes are in [g2, 2*g2[
        Pass moves are in [2*g2, 2*g2 + 1]
        """
        if 0 <= self.x and 0 <= self.y:  # normal move
            color_hash = 0 if self.color == B else gsize * gsize
            return (self.x + gsize * self.y) + color_hash
        else:   # "pass" move
            return 2 * gsize * gsize + (1 if self.color == W else 0)

    def __repr__(self):
        """ Tweaking the move coordinates printing during dev/debug may be useful.
        """
        # coord_type = SGF_TYPE
        # coord_type = NP_TYPE
        coord_type = KGS_TYPE
        # coord_type = TK_TYPE
        return self.repr(coord_type)
