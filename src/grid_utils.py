def assign_grid_ref(
    centroid_x: float,
    centroid_y: float,
    mosaic_width: int,
    mosaic_height: int,
    cols: int = 8,
    rows: int = 6
) -> str:
    """
    Converts pixel centroid to facade grid reference like B4 or C7.
    Rows A-F bottom to top, Columns 1-8 left to right.
    """
    col_idx = int((centroid_x / mosaic_width) * cols)
    row_idx = int((centroid_y / mosaic_height) * rows)

    col_idx = max(0, min(cols - 1, col_idx))
    row_idx = max(0, min(rows - 1, row_idx))

    # Invert row so A is bottom
    row_letter = chr(ord("A") + (rows - 1 - row_idx))
    col_number = col_idx + 1

    return f"{row_letter}{col_number}"
