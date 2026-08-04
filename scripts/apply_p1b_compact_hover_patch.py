from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

HISTOGRAM_PANEL = Path("src/pixelscope/ui/comparison_analysis_panel.py")
LINE_PROFILE_PANEL = Path("src/pixelscope/ui/line_profile_panel.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_histogram(text: str) -> str:
    text = replace_once(
        text,
        "from pixelscope.ui.plot_colors import channel_color, comparison_pen\n",
        (
            "from pixelscope.ui.plot_colors import channel_color, comparison_pen\n"
            "from pixelscope.ui.plot_text import "
            "coordinate_header, middle_elide, plot_number\n"
        ),
        "histogram plot-text import",
    )
    text = replace_once(
        text,
        '''            if len(title) > 36:
                title = f"{title[:17]}...{title[-16:]}"
            if not overlay:
                plot.setTitle(f"{image_index + 1}  {title}")
''',
        '''            if not overlay:
                plot.setTitle(middle_elide(f"{image_index + 1} · {title}"))
''',
        "histogram title elision",
    )
    text = replace_once(
        text,
        '''            label = self._documents[image_index].display_name
            rows.append(
                f"<tr><td><b>{image_index + 1} · {label}</b></td>"
                f'<td style="color:{channel_color(channel_name)}; padding-left:8px">'
                f"{channel_name}: {value:.6g}</td></tr>"
            )
''',
        '''            rows.append(
                f"<tr><td><b>{image_index + 1}</b></td>"
                f'<td style="color:{channel_color(channel_name)}; padding-left:7px">'
                f"{channel_name}</td>"
                f'<td style="padding-left:10px; text-align:right">'
                f"{plot_number(value)}</td></tr>"
            )
''',
        "compact histogram hover rows",
    )
    text = replace_once(
        text,
        '''        hint.setHtml(f"<table cellspacing='2'>{''.join(rows)}</table>")
''',
        '''        coordinate_label = (
            "Normalized code"
            if self.histogram_range.currentText() == "Normalized 0–1"
            else "Code"
        )
        header = coordinate_header(coordinate_label, cursor_x)
        hint.setHtml(
            f"<b>{header}</b><table cellspacing='2'>{''.join(rows)}</table>"
        )
''',
        "histogram hover coordinate header",
    )
    return text


def patch_line_profile(text: str) -> str:
    text = replace_once(
        text,
        (
            "from pixelscope.ui.plot_colors import "
            "channel_color, image_marker_symbol, line_profile_pen\n"
        ),
        (
            "from pixelscope.ui.plot_colors import "
            "channel_color, image_marker_symbol, line_profile_pen\n"
            "from pixelscope.ui.plot_text import "
            "coordinate_header, middle_elide, plot_number\n"
        ),
        "line-profile plot-text import",
    )
    text = replace_once(
        text,
        '''        self._plot_channel_filters: list[str | None] = [None] * 6
''',
        '''        self._plot_channel_filters: list[str | None] = [None] * 6
        self._profile_series: list[
            list[tuple[int, str, NDArray[np.float64], NDArray[np.float64]]]
        ] = [[] for _index in range(6)]
''',
        "line-profile hover series state",
    )
    text = replace_once(
        text,
        '''        self._plot_channel_filters = [None] * 6
        channel_names = {name for result in results for name in result.channel_names if name != "A"}
''',
        '''        self._plot_channel_filters = [None] * 6
        self._profile_series = [[] for _index in range(6)]
        channel_names = {name for result in results for name in result.channel_names if name != "A"}
''',
        "line-profile render series reset",
    )
    text = replace_once(
        text,
        "            plot.setTitle(title)\n",
        "            plot.setTitle(middle_elide(title))\n",
        "line-profile title elision",
    )
    text = replace_once(
        text,
        '''                    plot.plot(
                        x_values,
                        y_values,
                        pen=line_profile_pen(channel_name),
                        antialias=True,
                        connect="finite",
                        name=curve_name,
                    )
''',
        '''                    plot.plot(
                        x_values,
                        y_values,
                        pen=line_profile_pen(channel_name),
                        antialias=True,
                        connect="finite",
                        name=curve_name,
                    )
                    self._profile_series[plot_index].append(
                        (image_index, channel_name, x_values, y_values)
                    )
''',
        "line-profile transformed hover series capture",
    )
    text = replace_once(
        text,
        '''        self._plot_channel_filters = [None] * 6
        self._set_axes_visible(False)
''',
        '''        self._plot_channel_filters = [None] * 6
        self._profile_series = [[] for _index in range(6)]
        self._set_axes_visible(False)
''',
        "line-profile clear series reset",
    )

    method_start = text.index("    def _on_plot_mouse_moved(")
    method_end = text.index("    def _hide_hover(", method_start)
    new_method = '''    def _on_plot_mouse_moved(self, position: object, plot_index: int = 0) -> None:
        line = self._hover_lines[plot_index]
        hint = self._hover_texts[plot_index]
        plot = self.plots[plot_index]
        series = self._profile_series[plot_index]
        if (
            line is None
            or hint is None
            or not series
            or not plot.sceneBoundingRect().contains(position)
        ):
            self._hide_hover(plot_index)
            return

        point = plot.getViewBox().mapSceneToView(position)
        primary_x = series[0][2]
        if (
            primary_x.size == 0
            or point.x() < primary_x[0]
            or point.x() > primary_x[-1]
        ):
            self._hide_hover(plot_index)
            return
        primary_index = int(np.argmin(np.abs(primary_x - point.x())))
        cursor_x = float(primary_x[primary_index])

        rows: list[str] = []
        for image_index, channel_name, x_values, y_values in series:
            if x_values.size == 0 or y_values.size == 0:
                continue
            nearest = int(np.argmin(np.abs(x_values - cursor_x)))
            value = float(y_values[nearest])
            rows.append(
                f"<tr><td><b>{image_index + 1}</b></td>"
                f'<td style="color:{channel_color(channel_name)}; padding-left:7px">'
                f"{channel_name}</td>"
                f'<td style="padding-left:10px; text-align:right">'
                f"{plot_number(value)}</td></tr>"
            )
        if not rows:
            self._hide_hover(plot_index)
            return

        view_range = plot.getViewBox().viewRange()
        x_anchor = 1 if point.x() > sum(view_range[0]) / 2 else 0
        y_anchor = 0 if point.y() > sum(view_range[1]) / 2 else 1
        line.setPos(cursor_x)
        hint.setAnchor((x_anchor, y_anchor))
        normalized = self.x_mode.currentText() == "Normalized distance"
        header = coordinate_header(
            "Normalized distance" if normalized else "Distance",
            cursor_x,
            None if normalized else "px",
        )
        hint.setHtml(
            f"<b>{header}</b><table cellspacing='1'>{''.join(rows)}</table>"
        )
        x_range, y_range = view_range
        x_padding = (x_range[1] - x_range[0]) * 0.04
        y_padding = (y_range[1] - y_range[0]) * 0.08
        hint_x = min(max(cursor_x, x_range[0] + x_padding), x_range[1] - x_padding)
        hint_y = min(max(point.y(), y_range[0] + y_padding), y_range[1] - y_padding)
        hint.setPos(hint_x, hint_y)
        line.show()
        hint.show()

'''
    return text[:method_start] + new_method + text[method_end:]


def apply(path: Path, patcher: Callable[[str], str]) -> None:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)
    if updated == original:
        print(f"No changes required: {path}")
        return
    path.write_text(updated, encoding="utf-8")
    print(f"Updated: {path}")


def main() -> int:
    apply(HISTOGRAM_PANEL, patch_histogram)
    apply(LINE_PROFILE_PANEL, patch_line_profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
