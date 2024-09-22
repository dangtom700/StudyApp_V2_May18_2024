import sqlite3
from os.path import getmtime, basename
from datetime import datetime
from modules.path import chunk_database_path
from os.path import join
from modules.extract_text import batch_collect_files

def get_modification_time(file_path: str) -> tuple[str, int]:
    # Get the modification time in seconds since EPOCH
    modification_time = getmtime(file_path)
    # Convert the modification time to a recognizable timestamp
    formatted_modification_time = datetime.fromtimestamp(modification_time).strftime('%a, %b %d, %Y, %H:%M:%S')
    epoch_time = int(modification_time)
    return (formatted_modification_time, epoch_time)

def create_unique_id(file_basename: str, epoch_time: int, chunk_count: int, starting_id: int) -> str:
    encoded_file_name = sum(ord(char) for char in file_basename)
    encoded_file_name ^= 65536
    encoded_file_name &= 0xFFFFFF
    encoded_time = (epoch_time & 0xFFFFFF) >> 2
    encoded_num = (chunk_count * starting_id) & 0xFFFF << 1
    redundancy = encoded_file_name ^ encoded_time ^ encoded_num
    redundancy &= 0xFF
    unique_id = f"{encoded_file_name:06X}{encoded_time:06X}{encoded_num:04X}{redundancy:02X}"

    return unique_id

def count_chunk_for_each_title(cursor: sqlite3.Cursor, file_name: str) -> int:
    cursor.execute(f"SELECT COUNT(id) FROM pdf_chunks WHERE file_name = ?", (file_name,))
    chunk_count = cursor.fetchone()[0]
    # print(f"Chunk count for {file_name}: {chunk_count}")
    return chunk_count

def get_starting_and_ending_ids(cursor: sqlite3.Cursor, file_name: str) -> tuple[int, int]:
    start_id = cursor.execute(f"SELECT MIN(id) FROM pdf_chunks WHERE file_name = ?", (file_name,)).fetchone()[0]
    end_id = cursor.execute(f"SELECT MAX(id) FROM pdf_chunks WHERE file_name = ?", (file_name,)).fetchone()[0]
    if start_id is None or end_id is None:
        start_id, end_id = 0, 0
    return start_id, end_id

def store_files_in_db(file_names: list[str],
                      folder_path: str,
                      file_list: list[str], 
                      file_type: str, 
                      conn: sqlite3.Connection, 
                      cursor: sqlite3.Cursor) -> None:
    
    for file_name, file_path in zip(file_names, file_list):
        created_time, epoch_time = get_modification_time(file_path)
        file_basename = basename(file_path)
        full_path = join(folder_path, file_basename) if folder_path else file_path
        chunk_count = count_chunk_for_each_title(cursor, file_name=full_path)
        starting_id, ending_id = get_starting_and_ending_ids(cursor, file_name=full_path)
        hashed_data = create_unique_id(file_basename, epoch_time, chunk_count, starting_id)

        print(created_time, epoch_time, chunk_count, starting_id, ending_id, hashed_data)
        
        cursor.execute(f"""INSERT INTO file_list (
            id, 
            file_name, 
            file_path,
            file_type,
            created_time,
            epoch_time,
            chunk_count,
            start_id,
            end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (hashed_data, file_basename, file_path, file_type, created_time, epoch_time, chunk_count, starting_id, ending_id)
        )
    conn.commit()
# Main function
def extract_names(raw_list: list[str], extension: list[str]) -> list[str]:
    return [basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

def create_index_table(folder_path: str, extension: str) -> None:
    conn = sqlite3.connect(chunk_database_path)
    cursor = conn.cursor()
    # Reset the table if it already exists
    cursor.execute("DROP TABLE IF EXISTS file_list")
    cursor.execute("""CREATE TABLE IF NOT EXISTS file_list (
        id TEXT PRIMARY KEY,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT NOT NULL,
        created_time TEXT NOT NULL,
        epoch_time INTEGER NOT NULL,
        chunk_count INTEGER NOT NULL,
        start_id INTEGER NOT NULL,
        end_id INTEGER NOT NULL
    )""")
    conn.commit()
    conn.execute("SELECT * FROM pdf_chunks ORDER BY file_name")
    for file_batch in batch_collect_files(folder_path=folder_path, extension=extension):
        store_files_in_db(file_names=extract_names(file_batch, extension),
                        folder_path=folder_path,
                        file_list=file_batch,
                        file_type=extension,
                        conn=conn,
                        cursor=cursor)
        
    conn.close()