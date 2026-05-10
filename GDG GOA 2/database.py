"""
AthleticConnect — SQLite Database Layer
Handles schema creation, connection management, and seed data.
"""

import sqlite3
import os
import json
import bcrypt

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'athleticconnect.db')


def get_db():
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables and seed initial data if empty."""
    conn = get_db()
    cur = conn.cursor()

    # ── Create Tables ────────────────────────────────────────
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            location TEXT DEFAULT '',
            sports TEXT DEFAULT '[]',
            avatar_initials TEXT DEFAULT 'U',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            distance_km REAL,
            duration_minutes REAL,
            calories INTEGER,
            description TEXT,
            date DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS personal_bests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            time_display TEXT NOT NULL,
            time_seconds INTEGER,
            achieved_at DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, event_name)
        );

        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            duration_days INTEGER DEFAULT 30,
            target TEXT,
            icon TEXT DEFAULT '🏆',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            challenge_id INTEGER NOT NULL,
            progress TEXT DEFAULT '',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (challenge_id) REFERENCES challenges(id),
            UNIQUE(user_id, challenge_id)
        );

        CREATE TABLE IF NOT EXISTS community_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            post_type TEXT DEFAULT 'update',
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS weekly_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            calories INTEGER DEFAULT 0,
            active_minutes INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            week_start DATE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (friend_id) REFERENCES users(id),
            UNIQUE(user_id, friend_id)
        );
    """)

    # ── Seed Data (only if empty) ────────────────────────────
    user_count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    if user_count == 0:
        print("[*] Seeding database with initial data...")

        pw_hash = bcrypt.hashpw(b"demo123", bcrypt.gensalt()).decode('utf-8')

        # Users
        cur.execute(
            "INSERT INTO users (name, email, password_hash, location, sports, avatar_initials) VALUES (?,?,?,?,?,?)",
            ("Mohan K.", "mohan@example.com", pw_hash, "Bengaluru, India",
             json.dumps(["Running", "Cycling"]), "MK")
        )
        mohan_id = cur.lastrowid

        cur.execute(
            "INSERT INTO users (name, email, password_hash, location, sports, avatar_initials) VALUES (?,?,?,?,?,?)",
            ("Arjun R.", "arjun@example.com", pw_hash, "Mumbai, India",
             json.dumps(["Running"]), "AR")
        )
        arjun_id = cur.lastrowid

        cur.execute(
            "INSERT INTO users (name, email, password_hash, location, sports, avatar_initials) VALUES (?,?,?,?,?,?)",
            ("Priya S.", "priya@example.com", pw_hash, "Delhi, India",
             json.dumps(["Running", "Yoga"]), "PS")
        )
        priya_id = cur.lastrowid

        cur.execute(
            "INSERT INTO users (name, email, password_hash, location, sports, avatar_initials) VALUES (?,?,?,?,?,?)",
            ("Rahul M.", "rahul@example.com", pw_hash, "Bengaluru, India",
             json.dumps(["Cycling", "Swimming"]), "RM")
        )
        rahul_id = cur.lastrowid

        # Friendships
        for fid in [arjun_id, priya_id, rahul_id]:
            cur.execute("INSERT INTO friendships (user_id, friend_id) VALUES (?,?)", (mohan_id, fid))

        # Personal bests
        cur.execute("INSERT INTO personal_bests (user_id, event_name, time_display, time_seconds) VALUES (?,?,?,?)",
                    (mohan_id, "5km Run", "24:55", 1495))
        cur.execute("INSERT INTO personal_bests (user_id, event_name, time_display, time_seconds) VALUES (?,?,?,?)",
                    (mohan_id, "10km Run", "52:10", 3130))

        # Activities
        activities = [
            (mohan_id, "Running", 5, 24.92, 420, "5km morning run — felt great!", "2026-05-09"),
            (mohan_id, "Cycling", 15, 45, 380, "Evening cycling around Cubbon Park", "2026-05-08"),
            (mohan_id, "Running", 3, 16, 240, "Quick 3km tempo run", "2026-05-07"),
            (mohan_id, "Running", 8, 42, 650, "Long run through Lalbagh", "2026-05-06"),
            (mohan_id, "Cycling", 20, 60, 520, "20km ride on Outer Ring Road", "2026-05-05"),
        ]
        cur.executemany(
            "INSERT INTO activities (user_id, type, distance_km, duration_minutes, calories, description, date) VALUES (?,?,?,?,?,?,?)",
            activities
        )

        # Weekly stats
        cur.execute(
            "INSERT INTO weekly_stats (user_id, calories, active_minutes, points, week_start) VALUES (?,?,?,?,?)",
            (mohan_id, 3240, 318, 1870, "2026-05-05")
        )

        # Challenges
        challenge_data = [
            ("30-Day Run Streak", "Run at least 1km every day for 30 days", 30, "30 days", "🏃"),
            ("100km Cycling Month", "Cycle 100km total in one month", 30, "100km", "🚴"),
            ("Morning Warrior", "Complete 20 workouts before 7 AM", 30, "20 workouts", "🌅"),
            ("Hydration Hero", "Drink 3L of water every day for 14 days", 14, "14 days", "💧"),
        ]
        challenge_ids = []
        for c in challenge_data:
            cur.execute(
                "INSERT INTO challenges (title, description, duration_days, target, icon) VALUES (?,?,?,?,?)", c
            )
            challenge_ids.append(cur.lastrowid)

        # Mohan joins first two challenges
        cur.execute("INSERT INTO user_challenges (user_id, challenge_id, progress) VALUES (?,?,?)",
                    (mohan_id, challenge_ids[0], "Day 18 of 30"))
        cur.execute("INSERT INTO user_challenges (user_id, challenge_id, progress) VALUES (?,?,?)",
                    (mohan_id, challenge_ids[1], "43km completed"))

        # Community posts
        posts = [
            (arjun_id, "New Personal Best!", "achievement",
             json.dumps({"event": "5km", "time": "23:42"}), "2026-05-10T08:30:00"),
            (priya_id, "Joined the 30-Day Run Streak. Let's go!", "challenge_join",
             json.dumps({"challenge": "30-Day Run Streak"}), "2026-05-10T05:00:00"),
            (mohan_id, "Beautiful morning run through Lalbagh Gardens 🌿", "update",
             json.dumps({}), "2026-05-09T10:00:00"),
            (rahul_id, "Just completed my first 50km cycling week!", "milestone",
             json.dumps({"distance": "50km"}), "2026-05-09T06:00:00"),
        ]
        cur.executemany(
            "INSERT INTO community_posts (user_id, content, post_type, metadata, created_at) VALUES (?,?,?,?,?)",
            posts
        )

        conn.commit()
        print("[OK] Database seeded successfully!")
    else:
        conn.commit()

    conn.close()
