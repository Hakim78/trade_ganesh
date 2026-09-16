# Image Python du projet : backtest (one-shot) et live (long-running). python:3.12-slim (CLAUDE.md).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONIOENCODING=utf-8 \
    MPLBACKEND=Agg

WORKDIR /app

# Dépendances d'abord (cache Docker), code ensuite.
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install "pandas>=2.2" "numpy>=1.26" "vectorbt>=0.26" "yfinance>=0.2.40" "quantstats>=0.0.62" \
       "pyyaml>=6" "alpaca-py>=0.30" "python-dotenv>=1" "plotly>=5.24,<6" "matplotlib>=3.8" "requests>=2.31" \
       "pytest>=8"

COPY common ./common
COPY strategy ./strategy
COPY backtest ./backtest
COPY live ./live
COPY tests ./tests
COPY config.yaml ./

RUN mkdir -p outputs data
VOLUME ["/app/outputs", "/app/data"]

CMD ["python", "-m", "backtest.run", "--period", "smoke"]
