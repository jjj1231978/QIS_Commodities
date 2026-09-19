# Hugging Face Space runtime (docker SDK, CPU Basic).
#
# The Streamlit entrypoint lives at app/streamlit_app.py rather than the repo
# root, and src/config.py resolves PROJECT_ROOT from __file__, so the whole
# repo must land at a single WORKDIR for data/processed to resolve.

# Pinned to match the dev venv (3.12). When these drift, syntax that is valid
# locally can be a SyntaxError here, and Streamlit compiles a page lazily on
# first view — so the break is invisible until someone clicks that page.
# deploy_hf.sh reads this line and parses app/ + src/ under this version before
# pushing, so keep the `FROM python:X.Y-slim` shape intact.
FROM python:3.12-slim

WORKDIR /app

# Install deps first so Docker layer-caches them across content-only pushes.
# requirements-space.txt is the slim viewer set — see that file for why the
# data-acquisition and reporting deps are intentionally absent.
COPY requirements-space.txt .
RUN pip install --no-cache-dir -r requirements-space.txt

# Code plus the committed data/processed viewer artifacts.
COPY . .

# HF Spaces route traffic to port 7860.
EXPOSE 7860

# Belt-and-suspenders: these also live in .streamlit/config.toml. The README
# front-matter app_port MUST agree with both or the Space renders blank.
ENV STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PYTHONPATH=/app

CMD ["streamlit", "run", "app/streamlit_app.py"]
