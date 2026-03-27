import requests


def main() -> None:
    url = "http://127.0.0.1:8000/auth/token"
    data = {"username": "Admin", "password": "password"}
    try:
        response = requests.post(url, data=data, timeout=30)
        print(response.status_code, response.text)
    except Exception as exc:
        print("Request failed", exc)


if __name__ == "__main__":
    main()
