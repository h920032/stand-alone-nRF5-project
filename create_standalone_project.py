import os
import shutil
import xml.etree.ElementTree as ET
import argparse
import sys
import re # Import regex for more robust replacements

# --- Configuration ---
SDK_FILES_SUBDIR = "sdk_files" # Subdirectory in the output folder to store copied SDK files
# ---

def resolve_path(original_proj_dir, rel_path):
    """Resolves the absolute path of a file/dir based on the original project directory."""
    # Normalize path separators for consistency
    rel_path_norm = os.path.normpath(rel_path)
    return os.path.abspath(os.path.join(original_proj_dir, rel_path_norm))

def create_target_path(output_dir, sdk_subdir, original_rel_path_xml):
    """
    Creates the target absolute path and the new relative path (for XML)
    within the output directory's sdk_subdir, preserving structure.
    Uses forward slashes for the new relative path in XML.
    """
    # Normalize separators for splitting, but keep original for replacement key
    path_parts = original_rel_path_xml.replace('\\', '/').split('/')
    rel_to_sdk_root_parts = [part for part in path_parts if part != '..']

    if not rel_to_sdk_root_parts:
        print(f"Warning: Could not determine relative SDK path for: {original_rel_path_xml}")
        # Fallback: use the original filename directly under sdk_subdir
        target_rel_path_unix = f"{sdk_subdir}/{os.path.basename(original_rel_path_xml)}"
    else:
        target_rel_path_unix = f"{sdk_subdir}/{'/'.join(rel_to_sdk_root_parts)}"

    # Create the absolute path using OS-specific separators
    target_abs_path = os.path.join(output_dir, *target_rel_path_unix.split('/'))

    return target_abs_path, target_rel_path_unix


def copy_item(src_abs_path, dest_abs_path):
    """Copies a file or directory, creating destination directories."""
    if not os.path.exists(src_abs_path):
        print(f"Warning: Source item not found, skipping: {src_abs_path}")
        return False

    dest_dir = os.path.dirname(dest_abs_path)
    os.makedirs(dest_dir, exist_ok=True)

    try:
        if os.path.isdir(src_abs_path):
            # Use copytree for directories, allow overwriting content
            shutil.copytree(src_abs_path, dest_abs_path, dirs_exist_ok=True)
            # print(f"Copied Dir: {src_abs_path} -> {dest_abs_path}")
        else:
            # Use copy2 for files (preserves metadata)
            shutil.copy2(src_abs_path, dest_abs_path)
            # print(f"Copied File: {src_abs_path} -> {dest_abs_path}")
        return True
    except Exception as e:
        print(f"Error copying {src_abs_path} to {dest_abs_path}: {e}")
        return False

def main(project_file_path, output_dir, makefile_dir=None): # Add makefile_dir parameter
    abs_project_file_path = os.path.abspath(project_file_path)
    original_proj_dir = os.path.dirname(abs_project_file_path)
    project_filename = os.path.basename(abs_project_file_path)

    # Determine the directory containing the Makefile
    if makefile_dir:
        original_makefile_base_dir = os.path.abspath(makefile_dir)
        print(f"Using specified Makefile directory: {original_makefile_base_dir}")
    else:
        original_makefile_base_dir = original_proj_dir # Default to project directory
        print(f"Using project directory for Makefile: {original_makefile_base_dir}")

    print(f"Input Project: {abs_project_file_path}")
    print(f"Output Directory: {os.path.abspath(output_dir)}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    sdk_files_abs_dir = os.path.join(output_dir, SDK_FILES_SUBDIR)
    os.makedirs(sdk_files_abs_dir, exist_ok=True)

    # Destination project file path
    dest_project_file_path = os.path.join(output_dir, project_filename)

    # --- Explicitly copy Makefile.common ---
    print("Copying common Makefile components...")
    makefile_common_rel_path_xml = '../../../../../../components/toolchain/gcc/Makefile.common'
    makefile_common_src_abs = resolve_path(original_proj_dir, makefile_common_rel_path_xml)
    # Determine destination path within sdk_files subdir
    makefile_common_dest_abs, _ = create_target_path(output_dir, SDK_FILES_SUBDIR, makefile_common_rel_path_xml)
    if copy_item(makefile_common_src_abs, makefile_common_dest_abs):
        print(f"  Copied Makefile.common to: {makefile_common_dest_abs}")
    else:
        print(f"  Warning: Failed to copy Makefile.common from: {makefile_common_src_abs}")
    # ---

    # --- Read Original Project Content ---
    try:
        with open(abs_project_file_path, 'r', encoding='utf-8') as f:
            original_project_content = f.read()
    except FileNotFoundError:
        print(f"Error: Project file not found at {abs_project_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading project file {abs_project_file_path}: {e}")
        sys.exit(1)

    # --- Parse Original Project File (for information only) ---
    try:
        # Use the original file path for parsing to get accurate info
        tree = ET.parse(abs_project_file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing project file XML structure (for analysis): {abs_project_file_path}. {e}")
        root = None # Indicate parsing failed, proceed with caution
    except Exception as e:
         print(f"Unexpected error parsing project file XML: {e}")
         root = None

    copied_items_abs = set() # Track absolute paths of copied items to avoid re-copying
    # Add the explicitly copied Makefile.common to the set to avoid re-copying if listed elsewhere
    if os.path.exists(makefile_common_src_abs):
        copied_items_abs.add(makefile_common_src_abs)

    paths_to_replace = {} # Store {original_path_in_xml: new_path_in_xml}

    # --- Copy Essential Local Dirs First (e.g., config) ---
    config_rel_path_xml = '../config' # Use XML style path for finding source
    config_src_abs_path = resolve_path(original_proj_dir, config_rel_path_xml)
    # Destination should be directly inside output_dir
    config_dest_abs_path = os.path.abspath(os.path.join(output_dir, 'config')) # Destination is output_dir/config
    config_copied = False
    if os.path.isdir(config_src_abs_path):
        print("Copying config directory...")
        if copy_item(config_src_abs_path, config_dest_abs_path):
            config_copied = True
            # Track the source absolute path to prevent re-copying its contents
            copied_items_abs.add(config_src_abs_path)
            # Add contained files using their source absolute paths
            for root_dir, _, files in os.walk(config_src_abs_path):
                 for file in files:
                     copied_items_abs.add(os.path.join(root_dir, file))
            # The path "../config" in the XML file's include paths usually remains correct
            # relative to the moved project file, so no replacement needed for the include path itself.
        else:
             print(f"  Failed to copy config directory: {config_src_abs_path}")


    if root is not None:
        # --- Process configurations (Common) - Copy SDK Include Dirs ---
        print("Analyzing and copying SDK include directories...")
        common_config = root.find(".//configuration[@Name='Common']")
        if common_config is not None:
            include_dirs_attr = 'c_user_include_directories'
            original_includes_str = common_config.get(include_dirs_attr, '')
            original_includes = original_includes_str.split(';')
            new_includes_list = [] # Build the new list for the attribute value
            needs_include_update = False

            for inc_path_xml in original_includes: # Path exactly as in XML (forward slashes expected)
                if not inc_path_xml: continue

                # Skip the specific path "../../../config" if found
                if inc_path_xml == '../../../config':
                    needs_include_update = True # Mark for update as we are removing an entry
                    print(f"Scheduled removal of include path: '{inc_path_xml}'")
                    continue # Skip adding this path to the new list

                src_abs_path = resolve_path(original_proj_dir, inc_path_xml)

                # Identify SDK include paths (heuristic: starts with ../../)
                is_sdk_include = inc_path_xml.startswith('../../')

                if is_sdk_include:
                    if os.path.isdir(src_abs_path): # Only copy if it's a directory
                        dest_abs_path, new_rel_path_xml = create_target_path(output_dir, SDK_FILES_SUBDIR, inc_path_xml)
                        if src_abs_path not in copied_items_abs:
                            print(f"Copying SDK include directory: {inc_path_xml}")
                            if copy_item(src_abs_path, dest_abs_path):
                                copied_items_abs.add(src_abs_path)
                                # Add contained files to avoid individual copying later
                                for root_dir, _, files in os.walk(src_abs_path):
                                    for file in files:
                                        copied_items_abs.add(os.path.join(root_dir, file))
                            else:
                                print(f"  Failed to copy SDK include directory: {src_abs_path}")
                        # else: Already copied (e.g., nested include paths)

                        # Always update the path in the list
                        new_includes_list.append(new_rel_path_xml)
                        if new_rel_path_xml != inc_path_xml:
                            needs_include_update = True
                    else:
                        # Path exists but isn't a directory, or doesn't exist
                        print(f"Warning: SDK include path is not a directory or not found, keeping original: {inc_path_xml}")
                        new_includes_list.append(inc_path_xml) # Keep original path
                elif inc_path_xml == '../config':
                    # Change local config include path from '../config' to 'config'
                    new_config_include_path = 'config' # Changed from './config' to just 'config' for consistency
                    new_includes_list.append(new_config_include_path)
                    if new_config_include_path != inc_path_xml:
                         needs_include_update = True
                         print(f"Scheduled include path update: '{inc_path_xml}' -> '{new_config_include_path}'")
                else:
                    # Keep other paths (e.g., '.') as they are relative to the project file
                    new_includes_list.append(inc_path_xml)

            # Store the replacement for the entire attribute value if needed
            if needs_include_update:
                new_includes_str = ';'.join(new_includes_list)
                # Store replacement using exact attribute=value format
                paths_to_replace[f'{include_dirs_attr}="{original_includes_str}"'] = f'{include_dirs_attr}="{new_includes_str}"'
                print(f"Scheduled update for {include_dirs_attr}")

            # --- Process <file> elements ---
            print("Analyzing and copying source files listed in <file> tags...")
            files_processed_count = 0
            for file_element in root.findall('.//file'):
                original_rel_path_xml = file_element.get('file_name') # Path exactly as in XML
                if not original_rel_path_xml: continue

                src_abs_path = resolve_path(original_proj_dir, original_rel_path_xml)

                # Check if this file is inside the config directory that was copied
                is_in_copied_config = False
                if config_copied and src_abs_path.startswith(config_src_abs_path + os.sep):
                    is_in_copied_config = True

                # Skip if already copied, UNLESS it's in the config dir (needs path update)
                if src_abs_path in copied_items_abs and not is_in_copied_config:
                    # print(f"Skipping already copied item: {original_rel_path_xml}")
                    continue

                # Heuristic check if it's an SDK file needing relocation
                is_sdk_file = original_rel_path_xml.startswith('../../')

                # Handle local files
                is_local_file = not is_sdk_file

                if is_sdk_file:
                    # Handle SDK files (copy to sdk_files, schedule path replacement)
                    dest_abs_path, new_rel_path_xml = create_target_path(output_dir, SDK_FILES_SUBDIR, original_rel_path_xml)
                    if src_abs_path not in copied_items_abs: # Avoid re-copying if part of copied include dir
                        if copy_item(src_abs_path, dest_abs_path):
                            copied_items_abs.add(src_abs_path)
                            files_processed_count += 1
                        else:
                            continue # Skip replacement if copy failed

                    # Always schedule replacement for SDK files
                    paths_to_replace[f'file_name="{original_rel_path_xml}"'] = f'file_name="{new_rel_path_xml}"'

                elif is_local_file:
                    # Handle local files (../main.c, flash_placement.xml, ../config/sdk_config.h etc.)
                    if is_in_copied_config:
                        # File was already copied as part of the config directory.
                        # Need to update its path relative to the new project location.
                        # Original: ../config/file.h -> New: config/file.h
                        # Remove the leading '../'
                        if original_rel_path_xml.startswith('../'):
                            new_rel_path_xml = original_rel_path_xml[3:] # Remove '../'
                            paths_to_replace[f'file_name="{original_rel_path_xml}"'] = f'file_name="{new_rel_path_xml}"'
                            print(f"Scheduled path update for config file: {original_rel_path_xml} -> {new_rel_path_xml}")
                        else:
                            # Path didn't start with ../, unlikely for config but handle defensively
                            print(f"Warning: Config file path '{original_rel_path_xml}' doesn't start with '../'. Path not updated.")
                        # No need to copy again or increment files_processed_count here
                    else:
                        # Local file NOT in the config dir (e.g., ../main.c, flash_placement.xml)
                        # Calculate destination relative to output_dir root, maintaining structure
                        dest_abs_path = os.path.abspath(os.path.join(output_dir, os.path.normpath(original_rel_path_xml)))
                        if copy_item(src_abs_path, dest_abs_path):
                            copied_items_abs.add(src_abs_path) # Mark source as handled
                            files_processed_count += 1
                        # No path change needed in XML for these files, as their relative path
                        # to the project file remains the same (e.g., ../main.c stays ../main.c)

            print(f"Analyzed and copied/processed {files_processed_count} individual source files.")

            # --- Process Other Paths (Linker Script, Debug Files) ---
            print("Analyzing and copying other configured paths...")
            path_attrs = [
                'linker_section_placement_file',
                'debug_additional_load_file',
                'debug_register_definition_file'
            ]
            for attr_name in path_attrs:
                original_path_xml = common_config.get(attr_name) # Path as in XML
                if not original_path_xml: continue

                src_abs_path = resolve_path(original_proj_dir, original_path_xml)

                # Skip if already copied
                if src_abs_path in copied_items_abs:
                     # Check if it's flash_placement.xml which might be listed here and also as a <file>
                     # If it was copied as a local file, its path doesn't need changing.
                     continue


                # Check if it's an SDK path or local path
                is_sdk_path = original_path_xml.startswith('../../')
                is_local_path = not is_sdk_path

                if is_sdk_path:
                    dest_abs_path, new_rel_path_xml = create_target_path(output_dir, SDK_FILES_SUBDIR, original_path_xml)
                    if copy_item(src_abs_path, dest_abs_path):
                        copied_items_abs.add(src_abs_path)
                        # Store attribute=value replacement pair
                        paths_to_replace[f'{attr_name}="{original_path_xml}"'] = f'{attr_name}="{new_rel_path_xml}"'
                        print(f"Scheduled update for {attr_name} path: {original_path_xml} -> {new_rel_path_xml}")
                elif is_local_path:
                    # e.g., flash_placement.xml (might be listed here too)
                    # Calculate destination relative to output_dir root
                    dest_abs_path = os.path.abspath(os.path.join(output_dir, os.path.normpath(original_path_xml)))
                    if copy_item(src_abs_path, dest_abs_path):
                        copied_items_abs.add(src_abs_path)
                    # No path change needed in XML attribute for these local files relative to project

        else:
             print("Warning: Could not find <configuration Name='Common'> for analysis.")

    else:
        print("Skipping XML analysis due to parsing errors. Only directory copies performed.")


    # --- Perform String Replacements on Content ---
    print("Performing path replacements in project file content...")
    modified_project_content = original_project_content
    replacement_count = 0
    # Sort replacements by length descending to handle nested paths correctly
    sorted_replacements = sorted(paths_to_replace.items(), key=lambda item: len(item[0]), reverse=True)

    for original_attr_val, new_attr_val in sorted_replacements:
        # Use regex to replace attribute="value" safely, handling potential variations
        # Escape special regex characters in the original value part
        original_value = original_attr_val.split('="', 1)[1][:-1] # Extract value
        attr_name = original_attr_val.split('="', 1)[0]
        # Pattern: attr_name="<escaped_original_value>"
        # Need to escape regex metacharacters in the value being searched for
        pattern = re.escape(attr_name) + r'="' + re.escape(original_value) + r'"'

        # Perform replacement using re.sub for safety
        modified_project_content_new, num_subs = re.subn(pattern, new_attr_val, modified_project_content, flags=re.IGNORECASE)

        if num_subs > 0:
            modified_project_content = modified_project_content_new
            print(f"  Replaced {num_subs} instance(s) of '{original_attr_val}' with '{new_attr_val}'")
            replacement_count += num_subs
        # else:
        #     print(f"  Info: Did not find '{original_attr_val}' for replacement.")

    # --- Final generic SDK path replacement ---
    print(f"Performing final generic SDK path replacement ('../../../../../../' -> '{SDK_FILES_SUBDIR}/')...")
    generic_sdk_prefix = "../../../../../../"
    new_sdk_prefix = f"{SDK_FILES_SUBDIR}/"
    count_before = modified_project_content.count(generic_sdk_prefix)
    modified_project_content = modified_project_content.replace(generic_sdk_prefix, new_sdk_prefix)
    count_after = modified_project_content.count(generic_sdk_prefix) # Should be 0 if all replaced
    generic_replacements_made = count_before - count_after
    if generic_replacements_made > 0:
        print(f"  Replaced {generic_replacements_made} instance(s) of '{generic_sdk_prefix}' with '{new_sdk_prefix}'")
        replacement_count += generic_replacements_made

    # --- Write Modified Content to Destination ---
    # The DOCTYPE and comments are preserved because we started with original_project_content
    if replacement_count > 0:
        print(f"Total replacements made: {replacement_count}")
        try:
            with open(dest_project_file_path, 'w', encoding='utf-8') as f:
                f.write(modified_project_content)
            print(f"Successfully saved modified project file: {dest_project_file_path}")
        except Exception as e:
            print(f"Error writing modified project file {dest_project_file_path}: {e}")
            sys.exit(1) # Exit if writing fails
    else:
        # If no replacements were needed, just copy the original file
        try:
             shutil.copy2(abs_project_file_path, dest_project_file_path)
             print("No path replacements needed. Copied original project file.")
        except Exception as e:
             print(f"Error copying original project file {abs_project_file_path} to {dest_project_file_path}: {e}")
             sys.exit(1)

    # --- Copy and Modify Makefile ---
    print("Copying and modifying Makefile...")
    # Use the determined base directory for the Makefile
    original_makefile_path = os.path.join(original_makefile_base_dir, 'Makefile')
    dest_makefile_path = os.path.join(output_dir, 'Makefile')

    if os.path.isfile(original_makefile_path):
        try:
            shutil.copy2(original_makefile_path, dest_makefile_path)
            print(f"  Copied Makefile from '{original_makefile_path}' to: {dest_makefile_path}")

            # --- Copy Linker Script (.ld file) ---
            linker_script_copied = False
            for item in os.listdir(original_makefile_base_dir):
                if item.endswith(".ld"):
                    original_linker_script_path = os.path.join(original_makefile_base_dir, item)
                    dest_linker_script_path = os.path.join(output_dir, item)
                    if os.path.isfile(original_linker_script_path):
                        shutil.copy2(original_linker_script_path, dest_linker_script_path)
                        print(f"  Copied Linker Script from '{original_linker_script_path}' to: {dest_linker_script_path}")
                        linker_script_copied = True
                        break # Assume only one relevant .ld file
            if not linker_script_copied:
                print(f"  Warning: No linker script (.ld file) found in '{original_makefile_base_dir}'.")
            # --- End Linker Script Copy ---

            # Read the copied Makefile content
            with open(dest_makefile_path, 'r', encoding='utf-8') as f:
                makefile_lines = f.readlines()

            modified_makefile_lines = []
            sdk_root_updated = False
            proj_dir_defined = False
            cflags_inserted = False # Flag to track CFLAGS insertion

            # Define the new PROJ_DIR and SDK_ROOT lines
            new_proj_dir_line = 'PROJ_DIR := ./\n'
            new_sdk_root_definition = f'SDK_ROOT := $(PROJ_DIR)/{SDK_FILES_SUBDIR}\n'
            original_sdk_root_pattern = r'^SDK_ROOT\s*:=\s*\.\./\.\./\.\./\.\./\.\./\.\.'
            target_cflags_line = 'CFLAGS += -fno-builtin -fshort-enums' # Line to insert after

            for line in makefile_lines:
                # Check if the line defines SDK_ROOT
                match = re.match(original_sdk_root_pattern, line)
                if match and not sdk_root_updated:
                    # Insert PROJ_DIR before SDK_ROOT if not already done
                    if not proj_dir_defined:
                        modified_makefile_lines.append(new_proj_dir_line)
                        proj_dir_defined = True
                        print(f"  Defined PROJ_DIR in Makefile.")
                    # Replace the SDK_ROOT line
                    modified_makefile_lines.append(new_sdk_root_definition)
                    sdk_root_updated = True
                    print(f"  Updated SDK_ROOT path in Makefile.")
                else:
                    # Keep the original line
                    modified_makefile_lines.append(line)

                # Check if this is the line to insert CFLAGS after
                if line.strip() == target_cflags_line:
                    modified_makefile_lines.append('CFLAGS += -Wall -Werror\n')
                    modified_makefile_lines.append('CFLAGS += -Wno-array-bounds\n')
                    cflags_inserted = True
                    print(f"  Inserted additional CFLAGS after '{target_cflags_line}'.")

            # If SDK_ROOT wasn't found/updated, add PROJ_DIR and SDK_ROOT at the beginning (or a suitable place)
            if not sdk_root_updated:
                 print(f"  Warning: Original SDK_ROOT pattern not found. Adding PROJ_DIR and new SDK_ROOT definition near the top.")
                 # Insert after the first few lines (e.g., after PROJECT_NAME) or at the beginning
                 insert_pos = 0
                 for i, line in enumerate(modified_makefile_lines):
                     if line.startswith('PROJECT_NAME'):
                         insert_pos = i + 1
                         break
                 if not proj_dir_defined:
                     modified_makefile_lines.insert(insert_pos, new_proj_dir_line)
                     proj_dir_defined = True
                 modified_makefile_lines.insert(insert_pos + 1, new_sdk_root_definition)

            # Report if CFLAGS insertion failed
            if not cflags_inserted:
                print(f"  Warning: Target line '{target_cflags_line}' not found. Additional CFLAGS were not inserted.")

            modified_makefile_content = "".join(modified_makefile_lines)

            # --- Apply other Makefile modifications (config paths) ---
            # Ensure config paths use PROJ_DIR relative to the Makefile location
            # Replace '-I../config' with '-I$(PROJ_DIR)/config'
            original_config_include_pattern = r'(-I)\.\./config'
            new_config_include = r'\1$(PROJ_DIR)/config' # Use PROJ_DIR
            modified_makefile_content, num_config_inc_subs = re.subn(
                original_config_include_pattern,
                new_config_include,
                modified_makefile_content
            )
            if num_config_inc_subs > 0:
                print(f"  Updated {num_config_inc_subs} config include path(s) in Makefile.")

            # Replace '../config/sdk_config.h' with '$(PROJ_DIR)/config/sdk_config.h'
            # Make the pattern more general for any file within ../config/
            original_config_file_pattern = r'\.\./config/([^\s]+)' # Match ../config/ followed by non-whitespace chars
            new_config_file = r'$(PROJ_DIR)/config/\1' # Use PROJ_DIR
            modified_makefile_content, num_config_file_subs = re.subn(
                original_config_file_pattern,
                new_config_file,
                modified_makefile_content
            )
            if num_config_file_subs > 0:
                print(f"  Updated {num_config_file_subs} config file path(s) in Makefile.")

            # Replace '../config \' with '$(PROJ_DIR)/config \'
            original_config_dir_pattern = r'\.\./config \\\n' # Match '../config \' at the end of a line
            new_config_dir = r'$(PROJ_DIR)/config \\\n' # Use PROJ_DIR
            modified_makefile_content, num_config_dir_subs = re.subn(
                original_config_dir_pattern,
                new_config_dir,
                modified_makefile_content
            )
            if num_config_dir_subs > 0:
                print(f"  Updated {num_config_dir_subs} '../config \\' path(s) in Makefile.")

            # --- Add step to replace "$(PROJ_DIR)/main.c " with "$(SDK_ROOT)/main.c " ---
            original_main_c_pattern = r'\$\(PROJ_DIR\)/main\.c '
            new_main_c_path = r'$(SDK_ROOT)/main.c '
            modified_makefile_content, num_main_c_subs = re.subn(
                original_main_c_pattern,
                new_main_c_path,
                modified_makefile_content
            )
            if num_main_c_subs > 0:
                print(f"  Updated {num_main_c_subs} 'main.c' path(s) in Makefile.")

            # --- End of other modifications ---

            # Write the modified content back
            with open(dest_makefile_path, 'w', encoding='utf-8') as f:
                f.write(modified_makefile_content)
            print(f"  Successfully modified Makefile: {dest_makefile_path}")

        except Exception as e:
            print(f"Error processing Makefile {original_makefile_path}: {e}")
    else:
        print(f"Warning: Makefile not found at {original_makefile_path}. Skipping Makefile processing.")

    # --- Modify Makefile ---
    print("Modifying Makefile...")
    makefile_path = os.path.join(output_dir, 'Makefile')

    if os.path.isfile(makefile_path):
        try:
            with open(makefile_path, 'r', encoding='utf-8') as f:
                makefile_lines = f.readlines()

            modified_makefile_lines = []
            for line in makefile_lines:
                # Remove the line defining PROJ_DIR
                if line.strip().startswith('PROJ_DIR := ../../..'):
                    print(f"  Removed line defining PROJ_DIR: {line.strip()}")
                    continue  # Skip adding this line to the modified content
                modified_makefile_lines.append(line)

            # Write the modified content back
            with open(makefile_path, 'w', encoding='utf-8') as f:
                f.writelines(modified_makefile_lines)

            print("Successfully removed PROJ_DIR definition from Makefile.")

        except Exception as e:
            print(f"Error modifying Makefile: {e}")

    # --- Modify Makefile.posix ---
    print("Modifying Makefile.posix...")
    # Construct the expected path within the output directory
    makefile_posix_rel_path = os.path.join(SDK_FILES_SUBDIR, 'components', 'toolchain', 'gcc', 'Makefile.posix')
    makefile_posix_abs_path = os.path.join(output_dir, makefile_posix_rel_path)

    if os.path.isfile(makefile_posix_abs_path):
        try:
            with open(makefile_posix_abs_path, 'r', encoding='utf-8') as f:
                posix_content = f.read()

            original_gcc_path = "/usr/local/gcc-arm-none-eabi-9-2020-q2-update/bin/"
            new_gcc_path = "/usr/local/bin/" # Only replace the directory part

            modified_posix_content = posix_content.replace(original_gcc_path, new_gcc_path)

            if modified_posix_content != posix_content:
                with open(makefile_posix_abs_path, 'w', encoding='utf-8') as f:
                    f.write(modified_posix_content)
                print(f"  Updated GNU toolchain path in: {makefile_posix_abs_path}")
            else:
                print(f"  GNU toolchain path already correct or not found in: {makefile_posix_abs_path}")

        except Exception as e:
            print(f"Error processing Makefile.posix {makefile_posix_abs_path}: {e}")
    else:
        print(f"Warning: Makefile.posix not found at {makefile_posix_abs_path}. Skipping modification.")
        # Check if Makefile.common exists as a fallback check
        makefile_common_check_path = os.path.join(output_dir, SDK_FILES_SUBDIR, 'components', 'toolchain', 'gcc', 'Makefile.common')
        if not os.path.isfile(makefile_common_check_path):
             print(f"  Also note: Makefile.common not found at expected location. Toolchain files might be missing.")


    print("Standalone project creation process finished.")
    print(f"Output located at: {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a standalone Segger Embedded Studio project.')
    parser.add_argument('project_file', help='Path to the source .emProject file.')
    parser.add_argument('output_dir', help='Path to the directory where the standalone project will be created.')
    # Add the optional makefile directory argument
    parser.add_argument('--makefile-dir', help='Optional path to the directory containing the Makefile. Defaults to the project file directory.')

    args = parser.parse_args()

    if not os.path.isfile(args.project_file):
        print(f"Error: Project file not found at {args.project_file}")
        sys.exit(1)

    # Pass the makefile_dir argument to main
    main(args.project_file, args.output_dir, args.makefile_dir)
