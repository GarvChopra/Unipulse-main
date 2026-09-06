# PostgreSQL is the primary store; every worker shares it. --workers 1 is kept
# for now only because the login rate-limiter is process-local (see P2). Threads
# give request concurrency. Raise workers once the rate-limiter is shared.
web: gunicorn wsgi:app --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:$PORT
