from pathlib import Path

from db import db_pool


def initialize_database():
    schema_path = Path(__file__).with_name('schema.sql')
    statements = [
        statement.strip()
        for statement in schema_path.read_text(encoding='utf-8').split(';')
        if statement.strip()
    ]
    if not statements:
        raise RuntimeError(f'No SQL statements found in {schema_path}.')

    connection = cursor = None
    try:
        connection = db_pool.get_connection()
        cursor = connection.cursor()
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
        print(f'Applied {len(statements)} schema statements.')
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


if __name__ == '__main__':
    initialize_database()