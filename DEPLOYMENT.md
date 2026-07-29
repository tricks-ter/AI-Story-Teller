# Deployment Guide

This app has two parts that must be hosted separately:

| Part | What it is | Hosting options |
|---|---|---|
| **Frontend** | React/Vite static site | GitHub Pages, Vercel |
| **Backend** | Python FastAPI server | Render, Railway, Fly.io |

You must deploy the **backend first** to get its public URL, then configure the frontend to point at it.

---

## Part 1 — Deploy the Backend on Render (free)

Render is the easiest free option for a FastAPI server with persistent disk storage (needed for `chat_history.json`).

### Step 1 — Create a Render account

Go to [render.com](https://render.com) and sign up (free, no credit card required for the free plan).

### Step 2 — Connect your GitHub repository

1. In the Render dashboard click **New → Web Service**
2. Click **Connect a repository** and authorise Render to access your GitHub account
3. Select this repository

### Step 3 — Configure the service

Fill in the form:

| Field | Value |
|---|---|
| Name | `glm-chat-backend` (or anything you like) |
| Region | Choose one close to you |
| Branch | `main` |
| Root Directory | `backend` |
| Runtime | **Python 3** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | **Free** |

> **Tip:** Render will auto-detect the `render.yaml` file in the repo root and pre-fill most of these settings.

### Step 4 — Add a persistent disk

This keeps `chat_history.json` alive between deploys and restarts.

1. In the service settings go to **Disks**
2. Click **Add Disk**
3. Set **Mount Path** to `/data`
4. Set **Size** to `1 GB` (free tier allows this)

### Step 5 — Set environment variables

In the service settings go to **Environment** and add:

| Key | Value |
|---|---|
| `ZAI_API_KEY` | Your Z.AI API key |
| `DATA_DIR` | `/data` |
| `ALLOWED_ORIGINS` | *(leave empty for now — fill in after deploying the frontend)* |

### Step 6 — Deploy

Click **Create Web Service**. Render will build and deploy the backend. Wait for the status to show **Live**.

Your backend URL will be something like:
```
https://glm-chat-backend.onrender.com
```

Copy this URL — you need it for the frontend setup.

### Step 7 — Update CORS (after deploying the frontend)

Once the frontend is live, come back to Render → Environment and add:

```
ALLOWED_ORIGINS=https://your-app.vercel.app,https://yourusername.github.io
```

Then click **Save Changes** (Render will redeploy automatically).

---

## Part 2a — Deploy the Frontend on Vercel

Vercel is the recommended option — it takes under 2 minutes and handles everything automatically.

### Step 1 — Create a Vercel account

Go to [vercel.com](https://vercel.com) and sign up with your GitHub account.

### Step 2 — Import the project

1. In the Vercel dashboard click **Add New → Project**
2. Click **Import** next to this repository
3. In the **Configure Project** screen set:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build` *(auto-detected)*
   - **Output Directory**: `dist` *(auto-detected)*

### Step 3 — Set the environment variable

In the **Environment Variables** section add:

| Name | Value |
|---|---|
| `VITE_API_URL` | `https://glm-chat-backend.onrender.com` *(your Render URL from Part 1)* |

### Step 4 — Deploy

Click **Deploy**. Vercel will build and publish the site.

Your frontend URL will be something like:
```
https://glm-chat.vercel.app
```

### Step 5 — Update CORS on the backend

Go back to Render and update `ALLOWED_ORIGINS`:
```
ALLOWED_ORIGINS=https://glm-chat.vercel.app
```

### Subsequent deploys on Vercel

Every push to `main` triggers an automatic redeploy. No manual action needed.

---

## Part 2b — Deploy the Frontend on GitHub Pages

Use this if you prefer to stay entirely within GitHub.

### Step 1 — Enable GitHub Pages in the repository

1. Go to your repo on GitHub → **Settings → Pages**
2. Under **Source** select **GitHub Actions**

### Step 2 — Add the repository secret

1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Add:

| Name | Secret value |
|---|---|
| `VITE_API_URL` | `https://glm-chat-backend.onrender.com` *(your Render URL)* |

### Step 3 — Trigger the workflow

Push any change to `frontend/` on the `main` branch, or:

1. Go to **Actions → Deploy Frontend to GitHub Pages**
2. Click **Run workflow → Run workflow**

The workflow (`.github/workflows/deploy-pages.yml`) will:
- Install Node 22 dependencies
- Build the React app with `VITE_API_URL` injected
- Publish the `dist/` folder to GitHub Pages

### Step 4 — Find your URL

After the workflow completes, go to **Settings → Pages** to see your live URL:
```
https://yourusername.github.io/AI-Story-Teller/
```

> **Note:** If the repo is not at the root (e.g. `username.github.io/repo-name`), add this to `frontend/vite.config.js`:
> ```js
> base: '/AI-Story-Teller/',   // your repo name
> ```
> Then push again to trigger a redeploy.

### Step 5 — Update CORS on the backend

Go back to Render and update `ALLOWED_ORIGINS`:
```
ALLOWED_ORIGINS=https://yourusername.github.io
```

---

## Environment Variable Reference

### Backend (Render)

| Variable | Required | Description |
|---|---|---|
| `ZAI_API_KEY` | Yes | Your Z.AI / ZhipuAI API key |
| `ALLOWED_ORIGINS` | Yes (production) | Comma-separated list of allowed frontend URLs |
| `DATA_DIR` | Recommended | Directory for `chat_history.json`. Set to `/data` when using a Render disk |

### Frontend (Vercel or GitHub Pages)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | Yes (production) | Full URL of the deployed backend, e.g. `https://glm-chat-backend.onrender.com` |

---

## Troubleshooting

### "Failed to fetch" or CORS error in the browser
- The `ALLOWED_ORIGINS` variable on the backend does not include your frontend URL.
- Update it on Render and redeploy (or trigger a manual restart).

### Chat history is lost after every Render restart (free plan)
- The free Render tier spins down after 15 minutes of inactivity and spins back up on the next request (cold start ~30 s).
- **Without a disk**, `chat_history.json` is stored in the container filesystem and is wiped on each deploy.
- **With a disk** mounted at `/data` and `DATA_DIR=/data`, history persists across restarts and deploys.

### Render cold starts (free tier)
- The free plan spins down idle services. The first request after inactivity may take 30–60 seconds.
- Upgrade to the Starter plan ($7/month) to avoid this.

### Frontend shows blank page on GitHub Pages
- Check that `base` is set correctly in `vite.config.js` (see Step 4 in the GitHub Pages section).
- Make sure the Pages source is set to **GitHub Actions**, not a branch.

### Build fails on Vercel — "Cannot find module"
- Make sure the **Root Directory** in Vercel project settings is `frontend`, not the repo root.
