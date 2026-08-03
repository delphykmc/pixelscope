# Current PixelScope UI captures

These images document the current implementation, not historical design stages.
All captures are generated deterministically on Windows by
`scripts/capture_ui_review.py`.

| Capture | State |
| --- | --- |
| `empty_state.png` | Initial drop/open guidance |
| `single_image.png` | Single image, Files tree, and Statistics |
| `three_image_multiview.png` | Top Focus three-image layout (2:1 rows) |
| `five_image_multiview.png` | Top Focus five-image layout (2:1:1 rows) |
| `six_image_multiview.png` | Top Focus six-image 2-column raster |
| `three_image_left_focus.png` | Left Focus three-image layout (2:1 columns) |
| `five_image_left_focus.png` | Left Focus five-image layout (2:1:1 columns) |
| `six_image_left_focus.png` | Left Focus six-image 3-column raster |
| `difference_analysis.png` | Difference controls, metrics, and Diff view |
| `histogram_docked.png` | Full-width docked histogram |
| `line_profile_docked.png` | Shared line and docked Line Profile |
| `plots_floating.png` | Floating Plots window and custom title controls |
| `raw_profile_dialog.png` | RAW confirmation dialog without editable name |

Regenerate from the repository root:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe scripts\capture_ui_review.py docs\ui
```

The script requires an existing output directory. Replace old captures rather
than retaining stage-specific screenshots.
