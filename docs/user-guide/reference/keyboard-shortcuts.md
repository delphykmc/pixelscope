# Keyboard Shortcuts

The focused widget determines which command receives a key. Actions may be disabled when their required source or analysis context is unavailable.

| Shortcut | Action / scope |
|---|---|
| `F1` | Open local context Help for the focused workspace or Settings/RAW/YUV dialog; otherwise guide home |
| `Ctrl+O` | Open Images |
| `Ctrl+Shift+O` | Open Folder |
| `Alt+F4` | Exit |
| `Ctrl+Shift+M` | Show/hide Memo, including from its floating window |
| `Ctrl+1` | Single View |
| `Ctrl+2` | Multi View |
| `M` | Show Selected in Multi View |
| `F` | Fit Image |
| `Ctrl+0` | 100% physical-pixel Zoom |
| `1` … `6` | Activate the corresponding visible slot on the Current Comparison Page |
| `T` | Cycle the last actual current-page source to Primary; Image View or Files focus; excludes Difference and split-derived tiles |
| `Left` / `Right` | Previous / next image in the complete ordered Selected set |
| `Ctrl+Left` / `Ctrl+Right` | Previous / next Comparison Page |
| `Up` / `Down` | Normal row navigation with Files tree focus |
| `PageUp` / `PageDown` | Previous / next Folder Position (application-wide) |
| `Alt+PageUp` / `Alt+PageDown` | Add same-position source from the nearest eligible previous / next registered folder |
| `Ctrl+A` | Select all in the focused Files tree or Memo ROI list |
| `Delete` | Remove selected Files registrations or selected Memo ROI records, according to focus; never delete original image files |
| `Esc` | Clear/cancel ROI interaction; in Memo also clears ROI-list selection and cancels pending Memo work |
| `Shift+Esc` | Clear Line Profile; use with the Line Profile tab current |
| `S` | Split Channels when applicable |
| `+` / `-` | Increase/decrease shared Display Gain by one step with Image View focus; Files tree expands/collapses instead |
| `Ctrl+C` | Copy selected Statistics table cells with table focus |

## Display Gain

The gain options are 1×, 2×, 4×, 8×, 16×. Select 1× to reset. See [Image View](../features/image-view.md#display-gain). Difference Gain is separate.

## Pointer gestures

- `Ctrl+drag`: create a shared ROI in Image View; Memo records the ROI when Record ROI is enabled.
- `Shift+drag`: define a horizontal or vertical Line Profile.

If a key appears inactive, click the relevant Image View, Files tree or analysis widget and check that the associated action is enabled.
