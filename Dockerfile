FROM python:3.12

WORKDIR /app
RUN pip install uv

COPY requirements.txt ./

RUN uv venv && uv pip install --requirement requirements.txt

COPY . .

RUN ["chmod", "+x", "/app/entrypoint.sh"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD [".venv/bin/python", "-m", "src"]
