"""
unique id generator
"""

""" option 1: bitch about file name
    epoch_time is & 0xFFFF
    chunk_count * starting_id is & 0xFFFF, then bit shift by 1
"""
def create_unique_id(file_basename: str, epoch_time: int, chunk_count: int, starting_id: int) -> str:
    # Step 1: Encode the file basename
    # Sum the ASCII values of all characters, XOR by 1600, and apply & 0xFFFF
    encoded_file_name = sum(ord(char) for char in file_basename)
    encoded_file_name ^= 65536
    encoded_file_name &= 0xFFFF

    # Step 2: Encode the epoch time
    # Apply & 0xFFFF, then shift right by 1
    encoded_time = (epoch_time & 0xFFFF) >> 1

    # Step 3: Encode the chunk count and starting ID
    # Multiply, apply & 0xFFFF, then shift left by 1
    encoded_num = (chunk_count * starting_id) & 0xFFFF
    encoded_num <<= 1

    # Step 4: Add redundancy bits
    redundancy = encoded_file_name ^ encoded_time ^ encoded_num

    # Step 4: Combine the results into a unique ID
    unique_id = f"{encoded_file_name:04X}{encoded_time:04X}{encoded_num:05X}{redundancy:04X}"

    return unique_id

# Example usage
file_basename = "basic engineering science"
epoch_time = 1675154174
chunk_count = 481
starting_id = 0

print(create_unique_id(file_basename, epoch_time, chunk_count, starting_id))
