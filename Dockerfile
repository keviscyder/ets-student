# Etesis mokinių programėlė – paleidimas savo serveryje (ES), ne Streamlit debesyje.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Raktai (SUPABASE_URL, SUPABASE_KEY) paduodami kaip aplinkos kintamieji, ne failu.
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/_stcore/health' % os.environ.get('PORT','8501'))" || exit 1

CMD streamlit run main.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true
