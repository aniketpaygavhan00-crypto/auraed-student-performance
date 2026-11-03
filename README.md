# Northstar · Student Performance Forecast

A responsive Flask demo that estimates a student's final score from enrollment number, daily study hours, attendance, and a previous score. The interface is based on the supplied screenshots and includes a shareable WhatsApp result.

> **Sample model only:** `data/sample_student_data.csv` is synthetic demonstration data. The trained model is not validated for real academic decisions. Replace the CSV with appropriate, consented historical data and evaluate it before real use.

## Run locally

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python train.py
python app.py
```

Open <http://127.0.0.1:7860>. `train.py` creates `model/student_model.joblib` from the CSV. The model file is generated locally and is not required in source control.

## Supabase sign-in

The app opens on the login screen when there is no valid session. A successful sign-in leads to the forecast form. Each valid submission is saved in `public.student_predictions` and linked to the signed-in Supabase Auth user. Follow these steps to configure it:

1. Open your project in the Supabase Dashboard.
2. Open **SQL Editor**, create a new query, paste the contents of [`supabase/schema.sql`](./supabase/schema.sql), and run it. This creates the table, constraints, index, and Row Level Security policies. The policies allow signed-in users to insert and read only their own rows.
3. In **Authentication → Sign In / Providers**, enable **Email**. Create a test student under **Authentication → Users** (or enable sign-up separately if you later add a registration page).
4. Open **Project Settings → API** (or **API Keys**) and copy the **Project URL** and a client-safe **publishable key** (`sb_publishable_...`) or legacy **anon/public key**. Do not use the `service_role` or secret key.
5. In the project folder, copy `.env.example` to `.env` and set:
   - `SUPABASE_URL` to the Project URL.
   - `SUPABASE_ANON_KEY` to the publishable or legacy anon/public key.
   - `FLASK_SECRET_KEY` to a long, random secret that stays unchanged across restarts.
   - Set `AUTH_COOKIE_SECURE=true` when serving over HTTPS. Keep it `false` for local HTTP development.
6. Install dependencies, generate the demo model, then start the app:

   ```bash
   python -m pip install -r requirements.txt
   python train.py
   python app.py
   ```

7. Open <http://127.0.0.1:7860>. Sign in with the test account and submit the student form. In Supabase, open **Table Editor → student_predictions** to confirm the row and its `user_id`. Supabase access and refresh tokens are stored in HttpOnly cookies; expired access tokens are refreshed automatically.

The form's **Percentage** is the student's latest assessment percentage (the model's existing previous-score input). The table also saves the model's `predicted_percentage`. The Flask server sends the signed-in user's access token with each insert, and the database checks `auth.uid() = user_id`; the browser never chooses the `user_id`.

The only Supabase values needed are the **Project URL** and a **publishable/anon public key**. Never send or put a service-role/secret key in `.env`, source code, or the browser. The app does not need it.

## Replace the sample data

Edit `data/sample_student_data.csv`, keeping these numeric columns and units:

| Column | Meaning | Range |
| --- | --- | --- |
| `study_hours` | Average daily study hours | 0–24 |
| `attendance` | Attendance percentage | 0–100 |
| `previous_score` | Most recent assessment score | 0–100 |
| `final_score` | Observed final score to learn | 0–100 |

Keep at least eight complete rows. Then run `python train.py` again. Use representative, lawfully collected data and assess fairness and predictive quality before relying on predictions.

## Deploy on Render

This project includes a Render Blueprint in `render.yaml`. Push the repository to GitHub, then in Render choose **New → Blueprint**, select the repository, and apply the Blueprint. Render generates `FLASK_SECRET_KEY` and asks you to provide `SUPABASE_URL` and `SUPABASE_ANON_KEY` as private environment values during setup. Use your Project URL and publishable/anon key; never enter a service-role or secret key. The deployed service enables secure cookies and uses the included Dockerfile, which trains from the synthetic demo CSV during image build.

## Project structure

```text
app.py                 Flask routes and score prediction
train.py               Reproducible scikit-learn training script
data/sample_student_data.csv
templates/             Sign-in, predictor, and result pages
static/                Interface styles
supabase/schema.sql    Student submissions table and RLS policies
render.yaml            Render deployment Blueprint
.env.example           Supabase and Flask configuration placeholders
requirements.txt
Dockerfile
Procfile
```
