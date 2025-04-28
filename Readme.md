# Standalone Segger Embedded Studio Project Creator

This Python script (`create_standalone_project.py`) converts a Segger Embedded Studio (`.emProject`) project that relies on the nRF5 SDK into a self-contained, standalone project. It copies all necessary SDK source files, header files, Makefiles, and configuration files into a specified output directory and updates the project file and Makefiles to use these local copies.

## Purpose

The goal is to create a project folder that can be built (using SES or `make`) without needing the original nRF5 SDK installation present at its original location. This is useful for:

*   Archiving projects.
*   Sharing projects with others who might not have the exact SDK version or directory structure.
*   Version controlling the exact SDK components used by a specific project version.

## How it Works

1.  **Parses Project File:** Reads the input `.emProject` file to identify source files, include directories, and other referenced files (like linker scripts, SoftDevice hex).
2.  **Copies Files:**
    *   Copies essential local files/directories (like `main.c`, `config/`, `flash_placement.xml`) relative to the original project location into the output directory.
    *   Copies SDK files and directories referenced in the project file into a `sdk_files` subdirectory within the output directory, preserving the SDK's internal structure.
    *   Explicitly copies common GCC toolchain Makefiles (`Makefile.common`, `Makefile.posix`).
3.  **Modifies Project File:** Updates the paths within the copied `.emProject` file (`c_user_include_directories`, `file_name`, `linker_section_placement_file`, etc.) to point to the new locations within the output directory (primarily under `sdk_files/`).
4.  **Copies & Modifies Makefile:**
    *   Copies the project's `Makefile` (found either in the project directory or a specified `--makefile-dir`) to the output directory.
    *   Modifies the copied `Makefile` to:
        *   Define `PROJ_DIR := ./`.
        *   Update `SDK_ROOT` to point to the local `sdk_files` directory (`$(PROJ_DIR)/sdk_files`).
        *   Update include paths and source file paths (like `../config` to `$(PROJ_DIR)/config`, `../main.c` to `$(PROJ_DIR)/main.c`).
    *   Modifies the copied `Makefile.posix` (within `sdk_files`) to adjust the default GCC toolchain path if necessary.

## Usage

Run the script from your terminal:

```bash
python create_standalone_project.py <path_to_project.emProject> <output_directory> [--makefile-dir <path_to_makefile_dir>]
```

**Arguments:**

*   `<path_to_project.emProject>`: **Required**. The full path to the source Segger Embedded Studio project file you want to make standalone.
*   `<output_directory>`: **Required**. The path to the directory where the standalone project will be created. This directory will be created if it doesn't exist.
*   `--makefile-dir <path_to_makefile_dir>`: **Optional**. Specifies the directory containing the `Makefile` to be copied and modified. If omitted, the script assumes the `Makefile` is in the same directory as the `.emProject` file.

**Example:**

Assuming:
*   Your project file is at `ses/my_project.emProject`.
*   Your Makefile is at `../Makefile`.
*   You want the standalone project created in a new folder named `my_project_standalone`.

```bash
python create_standalone_project.py ses/my_project.emProject my_project_standalone --makefile-dir ..
```

This will create the `my_project_standalone` directory containing the modified project file, the modified Makefile, local source files (like `main.c`), the `config` directory, and the `sdk_files` directory with all necessary SDK components. You can then zip `my_project_standalone` or add it to version control.
