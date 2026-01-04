from __future__ import annotations

import re
from dataclasses import dataclass
from shutil import get_terminal_size
from typing import Callable, Iterable, Optional, Union
import math

Number = Union[int, float]

class AnsiHelp:
    _ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

    @staticmethod
    def truncate_visible(s: str, max_cols: int) -> str:
        """
        Truncate to max_cols *visible* characters,
        preserving ANSI escape sequences.
        Never splits an escape code.
        """
        if max_cols <= 0:
            return ""

        out = []
        vis = 0
        i = 0
        n = len(s)

        while i < n and vis < max_cols:
            if s[i] == '\x1b' and i + 1 < n and s[i + 1] == '[':
                # copy the whole SGR sequence
                j = i + 2
                while j < n and s[j] != 'm':
                    j += 1
                if j < n:
                    j += 1  # include 'm'
                    out.append(s[i:j])
                    i = j
                    continue
                # malformed escape; stop safely
                break

            out.append(s[i])
            vis += 1
            i += 1

        return "".join(out)

    @staticmethod
    def _sgr_wrap(sgr: Optional[str], text: str) -> str:
        """
        Wrap text in ANSI SGR escape codes.
        `sgr` is the *parameter string* (e.g. '38;5;196;48;5;234'),
        not including ESC[ and 'm'.
        """
        if not sgr:
            return text
        return f'\x1b[{sgr}m{text}\x1b[0m'


ValueColorCallback = Callable[..., Optional[str]]


@dataclass
class VerticalBarChart:
    """
    Dense vertical packed bar chart:
      - 10 positive rows (10% per row, with 5% sub-resolution per side)
      - optional 0 baseline + minimal negative rows if negatives exist
      - packs two values per column: (v0,v1), (v2,v3), ...

    Styling is applied AFTER construction via Set*() methods.
    Caller supplies raw SGR parameter strings; chart only wraps them.

    Glyph semantics per 10% band cell (each side is 0/5/10 within that band):
      Positive (bottom-filled):
        (L,R) ∈ {0,5,10}²
          (0,0)=' ' (0,5)='▗' (0,10)='▐'
          (5,0)='▖' (5,5)='▄' (5,10)='▟'
          (10,0)='▌' (10,5)='▙' (10,10)='█'

      Negative (top-filled) uses top-biased analogs:
          (0,0)=' ' (0,5)='▝' (0,10)='▐'
          (5,0)='▘' (5,5)='▀' (5,10)='▜'
          (10,0)='▌' (10,5)='▛' (10,10)='█'
    """

    values: Iterable[Number]
    title: Optional[str] = None

    # Width / scaling
    width: Optional[int] = None
    max_value: Optional[float] = None   # None => max(abs(values))
    clamp_to_100: bool = True

    # Labels / layout
    show_y_axis: bool = True
    show_rule: bool = True
    unicode: bool = True
    y_label_fmt: Optional[str] = None   # forced-scale: e.g. '$%+3.0f '; percent mode uses built-in labels

    # ---- Styling state (set via Set* methods) ----
    _border_enabled: bool = False
    _border_sgr: Optional[str] = None
    _border_style_name: str = 'single'     # 'single' | 'double' | 'ascii'

    _label_sgr: Optional[str] = None    # Y-axis labels (and title if you want to reuse)
    _axis_sgr: Optional[str] = None     # baseline / zero line
    _bar_sgr: Optional[str] = None      # default for bar glyphs

    _value_color_cb: Optional[ValueColorCallback] = None

    # ------------- Public styling API -------------

    def SetBorder(self, enabled: bool = True, *, sgr: Optional[str] = None, charset: str = 'single') -> 'VerticalBarChart':
        self._border_enabled = bool(enabled)
        self._border_sgr = sgr
        self._border_style_name = charset
        return self

    def SetLabelSgr(self, sgr: Optional[str]) -> 'VerticalBarChart':
        self._label_sgr = sgr
        return self

    def SetAxisSgr(self, sgr: Optional[str]) -> 'VerticalBarChart':
        self._axis_sgr = sgr
        return self

    def SetBarSgr(self, sgr: Optional[str]) -> 'VerticalBarChart':
        self._bar_sgr = sgr
        return self

    def SetValueColorCallback(self, cb: Optional[ValueColorCallback]) -> 'VerticalBarChart':
        self._value_color_cb = cb
        return self

    # ------------- Internals -------------

    def _term_cols(self) -> int:
        if self.width is not None:
            return max(20, int(self.width))
        return max(20, get_terminal_size(fallback=(80, 24)).columns)

    @staticmethod
    def _clamp_int(x: int, lo: int, hi: int) -> int:
        return lo if x < lo else hi if x > hi else x

    def _to_signed_steps_5pct(self, value: float, denom: float) -> int:
        if denom <= 0:
            return 0
        pct = (value / denom) * 100.0
        if self.clamp_to_100:
            pct = max(-100.0, min(100.0, pct))
        steps = int(round(pct / 5.0))
        return self._clamp_int(steps, -20, 20)

    def _glyph_pos(self, l_steps: int, r_steps: int) -> str:
        if not self.unicode:
            l_on, r_on = l_steps > 0, r_steps > 0
            if l_on and r_on: return '#'
            if l_on: return 'L'
            if r_on: return 'R'
            return ' '
        table = {
            (0, 0): ' ',
            (0, 1): '▗',
            (0, 2): '▐',
            (1, 0): '▖',
            (1, 1): '▄',
            (1, 2): '▟',
            (2, 0): '▌',
            (2, 1): '▙',
            (2, 2): '█',
        }
        return table[(l_steps, r_steps)]

    def _glyph_neg(self, l_steps: int, r_steps: int) -> str:
        if not self.unicode:
            l_on, r_on = l_steps > 0, r_steps > 0
            if l_on and r_on: return '#'
            if l_on: return 'L'
            if r_on: return 'R'
            return ' '
        table = {
            (0, 0): ' ',
            (0, 1): '▝',
            (0, 2): '▐',
            (1, 0): '▘',
            (1, 1): '▀',
            (1, 2): '▜',
            (2, 0): '▌',
            (2, 1): '▛',
            (2, 2): '█',
        }
        return table[(l_steps, r_steps)]

    def _default_forced_fmt(self) -> str:
        # trailing space is intentional (your preference)
        return self.y_label_fmt if self.y_label_fmt is not None else '%+d '

    def _render_y_label(self, *, kind: str, row: int, denom: float, forced: bool) -> str:
        """
        kind: 'pos'|'neg'|'zero'
        row:  1..10 magnitude band for pos/neg; ignored for zero
        forced: True if using denom-units labels, False if using percent labels
        """
        if not forced:
            if kind == 'zero':
                return '  0% '
            sign = +1 if kind == 'pos' else -1
            return f'{sign * row * 10:>3}% '

        fmt = self._default_forced_fmt()
        if kind == 'zero':
            return fmt % 0
        sign = +1 if kind == 'pos' else -1
        v = sign * (denom * row / 10.0)
        return fmt % v

    def _style_cell(
        self,
        *,
        glyph: str,
        value_left: float,
        value_right: float,
        denom: float,
        row_kind: str,   # 'pos'|'neg'
        row: int,        # 1..10 band index (pos: 10..1, neg: 1..N)
    ) -> str:
        # If callback exists, it wins.
        if self._value_color_cb is not None:
            pct_left = (value_left / denom) if denom else 0.0
            pct_right = (value_right / denom) if denom else 0.0
            sgr = self._value_color_cb(
                value_left=value_left,
                value_right=value_right,
                pct_left=pct_left,
                pct_right=pct_right,
                row_kind=row_kind,
                row=row,
                glyph=glyph,
            )
            return AnsiHelp._sgr_wrap(sgr, glyph)

        # Otherwise default bar sgr.
        return AnsiHelp._sgr_wrap(self._bar_sgr, glyph)

    def _border_chars(self) -> dict[str, str]:
        if self._border_style_name == 'double':
            return {'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝', 'h': '═', 'v': '║'}
        if self._border_style_name == 'ascii':
            return {'tl': '+', 'tr': '+', 'bl': '+', 'br': '+', 'h': '-', 'v': '|'}
        # default: single
        return {'tl': '┌', 'tr': '┐', 'bl': '└', 'br': '┘', 'h': '─', 'v': '│'}

    @staticmethod
    def _visible_len(s: str) -> int:
        """
        Approximate visible width by stripping ANSI escapes.
        Good enough for borders here (we only add escapes, not wide glyphs).
        """
        out = []
        i = 0
        while i < len(s):
            if s[i] == '\x1b' and i + 1 < len(s) and s[i + 1] == '[':
                # consume until 'm' (SGR)
                i += 2
                while i < len(s) and s[i] != 'm':
                    i += 1
                i += 1  # skip 'm'
                continue
            out.append(s[i])
            i += 1
        return len("".join(out))

    def _add_border(self, lines: list[str]) -> list[str]:
        if not self._border_enabled or not lines:
            return lines

        cs = self._border_chars()

        content_w = max(self._visible_len(ln) for ln in lines)

        def B(text: str) -> str:
            return AnsiHelp._sgr_wrap(self._border_sgr, text)

        # Top / bottom are easiest: wrap the entire line in border SGR.
        top_plain = cs['tl'] + cs['h'] * (content_w + 2) + cs['tr']
        bot_plain = cs['bl'] + cs['h'] * (content_w + 2) + cs['br']
        out = [B(top_plain)]

        # Sides: wrap only the border glyphs, never the interior.
        left_v = B(cs['v'])
        right_v = B(cs['v'])

        for ln in lines:
            pad = content_w - self._visible_len(ln)
            # IMPORTANT: pad is *visible* padding;
            #            ln already contains any ANSI it needs.
            out.append(f'{left_v} {ln}{' ' * pad} {right_v}')

        out.append(B(bot_plain))
        return out

    # ------------- Rendering -------------

    def __str__(self) -> str:
        vals = [float(v) for v in self.values]
        if not vals:
            return '(no data)'

        cols = self._term_cols()

        denom = float(self.max_value) if self.max_value is not None else max(abs(v) for v in vals)
        if denom <= 0:
            denom = 1.0

        # Pack sequentially into (left,right)
        left_vals: list[float] = []
        right_vals: list[float] = []
        it = iter(vals)
        for a in it:
            left_vals.append(a)
            right_vals.append(next(it, 0.0))

        # Convert to signed steps [-20..20]
        left_steps_total = [self._to_signed_steps_5pct(v, denom) for v in left_vals]
        right_steps_total = [self._to_signed_steps_5pct(v, denom) for v in right_vals]

        # Minimal negative rows
        max_neg_steps = 0
        for s in left_steps_total + right_steps_total:
            if s < 0:
                max_neg_steps = max(max_neg_steps, -s)
        neg_rows = int(math.ceil(max_neg_steps / 2.0))  # each row = 2 steps (10%)

        forced_labels = (self.max_value is not None) or (self.y_label_fmt is not None)

        # Compute y-axis width from labels we will render
        y_w = 0
        if self.show_y_axis:
            labels = [self._render_y_label(kind='pos', row=r, denom=denom, forced=forced_labels) for r in range(10, 0, -1)]
            if neg_rows > 0:
                labels.append(self._render_y_label(kind='zero', row=0, denom=denom, forced=forced_labels))
                labels.extend(self._render_y_label(kind='neg', row=r, denom=denom, forced=forced_labels) for r in range(1, neg_rows + 1))
            y_w = max(len(s) for s in labels)

        # Fit columns (1 glyph per packed column)
        usable = cols - y_w
        max_cols = max(1, usable)
        left_vals = left_vals[:max_cols]
        right_vals = right_vals[:max_cols]
        left_steps_total = left_steps_total[:max_cols]
        right_steps_total = right_steps_total[:max_cols]

        # Build lines (without border first)
        lines: list[str] = []

        if self.title:
            title_line = AnsiHelp.truncate_visible(self.title, cols)
            # If caller wants title styled, they can just SetLabelSgr and we'll reuse it here.
            lines.append(AnsiHelp._sgr_wrap(self._label_sgr, title_line))
            if self.show_rule:
                rule = ('─' if self.unicode else '-') * min(cols, max(10, len(self.title)))
                lines.append(AnsiHelp._sgr_wrap(self._axis_sgr, rule))

        # Positive region (10 rows)
        for row in range(10, 0, -1):
            steps_below = (row - 1) * 2
            parts = []

            if self.show_y_axis:
                lbl = self._render_y_label(kind='pos', row=row, denom=denom, forced=forced_labels)
                parts.append(AnsiHelp._sgr_wrap(self._label_sgr, lbl.rjust(y_w)))

            for lv, rv, ls, rs in zip(left_vals, right_vals, left_steps_total, right_steps_total):
                lmag = ls if ls > 0 else 0
                rmag = rs if rs > 0 else 0
                l_in_row = self._clamp_int(lmag - steps_below, 0, 2)
                r_in_row = self._clamp_int(rmag - steps_below, 0, 2)
                glyph = self._glyph_pos(l_in_row, r_in_row)
                parts.append(self._style_cell(
                    glyph=glyph,
                    value_left=lv,
                    value_right=rv,
                    denom=denom,
                    row_kind='pos',
                    row=row,
                ))

            lines.append(AnsiHelp.truncate_visible("".join(parts), cols))

        # Negative portion: either baseline only, or 0-axis + rows
        axis_char = '─' if self.unicode else '-'
        if neg_rows > 0:
            # 0 axis
            parts = []
            if self.show_y_axis:
                lbl0 = self._render_y_label(kind='zero', row=0, denom=denom, forced=forced_labels)
                parts.append(AnsiHelp._sgr_wrap(self._label_sgr, lbl0.rjust(y_w)))
            parts.append(AnsiHelp._sgr_wrap(self._axis_sgr, axis_char * len(left_vals)))
            lines.append(AnsiHelp.truncate_visible("".join(parts), cols))

            # negative rows: -10 .. -neg_rows*10
            for row in range(1, neg_rows + 1):
                steps_below = (row - 1) * 2
                parts = []
                if self.show_y_axis:
                    lbl = self._render_y_label(kind='neg', row=row, denom=denom, forced=forced_labels)
                    parts.append(AnsiHelp._sgr_wrap(self._label_sgr, lbl.rjust(y_w)))

                for lv, rv, ls, rs in zip(left_vals, right_vals, left_steps_total, right_steps_total):
                    lmag = (-ls) if ls < 0 else 0
                    rmag = (-rs) if rs < 0 else 0
                    l_in_row = self._clamp_int(lmag - steps_below, 0, 2)
                    r_in_row = self._clamp_int(rmag - steps_below, 0, 2)
                    glyph = self._glyph_neg(l_in_row, r_in_row)
                    parts.append(self._style_cell(
                        glyph=glyph,
                        value_left=lv,
                        value_right=rv,
                        denom=denom,
                        row_kind='neg',
                        row=row,
                    ))

                lines.append(AnsiHelp.truncate_visible("".join(parts), cols))
        else:
            # positive-only baseline at bottom
            parts = []
            if self.show_y_axis:
                parts.append(' ' * y_w)
            parts.append(AnsiHelp._sgr_wrap(self._axis_sgr, axis_char * len(left_vals)))
            lines.append(AnsiHelp.truncate_visible("".join(parts), cols))

        lines = self._add_border(lines)  # Add border last

        return '\n'.join(lines)
