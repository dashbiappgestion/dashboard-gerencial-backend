from app.database import reset_engine, test_connection

if __name__ == "__main__":
    reset_engine()
    result = test_connection()
    for key, value in result.items():
        print(f"{key}: {value}")
