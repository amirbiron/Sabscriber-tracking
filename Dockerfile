# השתמש בגרסת פייתון רשמית ורזה
FROM python:3.11-slim

# הגדר את תיקיית העבודה בתוך הקונטיינר
WORKDIR /app

# העתק תחילה את קובץ הדרישות כדי לנצל את המטמון של דוקר
COPY requirements.txt .

# התקן את כל החבילות מהקובץ
# --no-cache-dir מבטיח התקנה נקייה
RUN pip install --no-cache-dir -r requirements.txt

# העתק את כל שאר קבצי הפרויקט
COPY . .

# הגדר את פקודת ההפעלה
CMD ["python", "main.py"]
