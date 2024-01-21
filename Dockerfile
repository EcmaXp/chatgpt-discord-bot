FROM python:3.11 as requirements-stage
WORKDIR /tmp
RUN apt update && apt install rustc -y
RUN pip install poetry
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.11-slim
WORKDIR /code
COPY --from=requirements-stage /tmp/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./chatgpt_discord_bot /code/chatgpt_discord_bot
CMD ["python", "-m", "chatgpt_discord_bot"]
