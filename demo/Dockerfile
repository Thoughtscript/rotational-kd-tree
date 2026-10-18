FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY example.py test_example.py perf_test.py .

CMD ["sh", "-c", "python -u -m unittest discover -v -s . -p 'test_*.py' > /app/test-results.log 2>&1; test_status=$?; cat /app/test-results.log; if [ \"$test_status\" -ne 0 ]; then exit \"$test_status\"; fi; python -u example.py || exit $?; python -u perf_test.py > /app/perf-results.log 2>&1; perf_status=$?; cat /app/perf-results.log; if [ \"$perf_status\" -ne 0 ]; then exit \"$perf_status\"; fi; sleep 9999"]