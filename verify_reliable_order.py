import re
import sys # Import the sys module to access command-line arguments

def check_reliable_sequence(log_file_path):
    """
    Reads a log file and verifies that for channel=Reliable,
    the seq number is always increasing.

    Args:
        log_file_path (str): The path to the log file.
    """
    # Regex to capture seq number and channel
    # This regex looks for 'seq=NUMBER' and 'channel=CHANNEL_NAME'
    log_pattern = re.compile(r'seq=(\d+), channel=([^,]+),')
    
    last_reliable_seq = -1  # Initialize to a value lower than any expected seq
    line_number = 0
    error_found = False

    print(f"--- Checking log file: {log_file_path} ---")

    try:
        with open(log_file_path, 'r') as f:
            for line in f:
                line_number += 1
                match = log_pattern.search(line)
                
                if match:
                    seq_str, channel = match.groups()
                    
                    # Check only 'Reliable' channels
                    if channel == 'Reliable':
                        try:
                            seq = int(seq_str)
                            
                            # Check if the sequence number is increasing
                            if seq <= last_reliable_seq:
                                print(f"[VIOLATION] Line {line_number}: Reliable seq {seq} is not greater than previous {last_reliable_seq}.")
                                print(f"  > {line.strip()}")
                                error_found = True
                            
                            # Update the last seen reliable sequence number
                            last_reliable_seq = seq
                            
                        except ValueError:
                            print(f"[WARNING] Line {line_number}: Could not parse seq number '{seq_str}' as integer.")

    except FileNotFoundError:
        print(f"[ERROR] Log file not found: {log_file_path}")
        return
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
        return

    if not error_found:
        print("\n[SUCCESS] All 'Reliable' channel sequence numbers are in increasing order.")
    else:
        print("\n[FAILURE] Sequence order violations found.")

# --- Main execution ---
if __name__ == "__main__":
    # Check if a file path is provided as a command-line argument
    if len(sys.argv) > 1:
        log_file_to_check = sys.argv[1]
        check_reliable_sequence(log_file_to_check)
    else:
        # If no argument is provided, print usage instructions
        print("Usage: python check_reliable_seq.py <path_to_log_file>")
        print("Example: python check_reliable_seq.py log.txt")

