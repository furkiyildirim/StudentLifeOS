<<<<<<< HEAD
-- WAL modunu etkinleştirme
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Dersler
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,          -- Örn: MATH101
    name TEXT NOT NULL,          -- Örn: Calculus I
    instructor TEXT,
    classroom TEXT,
    credit INTEGER DEFAULT 3,
    max_absence INTEGER DEFAULT 4,
    color_hex TEXT DEFAULT '#3B82F6', -- UI renk kodu
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Haftalık Ders Programı Çizelgesi
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL, -- 0: Pazartesi, ..., 6: Pazar
    start_time TEXT NOT NULL,     -- '09:30'
    end_time TEXT NOT NULL        -- '11:20'
);

-- Sınavlar ve Değerlendirmeler
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,          -- 'Vize 1', 'Dönem Projesi'
    type TEXT NOT NULL,           -- 'vize', 'final', 'quiz', 'proje'
    weight REAL NOT NULL,         -- Ağırlık yüzdesi: 40.0
    score REAL,                   -- Alınan not: 85.5 (NULL ise henüz girilmedi)
    due_date TEXT NOT NULL        -- 'YYYY-MM-DD HH:MM'
);

-- Notlar ve Markdown Dokümanları
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    content_markdown TEXT,
    tags TEXT,                    -- Virgülle ayrılmış etiketler: 'fonksiyonlar,limit'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Materyaller (PDF, Sunum, Resim referansları)
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,      -- 'pdf', 'image', 'slide', 'doc'
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alışkanlık Takibi
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    icon TEXT DEFAULT 'target',
    created_at DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS habit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    is_completed BOOLEAN DEFAULT 1,
    UNIQUE(habit_id, date)
);

-- Spor ve Antrenman Takipçisi
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week INTEGER NOT NULL, -- 0: Pazartesi ... 6: Pazar
    routine_name TEXT NOT NULL    -- 'Göğüs - Triceps' veya 'Push Day'
);

CREATE TABLE IF NOT EXISTS workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_name TEXT NOT NULL,
    sets INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    target_weight REAL,           -- Hedef ağırlık (kg)
    rest_seconds INTEGER DEFAULT 60
);

CREATE TABLE IF NOT EXISTS workout_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER REFERENCES workout_exercises(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    actual_weight REAL,
    actual_reps INTEGER,
    completed BOOLEAN DEFAULT 1
=======
-- WAL modunu etkinleştirme
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Dersler
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,          -- Örn: MATH101
    name TEXT NOT NULL,          -- Örn: Calculus I
    instructor TEXT,
    classroom TEXT,
    credit INTEGER DEFAULT 3,
    max_absence INTEGER DEFAULT 4,
    color_hex TEXT DEFAULT '#3B82F6', -- UI renk kodu
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Haftalık Ders Programı Çizelgesi
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL, -- 0: Pazartesi, ..., 6: Pazar
    start_time TEXT NOT NULL,     -- '09:30'
    end_time TEXT NOT NULL        -- '11:20'
);

-- Sınavlar ve Değerlendirmeler
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,          -- 'Vize 1', 'Dönem Projesi'
    type TEXT NOT NULL,           -- 'vize', 'final', 'quiz', 'proje'
    weight REAL NOT NULL,         -- Ağırlık yüzdesi: 40.0
    score REAL,                   -- Alınan not: 85.5 (NULL ise henüz girilmedi)
    due_date TEXT NOT NULL        -- 'YYYY-MM-DD HH:MM'
);

-- Notlar ve Markdown Dokümanları
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    content_markdown TEXT,
    tags TEXT,                    -- Virgülle ayrılmış etiketler: 'fonksiyonlar,limit'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Materyaller (PDF, Sunum, Resim referansları)
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,      -- 'pdf', 'image', 'slide', 'doc'
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alışkanlık Takibi
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    icon TEXT DEFAULT 'target',
    created_at DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS habit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    is_completed BOOLEAN DEFAULT 1,
    UNIQUE(habit_id, date)
);

-- Spor ve Antrenman Takipçisi
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week INTEGER NOT NULL, -- 0: Pazartesi ... 6: Pazar
    routine_name TEXT NOT NULL    -- 'Göğüs - Triceps' veya 'Push Day'
);

CREATE TABLE IF NOT EXISTS workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_name TEXT NOT NULL,
    sets INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    target_weight REAL,           -- Hedef ağırlık (kg)
    rest_seconds INTEGER DEFAULT 60
);

CREATE TABLE IF NOT EXISTS workout_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER REFERENCES workout_exercises(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    actual_weight REAL,
    actual_reps INTEGER,
    completed BOOLEAN DEFAULT 1
>>>>>>> 5ca999bb9db413cea1ae04f016f41cac4e899701
);