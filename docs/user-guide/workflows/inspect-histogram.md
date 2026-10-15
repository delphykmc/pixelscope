# Inspect a Histogram

Histogram shows the value distribution of the sources on the Current Comparison Page.

## Open Histogram

Open the **Plots** workspace and select **Histogram**. With no ROI, Histogram analyzes the full image. With an ROI, it analyzes the shared ROI and reports that context in the controls.

## Compare sources

Use Multi View when you want the visible image set and plotted distributions to correspond directly. Channel choices depend on the source family: standard RGB/Gray, Bayer/RAW, and native YUV do not expose identical channel semantics.

Changing the Current Comparison Page changes the page-bounded analysis set.

While a new calculation is pending, the previous graph stays visible and is marked **Previous result**. Its hover readouts and Histogram export are unavailable until the current result is ready. If calculation fails, the previous graph remains marked and the error appears in Analysis. Clearing the selection clears the graph.

Analysis keeps space for its status and progress indicator when calculation finishes, so the table does not shift as the progress bar appears or disappears. Switching between Separate and Overlay can still resize the graph panes.

## Related tasks

Use [Statistics](../features/statistics.md) for scalar metrics and [Line Profile](inspect-line-profile.md) for spatial variation along one line.

## Troubleshooting keywords

**histogram empty**, **full image**, **ROI histogram**, **channel**, **Current Comparison Page**.
