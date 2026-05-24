"""Tests for the tabwriter-style table renderer (`output.table`)."""

from clawrium.cli.output.table import GAP, render


class TestRender:
    def test_padding_per_column(self) -> None:
        out = render(
            headers=["NAME", "TYPE", "AGE"],
            rows=[
                ["a", "x", "1d"],
                ["bbbb", "yy", "30s"],
                ["cc", "zzzz", "5m"],
            ],
        )
        # Headers: NAME(4), TYPE(4), AGE(3). Column widths from max:
        #   col0: max(NAME=4, a=1, bbbb=4, cc=2) = 4
        #   col1: max(TYPE=4, x=1, yy=2, zzzz=4) = 4
        #   col2 last column → no padding
        expected = (
            f"NAME{GAP}TYPE{GAP}AGE\n"
            f"a   {GAP}x   {GAP}1d\n"
            f"bbbb{GAP}yy  {GAP}30s\n"
            f"cc  {GAP}zzzz{GAP}5m\n"
        )
        assert out == expected

    def test_gap_is_exactly_three_spaces(self) -> None:
        out = render(headers=["A", "B"], rows=[["x", "y"]])
        # `A   B\nx   y\n` — 3 spaces between cols.
        first_line = out.splitlines()[0]
        assert first_line == "A   B"
        # explicit GAP check
        assert "   " in first_line
        assert "    " not in first_line  # not 4 spaces

    def test_no_trailing_whitespace(self) -> None:
        out = render(
            headers=["X", "Y"],
            rows=[["short", "longer-value"], ["alpha", "beta"]],
        )
        for line in out.splitlines():
            assert line == line.rstrip(), f"line has trailing whitespace: {line!r}"

    def test_no_headers_omits_header_row(self) -> None:
        out_with = render(
            headers=["NAME", "AGE"],
            rows=[["a", "1d"], ["bbbb", "5m"]],
        )
        out_without = render(
            headers=["NAME", "AGE"],
            rows=[["a", "1d"], ["bbbb", "5m"]],
            no_headers=True,
        )
        assert "NAME" not in out_without
        # widths must still be computed including header for compat with
        # piped output (columns line up). Without header AND header is
        # the widest cell, we want widths to be max(data) for tightness.
        # Here, header NAME(4) == bbbb(4) so result is the same width.
        assert "a   " in out_without
        # The header-less output should be a strict suffix of the row
        # data (no extra blank line)
        assert out_without == "\n".join(out_with.splitlines()[1:]) + "\n"

    def test_empty_input_returns_empty_string(self) -> None:
        assert render(headers=[], rows=[]) == ""

    def test_single_column_no_padding(self) -> None:
        # Last column gets no padding; with only one column there's no
        # padding at all.
        out = render(headers=["NAME"], rows=[["a"], ["bbbb"]])
        assert out == "NAME\na\nbbbb\n"
