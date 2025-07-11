# השתמש בגרסת פייתון רשמית ורזה
FROM python:3.11-slim

# הגדר את תיקיית העבודה בתוך הקונטיינר
WORKDIR /app

# --- השלב הקריטי ---
# העתק תחילה את קובץ הדרישות והתקן את החבילות
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# העתק את כל שאר קבצי הפרויקט
COPY . .

# הגדר את פקודת ההפעלה
CMD ["python", "main.py"]
