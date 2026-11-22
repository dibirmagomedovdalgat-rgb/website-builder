import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
NGINX_DIR = BASE_DIR / "nginx"
HTTP_TEMPLATE = NGINX_DIR / "http.conf.template"
SSL_TEMPLATE = NGINX_DIR / "ssl.conf.template"
ACTIVE_TEMPLATE = NGINX_DIR / "active.conf.template"


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({hint}): ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "д", "да")


def is_local_domain(domain: str) -> bool:
    return domain.lower() in ("", "localhost", "127.0.0.1", "0.0.0.0")


def find_free_local_port() -> str:
    """Сам находит свободный порт на компьютере (80, 8000 или 8080)."""
    for port in (80, 8000, 8080, 8888):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return str(port)
    return "8000"


def read_env_values() -> dict[str, str]:
    data: dict[str, str] = {}
    if not ENV_FILE.exists():
        return data
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def print_admin_info(base_url: str) -> None:
    print("\n" + "=" * 62)
    print(f"🚀 Магазин запущен! Откройте в браузере: {base_url}/")
    print(f"⚙️  Панель управления (админка):      {base_url}/admin")
    print("=" * 62)
    print("\n🔑 Данные администратора для первого входа:")
    print("   Email:  admin@myshop.com")
    print("   Пароль: admin12345")
    print("   (После входа перейдите в Профиль и смените email на свой)")


def main() -> None:
    print("=" * 62)
    print("  Установка и запуск интернет-магазина")
    print("=" * 62)

    if ENV_FILE.exists():
        print("\n⚠️  Магазин уже настроен (файл .env существует).")
        if not ask_yes_no("Сбросить настройки и настроить заново?", default=False):
            print("Запускаем с текущими настройками...")
            env_data = read_env_values()
            domain = env_data.get("DOMAIN", "localhost")
            port = env_data.get("PORT", "80")

            if is_local_domain(domain):
                subprocess.run(["docker", "compose", "up", "-d"], cwd=BASE_DIR)
                base_url = "http://127.0.0.1" if port == "80" else f"http://127.0.0.1:{port}"
            else:
                subprocess.run(["docker", "compose", "--profile", "ssl", "up", "-d"], cwd=BASE_DIR)
                proto = "https" if ACTIVE_TEMPLATE.exists() and "443 ssl" in ACTIVE_TEMPLATE.read_text(encoding="utf-8") else "http"
                base_url = f"{proto}://{domain}"

            print_admin_info(base_url)
            return

    domain = ask(
        "\nВведите адрес вашего сайта (например, myshop.ru)\n"
        "или просто нажмите Enter, чтобы запустить магазин на этом компьютере",
        default="localhost",
    )
    local_mode = is_local_domain(domain)

    if local_mode:
        port = find_free_local_port()
        ssl_email = ""
        print(f"-> Режим: запуск на этом компьютере (выбран свободный порт {port}).")
    else:
        port = "80"
        ssl_email = ask(
            "Введите ваш Email (нужен для бесплатного SSL-сертификата безопасности)",
            default="admin@shop.local",
        )
        print(f"-> Режим: публикация в интернет на домене {domain}.")

    db_url = "postgresql+asyncpg://myuser:mysecretpassword@db:5432/mydatabase"
    secret_key = secrets.token_hex(32)

    env_content = (
        f"DATABASE_URL={db_url}\n"
        f"SECRET_KEY={secret_key}\n"
        f"DOMAIN={domain}\n"
        f"PORT={port}\n"
        f"DEBUG=False\n"
    )
    ENV_FILE.write_text(env_content, encoding="utf-8")

    if HTTP_TEMPLATE.exists():
        shutil.copyfile(HTTP_TEMPLATE, ACTIVE_TEMPLATE)

    if not shutil.which("docker"):
        print("\n❌ Не найден Docker. Пожалуйста, установите и запустите Docker Desktop, затем повторите запуск.")
        return

    print("\n⏳ Собираем и запускаем магазин (при первом запуске это займёт 1–2 минуты)...")
    up_res = subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=BASE_DIR)
    if up_res.returncode != 0:
        print("\n❌ Не удалось запустить контейнеры. Убедитесь, что Docker Desktop запущен.")
        return

    if local_mode:
        base_url = "http://127.0.0.1" if port == "80" else f"http://127.0.0.1:{port}"
        print_admin_info(base_url)
        return

    print(f"\n🔒 Подключаем защищённое соединение (HTTPS) для {domain}...")
    time.sleep(3)
    cert_cmd = [
        "docker", "compose", "--profile", "ssl", "run", "--rm", "--entrypoint", "", "certbot",
        "certbot", "certonly", "--webroot", "-w", "/var/www/certbot",
        "-d", domain, "--email", ssl_email, "--agree-tos", "--no-eff-email",
    ]
    cert_res = subprocess.run(cert_cmd, cwd=BASE_DIR)

    if cert_res.returncode == 0 and SSL_TEMPLATE.exists():
        shutil.copyfile(SSL_TEMPLATE, ACTIVE_TEMPLATE)
        subprocess.run(["docker", "compose", "restart", "nginx"], cwd=BASE_DIR)
        subprocess.run(["docker", "compose", "--profile", "ssl", "up", "-d", "certbot"], cwd=BASE_DIR)
        print("\n✅ Защищённое соединение HTTPS успешно подключено!")
        print_admin_info(f"https://{domain}")
    else:
        print(
            "\n⚠️  Не удалось автоматически получить SSL-сертификат "
            "(убедитесь, что домен уже направлен на IP этого сервера)."
        )
        print_admin_info(f"http://{domain}")


if __name__ == "__main__":
    main()
