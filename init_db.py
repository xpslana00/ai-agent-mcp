"""Vytvori ukazkovou SQLite databazi IT majetku (data/it_assets.db).
Vsechna data jsou smyslena (fiktivni osoby a zarizeni)."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "it_assets.db"

USERS = [
    (1, "Jan Novak", "IT"),
    (2, "Petra Svobodova", "HR"),
    (3, "Tomas Dvorak", "Finance"),
    (4, "Lucie Cerna", "IT"),
    (5, "Karel Prochazka", "Vyvoj"),
]

DEVICES = [
    (1, "NB-IT-001", "Dell", "Latitude 5550", "Windows 11", "24H2", 1, "2024-03-12", "active"),
    (2, "NB-HR-002", "Dell", "Latitude 5440", "Windows 11", "23H2", 2, "2023-06-01", "active"),
    (3, "NB-FI-003", "HP", "EliteBook 840 G10", "Windows 11", "24H2", 3, "2024-01-20", "active"),
    (4, "NB-IT-004", "Dell", "Precision 3590", "Windows 11", "24H2", 4, "2025-10-05", "active"),
    (5, "NB-DEV-005", "Apple", "MacBook Pro 14", "macOS", "15.5", 5, "2025-02-14", "active"),
    (6, "NB-DEV-006", "Lenovo", "ThinkPad T14", "Ubuntu", "24.04", 5, "2024-09-30", "active"),
    (7, "NB-HR-007", "Dell", "Latitude 5420", "Windows 10", "22H2", 2, "2021-04-11", "retired"),
    (8, "MOB-IT-008", "Samsung", "Galaxy S24", "Android", "15", 1, "2024-05-02", "active"),
    (9, "MOB-FI-009", "Apple", "iPhone 15", "iOS", "18.5", 3, "2024-02-18", "active"),
    (10, "NB-FI-010", "Lenovo", "ThinkPad E16", "Windows 11", "24H2", None, "2026-11-10", "in_stock"),
]


def create_db(path: Path = DB_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL
        );
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY,
            hostname TEXT NOT NULL,
            manufacturer TEXT NOT NULL,
            model TEXT NOT NULL,
            os TEXT NOT NULL,
            os_version TEXT,
            user_id INTEGER REFERENCES users(id),
            purchase_date TEXT,
            status TEXT CHECK (status IN ('active', 'retired', 'in_stock'))
        );
        """
    )
    cur.executemany("INSERT INTO users VALUES (?, ?, ?)", USERS)
    cur.executemany("INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", DEVICES)
    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    print(f"Databaze vytvorena: {create_db()}")
