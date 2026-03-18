#!/bin/bash

# 1. Check if a URL argument was provided
if [ -z "$1" ]; then
    echo "Usage: $0 <website_url>"
    exit 1
fi

# Ensure required directories exist (create if missing)
for dir in csv html csv_old; do
    mkdir -p "$dir"
done


URL="$1"
HTML_FILE=$(date +"%Y%m%d%H%M%S").html

echo "Attempting to download: $URL"

# Helper function to handle errors cleanly
handle_error() {
    echo "Error: Download failed. Please check your internet connection or URL."
    rm -f "$HTML_FILE" 2>/dev/null # Clean up empty file if exists
    exit 1
}

# 2. Check for installed tools and attempt download with priority: curl -> wget

if command -v curl &> /dev/null; then
    echo "Attempting download with curl..."
    # -L: follow redirects, -s: silent, -S: show errors if silent is on
    # --user-agent: avoid blocks from sites that block non-browsers
    if curl -L -s -S -o "$HTML_FILE" --user-agent="Mozilla/5.0" "$URL"; then
        echo "Download successful with curl."
    else
        echo "curl failed. Attempting fallback to wget..."
        rm -f "$HTML_FILE"
        # Fallback 1: Use wget if curl fails
        if command -v wget &> /dev/null; then
            if wget -q --no-check-certificate -O "$HTML_FILE" "$URL"; then
                echo "Download successful with wget (fallback)."
            else
                handle_error
            fi
        else
            handle_error
        fi
    fi

elif command -v wget &> /dev/null; then
    echo "curl not found. Attempting download with wget..."
    # Use wget directly
    if wget -q --no-check-certificate -O "$HTML_FILE" "$URL"; then
        echo "Download successful with wget."
    else
        handle_error
    fi

else
    echo "Error: Neither 'curl' nor 'wget' is installed on this system."
    exit 1
fi

# 3. Validate the downloaded file
if [ ! -s "$HTML_FILE" ]; then
    echo "Error: Downloaded file is empty or invalid."
    rm -f "$HTML_FILE"
    handle_error
fi

echo "File saved as: $HTML_FILE"
echo "Running Python table extractor script on file..."

# 4. Run Python script if it exists
if [ -f "html_table_to_csv.py" ]; then
    python3 html_table_to_csv.py "$HTML_FILE"
else
    echo "Warning: 'html_table_to_csv.py' not found in current directory."
fi

# Move CSVs (only if any exist—avoids mv error)
if compgen -G "*.csv" > /dev/null 2>&1; then
    mv *.csv csv/
else
    echo "No .csv files found to move."
fi

# Move HTMLs
if compgen -G "*.html" > /dev/null 2>&1; then
    mv *.html html/
else
    echo "No .html files found to move."
fi

# Remove all HTMLs from html/ (force to avoid error if empty)
rm -f html/*.html || true

# Run Python script (check existence first)
if [[ ! -x "$(command -v python3)" ]]; then
    echo "Error: python3 not found. Aborting." >&2
    exit 1
fi

if [[ ! -f batch_csv_checker.py ]]; then
    echo "Error: batch_csv_checker.py not found in current directory." >&2
    exit 1
fi

python3 batch_csv_checker.py

# Move remaining CSVs to csv_old/ (only if any exist)
if compgen -G "csv/*.csv" > /dev/null 2>&1; then
    mv csv/*.csv csv_old/
else
    echo "No .csv files in csv/ directory to move."
fi
