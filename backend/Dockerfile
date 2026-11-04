FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements-app.txt requirements-model.txt ./
RUN pip install --no-cache-dir -r requirements-model.txt
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps -e .
COPY backend ./backend
COPY data/reference ./data/reference
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
