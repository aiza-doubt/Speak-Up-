import streamlit as st
import sqlite3
import json
import re
from datetime import datetime, date

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Speak Up", page_icon="🎙️", layout="wide")
DB_NAME = "speak_up.db"

# -------------------- DATABASE --------------------
def connect():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def setup_database():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                level TEXT NOT NULL,
                scores TEXT NOT NULL,
                total REAL NOT NULL,
                words TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                target INTEGER NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error TEXT NOT NULL UNIQUE,
                count INTEGER NOT NULL DEFAULT 1,
                last_seen TEXT NOT NULL
            )
        """)

def save_attempt(question, answer, level, scores, words):
    total = round(sum(scores.values()) / len(scores), 1)
    with connect() as conn:
        conn.execute(
            """INSERT INTO attempts
            (created_at, question, answer, level, scores, total, words)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(timespec="seconds"), question, answer,
             level, json.dumps(scores), total, json.dumps(words))
        )
    return total

def get_attempts():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, question, answer, level, scores, total, words "
            "FROM attempts ORDER BY id DESC"
        ).fetchall()
    return [
        {"id": r[0], "created_at": r[1], "question": r[2], "answer": r[3],
         "level": r[4], "scores": json.loads(r[5]), "total": r[6],
         "words": json.loads(r[7])}
        for r in rows
    ]

def add_error(error):
    with connect() as conn:
        existing = conn.execute(
            "SELECT count FROM errors WHERE error=?", (error,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE errors SET count=count+1, last_seen=? WHERE error=?",
                (datetime.now().isoformat(timespec="seconds"), error)
            )
        else:
            conn.execute(
                "INSERT INTO errors(error, count, last_seen) VALUES (?, 1, ?)",
                (error, datetime.now().isoformat(timespec="seconds"))
            )

def get_errors():
    with connect() as conn:
        return conn.execute(
            "SELECT error, count, last_seen FROM errors ORDER BY count DESC"
        ).fetchall()

def get_goals():
    with connect() as conn:
        return conn.execute(
            "SELECT id, title, target, progress, created_at FROM goals ORDER BY id DESC"
        ).fetchall()

def add_goal(title, target):
    with connect() as conn:
        conn.execute(
            "INSERT INTO goals(title, target, progress, created_at) VALUES (?, ?, 0, ?)",
            (title, target, date.today().isoformat())
        )

def update_goal(goal_id, progress):
    with connect() as conn:
        conn.execute(
            "UPDATE goals SET progress=? WHERE id=?", (progress, goal_id)
        )

def delete_goal(goal_id):
    with connect() as conn:
        conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))

setup_database()

# -------------------- SPEAKING ANALYSIS (STARTER VERSION) --------------------
COMMON_WORDS = {
    "the", "a", "an", "and", "or", "but", "because", "so", "to", "of", "in",
    "on", "at", "for", "with", "is", "are", "was", "were", "be", "been",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "this",
    "that", "have", "has", "had", "do", "does", "did", "will", "would",
    "can", "could", "should", "as", "from", "by", "about", "very", "really"
}

FILLERS = ["um", "uh", "like", "you know", "actually"]

def analyze_answer(answer, level):
    text = answer.strip()
    words = re.findall(r"[A-Za-z']+", text.lower())
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    word_count = len(words)
    unique_count = len(set(words))
    long_words = sum(1 for w in words if len(w) >= 7)
    fillers = sum(text.lower().count(f) for f in FILLERS)

    # These are transparent text-based estimates, not an official language test.
    grammar = 45
    if word_count >= 8:
        grammar += 15
    if any(x in text.lower() for x in ["because", "although", "however", "when", "if"]):
        grammar += 12
    if text and text[0].isupper():
        grammar += 8
    if re.search(r"[.!?]$", text):
        grammar += 8
    grammar = min(95, grammar)

    vocabulary = min(95, 35 + unique_count * 2 + long_words * 2)
    fluency = max(25, min(95, 45 + min(word_count, 70) * 0.65 - fillers * 5))
    coherence = min(95, 40 + len(sentences) * 8 +
                    (15 if any(x in text.lower() for x in
                               ["first", "also", "finally", "because", "for example"]) else 0))
    task_response = min(95, 30 + min(word_count, 100) * 0.7)
    # Pronunciation cannot be measured from typed text. Ask the learner to self-rate it.
    return {
        "Grammar": round(grammar),
        "Vocabulary": round(vocabulary),
        "Fluency (text estimate)": round(fluency),
        "Coherence": round(coherence),
        "Pronunciation (self-rating)": None,
        "Task Response": round(task_response),
        "word_count": word_count,
        "unique_count": unique_count
    }

def feedback_for(scores, answer):
    notes = []
    if scores["Grammar"] < 65:
        notes.append("Grammar: қысқа, дұрыс құрылған сөйлемдерден баста. Шақтарды тексер.")
    if scores["Vocabulary"] < 65:
        notes.append("Vocabulary: бір сөзді қайталамай, синонимдер мен нақты сипаттайтын сөздерді қолдан.")
    if scores["Fluency (text estimate)"] < 65:
        notes.append("Fluency: ойыңды толық жеткізетін 2–3 сөйлем құрастырып жаттық.")
    if scores["Coherence"] < 65:
        notes.append("Coherence: firstly, because, for example, finally сияқты байланыстырушы сөздерді қолдан.")
    if scores["Task Response"] < 65:
        notes.append("Task response: сұрақтың барлық бөлігіне жауап беріп, мысал келтір.")
    if not notes:
        notes.append("Жақсы жұмыс! Енді жауаптарыңа нақты мысалдар мен күрделірек сөз тіркестерін қос.")
    return notes

def find_simple_patterns(answer):
    t = answer.lower()
    found = []
    # Simple learning prompts, not a complete grammar checker.
    if re.search(r"\bi am agree\b", t):
        found.append(("I am agree", "I agree", "“Agree” етістігінің алдында “am” қолданылмайды."))
    if re.search(r"\bhe go\b", t):
        found.append(("he go", "he goes", "Present Simple шағында he/she/it үшін етістікке -s жалғанады."))
    if re.search(r"\bshe go\b", t):
        found.append(("she go", "she goes", "Present Simple шағында he/she/it үшін етістікке -s жалғанады."))
    if re.search(r"\bi have \d+ years old\b", t):
        found.append(("I have ... years old", "I am ... years old", "Жасты ағылшын тілінде “I am ... years old” деп айтады."))
    if re.search(r"\bmore better\b", t):
        found.append(("more better", "better", "“Better” сөзінің өзі салыстырмалы шырай."))
    return found

QUESTIONS = {
    "A1–A2": [
        "Tell me about yourself.",
        "What do you like doing in your free time?",
        "Describe your best friend.",
        "What is your favourite food and why?"
    ],
    "B1–B2": [
        "How has technology changed the way people communicate?",
        "What makes a good friend?",
        "Describe a challenge you have overcome.",
        "Do you think students should study abroad? Why or why not?"
    ],
    "Free Practice": [
        "Talk about any topic you enjoy.",
        "Describe a place you would like to visit.",
        "What skill would you like to learn and why?"
    ]
}

HINTS = {
    "Tell me about yourself.": ["I would describe myself as...", "In my free time...", "One thing I enjoy is..."],
    "What do you like doing in your free time?": ["I usually spend my free time...", "I am interested in...", "It helps me to..."],
    "Describe your best friend.": ["I have known my friend for...", "What I admire most is...", "We enjoy..."],
    "What is your favourite food and why?": ["My favourite dish is...", "I particularly like it because...", "It reminds me of..."],
    "How has technology changed the way people communicate?": ["One major change is...", "For example...", "On the other hand..."],
    "What makes a good friend?": ["In my opinion...", "A good friend should...", "For instance..."],
    "Describe a challenge you have overcome.": ["One challenge I faced was...", "At first...", "Eventually, I learned..."],
    "Do you think students should study abroad? Why or why not?": ["There are several advantages...", "For example...", "However, it may also..."],
    "Talk about any topic you enjoy.": ["I would like to talk about...", "The main reason is...", "Another point is..."],
    "Describe a place you would like to visit.": ["I have always wanted to visit...", "What attracts me is...", "If I had the chance..."],
    "What skill would you like to learn and why?": ["A skill I would love to learn is...", "It would help me...", "I plan to..."]
}

# -------------------- SIDEBAR --------------------
st.sidebar.title("🎙️ Speak Up")
st.sidebar.caption("Your English speaking practice space")
page = st.sidebar.radio(
    "Navigation",
    ["🏠 Home", "1. Speaking Assessment", "2. Adaptive Learning Path",
     "3. My Progress", "4. Before & After", "5. Smart Error Tracker",
     "6. Smart Hints", "7. Vocabulary Tracker", "8. Speaking Goals"]
)
st.sidebar.divider()
st.sidebar.caption("Starter version • Data is saved in a local SQLite database.")

attempts = get_attempts()

# -------------------- HOME --------------------
if page == "🏠 Home":
    st.title("Welcome to Speak Up 👋")
    st.subheader("Build confidence. Speak more. Improve every day.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Practice sessions", len(attempts))
    c2.metric("Average score", f"{sum(a['total'] for a in attempts)/len(attempts):.1f}/100" if attempts else "—")
    c3.metric("Active goals", sum(1 for g in get_goals() if g[3] < g[2]))
    st.markdown("### Your 8 learning tools")
    st.write("Use the menu on the left to practise speaking, review your progress, track errors, learn vocabulary and set goals.")
    st.info("Start with **Speaking Assessment**. Choose your level, answer a question in English, and submit your response.")
    st.markdown("### Today's speaking challenge")
    st.write("Speak or write 5–7 sentences about: **“A skill I want to learn.”** Try to use *because*, *for example*, and *in the future*.")

# -------------------- 1 ASSESSMENT --------------------
elif page == "1. Speaking Assessment":
    st.title("1. Speaking Assessment")
    st.write("Choose a level and answer the question in English.")
    level = st.selectbox("Your level", list(QUESTIONS.keys()))
    question = st.selectbox("Speaking question", QUESTIONS[level])
    answer = st.text_area("Your answer", height=200, placeholder="Write what you would say in a speaking test...")
    pronunciation = st.slider("Rate your pronunciation yourself (1 = needs work, 10 = confident)", 1, 10, 6)
    if st.button("Analyze my answer", type="primary"):
        if len(answer.strip().split()) < 5:
            st.warning("Please write at least 5 words so the starter assessment has enough text to review.")
        else:
            scores = analyze_answer(answer, level)
            scores["Pronunciation (self-rating)"] = pronunciation * 10
            total = save_attempt(question, answer, level, scores, [])
            st.success("Your practice session has been saved.")
            st.metric("Starter score", f"{total}/100")
            st.caption("This is an educational estimate based on typed text and your pronunciation self-rating, not an official CEFR or IELTS score.")
            for metric, value in scores.items():
                if metric not in ("word_count", "unique_count"):
                    st.write(f"**{metric}:** {'Not measured' if value is None else str(value) + '/100'}")
                    if value is not None:
                        st.progress(value / 100)
            st.markdown("### Feedback")
            for item in feedback_for(scores, answer):
                st.write("• " + item)
            patterns = find_simple_patterns(answer)
            if patterns:
                st.markdown("### Possible language corrections")
                for wrong, correct, explanation in patterns:
                    st.write(f"**{wrong} → {correct}**")
                    st.caption(explanation)
                    add_error(f"{wrong} → {correct}")
            st.markdown("### Your answer")
            st.write(answer)

# -------------------- 2 ADAPTIVE LEARNING PATH --------------------
elif page == "2. Adaptive Learning Path":
    st.title("2. AI Adaptive Learning Path")
    st.caption("Starter version: recommendations are generated from your saved practice scores. AI-generated coaching can be connected later.")
    if not attempts:
        st.info("Complete a Speaking Assessment first to receive your learning path.")
    else:
        latest = attempts[0]
        scores = latest["scores"]
        st.write(f"Based on your latest practice: **{latest['total']}/100**")
        priorities = sorted(
            [(k, v) for k, v in scores.items() if v is not None],
            key=lambda x: x[1]
        )
        st.markdown("### Your recommended focus areas")
        for name, value in priorities[:3]:
            st.write(f"**{name} — {value}/100**")
            if "Grammar" in name:
                st.write("Practice Present Simple, Past Simple and sentence structure. Write 5 example sentences.")
            elif "Vocabulary" in name:
                st.write("Learn 5 useful words about one topic and use each in your own sentence.")
            elif "Fluency" in name:
                st.write("Give a 60-second answer without stopping. Use linking phrases to connect ideas.")
            elif "Coherence" in name:
                st.write("Structure answers with an introduction, 2 supporting points and a short conclusion.")
            elif "Task Response" in name:
                st.write("Answer every part of the question and add one personal example.")
            elif "Pronunciation" in name:
                st.write("Practise word stress and record yourself. This app does not automatically score pronunciation.")
        st.markdown("### Suggested 7-day routine")
        routine = [
            "Day 1: practise your weakest area for 10 minutes.",
            "Day 2: learn 5 topic-related words.",
            "Day 3: answer 2 speaking questions.",
            "Day 4: review your common errors.",
            "Day 5: give a 1-minute answer and replay your recording using a separate recorder.",
            "Day 6: practise linking phrases and examples.",
            "Day 7: complete another assessment and compare results."
        ]
        for item in routine:
            st.write("☐ " + item)

# -------------------- 3 PROGRESS --------------------
elif page == "3. My Progress":
    st.title("3. My Progress")
    if not attempts:
        st.info("Your progress will appear here after your first assessment.")
    else:
        import pandas as pd
        data = [{
            "Date": a["created_at"][:10],
            "Score": a["total"],
            "Level": a["level"],
            "Words": len(a["answer"].split())
        } for a in reversed(attempts)]
        df = pd.DataFrame(data)
        a, b = st.columns(2)
        a.metric("Total sessions", len(attempts))
        b.metric("Best score", f"{max(x['total'] for x in attempts):.1f}/100")
        st.markdown("### Score history")
        st.line_chart(df.set_index("Date")["Score"])
        st.markdown("### Practice history")
        st.dataframe(df, use_container_width=True, hide_index=True)

# -------------------- 4 BEFORE & AFTER --------------------
elif page == "4. Before & After":
    st.title("4. Before & After Analysis")
    if len(attempts) < 2:
        st.info("Complete at least two assessments to compare your results.")
    else:
        older = attempts[-1]
        newer = attempts[0]
        difference = round(newer["total"] - older["total"], 1)
        st.write(f"**Earlier session:** {older['created_at'][:10]}  |  **Latest session:** {newer['created_at'][:10]}")
        x, y, z = st.columns(3)
        x.metric("Earlier score", f"{older['total']}/100")
        y.metric("Latest score", f"{newer['total']}/100")
        z.metric("Difference", f"{difference:+.1f}")
        st.markdown("### Compare the six directions")
        import pandas as pd
        compare = pd.DataFrame({
            "Earlier": older["scores"],
            "Latest": newer["scores"]
        })
        st.dataframe(compare, use_container_width=True)
        st.markdown("### Earlier answer")
        st.write(older["answer"])
        st.markdown("### Latest answer")
        st.write(newer["answer"])

# -------------------- 5 ERROR TRACKER --------------------
elif page == "5. Smart Error Tracker":
    st.title("5. Smart Error Tracker")
    st.caption("The starter version detects a small set of common patterns. It is not a full grammar checker.")
    errors = get_errors()
    if errors:
        for error, count, last_seen in errors:
            st.write(f"**{error}**")
            st.caption(f"Detected {count} time(s) • Last seen: {last_seen[:10]}")
    else:
        st.info("No tracked errors yet. Submit answers in Speaking Assessment to check supported patterns.")
    with st.expander("Add a personal error to practise"):
        personal_error = st.text_input("Error or phrase to remember")
        if st.button("Save personal error"):
            if personal_error.strip():
                add_error(personal_error.strip())
                st.success("Saved. It will appear in your tracker after refreshing.")
                st.rerun()

# -------------------- 6 SMART HINTS --------------------
elif page == "6. Smart Hints":
    st.title("6. Smart Hints")
    question = st.selectbox("Choose a speaking question", [q for group in QUESTIONS.values() for q in group])
    st.markdown("### Helpful sentence starters")
    for hint in HINTS.get(question, ["In my opinion...", "One reason is...", "For example..."]):
        st.write("• " + hint)
    st.markdown("### Answer structure")
    st.write("1. **Direct answer:** Give your main idea.")
    st.write("2. **Reason:** Explain why.")
    st.write("3. **Example:** Add a personal or real-life example.")
    st.write("4. **Wrap-up:** Finish with one concluding sentence.")
    st.info("Hints are prompts to help you build your own answer. Try not to memorize a complete response.")

# -------------------- 7 VOCABULARY TRACKER --------------------
elif page == "7. Vocabulary Tracker":
    st.title("7. Vocabulary Activation Tracker")
    st.write("Add target words, then use them in your next speaking answer.")
    target_words_text = st.text_input("Target words (separate with commas)", placeholder="confident, opportunity, improve")
    if st.button("Check words in my latest answer"):
        if not attempts:
            st.warning("Complete an assessment first.")
        elif not target_words_text.strip():
            st.warning("Enter at least one target word.")
        else:
            targets = [w.strip().lower() for w in target_words_text.split(",") if w.strip()]
            latest_answer = attempts[0]["answer"].lower()
            used = [w for w in targets if re.search(r"\b" + re.escape(w) + r"\b", latest_answer)]
            missing = [w for w in targets if w not in used]
            st.metric("Words activated", f"{len(used)}/{len(targets)}")
            if used:
                st.success("Used: " + ", ".join(used))
            if missing:
                st.warning("Not used yet: " + ", ".join(missing))
            st.caption("This checks whether the exact target words appear in your latest typed answer.")
    st.markdown("### Vocabulary practice tip")
    st.write("Choose 5 words about one topic. Write one original sentence for each, then use them naturally in a speaking answer.")

# -------------------- 8 GOALS --------------------
elif page == "8. Speaking Goals":
    st.title("8. Personal Speaking Goals")
    st.write("Set a measurable goal and update your progress as you practise.")
    with st.form("new_goal_form"):
        title = st.text_input("Goal", placeholder="Practise speaking 10 times")
        target = st.number_input("Target number", min_value=1, max_value=365, value=10)
        submitted = st.form_submit_button("Add goal")
        if submitted:
            if title.strip():
                add_goal(title.strip(), int(target))
                st.success("Goal added.")
                st.rerun()
            else:
                st.warning("Please enter a goal name.")
    st.markdown("### Your goals")
    goals = get_goals()
    if not goals:
        st.info("You have not created a goal yet.")
    for goal_id, title, target, progress, created_at in goals:
        with st.container(border=True):
            st.write(f"**{title}**")
            st.caption(f"Created: {created_at} • Target: {target}")
            new_progress = st.number_input(
                "Completed",
                min_value=0,
                max_value=int(target),
                value=min(int(progress), int(target)),
                key=f"goal_{goal_id}"
            )
            st.progress(min(new_progress / target, 1.0))
            st.write(f"{new_progress}/{target}")
            col1, col2 = st.columns(2)
            if col1.button("Update", key=f"update_{goal_id}"):
                update_goal(goal_id, int(new_progress))
                st.success("Progress updated.")
                st.rerun()
            if col2.button("Delete", key=f"delete_{goal_id}"):
                delete_goal(goal_id)
                st.rerun()

st.sidebar.divider()
st.sidebar.caption("Speak Up • Keep practising, one answer at a time.")
