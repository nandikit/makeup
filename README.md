# Makeover by Kavyanandeesh

A Flask-based bridal and beauty website with a public gallery, services and packages, appointment requests, and an admin dashboard.

## Deploy to Vercel

1. Extract this ZIP. Make sure `app.py` and `requirements.txt` are at the **project root** (not one folder deeper).
2. Push the contents of this folder to a GitHub repository.
3. In [Vercel](https://vercel.com/dashboard), choose **Add New → Project**, import that repository, and set **Root Directory** to the folder containing `app.py`.
4. Vercel should detect Flask automatically. Leave Build Command and Output Directory at their defaults.
5. In **Project → Settings → Environment Variables**, add:
   - `SECRET_KEY` — a long, random secret
   - `ADMIN_USERNAME` — your chosen admin username
   - `ADMIN_PASSWORD` — a strong admin password
6. Redeploy the project after setting the variables.

The project includes a `.vercelignore` file to avoid uploading the local Git metadata and virtual environment.

## Important hosting limitation

Vercel's function filesystem is ephemeral. This version uses `/tmp` on Vercel so the app can start without trying to write into the read-only deployment directory, but **SQLite records and uploaded photos are not durable** and may disappear or differ between instances/redeployments. Before using the site for real bookings, connect a managed database (for example, PostgreSQL) and persistent object storage for gallery images. Do not rely on this temporary storage for customer appointments.

## Run locally on Windows

```powershell
py -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000/`. Admin login: `http://127.0.0.1:5000/admin-login`.

For local first-run defaults, the admin credentials are `admin` / `ChangeMe123!`. Change these before public deployment; environment variables are used when the admin account is first created.
