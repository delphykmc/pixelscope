"""Continuous pixel-edge geometry for Remote IQA grids."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from pixelscope.remote.iqa_domain import GridGeometry, SceneGeometry


def _matrix(geometry: SceneGeometry) -> NDArray[np.float64]:
    matrix = np.asarray(geometry.source_to_analysis, dtype=np.float64)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("source_to_analysis must be a finite 3x3 affine")
    if not np.allclose(matrix[2], np.asarray([0.0, 0.0, 1.0])):
        raise ValueError("source_to_analysis last row must be [0, 0, 1]")
    if abs(float(np.linalg.det(matrix))) <= np.finfo(np.float64).eps:
        raise ValueError("source_to_analysis must be invertible")
    return matrix


def source_to_analysis(geometry: SceneGeometry, points: NDArray[np.float64]) -> NDArray[np.float64]:
    return _transform(_matrix(geometry), points)


def analysis_to_source(geometry: SceneGeometry, points: NDArray[np.float64]) -> NDArray[np.float64]:
    return _transform(np.linalg.inv(_matrix(geometry)), points)


def _transform(matrix: NDArray[np.float64], points: NDArray[np.float64]) -> NDArray[np.float64]:
    coordinates = np.asarray(points, dtype=np.float64)
    if coordinates.ndim != 2 or coordinates.shape[1] != 2:
        raise ValueError("points must have shape (N, 2)")
    homogeneous = np.column_stack((coordinates, np.ones(coordinates.shape[0])))
    return (matrix @ homogeneous.T).T[:, :2]


def analysis_cell_polygon(grid: GridGeometry, row: int, column: int) -> NDArray[np.float64]:
    if row < 0 or row >= grid.rows or column < 0 or column >= grid.columns:
        raise IndexError("grid cell outside declared grid")
    left = grid.origin_x + column * grid.block_width
    top = grid.origin_y + row * grid.block_height
    right = left + grid.block_width
    bottom = top + grid.block_height
    return np.asarray(
        [[left, top], [right, top], [right, bottom], [left, bottom]], dtype=np.float64
    )


def source_cell_polygon(
    geometry: SceneGeometry,
    grid: GridGeometry,
    row: int,
    column: int,
    source_width: int,
    source_height: int,
) -> NDArray[np.float64]:
    mapped = analysis_to_source(geometry, analysis_cell_polygon(grid, row, column))
    return _clip_to_source(mapped, float(source_width), float(source_height))


Point = NDArray[np.float64]
Inside = Callable[[Point], bool]
Intersection = Callable[[Point, Point], Point]


def _clip_edge(points: list[Point], inside: Inside, intersection: Intersection) -> list[Point]:
    if not points:
        return []
    output: list[Point] = []
    previous = points[-1]
    previous_inside = inside(previous)
    for current in points:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                output.append(intersection(previous, current))
            output.append(current)
        elif previous_inside:
            output.append(intersection(previous, current))
        previous = current
        previous_inside = current_inside
    return output


def _vertical_intersection(a: Point, b: Point, x: float) -> Point:
    factor = (x - a[0]) / (b[0] - a[0])
    return np.asarray([x, a[1] + factor * (b[1] - a[1])], dtype=np.float64)


def _horizontal_intersection(a: Point, b: Point, y: float) -> Point:
    factor = (y - a[1]) / (b[1] - a[1])
    return np.asarray([a[0] + factor * (b[0] - a[0]), y], dtype=np.float64)


def _clip_to_source(polygon: NDArray[np.float64], width: float, height: float) -> Point:
    """Sutherland-Hodgman clipping in continuous source pixel-edge coordinates."""
    vertices = [np.asarray(point, dtype=np.float64) for point in polygon]
    vertices = _clip_edge(
        vertices,
        lambda point: bool(point[0] >= 0.0),
        lambda a, b: _vertical_intersection(a, b, 0.0),
    )
    vertices = _clip_edge(
        vertices,
        lambda point: bool(point[0] <= width),
        lambda a, b: _vertical_intersection(a, b, width),
    )
    vertices = _clip_edge(
        vertices,
        lambda point: bool(point[1] >= 0.0),
        lambda a, b: _horizontal_intersection(a, b, 0.0),
    )
    vertices = _clip_edge(
        vertices,
        lambda point: bool(point[1] <= height),
        lambda a, b: _horizontal_intersection(a, b, height),
    )
    return np.vstack(vertices) if vertices else np.empty((0, 2), dtype=np.float64)
