import pickle
import sys


def verify_pickle_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        return

    # Check if data is a dictionary with required keys
    required_keys = {'onsets', 'offsets', 'labels'}
    if not isinstance(data, dict):
        print("Error: Pickle file does not contain a dictionary.")
        return
    if not required_keys.issubset(data.keys()):
        print(
            f"Error: Dictionary is missing required keys. Expected keys: {required_keys}, Found keys: {set(data.keys())}")
        return

    # Extract values
    onsets = data.get('onsets', [])
    offsets = data.get('offsets', [])
    labels = data.get('labels', [])

    # Check if onsets and offsets are lists of floats
    if not (isinstance(onsets, list) and all(isinstance(x, float) for x in onsets)):
        print("Error: 'onsets' must be a list containing only floats.")
        return
    if not (isinstance(offsets, list) and all(isinstance(x, float) for x in offsets)):
        print("Error: 'offsets' must be a list containing only floats.")
        return

    # Check if labels is a list of strings
    if not (isinstance(labels, list) and all(isinstance(x, str) for x in labels)):
        print("Error: 'labels' must be a list containing only strings.")
        return

    # Check length constraints
    if len(onsets) != len(offsets):
        print(
            f"Error: 'onsets' and 'offsets' must have the same number of elements. Found {len(onsets)} and {len(offsets)}.")
        return
    if len(labels) > len(onsets):
        print(
            f"Error: 'labels' must have equal or fewer elements than 'onsets'. Found {len(labels)} labels and {len(onsets)} onsets.")
        return

    # Check onset < offset for each pair
    for i, (onset, offset) in enumerate(zip(onsets, offsets)):
        if onset >= offset:
            print(
                f"Error: 'onsets' entry at index {i} ({onset}) must be smaller than corresponding 'offsets' entry ({offset}).")
            return

    print("Pickle file is valid.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python verify_pickle.py <pickle_file>")
    else:
        verify_pickle_file(sys.argv[1])
