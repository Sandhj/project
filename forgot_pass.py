import sqlite3

def search_user():
    db_path = "database.db"  # Nama file database
    table_name = "users"  # Ganti dengan nama tabel yang sesuai
    
    username = input("Masukkan username yang ingin dicari: ")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = f"SELECT username, password FROM {table_name} WHERE username = ?"
        cursor.execute(query, (username,))
        result = cursor.fetchone()
        
        if result:
            print(f"Username: {result[0]}, Password: {result[1]}")
        else:
            print("Username tidak ditemukan.")
        
    except sqlite3.Error as e:
        print(f"Terjadi kesalahan pada database: {e}")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    search_user()
