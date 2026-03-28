# fastSeek

**fastSeek** is a desktop video frame browser built for **fast manual frame selection**.

It was created for workflows where the main priority is to **move through a video quickly**, inspect frames interactively, and then **export exact frames** for downstream use such as **DeepLabCut labeling**.

The current implementation focuses on a simple idea:

- use a **preview-sized decoding path** for responsive browsing
- keep browsing responsive with **background decoding, caching, and prefetch**
- export the selected frame as an **exact full-resolution PNG**

---

## Why fastSeek exists

When selecting frames from behavioral videos, the bottleneck is often not export quality, but **interactive navigation speed**.

For labeling workflows, I usually want to:

1. open a long video
2. move through frames quickly
3. inspect candidate moments
4. export the exact frame I want

Most general-purpose viewers are not designed around that workflow.  
**fastSeek** is being developed as a lightweight tool that prioritizes **fast seeking first** and **exact export second**.

This makes it especially useful for computer-vision annotation workflows such as:

- DeepLabCut frame selection
- manual inspection of behavioral recordings
- quick extraction of representative frames from long videos

---

## Current status

This project is already a **working GUI application**, but it is still in **early development**.

At the moment, fastSeek already includes:

- video loading from a desktop file dialog
- optional launch with a video path from the command line
- frame stepping with buttons and keyboard shortcuts
- slider-based scrubbing
- jump-to-frame by frame number
- responsive preview rendering
- background loading and background decoding
- preview frame caching
- directional prefetch around the requested frame
- export of the current frame as a PNG

The current emphasis is:

> **very fast interactive preview now, exact full-resolution export later**

That is the core design principle of the project.

---

## How it works

fastSeek uses two different paths for two different jobs.

### 1. Preview path: interactive browsing

Interactive browsing uses a **preview-sized Decord reader**.  
Frames shown in the GUI are decoded at preview resolution so the application can stay responsive while scrubbing and stepping through long videos.

To support that, the application uses:

- a background `LoaderWorker` to open the file, read metadata, compute preview dimensions, and decode the first preview frame
- a `VideoSession` that wraps a preview-sized `decord.VideoReader`
- a `DecodeWorker` running in the background
- an LRU `FrameCache` for preview RGB frames
- directional prefetch around the current request

### 2. Export path: exact frame extraction

Export uses a separate full-resolution reader.

This means the frame shown during browsing is optimized for speed, while the exported frame is read from the original video and saved as a **PNG**.  
That preserves the intended “browse fast, export exact” behavior.

---

## Architecture

Project structure:
````markdown
FastSeek/
│   run_fastseek.bat
│
└───src
    ├───app
    │   run_fastseek.py
    ├───config
    ├───core
    │   decode_worker.py
    │   export_session.py
    │   export_worker.py
    │   frame_cache.py
    │   loader_worker.py
    │   video_session.py
    ├───tests
    └───ui
        main_window.py
````

## Current interface

The current GUI includes:

* **Open** button
* **previous / next** frame buttons
* **frame number** text box
* **Export Frame** button
* image preview area
* loading labels and progress bar
* slider for scrubbing
* info and status labels

### Keyboard shortcuts

* `Left` → step `-1`
* `Right` → step `+1`
* `Shift+Left` → step `-10`
* `Shift+Right` → step `+10`
* `Ctrl+Left` → step `-100`
* `Ctrl+Right` → step `+100`

---

## Export behavior

Export currently saves the selected frame as:

* **PNG**
* inside a subfolder named after the source video
* with zero-padded names like `img000123.png`

This naming style is convenient for annotation and dataset-building workflows.

---

## Installation

Create and activate your Python environment, then install the required packages.

Example:

```bash
pip install pyside6 decord opencv-python numpy
```

If you prefer, install them inside your existing project environment.

---

## Running the program

### From Python

```bash
python -m src.app.run_fastseek
```

### With a video path

```bash
python -m src.app.run_fastseek path/to/video.mp4
```

### From the batch file

```bat
run_fastseek.bat
```

---

## Typical use case

A typical workflow for me is:

1. open a behavioral video
2. scrub quickly to candidate moments
3. step frame-by-frame around the moment of interest
4. export the exact frame
5. use the exported PNG in a labeling workflow such as DeepLabCut

---

## Design goals

The project is being shaped around a few practical priorities:

* **fast interactive browsing**
* **clear separation between preview and export**
* **simple desktop workflow**
* **frame-accurate manual selection**
* **easy integration with labeling pipelines**

This is not intended to be a full video editor.
It is a focused research/annotation utility.

---

## Limitations of the current version

The current version is intentionally minimal.

At this stage, fastSeek does **not** yet provide:

* multi-frame bookmarking / selection sets
* batch export of many selected frames
* timeline thumbnails
* exact timestamp tools
* project/session save files
* duplicate-frame filtering
* direct DeepLabCut project integration

Those are natural future directions.

---

## Planned next steps

Planned or likely future improvements include:

* bookmark selected frames instead of exporting one-by-one
* batch export of marked frames
* cleaner export pipeline
* better session/state handling
* packaging into a standalone executable
* richer controls for large-step navigation
* optional metadata panel
* improved test coverage

---

## Motivation in the broader workflow

This project complements a behavioral analysis workflow where video handling needs to be practical and fast.

In the same spirit as research utilities like **Behavython**, fastSeek is meant to solve a narrow but real problem well:
**quickly finding and extracting the right frames from long videos**.

---
