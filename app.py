from flask import Flask, render_template, request, redirect, jsonify
import os
import sqlite3
import requests
import time
from urllib.parse import urlparse

app = Flask(__name__)

COMMIT = os.getenv(
    "RENDER_GIT_COMMIT",
    "local"
)[:7]

DATABASE = "database.db"

DEFAULT_THRESHOLD = 2500
HISTORY_LIMIT = 20


def get_db_connection():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def validate_service_data(name, url, threshold_text):
    if not name:
        return False, "Service name is required."

    parsed_url = urlparse(url)

    if parsed_url.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://."

    if not parsed_url.netloc:
        return False, "Please enter a valid URL."

    try:
        threshold = int(threshold_text)

        if threshold <= 0:
            return False, "Threshold must be greater than 0."

    except ValueError:
        return False, "Threshold must be a valid number."

    return True, ""


def init_database():

    connection = get_db_connection()

    # Services table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            threshold INTEGER DEFAULT 2500,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Checks table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            status_code INTEGER,
            response_time REAL,
            threshold INTEGER,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error_message TEXT,
            FOREIGN KEY (service_id) REFERENCES services (id)
        )
    """)

    # -------------------------------------------------
    # Database migration for older versions
    # -------------------------------------------------

    service_columns = connection.execute(
        "PRAGMA table_info(services)"
    ).fetchall()

    service_column_names = [
        column["name"]
        for column in service_columns
    ]

    if "threshold" not in service_column_names:

        connection.execute("""
            ALTER TABLE services
            ADD COLUMN threshold INTEGER DEFAULT 2500
        """)

    connection.execute("""
        UPDATE services
        SET threshold = ?
        WHERE threshold IS NULL
    """, (DEFAULT_THRESHOLD,))

    # Add threshold column to checks table
    check_columns = connection.execute(
        "PRAGMA table_info(checks)"
    ).fetchall()

    check_column_names = [
        column["name"]
        for column in check_columns
    ]

    if "threshold" not in check_column_names:

        connection.execute("""
            ALTER TABLE checks
            ADD COLUMN threshold INTEGER
        """)

        # For old history records, use the service's
        # current threshold as the best available value.
        connection.execute("""
            UPDATE checks

            SET threshold = (
                SELECT services.threshold
                FROM services
                WHERE services.id = checks.service_id
            )

            WHERE threshold IS NULL
        """)

    connection.commit()

    connection.close()


def perform_health_check(service_id):

    connection = get_db_connection()

    service = connection.execute(
        """
        SELECT *
        FROM services
        WHERE id = ?
        """,
        (service_id,)
    ).fetchone()

    if service is None:

        connection.close()

        return False

    # Store the threshold that is active
    # at the exact moment of this check.
    threshold = (
        service["threshold"]
        or DEFAULT_THRESHOLD
    )

    start_time = time.perf_counter()

    try:

        response = requests.get(
            service["url"],
            timeout=5
        )

        end_time = time.perf_counter()

        response_time = round(
            (end_time - start_time) * 1000,
            2
        )

        if 200 <= response.status_code < 400:

            if response_time > threshold:

                status = "SLOW"

            else:

                status = "UP"

        else:

            status = "DOWN"

        connection.execute(
            """
            INSERT INTO checks
            (
                service_id,
                status,
                status_code,
                response_time,
                threshold,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                service_id,
                status,
                response.status_code,
                response_time,
                threshold,
                None
            )
        )

        connection.commit()

        connection.close()

        return True

    except requests.RequestException as error:

        end_time = time.perf_counter()

        response_time = round(
            (end_time - start_time) * 1000,
            2
        )

        connection.execute(
            """
            INSERT INTO checks
            (
                service_id,
                status,
                status_code,
                response_time,
                threshold,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                service_id,
                "DOWN",
                None,
                response_time,
                threshold,
                str(error)
            )
        )

        connection.commit()

        connection.close()

        return True


def check_all_services():

    connection = get_db_connection()

    services = connection.execute(
        "SELECT id FROM services"
    ).fetchall()

    connection.close()

    for service in services:

        perform_health_check(
            service["id"]
        )


def get_latest_services():

    connection = get_db_connection()

    services = connection.execute("""
        SELECT
            services.*,
            checks.status,
            checks.status_code,
            checks.response_time,
            checks.threshold AS check_threshold,
            checks.checked_at,
            checks.error_message

        FROM services

        LEFT JOIN checks

        ON checks.id = (
            SELECT id

            FROM checks AS latest_checks

            WHERE latest_checks.service_id =
                  services.id

            ORDER BY latest_checks.id DESC

            LIMIT 1
        )

        ORDER BY services.id DESC
    """).fetchall()

    connection.close()

    return services


@app.route("/")
def home():
    check_all_services()
    services = get_latest_services()

    return render_template(
        "dashboard.html",
        services=services,
        commit=COMMIT
    )


@app.route("/add", methods=["POST"])
def add_service():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    threshold_text = request.form.get(
        "threshold",
        str(DEFAULT_THRESHOLD)
    ).strip()

    valid, error_message = validate_service_data(
        name,
        url,
        threshold_text
    )

    if not valid:
        return error_message, 400

    threshold = int(threshold_text)

    connection = get_db_connection()

    cursor = connection.execute(
        """
        INSERT INTO services
        (
            name,
            url,
            threshold
        )
        VALUES (?, ?, ?)
        """,
        (
            name,
            url,
            threshold
        )
    )

    service_id = cursor.lastrowid

    connection.commit()
    connection.close()

    perform_health_check(service_id)

    return redirect("/")

    service_id = cursor.lastrowid

    connection.commit()

    connection.close()

    # First check uses the newly selected threshold.
    perform_health_check(service_id)

    return redirect("/")


@app.route(
    "/edit/<int:service_id>",
    methods=["GET", "POST"]
)
def edit_service(service_id):

    connection = get_db_connection()

    service = connection.execute(
        """
        SELECT *
        FROM services
        WHERE id = ?
        """,
        (service_id,)
    ).fetchone()

    connection.close()

    if service is None:

        return "Service not found", 404

    # Display edit form
    if request.method == "GET":

        return render_template(
            "edit.html",
            service=service
        )

    name = request.form["name"].strip()

    url = request.form["url"].strip()

    threshold_text = request.form.get(
        "threshold",
        str(DEFAULT_THRESHOLD)
    ).strip()

    try:

        threshold = int(threshold_text)

        if threshold <= 0:

            threshold = DEFAULT_THRESHOLD

    except ValueError:

        threshold = DEFAULT_THRESHOLD

    connection = get_db_connection()

    connection.execute(
        """
        UPDATE services

        SET
            name = ?,
            url = ?,
            threshold = ?

        WHERE id = ?
        """,
        (
            name,
            url,
            threshold,
            service_id
        )
    )

    connection.commit()

    connection.close()

    # The new threshold is used for the new check.
    perform_health_check(service_id)

    return redirect("/")


@app.route("/delete/<int:service_id>")
def delete_service(service_id):

    connection = get_db_connection()

    service = connection.execute(
        """
        SELECT *
        FROM services
        WHERE id = ?
        """,
        (service_id,)
    ).fetchone()

    if service is None:

        connection.close()

        return "Service not found", 404

    # Delete history first.
    connection.execute(
        """
        DELETE FROM checks
        WHERE service_id = ?
        """,
        (service_id,)
    )

    # Delete service.
    connection.execute(
        """
        DELETE FROM services
        WHERE id = ?
        """,
        (service_id,)
    )

    connection.commit()

    connection.close()

    return redirect("/")


@app.route("/check/<int:service_id>")
def check_service(service_id):

    connection = get_db_connection()

    service = connection.execute(
        """
        SELECT *
        FROM services
        WHERE id = ?
        """,
        (service_id,)
    ).fetchone()

    connection.close()

    if service is None:

        return "Service not found", 404

    perform_health_check(service_id)

    return redirect("/")


@app.route("/history/<int:service_id>")
def service_history(service_id):

    connection = get_db_connection()

    service = connection.execute(
        """
        SELECT *
        FROM services
        WHERE id = ?
        """,
        (service_id,)
    ).fetchone()

    if service is None:

        connection.close()

        return "Service not found", 404

    checks = connection.execute(
        """
        SELECT
            id,
            status,
            status_code,
            response_time,
            threshold,
            checked_at,
            error_message

        FROM checks

        WHERE service_id = ?

        ORDER BY id DESC

        LIMIT ?
        """,
        (
            service_id,
            HISTORY_LIMIT
        )
    ).fetchall()

    connection.close()

    return render_template(
        "history.html",
        service=service,
        checks=checks
    )


@app.route("/api/services")
def api_services():
    connection = get_db_connection()

    services = connection.execute("""
        SELECT
            services.id,
            services.name,
            services.url,
            services.threshold,
            checks.status,
            checks.status_code,
            checks.response_time,
            checks.checked_at
        FROM services
        LEFT JOIN checks
        ON checks.id = (
            SELECT id
            FROM checks AS latest_checks
            WHERE latest_checks.service_id = services.id
            ORDER BY latest_checks.id DESC
            LIMIT 1
        )
        ORDER BY services.id DESC
    """).fetchall()

    connection.close()

    result = []

    for service in services:
        result.append({
            "id": service["id"],
            "name": service["name"],
            "url": service["url"],
            "threshold": service["threshold"],
            "status": service["status"],
            "status_code": service["status_code"],
            "response_time": service["response_time"],
            "checked_at": service["checked_at"]
        })

    return jsonify(result)


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "commit": COMMIT
    })


if __name__ == "__main__":

    init_database()

    app.run(
        debug=True
    )
