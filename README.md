# AuraEd · Student Performance Forecast

A static, responsive student performance forecast hosted on GitHub Pages. Supabase provides email/password authentication and stores each student's submissions under their account.

The estimate uses a small model fitted to synthetic demonstration data. It is not validated for real academic decisions and is not a measure of a student's potential.

## Supabase setup

1. In Supabase, open **SQL Editor → New query**, paste [`supabase/schema.sql`](./supabase/schema.sql), and run it. This creates `public.student_predictions` and row-level security policies that associate submissions with their authenticated user.
2. In **Authentication → Sign In / Providers**, enable **Email**, then create a test student under **Authentication → Users**.
3. Open **Authentication → URL Configuration**. Set **Site URL** to `https://aniketpaygavhan00-crypto.github.io/auraed-student-performance/` and add the same URL under **Redirect URLs**. The current sign-in uses email and password without an OAuth redirect; this also prepares for Supabase auth emails.
4. The project URL and publishable key are configured in [`js/supabase-config.js`](./js/supabase-config.js). The publishable key is intended to be public; never put a `service_role` or secret key in this file or any browser code. Database access is controlled by the SQL row-level security policies.

## GitHub Pages

This is a static website; GitHub Pages serves it directly from the repository without Flask, Render, or a build workflow.

1. Open the repository on GitHub and go to **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Set the branch to **`main`** and the folder to **`/ (root)`**, then click **Save**.
4. Wait for the Pages deployment to finish, then open the site link shown under **Settings → Pages**. It will be `https://aniketpaygavhan00-crypto.github.io/auraed-student-performance/`.

To attach a custom domain later, add it under **Settings → Pages → Custom domain**, configure the DNS records GitHub shows, and enable **Enforce HTTPS** after DNS verification.

## Student data and estimate

After sign-in, a student submits enrollment number, study hours per day, their latest assessment percentage, and attendance. The app computes the sample forecast in the browser, then sends the inputs, the estimated percentage, and the authenticated student's user ID to Supabase. Row-level security checks that the `user_id` matches the signed-in user. The browser never uses a privileged key.

The model runs in browser code because GitHub Pages serves static files and does not run Flask or Python. The embedded model values reproduce the current synthetic demo model; retraining it requires updating the model implementation in `js/forecast.mjs`.

## Security

- Never put a Supabase `service_role` key, database password, or other secret in this repository or frontend JavaScript.
- If a service-role key has been shared or exposed, rotate it in Supabase immediately.
- Only use the project publishable (or legacy anon/public) key in the static site. Keep Row Level Security enabled.
- Enrollment numbers and student data are personal information. Only collect data with the appropriate authorization and consent.
