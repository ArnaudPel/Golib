import tkinter as tk

from golib.config import golib_conf as gc  # needed to dynamically read rwidth value
from golib.config.golib_conf import gsize, B, W, E
from golib.model import Move, TK_TYPE


class Goban(tk.Canvas):
    """
    The widget dedicated to the display of the goban and the stones.

    """

    def __init__(self, master):
        tk.Canvas.__init__(self, master, width=gsize * gc.rwidth, height=gsize * gc.rwidth)
        self.stones = mtx(gsize)
        self.closed = False
        self._draw_board()

    def _draw_board(self):
        """
        Draw an empty goban.

        """
        self.configure(background="#F0CAA7")
        # vertical lines
        offset = gc.rwidth / 2
        for i in range(gsize):
            x = i * gc.rwidth + offset
            self.create_line(x, offset, x, gsize * gc.rwidth - offset)
            # horizontal lines
        for i in range(gsize):
            y = i * gc.rwidth + offset
            self.create_line(offset, y, gsize * gc.rwidth - offset, y)
            # hoshis
        for a in [3, 9, 15]:
            wid = 3
            for b in [3, 9, 15]:
                xcenter = a * gc.rwidth + gc.rwidth / 2
                ycenter = b * gc.rwidth + gc.rwidth / 2
                oval = self.create_oval(xcenter - wid, ycenter - wid, xcenter + wid, ycenter + wid)
                self.itemconfigure(oval, fill="black")

    def stones_changed(self, grid):
        """
        Update the displayed stones to match the color grid provided.
        grid -- a matrix of colors (B, W, or E).

        """
        for x in range(len(grid)):
            for y in range(len(grid[x])):
                color = grid[x][y]
                prev = self.stones[x][y]
                if color == E:
                    if prev is not None:
                        prev.erase()
                        self.stones[x][y] = None
                elif color in (B, W):
                    if prev is not None:
                        self.stones[x][y].erase()
                    stone = Stone(self, Move(TK_TYPE, ctuple=(color, x, y)))
                    stone.paint()
                    self.stones[x][y] = stone
                else:
                    raise TypeError("Unrecognized color: \"%s\"" % color)

    def clear(self):
        self.delete("all")
        self._draw_board()
        self.stones = mtx(gsize)

    def highlight(self, move, keep=False):
        if not keep:
            # loop is ugly, but no additional structure needed
            for stone in self:
                stone.highlight(False)
        try:
            self.stones[move.x][move.y].highlight(True)
        except (AttributeError, IndexError):
            pass

    def select(self, move):
        for stone in self:
            stone.select(False)
        try:
            self.stones[move.x][move.y].select(True)
        except (AttributeError, IndexError):
            pass  # selection cleared

    def __iter__(self):
        for x in range(gsize):
            for y in range(gsize):
                stone = self.stones[x][y]
                if stone is not None:
                    yield stone


def mtx(size):
    """
    Return a "square matrix" of the given size, as a list of lists.

    """
    return [[None for _ in range(size)] for _ in range(size)]

tkcolors = {B: "black", W: "white"}
tk_inv_colors = {W: "black", B: "white"}


class Stone:
    """
    Store attributes related to a displayed stone. Location, tkindex, highlight status, selection status.

    """
    def __init__(self, canvas, move, highlight=False, selected=False):
        self.goban = canvas
        self._move = move.copy()  # self.move location may be changed by Stone
        self._hl = highlight
        self.selected = selected
        self.tkindexes = []
        self.border = int(round(gc.rwidth / 10))

    def setpos(self, x, y):
        self._move.x = x
        self._move.y = y

    def paint(self):
        self.erase()  # clear any previous item from self
        self._paint_stone()
        self._paint_highlight()
        self._paint_selected()

    def erase(self):
        while len(self.tkindexes):
            idx = self.tkindexes.pop()
            self.goban.delete(idx)

    def highlight(self, hl):
        if hl != self._hl:
            self._hl = hl
            self.erase()
            self.paint()

    def select(self, sel):
        if sel != self.selected:
            self.selected = sel
            self.erase()
            self.paint()

    def _paint_stone(self):
        x_ = self._move.x
        y_ = self._move.y

        x0 = x_ * gc.rwidth + self.border
        y0 = y_ * gc.rwidth + self.border
        x1 = (x_ + 1) * gc.rwidth - self.border
        y1 = (y_ + 1) * gc.rwidth - self.border

        oval_id = self.goban.create_oval(x0, y0, x1, y1)
        self.goban.itemconfigure(oval_id, fill=tkcolors[self._move.color])
        self.tkindexes.append(oval_id)

    def _paint_highlight(self):
        if self._hl:
            x_ = self._move.x
            y_ = self._move.y
            x0 = (x_ + 1/2) * gc.rwidth - self.border
            y0 = (y_ + 1/2) * gc.rwidth - self.border
            x1 = (x_ + 1/2) * gc.rwidth + self.border
            y1 = (y_ + 1/2) * gc.rwidth + self.border

            hl_id = self.goban.create_oval(x0, y0, x1, y1)
            self.goban.itemconfigure(hl_id, fill=tk_inv_colors[self._move.color])
            self.tkindexes.append(hl_id)

    def _paint_selected(self):
        if self.selected:
            x_ = self._move.x
            y_ = self._move.y

            x0 = x_ * gc.rwidth + self.border
            y0 = y_ * gc.rwidth + self.border
            x1 = (x_ + 1) * gc.rwidth - self.border
            y1 = (y_ + 1) * gc.rwidth - self.border

            oval_id = self.goban.create_oval(x0, y0, x1, y1)
            self.goban.itemconfigure(oval_id, outline="red", width=self.border)
            self.tkindexes.append(oval_id)

    def copy(self):
        return Stone(self.goban, self._move, highlight=self._hl, selected=self.selected)
