
import argparse
import os
import platform
import re
import shutil
import unicodedata
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from engine import Engine

DOUBLE_QUOTE_REGEX = re.compile(
    "|".join(["«", "‹", "»", "›", "„", "“", "‟", "”", "❝", "❞", "❮", "❯", "〝", "〞", "〟", "＂", "＂"])
)

SINGLE_QUOTE_REGEX = re.compile("|".join(["‘", "‛", "’", "❛", "❜", "`", "´", "‘", "’"]))

def remove_hieroglyphs_unicode(text: str) -> str:
    allowed_categories = {
        "Lu",  # Uppercase letter
        "Ll",  # Lowercase letter
        "Lt",  # Titlecase letter
        "Nd",  # Decimal number
        "Nl",  # Letter number
        "No",  # Other number
        "Pc",  # Connector punctuation
        "Pd",  # Dash punctuation
        "Ps",  # Open punctuation
        "Pe",  # Close punctuation
        "Pi",  # Initial punctuation
        "Pf",  # Final punctuation
        "Po",  # Other punctuation
        "Sm",  # Math symbol
        "Sc",  # Currency symbol
        "Zs",  # Space separator
    }

    result: list[str] = []

    for char in text:
        category = unicodedata.category(char)

        if category in allowed_categories:
            result.append(char)

    cleaned_text = "".join(result).strip()

    # Ensure no more than one consecutive whitespace (extra safety)
    cleaned_text = re.sub(r"\s{2,}", " ", cleaned_text)

    return cleaned_text

def apply_punctuation_and_spacing(text: str) -> str:
        # Remove extra spaces before punctuation
        text = re.sub(r"\s+([,.!?…])", r"\1", text)

        # Ensure single space after punctuation, except for multiple punctuation marks
        text = re.sub(r"([,.!?…])(?!\s)(?![,.!?…])", r"\1 ", text)

        # Remove space between multiple punctuation marks
        text = re.sub(r"([,.!?…])\s+([,.!?…])", r"\1\2", text)

        return text.strip()

def fix_quotes(text: str) -> str:
    text = SINGLE_QUOTE_REGEX.sub("'", text)
    text = DOUBLE_QUOTE_REGEX.sub('"', text)
    return text

def get_image_raw_bytes_and_dims(image_path: str) -> tuple[bytes, int, int] | None:

    try:
        with Image.open(image_path) as img:
            width = img.width
            height = img.height

        with open(image_path, 'rb') as file:
            raw_bytes = file.read()

        return (raw_bytes, width, height)

    except FileNotFoundError:
        print(f"Error: Image file not found at '{image_path}'")
        return None
    except UnidentifiedImageError:
        print(f"Error: Pillow (PIL) cannot identify '{image_path}' as an image. Cannot get dimensions.")
        return None
    except IOError as e:
        print(f"Error reading raw file bytes from '{image_path}': {e}")
        return None
    except Exception as e:
        # Add type hints to help static analysis if possible, but Exception is broad
        print(f"An unexpected error occurred processing '{image_path}': {e}")
        return None
            
def float_range(mini, maxi):
    """Return function handle of an argument type function for
    ArgumentParser checking a float range: mini <= arg <= maxi
      mini - minimum acceptable argument
      maxi - maximum acceptable argument"""

    # Define the function with default arguments
    def float_range_checker(arg):
        """New Type function for argparse - a float within predefined range."""

        try:
            f = float(arg)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a floating point number") from exc

        if f < mini or f > maxi:
            raise argparse.ArgumentTypeError(
                "must be in range [" + str(mini) + " .. " + str(maxi) + "]"
            )
        return f

    # Return function handle to checking function
    return float_range_checker

def engine_type(value_str):
    """
    Argparse type function for Engine enum.
    Performs case-insensitive matching.
    """
    try:
        return Engine(value_str.lower())
    except ValueError:
        valid_choices = ', '.join([e.value for e in Engine])
        raise argparse.ArgumentTypeError(
            f"invalid choice: '{value_str}' (choose from {valid_choices})")

def get_in_path(name: str) -> str:
    if platform.system() == "Windows":
        search_name = name + ".exe"

    try:
        path = shutil.which(search_name)
        # Scoop
        if platform.system() == "Windows":
            shim_path = shutil.which(f"{name}.shim")
            if shim_path:
                path = str(Path(shim_path).parents[1]) + r"\apps\videosubfinder\current\VideoSubFinderWXW.exe"
        if path and os.access(path, os.X_OK):
            return path
        else:
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None